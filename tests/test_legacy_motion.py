import copy
import unittest
from pathlib import Path
from unittest.mock import Mock

from vigi_provisioner.vigi_factory_workflow import configure_motion_detection, ProvisioningError
from vigi_provisioner.vigi_initialization_config import load_provisioning_profile


class LegacyMotionTests(unittest.TestCase):
    def setUp(self):
        self.target = load_provisioning_profile(
            Path(__file__).resolve().parents[1] / "provisioning.example.toml"
        ).motion_detection
        self.motion = copy.deepcopy(self.target)
        self.motion["motion_det"].pop("obj_filter_enabled")
        self.motion["motion_notif_list"].pop("report_server_enabled")
        self.motion["motion_notif_list"]["capture_enabled"] = "off"
        self.motion["motion_notif_list"]["record_enabled"] = "on"
        self.motion["polygon_region_info"] = [{"polygon_region_info_1": {
            "points_num": 4, "points_x": [0, 10000, 10000, 0],
            "points_y": [0, 0, 10000, 10000],
        }}]
        self.requests = []

    def post(self, stage, payload, **kwargs):
        self.requests.append(copy.deepcopy(payload))
        query = payload["motion_detection"]
        if payload["method"] == "set":
            for section, fields in query.items():
                self.motion[section].update(fields)
        if query.get("name") == "arming_schedule":
            return 200, {"motion_detection": {"arming_schedule": self.motion["arming_schedule"]}}
        return 200, {"motion_detection": copy.deepcopy(self.motion)}

    def test_legacy_disables_processing_and_uses_older_table(self):
        original = copy.deepcopy(self.target)
        configure_motion_detection(Mock(post=self.post), "/test", self.target, legacy=True)
        self.assertEqual(self.target, original)
        self.assertEqual(self.motion["motion_notif_list"]["capture_enabled"], "off")
        self.assertEqual(self.motion["motion_notif_list"]["record_enabled"], "off")
        write = next(p for p in self.requests if p["method"] == "set")["motion_detection"]
        self.assertNotIn("obj_filter_enabled", write["motion_det"])
        self.assertNotIn("report_server_enabled", write["motion_notif_list"])
        self.assertEqual(self.requests[0]["motion_detection"]["table"], ["polygon_region_info"])
        self.assertNotIn("version", self.requests[0]["motion_detection"])
        self.assertTrue(all(p["method"] != "do" for p in self.requests))

    def test_changed_region_stops_before_write(self):
        self.motion["polygon_region_info"][0]["polygon_region_info_1"]["points_num"] = 3
        with self.assertRaises(ProvisioningError):
            configure_motion_detection(Mock(post=self.post), "/test", self.target, legacy=True)
        self.assertTrue(all(p["method"] == "get" for p in self.requests))

    def test_all_off_also_disables_additional_exposed_action_flags(self):
        self.motion["motion_notif_list"].update(client_enabled="on",app_enabled="on",target_track_enabled="on")
        configure_motion_detection(Mock(post=self.post), "/test", self.target, legacy=True)
        self.assertTrue(all(v=="off" for v in self.motion["motion_notif_list"].values()))

    def test_unknown_active_action_stops_before_writes(self):
        self.motion["motion_notif_list"]["unknown_enabled"] = "on"
        with self.assertRaises(ProvisioningError):
            configure_motion_detection(Mock(post=self.post), "/test", self.target, legacy=True)
        self.assertTrue(all(p["method"]=="get" for p in self.requests))
