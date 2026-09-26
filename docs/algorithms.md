# Algorithms and OS Theory

This document explains the operating-systems concepts this project
demonstrates, each tied directly to the specific line of code that
implements it. It intentionally does not cover topics the implementation
doesn't touch.

## 1. Process vs Thread

A **process** has its own memory address space; a **thread** shares its
process's memory with sibling threads. This project uses **threads**
(`backend/simulation/philosopher.py`, class `Philosopher(threading.Thread)`)
specifically because the philosophers need to share the same fork objects
directly — that shared-memory access is exactly what the Dining
Philosophers problem is about (contention over shared resources), and
processes would require explicit IPC to achieve the same sharing.

## 2. Concurrent Execution

All `Philosopher` threads, plus the `DeadlockDetector` thread, are started
independently in `Simulator.start()` and run their own `while` loops
without any central turn-taking. Which thread the OS scheduler runs at any
instant is not controlled by this code at all — the "Step" mode
(`step_controller.py`) pauses threads at defined gate points, but even
then, which of several waiting threads gets the next permit is left to the
OS.

## 3. Critical Section

The critical section here is the pair of statements "check whether a fork
is free" and "take it" — in this implementation those two steps are
**one atomic operation**, `threading.Lock.acquire()`, so there is no
window in which two threads could both observe a fork as free and both
take it. See `Fork.try_acquire()` in `fork.py`.

## 4. Race Condition

A race condition would occur if two philosophers could both believe they
hold the same fork. This is structurally prevented by using a real
`threading.Lock` per fork rather than, say, a plain boolean flag (a flag
read-then-write is *not* atomic and would race). `tests/test_fork.py::
test_mutual_exclusion_stress` stress-tests this directly with 8 threads
hammering one fork 150 times each and asserting the maximum number of
concurrent holders is exactly 1.

A **separate** race was caught during development of this project itself:
`Philosopher.state` and `Philosopher.waiting_for_fork` were originally set
in two separate `state_lock` acquisitions, leaving a window where a
snapshot could observe `state == WAITING` with `waiting_for_fork` still
`None`. The fix (`Philosopher._enter_waiting()`) sets both fields inside a
single `with state_lock:` block. This is left in the codebase as a
realistic illustration of exactly the class of bug this section is about.

## 5. Mutual Exclusion

Provided by `threading.Lock` (one per fork). Only the thread that
successfully calls `acquire()` may proceed to eat; every other thread
attempting the same fork blocks (or, in this implementation, retries)
until `release()` is called.

## 6. Locks

`Fork.lock` is a `threading.Lock`. `Simulator.state_lock` is a
`threading.RLock` (re-entrant, since `Simulator` methods that already
hold it sometimes call other methods that also acquire it).

## 7. Semaphores

Used in two places:
- **Waiter strategy** (`strategies.py`, `WaiterStrategy`): a
  `threading.Semaphore(N-1)` gates entry into fork contention, guaranteeing
  at most N-1 philosophers are ever mid-acquisition.
- **Step controller** (`step_controller.py`): a `threading.Semaphore(0)`
  ("permits") gates every philosopher action in manual mode; each call to
  `advance()` releases exactly one permit.

## 8. Condition Variables

Not used directly as `threading.Condition` in the final design — pause/
resume and step-gating are implemented with `threading.Event` and
`threading.Semaphore` instead, which is a simpler and equally correct fit
for "wait until a flag/count changes" here. (If you are asked in viva why
`Condition` wasn't used: a `Condition` is most valuable when a thread needs
to wait on an arbitrary, checkable predicate over shared state with
`notify()`/`wait()`; our two gating needs — "is manual mode still on and
do I have a permit" and "is pause_event set" — are naturally expressed
with `Event`/`Semaphore` alone, so introducing `Condition` would add
complexity without adding capability.)

## 9. Shared Resources

The five (or N) forks are the shared resources. Each is represented by a
`Fork` object wrapping exactly one `threading.Lock` — modelling the
physical constraint that a fork can only be in one hand at a time.

## 10. Deadlock

A state where a set of threads are each waiting for a resource held by
another thread in the same set, such that none can ever proceed. This
project produces a **real** deadlock (not a simulated label) in the naive
strategy: see `tests/test_deadlock.py::test_naive_strategy_deadlocks_when_triggered`,
which starts real threads, forces the classic case via
`Simulator.trigger_deadlock()`, and asserts the detector finds a genuine
5-cycle.

## 11. The Four Coffman Conditions

All four must hold simultaneously for deadlock to be possible; this
project's naive strategy exhibits all four:

| Condition | How it appears here |
|---|---|
| **Mutual exclusion** | Each fork is a `threading.Lock` — only one philosopher can hold it. |
| **Hold and wait** | A philosopher keeps its first fork (never releases it) while blocked polling for its second — see the loop in `Philosopher._acquire_forks()`. |
| **No preemption** | Nothing in this codebase ever forcibly takes a fork away from a thread that holds it; a fork is only released voluntarily, in `Philosopher._release_forks()`. |
| **Circular wait** | The naive strategy's fork ordering (`NaiveStrategy.fork_order()`) creates exactly the asymmetric pattern (P(N-1) requests the "wrong way round") that allows P0→P1→...→P(N-1)→P0. |

## 12. The Dining Philosophers Problem

N philosophers sit at a round table with N forks, one between each
adjacent pair. Each philosopher alternately thinks and eats; eating
requires holding both adjacent forks. It's a classical illustration of
resource contention, mutual exclusion, and deadlock because the "obvious"
solution (always pick up left, then right) creates a circular wait.

## 13. Deadlock Prevention

Attacks one of the four Coffman conditions structurally, so deadlock is
made **impossible**, not just unlikely. Both alternative strategies in
this project are prevention strategies:

- **Resource ordering** (`OrderedStrategy`) removes **circular wait**: fork
  ids must be acquired in increasing order, so a cyclic wait chain would
  require fork ids to decrease forever around the cycle — impossible.
- **Waiter/semaphore** (`WaiterStrategy`) removes the possibility of **all
  N** philosophers simultaneously holding one fork each (a prerequisite
  for the naive deadlock) by removing **hold-and-wait at full scale**: at
  most N-1 philosophers may contend for forks at once, so at least one
  fork is always available to break the chain.

## 14. Deadlock Avoidance vs Deadlock Prevention

These are frequently confused, so it is worth being precise for the viva:

- **Prevention** (what this project implements) removes the structural
  possibility of one of the four Coffman conditions ahead of time, via a
  fixed policy (e.g. a global lock ordering). It requires no runtime
  knowledge of future requests.
- **Avoidance** (e.g. the Banker's Algorithm) instead requires each
  thread to declare its maximum future resource needs in advance, and the
  OS grants a request only if the resulting state is still "safe" (some
  ordering exists in which everyone can finish). This project does
  **not** implement avoidance — no strategy here does runtime
  safe-state analysis; both alternative strategies work by fixed
  structural policy, decided once, not by evaluating each request.

## 15. Circular Wait

A cycle P0 waits-for P1 waits-for P2 ... waits-for P0 in the resource
allocation graph. Directly detected by `DeadlockDetector._find_cycle()`,
which walks the wait-for graph (out-degree ≤ 1 per node, since a
philosopher waits for at most one fork) following pointers until it
revisits a node.

## 16. Resource (Lock) Ordering

The general technique of imposing a total order on all resources in the
system and requiring every thread to request them in increasing order.
Implemented exactly this way in `OrderedStrategy.fork_order()`.

## 17. Starvation

A thread that is *able* to make progress in principle (no deadlock) but
never actually gets scheduled/served in practice. This project does
**not** prove any strategy is starvation-free — that would require a
fairness argument about the underlying OS scheduler, which is out of
scope. Instead, it **measures** a starvation proxy honestly: `max_wait_time`
per philosopher, visible in the Metrics panel and the Comparison table. If
one philosopher's max wait time grows unboundedly over a long run under a
given strategy, that would be observed starvation — the dashboard would
show it rather than hide it.

## 18. Fairness

Related to starvation: whether all threads get a roughly equal share of
resource access over time. This project does not implement any fairness
mechanism (e.g. ticket locks, FIFO queuing for forks) — `Lock.acquire()`'s
internal wake-up order is whatever the platform's threading implementation
provides, which is not guaranteed FIFO in CPython. This is a known,
documented limitation, not an oversight — see `README.md` § Limitations.

## 19. Progress

The liveness property that the system as a whole keeps making forward
progress (some thread's request is eventually granted), as distinct from
starvation (a specific thread being denied indefinitely) and deadlock (no
thread anywhere can proceed). `tests/test_deadlock.py::
test_ordered_strategy_never_deadlocks_over_a_run` and the waiter-strategy
equivalent both assert `total_meals > 0` after a timed run — a direct,
measured check of system-wide progress, not merely an absence of
deadlock.
