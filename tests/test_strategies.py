from simulation.strategies import NaiveStrategy, OrderedStrategy, WaiterStrategy


def test_naive_strategy_has_no_global_ordering():
    """
    Philosopher N-1's fork ids are (N-1, 0) -- its LEFT fork has a HIGHER id
    than its RIGHT fork, unlike every other philosopher. This asymmetry
    around the table is exactly what makes a circular wait possible.
    """
    s = NaiveStrategy()
    n = 5
    first, second = s.fork_order(n - 1, n)
    assert (first, second) == (n - 1, 0)
    # Meanwhile every other philosopher's left id is lower than their right id.
    for pid in range(n - 1):
        f, sec = s.fork_order(pid, n)
        assert f < sec


def test_ordered_strategy_always_picks_lower_id_first():
    s = OrderedStrategy()
    n = 5
    for pid in range(n):
        first, second = s.fork_order(pid, n)
        assert first < second
        assert {first, second} == {pid, (pid + 1) % n}


def test_ordered_strategy_breaks_the_naive_asymmetry():
    naive = NaiveStrategy()
    ordered = OrderedStrategy()
    n = 5
    # Under naive, P(N-1) requests its higher-numbered fork first (F4).
    assert naive.fork_order(n - 1, n)[0] == n - 1
    # Under ordered, P(N-1) is forced to request the lower-numbered fork
    # first instead (F0) -- this is the whole fix.
    assert ordered.fork_order(n - 1, n)[0] == 0


def test_waiter_strategy_exposes_synchronization_hooks():
    s = WaiterStrategy()
    assert callable(s.pre_acquire_hook)
    assert callable(s.post_release_hook)


def test_all_strategies_provide_a_non_empty_explanation():
    for cls in (NaiveStrategy, OrderedStrategy, WaiterStrategy):
        text = cls().explanation()
        assert isinstance(text, str) and len(text) > 20
