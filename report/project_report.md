# Dining Philosophers Problem Visualizer

### A Mini-Project Report

---

## 1. Cover Page

**Project Title:** Dining Philosophers Problem Visualizer
**Project Number:** 9
**Course:** Operating Systems (Semester / Mini-Project)
**Programme:** B.Tech, Computer Engineering

`[INSERT: Your Name, Roll Number, Class/Division]`
`[INSERT: Institution Name, Department, Academic Year]`
`[INSERT: Guide/Faculty Name]`
`[INSERT: Submission Date]`

---

## 2. Certificate / Declaration

`[INSERT INSTITUTION-SPECIFIC CERTIFICATE/DECLARATION TEXT HERE]`

*(This section is institution-specific and must be filled in using your
department's standard certificate/declaration format, typically including
a statement that the work is original, the guide's countersignature line,
and the examination date.)*

---

## 3. Abstract

The Dining Philosophers problem is a classical illustration of resource
contention, mutual exclusion, and deadlock in concurrent systems. This
project implements and visualizes the problem using real operating-system
synchronization primitives rather than a scripted animation: five (or up
to ten) philosophers are independent Python `threading.Thread` instances
contending for shared fork resources represented by `threading.Lock`
objects. Three fork-acquisition strategies are implemented — a naive
strategy that can genuinely deadlock, a resource-ordering strategy, and a
semaphore-bounded waiter strategy, the latter two being provably
deadlock-free by construction. A deterministic trigger, built on
`threading.Barrier`, reliably reproduces the textbook deadlock on demand
for live demonstration, and a background thread detects the resulting
circular wait by building and walking a live wait-for graph. A Flask
backend exposes the running simulation's state, event log, and metrics
over a small REST API; a vanilla-JavaScript frontend polls this API and
renders philosopher state, fork ownership, and the deadlock cycle in
real time, without simulating any behaviour of its own. The system is
validated by an automated test suite covering mutual exclusion, deadlock
reproduction, deadlock prevention, and simulator lifecycle correctness.

---

## 4. Introduction

Operating systems must routinely manage multiple threads or processes
competing for a limited set of shared resources — file handles, memory
regions, device locks, and so on. When such competition is not carefully
synchronized, it can produce race conditions or deadlock: the system can
freeze permanently even though every individual component is otherwise
functioning correctly. The Dining Philosophers problem, introduced by
Edsger Dijkstra, is the standard classroom vehicle for reasoning precisely
about this class of failure, because it distills the general problem
("many workers, each needing two of several shared, exclusively-held
resources at once") down to a small, symmetric, easily visualized case.

This project's aim was not to *explain* the problem with static diagrams,
but to make the failure and its fixes **observable as they actually
happen** — a real deadlock occurring in real threads, and a real recovery
in behaviour once the synchronization policy changes — with the
underlying mechanics made visible through a browser-based live
visualization and event log.

## 5. Problem Statement

*"Simulate the classic dining philosophers problem with a deadlock-free
solution."*

Concretely, this requires: (a) modelling N philosophers and N forks as
genuinely concurrent entities and genuinely shared, exclusively-held
resources; (b) demonstrating that a naive synchronization policy can
produce deadlock; (c) implementing at least one synchronization policy
that is provably free of deadlock; and (d) making both the failure and
the fix legible to an observer in real time, with supporting metrics
rather than a purely qualitative demonstration.

## 6. Objectives

1. Implement N philosophers as real, independently-scheduled OS threads.
2. Implement N forks as real, exclusively-lockable shared resources.
3. Reproduce the classic deadlock reliably, on demand, for a live
   demonstration.
4. Implement at least one — this project implements two — genuinely
   deadlock-free synchronization strategies, each provable by structural
   argument, not just empirical observation.
5. Detect deadlock algorithmically (wait-for graph cycle detection),
   rather than only by a human noticing the system has frozen.
6. Visualize philosopher state, fork ownership, and the deadlock's
   circular-wait structure in a live, browser-based interface.
7. Record an accurate event log and a set of real, measured runtime
   metrics (never fabricated) to support quantitative comparison between
   strategies.
8. Validate correctness with an automated test suite.

## 7. Related Concepts / Theory

See `docs/algorithms.md` for the full treatment. In summary, this project
directly exercises: processes vs. threads, concurrent execution, critical
sections, race conditions, mutual exclusion, locks, semaphores, shared
resources, deadlock, the four Coffman conditions, deadlock prevention
(as distinct from deadlock avoidance), circular wait, resource ordering,
starvation, fairness, and progress. Each concept in that document is tied
to the specific code that implements or demonstrates it, rather than
presented as generic background.

## 8. Existing / Naive Approach

The naive approach — implemented here as the **Naive strategy**
(`backend/simulation/strategies.py`, class `NaiveStrategy`) — has every
philosopher acquire their left fork (fork with the same id as the
philosopher), then attempt their right fork (fork `(id + 1) mod N`). This
is the textbook "obvious" first attempt at a solution, and it is exactly
what produces deadlock: if all N philosophers acquire their left fork at
roughly the same time, every fork becomes held and every philosopher
blocks waiting for their right-hand neighbour's fork — a permanent
circular wait, since hold-and-wait and no-preemption both hold in this
implementation (a philosopher never releases a fork it already has while
waiting for the other, and no fork is ever forcibly reclaimed).

Because relying on natural thread-scheduling timing to *reliably*
reproduce this for a live demonstration is impractical, this project adds
a deterministic trigger (`Simulator.trigger_deadlock()`) that uses a
`threading.Barrier` to force all N philosophers to rendezvous immediately
after taking their first fork — guaranteeing the worst case occurs
on demand, while still being a completely real execution of the naive
policy, not a scripted outcome.

## 9. Proposed Solution

Two independent, structurally deadlock-free strategies are implemented,
so the project demonstrates that there is more than one valid way to
attack the same problem by targeting different Coffman conditions:

**Resource Ordering (`OrderedStrategy`).** Every philosopher acquires the
*lower-numbered* fork first, regardless of which side it is physically
on. Philosopher N-1's forks are (N-1, 0); under this rule it requests
fork 0 first, breaking exactly the asymmetry the naive strategy relies on
to deadlock. This eliminates **circular wait**: a wait-for cycle would
require fork ids to strictly decrease all the way around the cycle, which
is impossible for a finite set of integers.

**Waiter / Semaphore (`WaiterStrategy`).** A counting semaphore
initialised to N-1 must be acquired before a philosopher may attempt
either fork, and is released only after both forks are released. At most
N-1 philosophers can be mid-acquisition at any instant, so the "all N
philosophers hold one fork each" configuration required for the naive
deadlock can never arise. This attacks the *scale* at which
**hold-and-wait** can occur.

Both strategies share the same low-level fork-acquisition mechanics
(`Philosopher._acquire_forks()`) as the naive strategy — only the
*ordering policy* (`Strategy.fork_order()`) and, for the waiter strategy,
an additional admission gate (`pre_acquire_hook` / `post_release_hook`)
differ. This was a deliberate design choice: it isolates the
synchronization *policy* as the variable under test, rather than
conflating it with unrelated implementation differences between
strategies.

## 10. System Architecture

See `docs/architecture.md` for full Mermaid diagrams (system architecture,
module diagram, state transition diagram, simulation lifecycle flowchart,
deadlock dependency graph, fork-acquisition sequence diagram, and
frontend–backend data flow). In summary: a vanilla-JS frontend polls a
thin Flask API layer, which delegates every operation to a single
`Simulator` instance; the `Simulator` owns the philosopher threads, the
fork locks, the active strategy, a background deadlock detector thread, a
thread-safe event logger, and a thread-safe metrics collector.

## 11. Algorithms

**Fork acquisition (all strategies):** for each of the two forks in the
strategy-determined order, repeatedly call `Lock.acquire(timeout=0.05s)`
until it succeeds or the simulation is stopped; on the first failed
attempt, transition to `WAITING` and record a blocked-attempt metric; on
success, record the wait duration (if any) and proceed.

**Resource ordering:** `fork_order(pid, N) = (min(pid, (pid+1)%N),
max(pid, (pid+1)%N))`.

**Waiter admission:** `Semaphore(N-1).acquire()` before the fork loop;
`Semaphore(N-1).release()` after both forks are released.

**Deterministic deadlock trigger:** create a `threading.Barrier(N)`; every
philosopher calls `barrier.wait(timeout=5)` immediately after acquiring
its *first* fork (only) for the remainder of the run.

**Deadlock detection:** every 150ms, build `graph = {Pi: Pj for each Pi
WAITING on a fork Pj holds}`; walk from each node following `graph[node]`
until a previously-visited node is revisited, which yields the cycle;
report only if the same cycle persists for ≥1.5s (to filter transient
waits that are about to resolve on their own).

## 12. Module Design

| Module | Responsibility |
|---|---|
| `models.py` | Shared enums (`PhilosopherState`, `EventType`) and the `Event` dataclass |
| `fork.py` | `Fork`: a `threading.Lock` plus ownership metadata |
| `philosopher.py` | `Philosopher(threading.Thread)`: the state machine and fork-acquisition loop |
| `strategies.py` | `NaiveStrategy`, `OrderedStrategy`, `WaiterStrategy` |
| `step_controller.py` | Semaphore-based single-step gate for manual mode |
| `deadlock_detector.py` | Background thread: wait-for graph construction + cycle detection |
| `simulator.py` | Lifecycle owner: start/pause/resume/reset/step, thread-safe snapshots |
| `metrics.py` | `MetricsCollector`: thread-safe counters and derived statistics |
| `event_logger.py` | `EventLogger`: thread-safe, incrementally-readable event log |
| `app.py` | Flask routes; delegates every request to `Simulator` |

## 13. Implementation

Implemented in Python 3.12 (compatible with 3.10+) using only the
standard library's `threading` module for concurrency (`Lock`,
`RLock`, `Semaphore`, `Event`, `Barrier`) and Flask for the HTTP layer.
The frontend is HTML5/CSS3/vanilla JavaScript with no build step and no
external JS libraries — the live table visualization is hand-built SVG,
generated and redrawn by `script.js` from the JSON returned by
`GET /api/state`.

Key implementation details of note (elaborated in `docs/algorithms.md`):
poll-with-timeout fork acquisition (rather than an indefinite blocking
`acquire()`) to keep Pause/Reset/Step responsive without weakening
hold-and-wait semantics; a single-lock-acquisition update for
`state` + `waiting_for_fork` together, to close a real display race found
and fixed during development; and a `try/finally`-guarded release path
that guarantees no fork or semaphore permit is ever leaked, even when a
thread is stopped mid-deadlock.

`[INSERT ACTUAL SCREENSHOT: main table visualization mid-run]`
`[INSERT ACTUAL SCREENSHOT: DEADLOCK DETECTED banner with circular-wait arrows]`
`[INSERT ACTUAL SCREENSHOT: strategy comparison table after running all three strategies]`

## 14. Testing

An automated `pytest` suite (`tests/`, 28 tests across 6 files) exercises:
fork mutual exclusion (stress test with 8 threads), acquire/release
correctness, fork-ownership consistency, deadlock reproduction under the
naive strategy (asserting a genuine 5-cycle is detected), absence of
deadlock over timed runs of both alternative strategies (with a
progress assertion, not merely an absence check), philosopher state-
machine validity, simulator reset (no stale threads via
`threading.enumerate()`), pause/resume, event log monotonicity and
incremental-fetch correctness, metrics correctness against hand-computed
expected values, and manual step-mode gating. See `tests/` and
`docs/architecture.md` for details of what each test asserts and why.

`[INSERT ACTUAL SCREENSHOT/OUTPUT: `pytest tests -v` run on your machine, showing N passed]`

## 15. Results and Discussion

`[INSERT MEASURED RESULT: your own strategy-comparison table, generated by running Naive (with the trigger), Ordered, and Waiter for a fixed duration each, then reading /api/comparison or the on-page table]`

`[INSERT MEASURED RESULT: your own recorded wait-time / meals-eaten numbers per philosopher for at least one full run of each strategy]`

During development, the implementation was exercised directly (both via
direct Python calls to `Simulator` and via real HTTP requests to the
running Flask server) to verify: (a) the naive strategy, when triggered,
reliably reaches a detected deadlock with the exact expected 5-node cycle
and every philosopher correctly holding exactly one fork; (b) the ordered
and waiter strategies sustain continuous meal completion with zero
deadlock detections over multi-second runs; (c) metrics and the event log
update consistently with the underlying thread activity. These
verification runs confirm the engine behaves as designed; they are not a
substitute for the student's own recorded results above, which should
reflect your own machine and your own live demonstration.

## 16. Limitations

- No fairness/starvation guarantee is implemented or claimed for any
  strategy — only measured (see `max_wait_time` in the metrics panel).
- Deadlock **avoidance** (e.g. Banker's Algorithm) is out of scope; only
  deadlock **prevention** strategies are implemented (see
  `docs/algorithms.md` §14 for the distinction).
- The Flask development server is used as-is, appropriate for local
  demonstration but not production deployment.
- Fork utilization is measured only for time spent actively eating, not
  time spent holding one fork while blocked on the other — a deliberate,
  documented definition, not an omission.
- Manual step mode gates the four major lifecycle transitions per cycle,
  not the passage of think/eat time itself.

## 17. Conclusion

This project demonstrates that the Dining Philosophers problem, and the
concepts of deadlock and deadlock prevention it is used to teach, can be
made directly observable rather than purely theoretical: the same Python
threads and locks that produce a genuine, permanent deadlock under one
policy make genuine, continuous progress under another, with no change to
the underlying resource model — only to the ordering/admission policy
governing how those resources are requested. The accompanying live
visualization, event log, and measured metrics make both the failure mode
and its resolution legible in real time.

## 18. Future Scope

- A fourth, monitor/condition-variable-based strategy that acquires both
  forks atomically (an "all-or-nothing" request, attacking hold-and-wait
  directly rather than via admission limiting) — see viva question 33 for
  the design sketch.
- An implementation of deadlock **avoidance** (Banker's Algorithm) as a
  contrasting fourth category alongside the three prevention-style
  strategies already present.
- Persisting run history across server restarts (would introduce a
  lightweight storage layer, deliberately out of scope for this version
  per the "no database unless clearly required" project constraint).
- A fairness-focused strategy (e.g. FIFO ticket-based fork queuing) paired
  with an explicit starvation-bound test, to move §17 (Fairness) from
  "measured, not guaranteed" to "guaranteed and verified."

## 19. References

1. Dijkstra, E. W. (1971). *Hierarchical ordering of sequential
   processes.* Acta Informatica.
2. Silberschatz, A., Galvin, P. B., & Gagne, G. *Operating System
   Concepts* — chapters on Process Synchronization and Deadlocks.
3. Python Software Foundation. *threading — Thread-based parallelism.*
   Python 3 documentation. https://docs.python.org/3/library/threading.html
4. Pallets Projects. *Flask documentation.* https://flask.palletsprojects.com/
5. This project's own source code and test suite, `backend/simulation/`
   and `tests/`, as the primary implementation reference.
