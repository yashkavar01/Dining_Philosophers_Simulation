"""
MetricsCollector records raw numbers as the simulation runs, and only ever
derives averages/percentages from those recorded numbers -- nothing here
is a fixed, estimated, or hardcoded value. If a run produced zero eating
cycles, the metrics will honestly show zero, not a plausible-looking
placeholder.

Note on fork utilization: it measures the fraction of elapsed time a fork
spent being held WHILE its philosopher was actively eating -- not time
held while a philosopher sits blocked with one fork waiting for the other.
This is a deliberate, documented choice (see docs/algorithms.md) so the
number means one specific thing rather than conflating "useful work" with
"stuck holding a resource."
"""
from __future__ import annotations

import threading
import time
from typing import Dict


class MetricsCollector:
    def __init__(self, num_philosophers: int):
        self._lock = threading.Lock()
        self.reset(num_philosophers)

    def reset(self, num_philosophers: int) -> None:
        with self._lock:
            self.num_philosophers = num_philosophers
            self.start_time = time.monotonic()
            self.meals_eaten: Dict[int, int] = {i: 0 for i in range(num_philosophers)}
            self.total_wait_time: Dict[int, float] = {i: 0.0 for i in range(num_philosophers)}
            self.max_wait_time: Dict[int, float] = {i: 0.0 for i in range(num_philosophers)}
            self.wait_episodes: Dict[int, int] = {i: 0 for i in range(num_philosophers)}
            self.fork_acquire_attempts = 0
            self.blocked_attempts = 0
            self.deadlock_detections = 0
            self.fork_hold_time: Dict[int, float] = {i: 0.0 for i in range(num_philosophers)}

    def record_meal(self, pid: int) -> None:
        with self._lock:
            self.meals_eaten[pid] = self.meals_eaten.get(pid, 0) + 1

    def record_wait(self, pid: int, duration: float) -> None:
        with self._lock:
            self.total_wait_time[pid] = self.total_wait_time.get(pid, 0.0) + duration
            self.wait_episodes[pid] = self.wait_episodes.get(pid, 0) + 1
            if duration > self.max_wait_time.get(pid, 0.0):
                self.max_wait_time[pid] = duration

    def record_fork_attempt(self) -> None:
        with self._lock:
            self.fork_acquire_attempts += 1

    def record_blocked(self) -> None:
        with self._lock:
            self.blocked_attempts += 1

    def record_deadlock(self) -> None:
        with self._lock:
            self.deadlock_detections += 1

    def record_fork_hold(self, fork_id: int, duration: float) -> None:
        with self._lock:
            self.fork_hold_time[fork_id] = self.fork_hold_time.get(fork_id, 0.0) + duration

    def snapshot(self) -> dict:
        with self._lock:
            elapsed = max(time.monotonic() - self.start_time, 1e-6)
            avg_wait_per_phil = {
                i: (self.total_wait_time[i] / self.wait_episodes[i]) if self.wait_episodes[i] else 0.0
                for i in range(self.num_philosophers)
            }
            total_wait_episodes = sum(self.wait_episodes.values())
            overall_avg_wait = (
                sum(self.total_wait_time.values()) / total_wait_episodes if total_wait_episodes else 0.0
            )
            fork_utilization = {
                fid: round(min(t / elapsed, 1.0), 3) for fid, t in self.fork_hold_time.items()
            }
            return {
                "elapsed_time": round(elapsed, 2),
                "meals_eaten": dict(self.meals_eaten),
                "total_meals": sum(self.meals_eaten.values()),
                "avg_wait_time_per_philosopher": {i: round(v, 3) for i, v in avg_wait_per_phil.items()},
                "overall_avg_wait_time": round(overall_avg_wait, 3),
                "max_wait_time": {i: round(v, 3) for i, v in self.max_wait_time.items()},
                "overall_max_wait_time": round(max(self.max_wait_time.values(), default=0.0), 3),
                "fork_acquire_attempts": self.fork_acquire_attempts,
                "blocked_attempts": self.blocked_attempts,
                "deadlock_detections": self.deadlock_detections,
                "fork_utilization": fork_utilization,
            }
