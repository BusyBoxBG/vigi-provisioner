import unittest
from vigi_provisioner.vigi_discovery import decode_device_id

class DiscoveryDeviceIdTests(unittest.TestCase):
    def test_observed_wrappers(self):
        self.assertEqual(decode_device_id("TP13B27D0E00114896A2040"), "3B27D0E00114896A2")
        self.assertEqual(decode_device_id("TP15B7292F5C7DE00D62020"), "5B7292F5C7DE00D62")
        self.assertEqual(decode_device_id("tp13b27d0e00114896a2040"), "3B27D0E00114896A2")

    def test_unknown_or_malformed_wrappers(self):
        for value in (None, "", "TP13B27D0E00114896A2999", "TP13B27D0E00114896A20400", "TP13B27D0E00114896A2040junk"):
            self.assertIsNone(decode_device_id(value))
