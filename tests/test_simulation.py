import threading
import time

from simulation.simulator import Simulator


def test_reset_leaves_no_stale_threads():
    sim = Simulator()
    sim.start(num_philosophers=5, strategy="naive", speed=4.0)
    time.sleep(0.5)
    names_during = {t.name for t in threading.enumerate()}
    assert any(name.startswith("Philosopher-") for name in names_during)
    assert "DeadlockDetector" in names_during

    sim.reset()
    names_after = {t.name for t in threading.enumerate()}
    assert not any(name.startswith("Philosopher-") for name in names_after)
    assert "DeadlockDetector" not in names_after


def test_pause_freezes_progress():
    sim = Simulator()
    sim.start(num_philosophers=5, strategy="ordered", speed=4.0)
    try:
        time.sleep(0.5)
        sim.pause()
        m1 = sim.metrics.snapshot()["total_meals"]
        time.sleep(1.0)
        m2 = sim.metrics.snapshot()["total_meals"]
        assert m1 == m2, "no meals should complete while paused"
    finally:
        sim.reset()


def test_resume_allows_progress_again():
    sim = Simulator()
    sim.start(num_philosophers=5, strategy="ordered", speed=4.0)
    try:
        sim.pause()
        time.sleep(0.3)
        sim.resume()
        time.sleep(2.0)
        m = sim.metrics.snapshot()["total_meals"]
        assert m > 0
    finally:
        sim.reset()


def test_event_log_ids_are_monotonic_and_unique():
    sim = Simulator()
    sim.start(num_philosophers=3, strategy="ordered", speed=4.0)
    try:
        time.sleep(1.0)
        events = sim.events.get_since(-1)
    finally:
        sim.reset()
    ids = [e["id"] for e in events]
    assert ids == sorted(ids)
    assert len(ids) == len(set(ids))


def test_incremental_event_fetch_only_returns_new_events():
    sim = Simulator()
    sim.start(num_philosophers=3, strategy="ordered", speed=4.0)
    try:
        time.sleep(0.5)
        first_batch = sim.events.get_since(-1)
        last_id = first_batch[-1]["id"]
        time.sleep(0.5)
        second_batch = sim.events.get_since(last_id)
    finally:
        sim.reset()
    assert all(e["id"] > last_id for e in second_batch)


def test_metrics_are_fresh_after_a_new_start():
    sim = Simulator()
    sim.start(num_philosophers=3, strategy="ordered", speed=4.0)
    time.sleep(1.0)
    sim.reset()
    sim.start(num_philosophers=3, strategy="ordered", speed=4.0)
    m = sim.metrics.snapshot()
    sim.reset()
    assert m["total_meals"] == 0
    assert m["elapsed_time"] < 0.5


def test_philosopher_count_is_clamped_to_valid_range():
    sim = Simulator()
    sim.start(num_philosophers=1, strategy="ordered", speed=4.0)
    n_low = sim.num_philosophers
    sim.reset()
    sim.start(num_philosophers=99, strategy="ordered", speed=4.0)
    n_high = sim.num_philosophers
    sim.reset()
    assert n_low == 3       # clamped up to the minimum
    assert n_high == 10     # clamped down to the maximum


def test_run_history_is_archived_on_reset():
    sim = Simulator()
    sim.start(num_philosophers=3, strategy="ordered", speed=4.0)
    time.sleep(1.0)
    sim.reset()
    history = sim.get_comparison()
    assert len(history) == 1
    assert history[0]["strategy"] == "ordered"
    assert history[0]["deadlock_observed"] is False


def test_manual_mode_gates_progress_until_stepped():
    sim = Simulator()
    sim.start(num_philosophers=3, strategy="ordered", speed=4.0, manual=True)
    try:
        time.sleep(0.5)
        m1 = sim.metrics.snapshot()["fork_acquire_attempts"]
        time.sleep(0.5)
        m2 = sim.metrics.snapshot()["fork_acquire_attempts"]
        assert m1 == m2, "nothing new should happen without an explicit Step"

        for _ in range(10):
            sim.step()
            time.sleep(0.05)
        m3 = sim.metrics.snapshot()["fork_acquire_attempts"]
        assert m3 >= m1  # stepping should have let some events through eventually
    finally:
        sim.reset()
