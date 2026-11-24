import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from vigi_provisioner import vigi_factory_workflow as workflow
from vigi_provisioner.vigi_test_gui import initialize_inventory, Application

class InitializeOnlyTests(unittest.TestCase):
    def test_c340s_activation_never_enters_firmware_or_site_stages(self):
        with tempfile.TemporaryDirectory() as directory:
            database = str(Path(directory) / "inventory.sqlite3")
            initialize_inventory(database)
            device_id = "3B27D0E00114896A2"
            with closing(sqlite3.connect(database)) as db, db:
                db.execute("INSERT INTO camera_inventory (device_id,mac_address,model,approved_ipv4,prefix_length,gateway_ipv4,hardware_version) VALUES (?,?,?,?,?,?,?)",
                           (device_id, "30689353CD67", "VIGI C340S", "192.168.0.154", 24, "192.168.0.1", "1"))
            camera = Mock()
            camera.post.return_value = (200, {"device_info": {"info": {"sw_version": "old", "hw_version": "1.0", "device_model": "VIGI%20C340S"}}})
            observation = dict(ip="192.168.0.60", mac="30-68-93-53-cd-67", model="VIGI C340S", factory_flag=0, serial="TP1"+device_id+"040")
            args = SimpleNamespace(inventory=database, device_id=device_id, pin=None, config=str(Path(__file__).resolve().parents[1]/"provisioning.example.toml"))
            with patch.object(workflow, "discover", return_value=[observation]), patch.object(workflow, "CameraHTTPS", return_value=camera), patch.object(workflow, "approve_observed_pin", return_value="pin"), patch.object(workflow, "confirm_factory"), patch.object(workflow, "detect_activation_format", return_value="legacy-2.0.4"), patch.object(workflow, "getpass", return_value="offline-test"), patch.object(workflow, "input", return_value="INITIALIZE "+device_id), patch.object(workflow, "login", return_value="/session"), patch.object(workflow, "configure_region") as region, patch.object(workflow, "configure_network") as network, patch("vigi_provisioner.vigi_firmware_upgrade.upgrade_after_activation") as upgrade:
                result = workflow.initialize_only(args)
                self.assertTrue(result["initialization_only"])
                self.assertEqual([c.args[0] for c in camera.post.call_args_list], ["Factory activation", "Read initialized device metadata"])
                region.assert_not_called()
                network.assert_not_called()
                upgrade.assert_not_called()
            app = Application(database, args.config)
            with patch("vigi_provisioner.vigi_test_gui.subprocess.Popen") as launch, patch("vigi_provisioner.vigi_test_gui.threading.Thread"):
                app.start(device_id, firmware_mode="initialize")
                command = launch.call_args.args[0]
                self.assertIn("--initialize-only", command)
                self.assertIn("--skip-firmware", command)
                self.assertNotIn("--firmware-file", command)

    def test_main_rejects_firmware_override_in_initialize_only_mode(self):
        with patch("sys.argv", ["workflow", "--initialize-only", "--firmware-file", "image.bin"]), patch.object(workflow, "initialize_only") as initialize:
            with self.assertRaises(SystemExit): workflow.main()
            initialize.assert_not_called()

    def test_gui_discovery_observer_accepts_c340s_inventory(self):
        from vigi_provisioner.vigi_test_gui import worker
        with tempfile.TemporaryDirectory() as directory:
            database = str(Path(directory) / "inventory.sqlite3")
            initialize_inventory(database)
            device_id = "3B27D0E00114896A2"
            with closing(sqlite3.connect(database)) as db, db:
                db.execute("INSERT INTO camera_inventory (device_id,mac_address,model,approved_ipv4,prefix_length,gateway_ipv4) VALUES (?,?,?,?,?,?)",
                           (device_id, "30689353CD67", "VIGI C340S", "192.168.0.154", 24, "192.168.0.1"))
            observation = dict(ip="192.168.0.60", mac="30-68-93-53-cd-67", model="VIGI C340S")
            args = SimpleNamespace(inventory=database, config="profile.toml", device_id=device_id, initialize_only=True, skip_firmware=True, firmware_file=None)
            def main():
                import sys
                self.assertIn("--initialize-only", sys.argv)
                self.assertEqual(workflow.discover(), [observation])
            # Worker installs wrappers; restore the module dictionary after this test.
            with patch.dict(workflow.__dict__, {}), patch.object(workflow, "discover", return_value=[observation]), patch.object(workflow, "main", side_effect=main), patch("sys.argv", ["gui-worker"]):
                worker(args)
