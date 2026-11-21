"""Noisy-neighbour simulation: one tenant bursts, another sends a few interactive calls.

Synthetic: a fake provider with a fixed delay. Timing makes counts vary slightly
between runs; the gap between the two configurations does not.
"""

import threading
import time

from llmbulkhead import Bulkhead, FakeProvider, Gateway, Rejected, Request

DELAY_S = 0.05
WAIT_TIMEOUT_S = 0.3
NOISY_REQUESTS = 60
QUIET_REQUESTS = 10
QUIET_GAP_S = 0.03
MAX_CONCURRENT = 4
MAX_QUEUE = 8
BATCH_PRIORITY = 5
INTERACTIVE_PRIORITY = 0
TENANT_LIMIT = 3


def run(tenant_limit: int, quiet_priority: int) -> tuple[int, int, float]:
    gateway = Gateway(
        FakeProvider(DELAY_S),
        Bulkhead(MAX_CONCURRENT, MAX_QUEUE, tenant_limit),
        WAIT_TIMEOUT_S,
    )
    quiet_ok = [0]
    noisy_ok = [0]
    lock = threading.Lock()

    def call(tenant, priority, counter):
        try:
            gateway.complete(Request("ping", tenant=tenant, priority=priority))
        except Rejected:
            return
        with lock:
            counter[0] += 1

    started = time.monotonic()
    threads = [
        threading.Thread(target=call, args=("batch", BATCH_PRIORITY, noisy_ok))
        for _ in range(NOISY_REQUESTS)
    ]
    for t in threads:
        t.start()
    for _ in range(QUIET_REQUESTS):
        t = threading.Thread(target=call, args=("ui", quiet_priority, quiet_ok))
        t.start()
        threads.append(t)
        time.sleep(QUIET_GAP_S)
    for t in threads:
        t.join()
    return quiet_ok[0], noisy_ok[0], time.monotonic() - started


if __name__ == "__main__":
    print(
        f"synthetic: {NOISY_REQUESTS} batch + {QUIET_REQUESTS} interactive requests, "
        f"{MAX_CONCURRENT} slots, queue {MAX_QUEUE}, {DELAY_S * 1000:.0f} ms provider"
    )
    configs = (
        ("same priority", MAX_CONCURRENT, BATCH_PRIORITY),
        (f"tenant limit {TENANT_LIMIT}", TENANT_LIMIT, BATCH_PRIORITY),
        ("ui priority", MAX_CONCURRENT, INTERACTIVE_PRIORITY),
    )
    for label, limit, priority in configs:
        quiet, noisy, elapsed = run(limit, priority)
        print(
            f"{label:16} interactive ok {quiet}/{QUIET_REQUESTS}  "
            f"batch ok {noisy}/{NOISY_REQUESTS}  {elapsed:.2f}s"
        )
