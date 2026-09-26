import time

from simulation.models import PhilosopherState
from simulation.simulator import Simulator


def test_philosopher_states_are_always_valid_enum_values():
    sim = Simulator()
    sim.start(num_philosophers=3, strategy="ordered", speed=4.0)
    try:
        valid_states = {s.value for s in PhilosopherState}
        for _ in range(10):
            time.sleep(0.15)
            snap = sim.state_snapshot()
            for p in snap["philosophers"]:
                assert p["state"] in valid_states
                # A philosopher can only be WAITING while it names a fork
                # it's waiting for, and vice versa.
                if p["state"] == "WAITING":
                    assert p["waiting_for_fork"] is not None
                else:
                    assert p["waiting_for_fork"] is None
    finally:
        sim.reset()


def test_fork_ownership_is_consistent_and_never_double_booked():
    """
    A fork's `held_by` field is a single scalar written only under its own
    Lock, so two DIFFERENT philosophers can never claim the same fork --
    that's structurally guaranteed (see test_fork.py's stress test for the
    direct proof). What this test checks instead is that the two views of
    ownership -- Fork.held_by, and each Philosopher's own held_forks list
    -- always agree with each other, and that no philosopher ever holds
    more than the 2 forks its cycle requires.
    """
    sim = Simulator()
    sim.start(num_philosophers=5, strategy="naive", speed=4.0)
    try:
        for _ in range(15):
            time.sleep(0.15)
            snap = sim.state_snapshot()
            phil_by_id = {p["id"]: p for p in snap["philosophers"]}

            for f in snap["forks"]:
                if f["held_by"] is not None:
                    owner = phil_by_id[f["held_by"]]
                    assert f["id"] in owner["held_forks"], (
                        f"fork {f['id']} says it's held by P{f['held_by']}, "
                        f"but that philosopher's held_forks is {owner['held_forks']}"
                    )

            for p in snap["philosophers"]:
                assert len(p["held_forks"]) <= 2
                for fid in p["held_forks"]:
                    assert snap["forks"][fid]["held_by"] == p["id"]
    finally:
        sim.reset()


def test_philosophers_eventually_eat_under_a_safe_strategy():
    sim = Simulator()
    sim.start(num_philosophers=5, strategy="ordered", speed=4.0)
    try:
        time.sleep(3.0)
        m = sim.metrics.snapshot()
        for pid, count in m["meals_eaten"].items():
            assert count >= 1, f"philosopher {pid} never got to eat -- possible starvation"
    finally:
        sim.reset()
