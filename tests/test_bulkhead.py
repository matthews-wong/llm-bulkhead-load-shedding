import threading
import time
import unittest

from llmbulkhead import Bulkhead, Rejected
from llmbulkhead.bulkhead import REASON_QUEUE_FULL, REASON_SHED, REASON_TIMEOUT


def in_thread(fn):
    out = {}

    def run():
        try:
            out["result"] = fn()
        except Rejected as exc:
            out["rejected"] = exc

    t = threading.Thread(target=run)
    t.start()
    return t, out


def wait_until(predicate, timeout_s=2.0):
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(0.005)
    return False


class BulkheadTest(unittest.TestCase):
    def test_rejects_invalid_limits(self):
        with self.assertRaisesRegex(ValueError, "max_concurrent=0"):
            Bulkhead(max_concurrent=0, max_queue=1, tenant_limit=1)

    def test_grants_immediately_under_limits(self):
        b = Bulkhead(2, 1, 2)
        b.acquire("a", 1, 0.1)
        b.acquire("a", 1, 0.1)

    def test_wait_times_out_with_reason(self):
        b = Bulkhead(1, 1, 1)
        b.acquire("a", 1, 0.1)
        with self.assertRaises(Rejected) as ctx:
            b.acquire("a", 1, 0.05)
        self.assertEqual(ctx.exception.reason, REASON_TIMEOUT)

    def test_queue_full_rejects_newcomer_of_equal_priority(self):
        b = Bulkhead(1, 1, 1)
        b.acquire("a", 1, 0.1)
        t, _ = in_thread(lambda: b.acquire("b", 1, 1.0))
        self.assertTrue(wait_until(lambda: len(b._waiters) == 1))
        with self.assertRaises(Rejected) as ctx:
            b.acquire("c", 1, 0.1)
        self.assertEqual(ctx.exception.reason, REASON_QUEUE_FULL)
        b.release("a")
        t.join()

    def test_higher_priority_sheds_queued_low_priority(self):
        b = Bulkhead(1, 1, 1)
        b.acquire("a", 1, 0.1)
        t, out = in_thread(lambda: b.acquire("batch", 5, 1.0))
        self.assertTrue(wait_until(lambda: len(b._waiters) == 1))
        t2, out2 = in_thread(lambda: b.acquire("ui", 0, 1.0))
        t.join(timeout=2)
        self.assertEqual(out["rejected"].reason, REASON_SHED)
        b.release("a")
        t2.join(timeout=2)
        self.assertNotIn("rejected", out2)

    def test_priority_order_when_slot_frees(self):
        b = Bulkhead(1, 5, 1)
        b.acquire("a", 1, 0.1)
        order = []
        lock = threading.Lock()

        def waiter(tenant, prio):
            b.acquire(tenant, prio, 2.0)
            with lock:
                order.append(tenant)
            b.release(tenant)

        threads = []
        for tenant, prio in [("low", 9), ("high", 0)]:
            t = threading.Thread(target=waiter, args=(tenant, prio))
            t.start()
            threads.append(t)
            self.assertTrue(wait_until(lambda: len(b._waiters) == len(threads)))
        b.release("a")
        for t in threads:
            t.join(timeout=2)
        self.assertEqual(order, ["high", "low"])

    def test_tenant_limit_does_not_block_other_tenants(self):
        b = Bulkhead(max_concurrent=3, max_queue=2, tenant_limit=1)
        b.acquire("noisy", 1, 0.1)
        t, out = in_thread(lambda: b.acquire("noisy", 1, 0.3))
        self.assertTrue(wait_until(lambda: len(b._waiters) == 1))
        b.acquire("quiet", 1, 0.1)  # free slot exists and quiet is under its limit
        t.join(timeout=2)
        self.assertEqual(out["rejected"].reason, REASON_TIMEOUT)

    def test_release_frees_tenant_slot(self):
        b = Bulkhead(2, 0, 1)
        b.acquire("a", 1, 0.1)
        b.release("a")
        b.acquire("a", 1, 0.1)


if __name__ == "__main__":
    unittest.main()
