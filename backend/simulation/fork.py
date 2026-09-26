"""
A Fork is a single shared resource. `self.lock` (a real threading.Lock) IS
the actual mutual-exclusion mechanism used by the simulation -- it is what
prevents two philosophers from ever holding the same fork at once.

`held_by` / `acquired_at` are metadata, written only by whichever thread
currently owns the lock. They exist purely so the API layer can describe
current ownership to the browser; they play no role in the synchronization
itself. Because CPython attribute writes are atomic with respect to the
GIL, reading them from another thread for a display snapshot is safe
(never a crash, at worst a snapshot that is a few milliseconds stale).
"""
from __future__ import annotations

import threading
import time
from typing import Optional


class Fork:
    def __init__(self, fork_id: int):
        self.id = fork_id
        self.lock = threading.Lock()
        self.held_by: Optional[int] = None
        self.acquired_at: Optional[float] = None

    def try_acquire(self, philosopher_id: int, timeout: float) -> bool:
        """
        Attempt to acquire this fork's lock, blocking for at most `timeout`
        seconds. Returns True/False. The timeout exists so a philosopher
        thread can periodically re-check for pause/stop signals while
        waiting -- it does NOT cause the fork to be given up; the caller
        simply loops and tries again, so hold-and-wait on a fork the
        philosopher already owns is completely unaffected.
        """
        acquired = self.lock.acquire(timeout=timeout)
        if acquired:
            self.held_by = philosopher_id
            self.acquired_at = time.monotonic()
        return acquired

    def release(self, philosopher_id: int) -> None:
        if self.held_by != philosopher_id:
            # Defensive guard: should never trigger if strategies/philosopher
            # code are correct, since only the owning thread ever calls this.
            return
        self.held_by = None
        self.acquired_at = None
        self.lock.release()

    def snapshot(self) -> dict:
        return {"id": self.id, "held_by": self.held_by}
