import threading
import time

from simulation.fork import Fork


def test_mutual_exclusion_stress():
    """Many threads hammer one fork; at most one may hold it at any instant."""
    fork = Fork(0)
    current = [0]
    max_concurrent = [0]
    counter_lock = threading.Lock()

    def worker(pid):
        for _ in range(150):
            if fork.try_acquire(pid, timeout=1.0):
                with counter_lock:
                    current[0] += 1
                    max_concurrent[0] = max(max_concurrent[0], current[0])
                time.sleep(0.001)
                with counter_lock:
                    current[0] -= 1
                fork.release(pid)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert max_concurrent[0] == 1


def test_acquire_sets_and_release_clears_metadata():
    fork = Fork(3)
    assert fork.held_by is None
    assert fork.try_acquire(philosopher_id=7, timeout=1.0) is True
    assert fork.held_by == 7
    fork.release(7)
    assert fork.held_by is None


def test_second_acquire_blocks_until_release():
    fork = Fork(2)
    assert fork.try_acquire(philosopher_id=1, timeout=1.0)
    # A different philosopher must NOT be able to acquire it while held.
    assert fork.try_acquire(philosopher_id=2, timeout=0.1) is False
    fork.release(1)
    assert fork.try_acquire(philosopher_id=2, timeout=1.0) is True
    fork.release(2)


def test_release_by_non_owner_is_a_safe_noop():
    fork = Fork(1)
    fork.try_acquire(philosopher_id=2, timeout=1.0)
    fork.release(philosopher_id=99)  # not the current owner
    assert fork.held_by == 2
    fork.release(philosopher_id=2)
    assert fork.held_by is None
