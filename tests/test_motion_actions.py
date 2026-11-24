import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from vigi_provisioner.vigi_motion_actions import disable_actions, update_profile
from vigi_provisioner.vigi_initialization_config import load_provisioning_profile

class MotionActionsTests(unittest.TestCase):
    def test_only_notification_actions_are_written(self):
        state={"motion_det":{"enabled":"on","digital_sensitivity":85},"arming_schedule":{"monday":"all-day"},"motion_notif_list":{"record_enabled":"on","capture_enabled":"on","target_track_enabled":"on","msg_push_enabled":"off"}}
        initial=copy.deepcopy(state)
        writes=[]
        def post(stage,payload,**kwargs):
            if payload["method"]=="set":
                writes.append(copy.deepcopy(payload))
                state["motion_notif_list"].update(payload["motion_detection"]["motion_notif_list"])
            return 200,{"motion_detection":copy.deepcopy(state)}
        disable_actions(Mock(post=post),"/test")
        self.assertEqual(list(writes[0]["motion_detection"]),["motion_notif_list"])
        self.assertEqual(state["motion_det"],initial["motion_det"])
        self.assertEqual(state["arming_schedule"],initial["arming_schedule"])
        self.assertTrue(all(v=="off" for v in state["motion_notif_list"].values()))

    def test_profile_update_preserves_detector_and_other_sections(self):
        source=Path(__file__).resolve().parents[1]/"provisioning.example.toml"
        before=load_provisioning_profile(source)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"provisioning.toml"
            path.write_text(source.read_text().replace("record = false","record = true").replace("snapshots = false","snapshots = true"))
            update_profile(path)
            after=load_provisioning_profile(path)
            self.assertEqual(after.motion_detection["motion_det"],before.motion_detection["motion_det"])
            self.assertEqual(after.motion_detection["arming_schedule"],before.motion_detection["arming_schedule"])
            self.assertEqual(after.clock,before.clock)
            self.assertTrue(all(v=="off" for v in after.motion_detection["motion_notif_list"].values()))
