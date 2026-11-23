import copy
import unittest
from unittest.mock import Mock, patch

from vigi_provisioner.vigi_factory_workflow import configure_region, ProvisioningError
from vigi_provisioner.vigi_initialization_config import ClockProfile, VigiInitializationConfig


class LegacyClockTests(unittest.TestCase):
    def setUp(self):
        self.config = VigiInitializationConfig(clock=ClockProfile(
            ntp={"server": "84.54.128.102", "port": 123, "interval": 60},
            dst_manual={"enabled": "on", "start_hour": "3", "end_hour": "4"},
        ))
        self.system = {
            "basic": {"timing_mode": "ntp"},
            "dst_manual": dict(self.config.clock.dst_manual),
            "ntp": dict(self.config.clock.ntp),
        }
        self.camera = Mock()

    def read(self, system):
        return ((self.config.time_zone, self.config.zone_id, "50hz"), "English", None, system)

    def test_legacy_omits_unsupported_fields_from_write(self):
        initial = copy.deepcopy(self.system)
        initial["dst_manual"]["enabled"] = "off"
        with patch("vigi_provisioner.vigi_factory_workflow.read_regional_settings",
                   side_effect=[self.read(initial), self.read(self.system)]):
            configure_region(self.camera, "/test", self.config, legacy_clock=True)
        basic = self.camera.post.call_args_list[0].args[1]["system"]["basic"]
        self.assertNotIn("date_format", basic)
        self.assertNotIn("time_format", basic)

    def test_modern_missing_fields_still_fails(self):
        with patch("vigi_provisioner.vigi_factory_workflow.read_regional_settings",
                   return_value=self.read(self.system)):
            with self.assertRaises(ProvisioningError):
                configure_region(self.camera, "/test", self.config)

    def test_legacy_partial_absence_still_fails(self):
        self.system["basic"]["time_format"] = 0
        with patch("vigi_provisioner.vigi_factory_workflow.read_regional_settings",
                   return_value=self.read(self.system)):
            with self.assertRaises(ProvisioningError):
                configure_region(self.camera, "/test", self.config, legacy_clock=True)

    def test_legacy_ntp_mismatch_still_fails(self):
        self.system["ntp"]["server"] = "0.0.0.0"
        with patch("vigi_provisioner.vigi_factory_workflow.read_regional_settings",
                   return_value=self.read(self.system)):
            with self.assertRaises(ProvisioningError):
                configure_region(self.camera, "/test", self.config, legacy_clock=True)
