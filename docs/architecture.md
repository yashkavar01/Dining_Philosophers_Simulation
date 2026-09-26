# Architecture

## 1. System Architecture

```mermaid
graph TD
    A[Browser UI<br/>HTML/CSS/Vanilla JS] -->|HTTP POST: start/pause/reset/step/strategy| B[Flask API Layer<br/>backend/app.py]
    A -->|HTTP GET /api/state every 300ms| B
    A -->|HTTP GET /api/events?since=id| B
    A -->|HTTP GET /api/metrics, /api/comparison| B
    B --> C[Simulator<br/>simulation/simulator.py]
    C --> D[Philosopher Threads x N<br/>real threading.Thread]
    C --> E[DeadlockDetector Thread]
    C --> F[StepController<br/>manual-mode gate]
    D --> G[Strategy Object<br/>naive / ordered / waiter]
    G --> H[Fork Resources x N<br/>real threading.Lock]
    D --> I[EventLogger]
    D --> J[MetricsCollector]
    E --> I
    E --> J
    C -->|state_lock-protected snapshot| B
```

The browser never talks to threads, locks, or the strategy objects
directly — it only ever calls the Flask layer, which only ever calls the
`Simulator`. This one-way funnel is what keeps the concurrency correctness
independent of anything happening in the browser.

## 2. Module Diagram

```mermaid
graph LR
    app[app.py] --> simulator[simulator.py]
    simulator --> philosopher[philosopher.py]
    simulator --> fork[fork.py]
    simulator --> strategies[strategies.py]
    simulator --> deadlock_detector[deadlock_detector.py]
    simulator --> step_controller[step_controller.py]
    simulator --> metrics[metrics.py]
    simulator --> event_logger[event_logger.py]
    philosopher --> fork
    philosopher --> strategies
    philosopher --> models[models.py]
    deadlock_detector --> models
    event_logger --> models
```

`models.py` (enums + the `Event` dataclass) has no dependencies of its own
and is imported by nearly everything else — it is the shared vocabulary
of the whole engine.

## 3. Philosopher State Transition Diagram

```mermaid
stateDiagram-v2
    [*] --> THINKING
    THINKING --> HUNGRY: think() finishes
    HUNGRY --> HUNGRY: fork acquired immediately (no wait)
    HUNGRY --> WAITING: fork request blocks
    WAITING --> HUNGRY: fork finally acquired,<br/>still needs the other fork
    HUNGRY --> EATING: both forks held
    EATING --> THINKING: eat() finishes, forks released
    WAITING --> STOPPED: Reset / stop requested
    HUNGRY --> STOPPED: Reset / stop requested
    THINKING --> STOPPED: Reset / stop requested
    EATING --> STOPPED: Reset / stop requested
    STOPPED --> [*]
```

Note the `WAITING -> HUNGRY` edge: once a blocked fork is finally
acquired, the philosopher's state returns to `HUNGRY` (it still needs the
second fork) rather than staying labelled `WAITING` with nothing left to
wait for. Both the state and its companion `waiting_for_fork` field are
updated together, under a single lock acquisition, specifically to avoid
a display race where a snapshot could catch `WAITING` paired with a stale
or `None` fork id.

## 4. Simulation Lifecycle Flowchart

```mermaid
flowchart TD
    Start([POST /api/simulation/start]) --> Reset1[reset: join any previous threads]
    Reset1 --> Create[Create N Fork objects + Strategy object]
    Create --> Spawn[Spawn N Philosopher threads + 1 DeadlockDetector thread]
    Spawn --> Running{status = running}
    Running -->|POST pause| Paused[status = paused<br/>pause_event.set]
    Paused -->|POST resume| Running
    Running -->|POST step, manual mode on| OneEvent[One thread's one gated action proceeds]
    OneEvent --> Running
    Running -->|POST deadlock/trigger, naive only| Barrier[Create threading.Barrier N]
    Barrier --> Running
    Running -->|GET state/events/metrics repeatedly| Running
    Running -->|POST reset| Teardown[stop_event.set, abort barrier,<br/>join all threads with timeout]
    Paused -->|POST reset| Teardown
    Teardown --> Idle([status = idle])
```

## 5. Deadlock Dependency Graph (naive strategy, triggered demo)

```mermaid
graph LR
    P0 -->|waits for F1, held by| P1
    P1 -->|waits for F2, held by| P2
    P2 -->|waits for F3, held by| P3
    P3 -->|waits for F4, held by| P4
    P4 -->|waits for F0, held by| P0
```

This is exactly the graph the `DeadlockDetector` builds from live state
(`Pi -> Pj` whenever `Pi` is `WAITING` for a fork `Pj` currently holds) and
walks to find the cycle — not a static illustration.

## 6. Sequence Diagram: Fork Acquisition (naive strategy, contested case)

```mermaid
sequenceDiagram
    participant P0 as Philosopher 0 (thread)
    participant F0 as Fork 0 (Lock)
    participant F1 as Fork 1 (Lock)
    participant P1 as Philosopher 1 (thread)
    participant EL as EventLogger

    P0->>EL: log FORK_REQUEST F0
    P0->>F0: try_acquire(timeout=0.05)
    F0-->>P0: acquired
    P0->>EL: log FORK_ACQUIRED F0
    P0->>EL: log FORK_REQUEST F1
    P0->>F1: try_acquire(timeout=0.05)
    F1-->>P0: False (P1 holds it)
    P0->>EL: log STATE_CHANGE WAITING (blocked on F1, held by P1)
    loop every 50ms until acquired or stopped
        P0->>F1: try_acquire(timeout=0.05)
    end
    P1->>F1: release()
    F1-->>P0: acquired
    P0->>EL: log FORK_ACQUIRED F1
    P0->>EL: log STATE_CHANGE HUNGRY (has F1, both forks now held -> EATING next)
```

## 7. Data Flow Between Frontend and Backend

```mermaid
sequenceDiagram
    participant UI as Browser (script.js)
    participant API as Flask (app.py)
    participant SIM as Simulator

    UI->>API: POST /api/simulation/start {N, strategy, speed}
    API->>SIM: sim.start(...)
    SIM-->>API: state_snapshot()
    API-->>UI: 200 JSON state

    loop every 300ms
        UI->>API: GET /api/state
        API->>SIM: sim.state_snapshot()
        SIM-->>API: philosophers, forks, deadlock, status
        API-->>UI: 200 JSON
        UI->>API: GET /api/events?since=lastId
        API-->>UI: 200 JSON new events only
        UI->>API: GET /api/metrics
        API-->>UI: 200 JSON metrics
    end

    UI->>API: POST /api/simulation/reset
    API->>SIM: sim.reset()
    SIM-->>API: state_snapshot() (idle)
    API-->>UI: 200 JSON
    UI->>API: GET /api/comparison
    API-->>UI: 200 JSON run_history
```

The frontend never receives raw thread objects or locks, obviously — only
plain JSON built by `state_snapshot()`, `events.get_since()`, and
`metrics.snapshot()`, all of which are read under `state_lock` (or their
own internal lock) so the JSON returned is a consistent point-in-time
view even though five-plus threads are mutating the underlying state
concurrently.

## 8. Concurrency Notes for the Viva

- **CPython's GIL** means only one thread executes Python bytecode at an
  instant, but `Lock.acquire()`, `Semaphore.acquire()`, and
  `time.sleep()` all release the GIL while blocked, so real OS-level
  thread scheduling and real blocking still occur. The problem being
  demonstrated (resource contention and scheduling) is about
  synchronization, not CPU parallelism, so this is not a limitation for
  this project's purpose.
- **Why polling-with-timeout instead of a plain blocking `acquire()`:**
  `Fork.try_acquire(philosopher_id, timeout=0.05)` lets a philosopher
  thread periodically re-check for pause/stop signals while it waits.
  Critically, the philosopher does **not** release a fork it already
  holds while polling for the next one — hold-and-wait is completely
  real, and in the naive strategy's uncontrolled case the retry loop runs
  forever until Reset, a genuine permanent deadlock, not a simulated one.
- **Thread safety split:** `Fork.lock` provides the actual mutual
  exclusion over the resource. `Simulator.state_lock` (a separate `RLock`)
  protects the *metadata* used for display snapshots (`philosopher.state`,
  `.waiting_for_fork`, `.held_forks`) so that a snapshot read from the
  Flask request thread is never torn mid-update.
