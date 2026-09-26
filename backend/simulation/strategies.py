"""
Pluggable fork-acquisition strategies.

Each strategy decides two things for a philosopher:
  1. fork_order()          -- which fork to attempt FIRST, which SECOND
  2. pre_acquire/post_release hooks -- any extra synchronization gate
                                        (used by the waiter strategy)

The actual blocking/locking mechanics (the poll loop, hold-and-wait
behaviour) live in Philosopher._acquire_forks and are IDENTICAL for every
strategy. This is deliberate: it is the ORDERING policy that determines
whether deadlock is possible, not the low-level locking code -- exactly
the point this project is meant to demonstrate.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Tuple


class BaseStrategy(ABC):
    name: str = "base"

    @abstractmethod
    def fork_order(self, philosopher_id: int, num_philosophers: int) -> Tuple[int, int]:
        """Return (first_fork_id, second_fork_id) this philosopher must acquire, in order."""
        raise NotImplementedError

    def pre_acquire_hook(self, philosopher) -> None:
        """Optional extra gate before attempting the first fork."""
        pass

    def post_release_hook(self, philosopher) -> None:
        """Optional cleanup after both forks have been released."""
        pass

    def explanation(self) -> str:
        raise NotImplementedError


class NaiveStrategy(BaseStrategy):
    """Left fork = own id, right fork = next id. No global ordering -> can deadlock."""
    name = "naive"

    def fork_order(self, philosopher_id, num_philosophers):
        left = philosopher_id
        right = (philosopher_id + 1) % num_philosophers
        return left, right

    def explanation(self) -> str:
        return (
            "UNSAFE: every philosopher picks up their LEFT fork first, then their "
            "RIGHT fork. If all N philosophers pick up their left fork at roughly "
            "the same time, every fork is held and every philosopher is waiting on "
            "a neighbour's fork -> circular wait -> deadlock. All four Coffman "
            "conditions hold at once: mutual exclusion (forks are exclusive locks), "
            "hold-and-wait (each Pi keeps its left fork while blocked on its right), "
            "no preemption (a fork is never forcibly taken back), circular wait "
            "(P0 -> P1 -> ... -> P(N-1) -> P0)."
        )


class OrderedStrategy(BaseStrategy):
    """Resource-ordering (Dijkstra): always acquire the lower-numbered fork first."""
    name = "ordered"

    def fork_order(self, philosopher_id, num_philosophers):
        left = philosopher_id
        right = (philosopher_id + 1) % num_philosophers
        return (left, right) if left < right else (right, left)

    def explanation(self) -> str:
        return (
            "DEADLOCK-FREE (prevention, via circular wait elimination): every "
            "philosopher acquires the LOWER-numbered fork first, regardless of "
            "which side it is physically on. Philosopher N-1's forks are "
            "(N-1, 0); under this rule it requests fork 0 first, breaking the "
            "'everyone waits on the next seat' pattern. Any wait-for chain would "
            "require a philosopher waiting on a lower-numbered fork held by someone "
            "already waiting on a strictly lower one -- fork ids would have to "
            "decrease forever around the chain, which is impossible in a finite "
            "set. So a cycle (circular wait, Coffman condition 4) can never form -- "
            "deadlock is structurally impossible, not just unlikely."
        )


class WaiterStrategy(BaseStrategy):
    """Bounded concurrency (the 'waiter' / limited-admission solution)."""
    name = "waiter"

    def fork_order(self, philosopher_id, num_philosophers):
        left = philosopher_id
        right = (philosopher_id + 1) % num_philosophers
        return left, right

    def pre_acquire_hook(self, philosopher) -> None:
        philosopher.simulator.dining_semaphore.acquire()

    def post_release_hook(self, philosopher) -> None:
        philosopher.simulator.dining_semaphore.release()

    def explanation(self) -> str:
        return (
            "DEADLOCK-FREE (prevention, via hold-and-wait limitation): a counting "
            "semaphore initialised to N-1 must be acquired before a philosopher may "
            "attempt EITHER fork, and is released only after both forks have been "
            "released. At most N-1 philosophers can be mid-acquisition at any "
            "instant, so at least one philosopher is always excluded from fork "
            "contention entirely. The full ring of N simultaneous fork-holders "
            "required for a circular wait can therefore never form."
        )


STRATEGY_REGISTRY = {
    "naive": NaiveStrategy,
    "ordered": OrderedStrategy,
    "waiter": WaiterStrategy,
}
