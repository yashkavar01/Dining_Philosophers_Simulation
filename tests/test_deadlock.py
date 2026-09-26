import time

from simulation.simulator import Simulator


def test_naive_strategy_deadlocks_when_triggered():
    """
    The core demonstration of the whole project: the naive strategy, when
    deterministically triggered, produces a REAL deadlock -- five live
    threads, each genuinely holding one fork and genuinely blocked forever
    waiting for the next -- which the detector then finds as a length-5
    cycle in the wait-for graph.
    """
    sim = Simulator()
    sim.start(num_philosophers=5, strategy="naive", speed=4.0)
    try:
        time.sleep(0.3)
        assert sim.trigger_deadlock() is True

        deadlock_seen = False
        cycle = None
        for _ in range(60):  # poll for up to ~12s
            time.sleep(0.2)
            snap = sim.state_snapshot()
            if snap["deadlock"]["detected"]:
                deadlock_seen = True
                cycle = snap["deadlock"]["cycle"]
                break

        assert deadlock_seen, "expected the deterministic demo to produce a detected deadlock"
        assert len(cycle) == 5
        assert len(set(cycle)) == 5  # every philosopher appears exactly once

        # Every philosopher must be genuinely WAITING, each holding exactly
        # one fork -- the textbook picture, not a simulated label.
        snap = sim.state_snapshot()
        for p in snap["philosophers"]:
            assert p["state"] == "WAITING"
            assert len(p["held_forks"]) == 1
    finally:
        sim.reset()


def test_ordered_strategy_never_deadlocks_over_a_run():
    sim = Simulator()
    sim.start(num_philosophers=5, strategy="ordered", speed=4.0)
    try:
        for _ in range(20):  # ~4s
            time.sleep(0.2)
            snap = sim.state_snapshot()
            assert snap["deadlock"]["detected"] is False
        m = sim.metrics.snapshot()
        assert m["total_meals"] > 0, "philosophers must keep making real progress"
    finally:
        sim.reset()


def test_waiter_strategy_never_deadlocks_over_a_run():
    sim = Simulator()
    sim.start(num_philosophers=5, strategy="waiter", speed=4.0)
    try:
        for _ in range(20):
            time.sleep(0.2)
            snap = sim.state_snapshot()
            assert snap["deadlock"]["detected"] is False
        m = sim.metrics.snapshot()
        assert m["total_meals"] > 0
    finally:
        sim.reset()


def test_deadlock_trigger_is_rejected_outside_naive_mode():
    sim = Simulator()
    sim.start(num_philosophers=5, strategy="ordered", speed=4.0)
    try:
        assert sim.trigger_deadlock() is False
    finally:
        sim.reset()
