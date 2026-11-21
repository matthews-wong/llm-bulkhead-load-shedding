import unittest

from llmbulkhead import Bulkhead, FakeProvider, Gateway, Rejected, Request


class ExplodingProvider:
    def complete(self, request):
        raise RuntimeError("upstream 500")


class GatewayTest(unittest.TestCase):
    def test_returns_provider_response(self):
        gw = Gateway(FakeProvider(), Bulkhead(1, 0, 1))
        self.assertEqual(gw.complete(Request("hi")).text, "echo: hi")

    def test_slot_is_released_when_provider_raises(self):
        bulkhead = Bulkhead(1, 0, 1)
        gw = Gateway(ExplodingProvider(), bulkhead, wait_timeout_s=0.05)
        for _ in range(3):  # a leaked slot would turn the 2nd call into Rejected
            with self.assertRaises(RuntimeError):
                gw.complete(Request("x"))

    def test_saturated_gateway_rejects_with_tenant_in_message(self):
        bulkhead = Bulkhead(1, 0, 1)
        bulkhead.acquire("held", 1, 0.1)
        gw = Gateway(FakeProvider(), bulkhead, wait_timeout_s=0.05)
        with self.assertRaisesRegex(Rejected, "tenant 'acme'"):
            gw.complete(Request("x", tenant="acme"))


if __name__ == "__main__":
    unittest.main()
