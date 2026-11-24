import sqlite3
import tempfile
import unittest
from contextlib import closing, ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from vigi_provisioner import vigi_factory_workflow as workflow
from vigi_provisioner.vigi_test_gui import initialize_inventory, Application

class C340SWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = str(Path(self.directory.name) / "inventory.sqlite3")
        initialize_inventory(self.database)
        self.device_id = "3B27D0E00114896A2"
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute("INSERT INTO camera_inventory (device_id,mac_address,model,hardware_version,label_serial,approved_ipv4,prefix_length,gateway_ipv4) VALUES (?,?,?,?,?,?,?,?)",
                       (self.device_id, "30689353CD67", "VIGI C340S", "1", "224a3q2000438", "192.168.0.160", 24, "192.168.0.1"))
        self.args = SimpleNamespace(inventory=self.database, device_id=self.device_id,
            config=str(Path(__file__).resolve().parents[1]/"provisioning.example.toml"),
            mac="30689353CD67", target_ip="192.168.0.160", prefix=24, gateway="192.168.0.1",
            pin=None, firmware_file=None, skip_firmware=True, activation_format="auto")

    def run_mock(self, firmware="2.0.3 Build 240412 Rel.42481n"):
        stack = self.enterContext(ExitStack())
        observation = dict(ip="192.168.0.60", mac="30-68-93-53-cd-67", model="VIGI C340S", factory_flag=0, serial="TP1"+self.device_id+"040")
        values = dict(discover=[observation], approve_observed_pin="00"*32,
            CameraHTTPS=Mock(), confirm_factory=None, detect_activation_format="legacy-2024",
            input="192.168.0.160", getpass="offline-test", login="/test", selected_interface={},
            pin_after_network_move="00"*32)
        for name, value in values.items(): stack.enter_context(patch.object(workflow, name, return_value=value))
        steps = {}
        for name in ("configure_device_alias", "configure_region", "configure_video", "configure_platform_access", "configure_osd", "configure_audio", "configure_motion_detection", "configure_login_error", "configure_network", "configure_dns"):
            steps[name] = stack.enter_context(patch.object(workflow, name))
        stack.enter_context(patch("vigi_provisioner.vigi_onvif.get_device_information", return_value=dict(Model="VIGI C340S", HardwareId="1.0", FirmwareVersion=firmware)))
        upgrade = stack.enter_context(patch("vigi_provisioner.vigi_firmware_upgrade.upgrade_after_activation"))
        return steps, upgrade

    def test_complete_preserved_c340s_dispatch(self):
        steps, upgrade = self.run_mock()
        workflow.provision(self.args)
        self.assertTrue(steps["configure_region"].call_args.kwargs["legacy_clock"])
        self.assertTrue(steps["configure_motion_detection"].call_args.kwargs["legacy"])
        plan = steps["configure_network"].call_args.args[0]
        self.assertEqual(plan["onvif_port"], 2020)
        self.assertEqual(plan["target_ip"], "192.168.0.160")
        steps["configure_dns"].assert_called_once()
        upgrade.assert_not_called()

    def test_unknown_c340s_firmware_stops_before_site_writes(self):
        steps, upgrade = self.run_mock("untested firmware")
        with self.assertRaises(workflow.ProvisioningError): workflow.provision(self.args)
        for step in steps.values(): step.assert_not_called()
        upgrade.assert_not_called()

    def test_cli_requires_skip_firmware_before_camera_access(self):
        self.args.skip_firmware = False
        with patch.object(workflow, "discover") as discover:
            with self.assertRaises(workflow.ProvisioningError): workflow.provision(self.args)
            discover.assert_not_called()

    def test_gui_preserve_allowed_but_approved_upgrade_blocked(self):
        app = Application(self.database, "profile.toml")
        with self.assertRaises(ValueError): app.start(self.device_id, firmware_mode="approved")
        with patch("vigi_provisioner.vigi_test_gui.subprocess.Popen") as launch, patch("vigi_provisioner.vigi_test_gui.threading.Thread"):
            app.start(self.device_id, firmware_mode="preserve")
            command = launch.call_args.args[0]
            self.assertIn("--skip-firmware", command)
            self.assertNotIn("--initialize-only", command)
