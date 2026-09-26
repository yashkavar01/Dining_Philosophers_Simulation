from simulation.metrics import MetricsCollector


def test_avg_and_max_wait_computation():
    m = MetricsCollector(num_philosophers=2)
    m.record_wait(0, 1.0)
    m.record_wait(0, 3.0)
    m.record_wait(1, 2.0)
    snap = m.snapshot()
    assert snap["avg_wait_time_per_philosopher"][0] == 2.0
    assert snap["max_wait_time"][0] == 3.0
    assert snap["max_wait_time"][1] == 2.0
    assert snap["overall_max_wait_time"] == 3.0


def test_meal_and_blocked_counters():
    m = MetricsCollector(num_philosophers=2)
    m.record_meal(0)
    m.record_meal(0)
    m.record_meal(1)
    m.record_blocked()
    m.record_blocked()
    snap = m.snapshot()
    assert snap["meals_eaten"] == {0: 2, 1: 1}
    assert snap["total_meals"] == 3
    assert snap["blocked_attempts"] == 2


def test_metrics_with_no_activity_are_all_zero_not_fabricated():
    m = MetricsCollector(num_philosophers=3)
    snap = m.snapshot()
    assert snap["total_meals"] == 0
    assert snap["overall_avg_wait_time"] == 0.0
    assert snap["overall_max_wait_time"] == 0.0
    assert snap["blocked_attempts"] == 0
