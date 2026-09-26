"""
Philosopher is a real threading.Thread. Every philosopher in the
simulation is a genuinely separate OS-scheduled thread running this loop
concurrently with the others -- there is no central "scheduler" deciding
turns, and no JavaScript timer anywhere in this file.

Lifecycle per cycle: THINKING -> HUNGRY -> (request/acquire forks,
possibly WAITING) -> EATING -> release forks -> back to THINKING.

Fork acquisition uses acquire(timeout=POLL_INTERVAL) in a loop instead of
a plain blocking acquire(). This does NOT weaken the synchronization --
a philosopher never gives up a fork it already holds while polling for
the next one, so hold-and-wait is completely real. The timeout only
controls how often the thread re-checks for pause/stop/step signals, so
that Pause, Reset, and Step all stay responsive even while a philosopher
is (genuinely, indefinitely) blocked in a deadlock.
"""
from __future__ import annotations

import random
import threading
import time
from typing import List, Optional

from .models import PhilosopherState, EventType

POLL_INTERVAL = 0.05


class Philosopher(threading.Thread):
    def __init__(self, philosopher_id: int, simulator):
        super().__init__(daemon=True, name=f"Philosopher-{philosopher_id}")
        self.id = philosopher_id
        self.simulator = simulator
        self.state = PhilosopherState.THINKING
        self.state_since = time.monotonic()
        self.waiting_for_fork: Optional[int] = None
        self.held_forks: List[int] = []
        self._holds_permit = False   # tracks whether the waiter-strategy semaphore is held

    # ------------------------------------------------------------- state --
    def _set_state(self, new_state: PhilosopherState, extra_msg: str = "") -> None:
        sim = self.simulator
        with sim.state_lock:
            self.state = new_state
            self.state_since = time.monotonic()
        sim.events.log(
            EventType.STATE_CHANGE,
            f"P{self.id} became {new_state.value}{extra_msg}",
            philosopher_id=self.id,
            data={"state": new_state.value},
        )

    # ---------------------------------------------------------- main loop --
    def run(self) -> None:
        sim = self.simulator
        try:
            while not sim.stop_event.is_set():
                self._wait_if_paused()
                if sim.stop_event.is_set():
                    break
                self._think()
                if sim.stop_event.is_set():
                    break
                self._get_hungry()
                if sim.stop_event.is_set():
                    break
                acquired = self._acquire_forks()
                if not acquired:
                    break  # stop was requested mid-acquisition; unwind via finally
                self._eat()
                self._release_forks()
        finally:
            # Safety net: guarantees any fork this thread still holds (e.g.
            # because Reset happened mid-cycle) is released, on every exit
            # path, including exceptions.
            self._release_forks(force=True)
            with sim.state_lock:
                self.state = PhilosopherState.STOPPED

    def _wait_if_paused(self) -> None:
        sim = self.simulator
        while sim.pause_event.is_set() and not sim.stop_event.is_set():
            time.sleep(POLL_INTERVAL)

    def _gate_step(self) -> None:
        """In manual/step mode, block here until the user clicks Step."""
        if self.simulator.manual_mode.is_set():
            self.simulator.step_controller.wait_for_turn(self)

    def _enter_waiting(self, fork_id: int, holder_id: Optional[int]) -> None:
        """
        Atomically set state=WAITING together with waiting_for_fork in a
        SINGLE lock acquisition. Setting them in two separate `with
        state_lock:` blocks would leave a real window where a concurrent
        snapshot reader could observe state==WAITING with waiting_for_fork
        still None (or stale) -- exactly the kind of race this project is
        supposed to demonstrate correct handling of, not fall into.
        """
        sim = self.simulator
        with sim.state_lock:
            self.state = PhilosopherState.WAITING
            self.state_since = time.monotonic()
            self.waiting_for_fork = fork_id
        sim.events.log(
            EventType.STATE_CHANGE,
            f"P{self.id} became WAITING (blocked on F{fork_id}, held by P{holder_id})",
            philosopher_id=self.id,
            data={"state": "WAITING", "fork_id": fork_id},
        )

    # --------------------------------------------------------- lifecycle --
    def _think(self) -> None:
        self._gate_step()
        self._set_state(PhilosopherState.THINKING)
        duration = random.uniform(*self.simulator.think_time_range) / self.simulator.speed
        self._interruptible_sleep(duration)

    def _get_hungry(self) -> None:
        self._gate_step()
        self._set_state(PhilosopherState.HUNGRY)

    def _acquire_forks(self) -> bool:
        sim = self.simulator
        strategy = sim.strategy
        first_id, second_id = strategy.fork_order(self.id, sim.num_philosophers)

        strategy.pre_acquire_hook(self)
        self._holds_permit = True

        for fork_id in (first_id, second_id):
            self._gate_step()
            fork = sim.forks[fork_id]
            sim.events.log(EventType.FORK_REQUEST, f"P{self.id} requested F{fork_id}",
                            philosopher_id=self.id, data={"fork_id": fork_id})
            sim.metrics.record_fork_attempt()

            got_it = False
            wait_start = time.monotonic()
            reported_blocked = False
            while not sim.stop_event.is_set():
                self._wait_if_paused()
                if fork.try_acquire(self.id, timeout=POLL_INTERVAL):
                    got_it = True
                    break
                if not reported_blocked:
                    sim.metrics.record_blocked()
                    self._enter_waiting(fork_id, fork.held_by)
                    reported_blocked = True

            if not got_it:
                return False  # stop requested; cleanup happens centrally in run()'s finally

            wait_duration = time.monotonic() - wait_start
            if reported_blocked:
                sim.metrics.record_wait(self.id, wait_duration)

            with sim.state_lock:
                self.waiting_for_fork = None
                self.held_forks.append(fork_id)
                if reported_blocked:
                    # We were WAITING; now that the fork is in hand, go back
                    # to HUNGRY (still hungry for the other fork) instead of
                    # leaving a stale WAITING label with nothing to point at.
                    self.state = PhilosopherState.HUNGRY
                    self.state_since = time.monotonic()
            sim.events.log(EventType.FORK_ACQUIRED, f"P{self.id} acquired F{fork_id}",
                            philosopher_id=self.id, data={"fork_id": fork_id})
            if reported_blocked:
                sim.events.log(
                    EventType.STATE_CHANGE,
                    f"P{self.id} became HUNGRY (acquired F{fork_id}, still needs the other fork)",
                    philosopher_id=self.id, data={"state": "HUNGRY"},
                )

            # Deterministic deadlock demo: rendezvous once every philosopher
            # has taken its FIRST fork, forcing the textbook worst case on
            # demand instead of hoping timing lines up on its own.
            if sim.deadlock_barrier is not None and fork_id == first_id:
                try:
                    sim.deadlock_barrier.wait(timeout=5)
                except threading.BrokenBarrierError:
                    pass

        return True

    def _eat(self) -> None:
        self._gate_step()
        self._set_state(PhilosopherState.EATING)
        sim = self.simulator
        sim.events.log(EventType.EATING_STARTED, f"P{self.id} started EATING", philosopher_id=self.id)
        duration = random.uniform(*sim.eat_time_range) / sim.speed
        eat_start = time.monotonic()
        self._interruptible_sleep(duration)
        held_duration = time.monotonic() - eat_start
        for fid in self.held_forks:
            sim.metrics.record_fork_hold(fid, held_duration)
        sim.metrics.record_meal(self.id)
        sim.events.log(EventType.EATING_DONE, f"P{self.id} finished EATING", philosopher_id=self.id)

    def _release_forks(self, force: bool = False) -> None:
        sim = self.simulator
        with sim.state_lock:
            forks_to_release = list(self.held_forks)
            self.held_forks.clear()
        for fid in forks_to_release:
            fork = sim.forks[fid]
            fork.release(self.id)
            sim.events.log(EventType.FORK_RELEASED, f"P{self.id} released F{fid}",
                            philosopher_id=self.id, data={"fork_id": fid})
        if self._holds_permit:
            sim.strategy.post_release_hook(self)
            self._holds_permit = False

    def _interruptible_sleep(self, duration: float) -> None:
        sim = self.simulator
        end = time.monotonic() + duration
        while time.monotonic() < end and not sim.stop_event.is_set():
            self._wait_if_paused()
            time.sleep(min(POLL_INTERVAL, max(end - time.monotonic(), 0)))

    # ------------------------------------------------------------ output --
    def snapshot(self) -> dict:
        sim = self.simulator
        with sim.state_lock:
            return {
                "id": self.id,
                "state": self.state.value,
                "state_since": round(time.monotonic() - self.state_since, 2),
                "waiting_for_fork": self.waiting_for_fork,
                "held_forks": list(self.held_forks),
            }
