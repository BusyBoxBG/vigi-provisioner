import unittest
from pathlib import Path
from vigi_provisioner.vigi_initialization_config import load_provisioning_profile, load_motion_profile

class MotionRecordProfileTests(unittest.TestCase):
    def test_example_disables_motion_recording_but_keeps_snapshots(self):
        profile = load_provisioning_profile(Path(__file__).resolve().parents[1]/"provisioning.example.toml")
        flags = profile.motion_detection["motion_notif_list"]
        self.assertEqual(flags["record_enabled"], "off")
        self.assertEqual(flags["capture_enabled"], "on")
