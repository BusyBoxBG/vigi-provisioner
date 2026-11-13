import unittest

from vigi_provisioner.vigi_gateway_transport_lease import (
    GatewayTransportLeaseError,
    create_gateway_transport_lease,
)
from vigi_provisioner.vigi_initialization_execution_plan import InitializationExecutionPlan


class FakeTransport:
    def __init__(self, fail_close=False):
        self.closes = 0
        self.fail_close = fail_close

    def close(self):
        self.closes += 1
        if self.fail_close:
            raise OSError("simulated close failure")


class GatewayTransportLeaseTests(unittest.TestCase):
    def setUp(self):
        self.plan = InitializationExecutionPlan("02:00:00:00:00:01", "192.0.2.2", 443, "192.0.2.1")

    def test_claim_transfers_ownership(self):
        transport = FakeTransport()
        lease = create_gateway_transport_lease(self.plan, transport)
        self.assertIs(lease.execution_plan, self.plan)
        self.assertIs(lease.claim(self.plan), transport)
        with self.assertRaises(GatewayTransportLeaseError):
            lease.claim(self.plan)
        lease.close()
        self.assertEqual(transport.closes, 0)

    def test_rejected_claim_preserves_cleanup(self):
        transport = FakeTransport()
        lease = create_gateway_transport_lease(self.plan, transport)
        other = InitializationExecutionPlan("02:00:00:00:00:02", "192.0.2.2", 443, "192.0.2.1")
        with self.assertRaises(GatewayTransportLeaseError):
            lease.claim(other)
        lease.close()
        lease.close()
        self.assertEqual(transport.closes, 1)
        with self.assertRaises(GatewayTransportLeaseError):
            lease.claim(self.plan)

    def test_close_failure_leaves_lease_terminal(self):
        transport = FakeTransport(fail_close=True)
        lease = create_gateway_transport_lease(self.plan, transport)
        with self.assertRaises(OSError):
            lease.close()
        lease.close()
        self.assertEqual(transport.closes, 1)
        with self.assertRaises(GatewayTransportLeaseError):
            lease.claim(self.plan)
