"""
DeadlockDetector runs as its own background thread and periodically builds
a wait-for graph from the CURRENT live state: an edge Pi -> Pj exists
whenever philosopher Pi is WAITING for a fork that philosopher Pj
currently holds. Because each philosopher waits for at most one fork at a
time, this graph has out-degree <= 1 per node, so it is really just a set
of pointer chains -- finding a cycle is a simple walk, no general graph
library needed.

A cycle must persist for CONFIRM_THRESHOLD seconds before being reported,
so a fork that is about to be released a moment later is not mistaken for
a real deadlock. This is a real (if simple) instance of the classic
resource-allocation-graph deadlock detection algorithm, not a scripted
demo -- it runs identically regardless of which strategy is active, which
is precisely how the ordered/waiter strategies get to PROVE (by producing
zero detections over a run) rather than just claim to be deadlock-free.
"""
from __future__ import annotations

import threading
import time
from typing import Dict, List, Optional

from .models import EventType, PhilosopherState

CHECK_INTERVAL = 0.15
CONFIRM_THRESHOLD = 1.5  # seconds a cycle must persist before being reported


class DeadlockDetector(threading.Thread):
    def __init__(self, simulator):
        super().__init__(daemon=True, name="DeadlockDetector")
        self.simulator = simulator
        self._cycle_since: Optional[float] = None
        self._last_cycle: Optional[List[int]] = None

    def _build_wait_for_graph(self) -> Dict[int, int]:
        sim = self.simulator
        graph: Dict[int, int] = {}
        with sim.state_lock:
            for p in sim.philosophers:
                if p.state == PhilosopherState.WAITING and p.waiting_for_fork is not None:
                    holder = sim.forks[p.waiting_for_fork].held_by
                    if holder is not None:
                        graph[p.id] = holder
        return graph

    @staticmethod
    def _find_cycle(graph: Dict[int, int]) -> Optional[List[int]]:
        for start in graph:
            visited: List[int] = []
            seen = set()
            node = start
            while node in graph:
                if node in seen:
                    idx = visited.index(node)
                    return visited[idx:]
                seen.add(node)
                visited.append(node)
                node = graph[node]
        return None

    def run(self) -> None:
        sim = self.simulator
        while not sim.stop_event.is_set():
            time.sleep(CHECK_INTERVAL)
            if sim.stop_event.is_set():
                break
            if sim.pause_event.is_set():
                continue

            graph = self._build_wait_for_graph()
            cycle = self._find_cycle(graph)

            if cycle:
                if self._last_cycle == cycle:
                    if self._cycle_since is not None and (time.monotonic() - self._cycle_since) >= CONFIRM_THRESHOLD:
                        if not sim.deadlock_info["detected"]:
                            self._report(cycle, graph)
                else:
                    self._last_cycle = cycle
                    self._cycle_since = time.monotonic()
            else:
                self._last_cycle = None
                self._cycle_since = None
                if sim.deadlock_info["detected"]:
                    with sim.state_lock:
                        sim.deadlock_info["detected"] = False
                    sim.events.log(EventType.DEADLOCK_CLEARED, "Deadlock condition cleared")

    def _report(self, cycle: List[int], graph: Dict[int, int]) -> None:
        sim = self.simulator
        with sim.state_lock:
            sim.deadlock_info.update({
                "detected": True,
                "cycle": cycle,
                "wait_for_graph": dict(graph),
                "detected_at": sim.events.elapsed(),
            })
        sim.metrics.record_deadlock()
        cycle_str = " -> ".join(f"P{c}" for c in cycle) + f" -> P{cycle[0]}"
        sim.events.log(
            EventType.DEADLOCK_DETECTED,
            f"DEADLOCK DETECTED: circular wait {cycle_str}",
            data={"cycle": cycle, "wait_for_graph": graph},
        )
