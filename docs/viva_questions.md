# Viva Questions & Answers

Organized by theme. Answers are deliberately concise — expand verbally in
the viva using `docs/algorithms.md` and `docs/architecture.md` if pressed
for more depth.

## Core Concepts

**1. Why is Dining Philosophers a concurrency problem, not just a puzzle?**
Because it models N independent threads of control competing for shared,
exclusively-held resources (forks) with an interleaving/ordering
dependency between two resources per requester — the same shape as real
resource-contention bugs in OS kernels, database engines, etc.

**2. What is a deadlock?**
A state where a set of threads are each waiting for a resource held by
another thread in the same set, so that none of them can ever proceed,
even though the system as a whole is not making progress and never will
without external intervention.

**3. What are the four Coffman conditions?**
Mutual exclusion, hold-and-wait, no preemption, circular wait. All four
must hold simultaneously for deadlock to be possible.

**4. Why does the naive solution deadlock?**
Every philosopher picks up their left fork, then tries their right fork.
If all N pick up their left fork around the same time, every fork is held
and every philosopher is blocked waiting on a neighbour — a full circular
wait forms, and since forks are never released while waiting (hold-and-
wait) and never preempted, the wait is permanent.

**5. Why does resource ordering prevent circular wait?**
Every philosopher must acquire the lower-numbered fork before the
higher-numbered one. A cycle in the wait-for graph would require fork ids
to strictly decrease all the way around the cycle back to the start —
impossible for a finite set of integers. So no cycle, and therefore no
deadlock, can ever form.

**6. Why does the waiter/semaphore strategy prevent deadlock?**
A semaphore initialised to N-1 admits at most N-1 philosophers into fork
contention at once. The specific deadlock scenario requires **all N**
philosophers to simultaneously hold one fork each — with at most N-1
admitted, that configuration can never occur.

**7. What is starvation, and is it different from deadlock?**
Starvation is a thread being denied progress indefinitely even though the
*system* is making progress elsewhere; deadlock is *no* thread anywhere
making progress. A strategy can be deadlock-free and still allow
starvation of one unlucky thread.

**8. Can a deadlock-free solution still suffer starvation?**
Yes. Neither `OrderedStrategy` nor `WaiterStrategy` in this project makes
any fairness guarantee — see `docs/algorithms.md` §17. The project
measures (not assumes) this via `max_wait_time` per philosopher rather
than claiming fairness it hasn't proven.

## Threads, Locks, Synchronization

**9. Why use threads instead of processes here?**
Philosophers need to share the same `Fork` objects directly. Threads
share their process's memory natively; processes would need explicit IPC
(shared memory segments, pipes) to achieve the same sharing, adding
complexity with no benefit for this problem.

**10. What is a critical section?**
The minimal sequence of instructions that must execute as if atomically
with respect to other threads accessing the same shared state — here,
"check a fork is free and take it," collapsed into the single atomic call
`Lock.acquire()`.

**11. What is a race condition? Give an example from this project.**
An outcome that depends on timing/interleaving of concurrent operations
that should be atomic but aren't. During development, `Philosopher.state`
and `.waiting_for_fork` were set in two separate lock acquisitions,
creating a real window where a snapshot could see `state == WAITING` with
`waiting_for_fork == None`. Fixed in `_enter_waiting()` by writing both
fields in one `with state_lock:` block. (See `docs/algorithms.md` §4.)

**12. What is a lock? What is a semaphore? What's the difference?**
A lock (`threading.Lock`) is a binary mutual-exclusion primitive: held by
at most one thread at a time. A semaphore (`threading.Semaphore`) is a
counter: up to N threads may hold it concurrently. A lock is a semaphore
with count 1, conceptually — this project uses `Lock` for forks
(exclusive by nature) and `Semaphore` for the waiter strategy's admission
control (N-1 concurrent slots).

**13. Why poll with a timeout (`acquire(timeout=0.05)`) instead of a plain
blocking `acquire()`?**
So a philosopher thread can periodically re-check for pause/stop/step
signals while waiting, keeping Pause and Reset responsive even for a
thread that is (genuinely) permanently blocked in a deadlock. It does
**not** release the fork the thread already holds — hold-and-wait is
completely unaffected; the timeout only controls how often the *next*
fork attempt is retried.

**14. Does polling with a timeout turn this into "busy waiting"? Isn't
that wasteful/a different problem?**
It is closer to busy-waiting than an indefinite blocking `acquire()`, yes,
but each poll blocks for up to 50ms via a real OS-level wait inside
`Lock.acquire(timeout=...)`, not a spin loop — so the thread is not
consuming CPU between attempts. Trade-off explicitly accepted for
controllability (responsive Pause/Reset/Step) over marginal CPU savings
that don't matter at this small scale.

**15. What ensures a fork is never held by two philosophers at once?**
The `threading.Lock` itself — `Lock.acquire()` is provided by the
platform's threading implementation as an atomic operation; two threads
cannot both succeed. Directly stress-tested in `tests/test_fork.py::
test_mutual_exclusion_stress` (8 threads, 150 iterations each, asserting
max concurrent holders == 1).

**16. What happens if two philosophers request the same fork
simultaneously?**
Both call `Fork.try_acquire()`. Exactly one succeeds (returns `True`); the
other's call returns `False` after its timeout elapses, and that
philosopher's thread logs a `WAITING` state and retries.

**17. Why is a `state_lock` (RLock) needed in addition to each fork's own
`Lock`?**
Fork locks provide mutual exclusion over the *resource*. `state_lock`
protects the separate problem of giving the API layer a consistent,
non-torn snapshot of *metadata* (which state a philosopher is in, which
fork it's waiting for) while philosopher threads are concurrently
updating it.

**18. Why `RLock` and not a plain `Lock` for `state_lock`?**
Some `Simulator` methods that already hold `state_lock` call other methods
that also acquire it (e.g. via nested `with` blocks in `philosopher.py`).
A plain `Lock` would deadlock the state-management code itself on
re-entry; `RLock` allows the same thread to re-acquire it.

**19. What is a `threading.Barrier`, and how is it used here?**
A `Barrier(N)` blocks each calling thread until exactly N threads have
called `.wait()` on it, then releases them all simultaneously. Used in
`Simulator.trigger_deadlock()` to force all N philosophers to rendezvous
right after taking their first fork — making the deadlock scenario
happen deterministically on demand instead of only by chance.

**20. What is a `threading.Event`, and how is it used here?**
A simple thread-safe flag with `set()`/`clear()`/`is_set()`/`wait()`. Used
for `stop_event` (signals shutdown), `pause_event` (signals pause), and
`manual_mode` (signals step-gating is active).

## Deadlock Detection

**21. How is deadlock detected in this project?**
A background `DeadlockDetector` thread polls live state every 150ms,
builds a wait-for graph (`Pi -> Pj` if `Pi` is `WAITING` on a fork `Pj`
holds), and walks it looking for a cycle. A detected cycle must persist
for 1.5 seconds before being reported, to avoid flagging a fork that's
about to be released a moment later as a false positive.

**22. Why is the wait-for graph simple to search here (no general graph
algorithm needed)?**
Because each philosopher waits for at most one fork at a time, every node
in the graph has out-degree ≤ 1 — the graph is just a set of pointer
chains. Finding a cycle is a simple walk-until-you-revisit-a-node, not a
general-purpose algorithm like Tarjan's SCC.

**23. What would you need to change to detect deadlock if a thread could
wait on multiple resources at once?**
The wait-for graph would need multiple outgoing edges per node, and
you'd need a general cycle-detection algorithm (e.g. DFS with a
recursion-stack check, or Tarjan's SCC algorithm) instead of the simple
pointer-chain walk used here.

## Project-Specific / Implementation Decisions

**24. Why does "Force Deadlock Demo" only work in naive mode?**
Because `OrderedStrategy` and `WaiterStrategy` are structurally
deadlock-free — forcing philosophers to rendezvous at their first fork
would not produce a deadlock under those strategies (the code checks
`self.strategy_name != "naive"` and refuses in
`Simulator.trigger_deadlock()`), so offering the button there would be
misleading.

**25. What happens when the simulation is reset mid-deadlock?**
`Simulator.reset()` sets `stop_event`, calls `deadlock_barrier.abort()`
(unblocking anything waiting on it with a `BrokenBarrierError`), then
`join()`s every philosopher thread with a timeout. Each philosopher's
`run()` method has a `finally` block that releases any forks it still
holds and transitions to `STOPPED`, so no thread or lock is left dangling
even though it was mid-deadlock.

**26. How do you guarantee no stale threads survive a Reset?**
`Simulator.reset()` explicitly calls `p.join(timeout=2.0)` on every
philosopher thread (and the detector thread) before returning, and
`tests/test_simulation.py::test_reset_leaves_no_stale_threads` asserts via
`threading.enumerate()` that no `Philosopher-*` or `DeadlockDetector`
thread remains afterward.

**27. How are locks/semaphores guaranteed to be released even on an
exception or forced stop?**
`Philosopher.run()` wraps its entire loop in `try/finally`, and the
`finally` block unconditionally calls `_release_forks(force=True)`, which
releases every fork still in `held_forks` and, if the waiter strategy's
semaphore permit is still held (tracked via `self._holds_permit`),
releases that too.

**28. Why does Step mode not pause mid-think or mid-eat?**
Because "Step" is defined to advance the simulation by one meaningful
*synchronization* event (becoming hungry, requesting a fork, starting to
eat), not by a fixed time slice. The think/eat durations themselves are
just elapsed time, not a synchronization event, so gating them would
contradict the definition rather than support it.

**29. Why can't JavaScript alone represent the actual OS concurrency this
project demonstrates?**
`setTimeout`/`setInterval` in JS run on a single-threaded event loop with
cooperative, deterministic callback ordering — there is no real
concurrent execution, no real blocking, and no real mutual exclusion
being demonstrated; you would only be animating a story you already
decided. This project's states, wait times, and the deadlock itself are
outcomes computed by genuinely concurrent, OS-scheduled Python threads
contending over real `Lock` objects — the browser only polls and displays
results it did not produce.

**30. Why is fork utilization only measured during eating, not while
blocked holding one fork?**
A deliberate, documented choice (`docs/algorithms.md` §"Metrics" note) so
the number has one unambiguous meaning — "productive" hold time as a
fraction of elapsed time — rather than conflating useful work with a
philosopher stuck mid-acquisition.

**31. Why does the project use Flask's built-in development server rather
than a production WSGI server?**
Scope: this is a local, single-operator teaching/demo tool, not a
deployed multi-user service — a production server (gunicorn/waitress)
would add operational complexity with no benefit here. This is stated
explicitly in `README.md` § Limitations, not left implicit.

**32. What's the difference between deadlock avoidance and deadlock
prevention, and which does this project implement?**
Prevention removes a Coffman condition structurally via a fixed policy
decided in advance (this project: resource ordering removes circular
wait; the semaphore removes full-scale hold-and-wait). Avoidance
(Banker's Algorithm) instead evaluates each individual request at runtime
against declared maximum future needs, granting only requests that leave
the system in a "safe" state. This project implements **prevention only**
— no strategy here does runtime safe-state analysis.

**33. If you added a 4th, monitor/condition-variable-based strategy
("test-and-set with waiting"), how would it differ from the two already
implemented?**
It would typically have a philosopher acquire a single mutex protecting
all fork state, check "are both my forks free?" and only take them
together atomically (or wait on a `Condition` if not), rather than
acquiring them one at a time. This avoids hold-and-wait entirely (an
"all-or-nothing" resource request) instead of avoiding circular wait
(ordering) or limiting concurrency (semaphore) — a third distinct
Coffman-condition attack, left as documented future work.
