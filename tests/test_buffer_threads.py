import sys
import threading

from drift_guard import DriftGuardBuffer


def test_concurrent_on_message_and_on_step_end_loses_nothing():
    guard = DriftGuardBuffer()
    n_producers = 4
    per_producer = 500
    total_sent = n_producers * per_producer
    received: list = []
    stop = threading.Event()

    def producer() -> None:
        for _ in range(per_producer):
            guard.on_message(1)

    def consumer() -> None:
        while not stop.is_set():
            received.extend(guard.on_step_end())
        received.extend(guard.on_step_end())

    old_interval = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        threads = [threading.Thread(target=producer) for _ in range(n_producers)]
        con = threading.Thread(target=consumer)
        con.start()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        stop.set()
        con.join()
        received.extend(guard.on_step_end())
    finally:
        sys.setswitchinterval(old_interval)

    assert len(received) == total_sent
    assert guard.pending_count() == 0
