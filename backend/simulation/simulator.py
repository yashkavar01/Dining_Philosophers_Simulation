"""
Simulator owns the full lifecycle of a run: creating/destroying real
philosopher threads, holding the active strategy, and exposing thread-safe
snapshots for the Flask layer. This is the ONLY class app.py talks to --
Flask never touches a Lock, Thread, or Semaphore directly.
"""
from __future__ import annotations

import threading
import time
from typing import List, Optional

from .deadlock_detector import DeadlockDetector
from .event_logger import EventLogger
from .fork import Fork
from .metrics import MetricsCollector
from .models import EventType
from .philosopher import Philosopher
from .step_controller import StepController
from .strategies import STRATEGY_REGISTRY

DEFAULT_THINK_RANGE = (1.0, 3.0)
DEFAULT_EAT_RANGE = (1.0, 2.0)
MIN_PHILOSOPHERS = 3
MAX_PHILOSOPHERS = 10


class Simulator:
    def __init__(self):
        # state_lock protects every field below that is read/written from
        # more than one thread (philosopher threads + the Flask request
        # thread). Fork/lock internals are NOT protected by this lock --
        # they have their own, separate synchronization (see fork.py).
        self.state_lock = threading.RLock()

        self.events = EventLogger()
        self.num_philosophers = 5
        self.speed = 1.0
        self.think_time_range = DEFAULT_THINK_RANGE
        self.eat_time_range = DEFAULT_EAT_RANGE

        self.strategy_name = "naive"
        self.strategy = STRATEGY_REGISTRY[self.strategy_name]()

        self.forks: List[Fork] = []
        self.philosophers: List[Philosopher] = []
        self.metrics = MetricsCollector(self.num_philosophers)

        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.manual_mode = threading.Event()
        self.step_controller = StepController()

        self.dining_semaphore: Optional[threading.Semaphore] = None
        self.deadlock_barrier: Optional[threading.Barrier] = None

        self.deadlock_info = {"detected": False, "cycle": [], "wait_for_graph": {}, "detected_at": None}
        self.detector: Optional[DeadlockDetector] = None
        self.status = "idle"  # idle | running | paused
        self.run_history: List[dict] = []

    # ------------------------------------------------------------ lifecycle --
    def start(self, num_philosophers=5, strategy="naive", speed=1.0, manual=False) -> None:
        if strategy not in STRATEGY_REGISTRY:
            raise ValueError(f"Unknown strategy: {strategy}")

        self.reset()  # ensures a clean slate; joins any previous run's threads

        self.num_philosophers = max(MIN_PHILOSOPHERS, min(MAX_PHILOSOPHERS, int(num_philosophers)))
        self.speed = max(0.25, min(4.0, float(speed)))
        self.strategy_name = strategy
        self.strategy = STRATEGY_REGISTRY[strategy]()

        self.forks = [Fork(i) for i in range(self.num_philosophers)]
        self.metrics.reset(self.num_philosophers)
        self.events.reset()
        self.deadlock_info = {"detected": False, "cycle": [], "wait_for_graph": {}, "detected_at": None}
        self.step_controller = StepController()  # fresh permit count for this run

        self.stop_event.clear()
        self.pause_event.clear()
        self.manual_mode.set() if manual else self.manual_mode.clear()

        self.dining_semaphore = (
            threading.Semaphore(self.num_philosophers - 1) if strategy == "waiter" else None
        )
        self.deadlock_barrier = None

        self.philosophers = [Philosopher(i, self) for i in range(self.num_philosophers)]
        self.status = "running"
        self.events.log(
            EventType.SIMULATION_STARTED,
            f"Simulation started: N={self.num_philosophers}, strategy={strategy}, speed={self.speed}x",
        )
        for p in self.philosophers:
            p.start()
        self.detector = DeadlockDetector(self)
        self.detector.start()

    def pause(self) -> None:
        if self.status == "running":
            self.pause_event.set()
            self.status = "paused"
            self.events.log(EventType.SIMULATION_PAUSED, "Simulation paused")

    def resume(self) -> None:
        if self.status == "paused":
            self.pause_event.clear()
            self.status = "running"
            self.events.log(EventType.SIMULATION_RESUMED, "Simulation resumed")

    def step(self) -> None:
        if self.manual_mode.is_set():
            self.step_controller.advance()

    def set_manual_mode(self, enabled: bool) -> None:
        self.manual_mode.set() if enabled else self.manual_mode.clear()

    def set_speed(self, speed: float) -> None:
        self.speed = max(0.25, min(4.0, float(speed)))

    def trigger_deadlock(self) -> bool:
        """Only meaningful in naive mode: forces the textbook deadlock deterministically."""
        if self.strategy_name != "naive" or self.status != "running":
            return False
        self.deadlock_barrier = threading.Barrier(self.num_philosophers)
        self.events.log(
            EventType.STRATEGY_CHANGED,
            "Deadlock demo triggered: philosophers will rendezvous after taking their first fork",
        )
        return True

    def change_strategy(self, strategy: str) -> None:
        if strategy not in STRATEGY_REGISTRY:
            raise ValueError(f"Unknown strategy: {strategy}")
        was_active = self.status in ("running", "paused")
        if was_active:
            n, speed, manual = self.num_philosophers, self.speed, self.manual_mode.is_set()
            self.start(num_philosophers=n, strategy=strategy, speed=speed, manual=manual)
        else:
            self.strategy_name = strategy
            self.strategy = STRATEGY_REGISTRY[strategy]()

    def reset(self) -> None:
        if self.status != "idle" and self.philosophers:
            self._archive_run()

        self.stop_event.set()
        self.pause_event.clear()
        if self.deadlock_barrier is not None:
            try:
                self.deadlock_barrier.abort()
            except Exception:
                pass
        self.manual_mode.clear()  # release any thread stuck waiting at a step gate

        for p in self.philosophers:
            p.join(timeout=2.0)
        if self.detector is not None:
            self.detector.join(timeout=2.0)

        self.philosophers = []
        self.forks = []
        self.detector = None
        self.status = "idle"
        self.stop_event.clear()
        self.deadlock_barrier = None
        self.deadlock_info = {"detected": False, "cycle": [], "wait_for_graph": {}, "detected_at": None}

    def _archive_run(self) -> None:
        m = self.metrics.snapshot()
        util = m["fork_utilization"]
        self.run_history.append({
            "strategy": self.strategy_name,
            "num_philosophers": self.num_philosophers,
            "deadlock_observed": self.deadlock_info["detected"],
            "total_meals": m["total_meals"],
            "overall_avg_wait_time": m["overall_avg_wait_time"],
            "overall_max_wait_time": m["overall_max_wait_time"],
            "blocked_attempts": m["blocked_attempts"],
            "elapsed_time": m["elapsed_time"],
            "avg_fork_utilization": round(sum(util.values()) / len(util), 3) if util else 0.0,
        })
        if len(self.run_history) > 20:
            self.run_history.pop(0)

    # ------------------------------------------------------------ snapshots --
    def state_snapshot(self) -> dict:
        with self.state_lock:
            return {
                "status": self.status,
                "strategy": self.strategy_name,
                "strategy_explanation": self.strategy.explanation(),
                "num_philosophers": self.num_philosophers,
                "speed": self.speed,
                "manual_mode": self.manual_mode.is_set(),
                "philosophers": [p.snapshot() for p in self.philosophers],
                "forks": [f.snapshot() for f in self.forks],
                "deadlock": dict(self.deadlock_info),
                "event_count": self.events.count(),
            }

    def get_comparison(self) -> List[dict]:
        return list(self.run_history)
