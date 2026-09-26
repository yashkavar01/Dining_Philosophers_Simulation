"""
StepController gates philosopher threads in manual/step mode.

Design: a single counting semaphore starting at 0 ("permits"). When manual
mode is on, a philosopher thread calls wait_for_turn() before every
loggable synchronization action (becoming hungry, requesting a fork,
starting to eat, ...) and blocks until a permit is available. Each call to
advance() (triggered by POST /api/simulation/step) releases exactly one
permit, letting exactly one currently-waiting thread's one action through.

Which of the several waiting threads actually gets that permit is decided
by the OS scheduler, not by this code -- so single-stepping still shows
genuine, unscripted nondeterministic concurrency, just paused between
events instead of running freely.
"""
from __future__ import annotations

import threading

POLL_INTERVAL = 0.05


class StepController:
    def __init__(self):
        self._permits = threading.Semaphore(0)

    def wait_for_turn(self, philosopher) -> None:
        sim = philosopher.simulator
        while sim.manual_mode.is_set() and not sim.stop_event.is_set():
            if self._permits.acquire(timeout=POLL_INTERVAL):
                return
        # Manual mode was switched off, or the simulation is stopping:
        # let the thread proceed freely rather than hang forever.

    def advance(self) -> None:
        self._permits.release()
