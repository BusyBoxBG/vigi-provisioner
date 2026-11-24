import sqlite3
import tempfile
import unittest
from contextlib import closing, ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from vigi_provisioner import vigi_factory_workflow as workflow
from vigi_provisioner.vigi_test_gui import Application, initialize_inventory

class C540SWorkflowTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.database = str(Path(directory)/"inventory.sqlite3")
        initialize_inventory(self.database)
        self.device_id = "CB7516E6763362E22"
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute("INSERT INTO camera_inventory (device_id,mac_address,model,hardware_version,label_serial,approved_ipv4,prefix_length,gateway_ipv4) VALUES (?,?,?,?,?,?,?,?)",
                (self.device_id,"C03A5555BA40","VIGI C540S","1","2264481000089","192.168.0.170",24,"192.168.0.1"))
        self.args = SimpleNamespace(inventory=self.database,device_id=self.device_id,
            config=str(Path(__file__).resolve().parents[1]/"provisioning.example.toml"),
            mac="C03A5555BA40",target_ip="192.168.0.170",prefix=24,gateway="192.168.0.1",
            pin=None,firmware_file=None,skip_firmware=True,activation_format="auto")

    def test_gui_preserve_and_upgrade_rejection(self):
        for mode in ("approved","profile",None):
            app=Application(self.database,self.args.config)
            with patch("vigi_provisioner.vigi_test_gui.subprocess.Popen") as launch:
                with self.assertRaises(ValueError): app.start(self.device_id,firmware_mode=mode)
                launch.assert_not_called()
        app=Application(self.database,self.args.config)
        with patch("vigi_provisioner.vigi_test_gui.subprocess.Popen") as launch, patch("vigi_provisioner.vigi_test_gui.threading.Thread"):
            app.start(self.device_id,firmware_mode="preserve")
            self.assertIn("--skip-firmware",launch.call_args.args[0])

    def test_cli_upgrade_stops_before_discovery(self):
        self.args.skip_firmware=False
        with patch.object(workflow,"discover") as discovery:
            with self.assertRaises(workflow.ProvisioningError): workflow.provision(self.args)
            discovery.assert_not_called()

    def test_preserve_dispatch_and_unknown_firmware_stop(self):
        for firmware in ("3.2.0 Build 251111 Rel.66535n","untested"):
            with self.subTest(firmware=firmware), ExitStack() as stack:
                values=dict(discover=[dict(ip="192.168.0.60",mac="c0-3a-55-55-ba-40",model="VIGI C540S",factory_flag=0,serial="TP1"+self.device_id+"040")],
                    approve_observed_pin="00"*32,CameraHTTPS=Mock(),confirm_factory=None,detect_activation_format="modern",
                    input="192.168.0.170",getpass="offline-test",login="/test",selected_interface={},pin_after_network_move="00"*32,
                    get_device_information=dict(Model="VIGI C540S",HardwareId="1.0",FirmwareVersion=firmware))
                for name,value in values.items(): stack.enter_context(patch.object(workflow,name,return_value=value))
                steps={name:stack.enter_context(patch.object(workflow,name)) for name in (
                    "configure_device_alias","configure_region","configure_video","configure_platform_access","configure_osd","configure_audio",
                    "configure_motion_detection","configure_login_error","configure_network","configure_dns")}
                upload=stack.enter_context(patch("vigi_provisioner.vigi_firmware_upgrade.upgrade_after_activation"))
                if firmware=="untested":
                    with self.assertRaises(workflow.ProvisioningError): workflow.provision(self.args)
                    for step in steps.values(): step.assert_not_called()
                else:
                    workflow.provision(self.args)
                    self.assertFalse(steps["configure_region"].call_args.kwargs["legacy_clock"])
                    self.assertFalse(steps["configure_motion_detection"].call_args.kwargs["legacy"])
                    self.assertEqual(steps["configure_network"].call_args.args[0]["onvif_port"],80)
                    steps["configure_dns"].assert_called_once()
                upload.assert_not_called()
