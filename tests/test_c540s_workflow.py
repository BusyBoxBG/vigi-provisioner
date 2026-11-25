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
        for mode in ("profile",None):
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
                stack.enter_context(patch("vigi_provisioner.vigi_c540s_upgrade.read_identity",return_value=(values["get_device_information"],80)))
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

    def test_gui_approved_image_is_c540s_checked(self):
        app=Application(self.database,self.args.config)
        app.catalog_path="catalog.toml"
        app.firmware_dir="firmware"
        with closing(sqlite3.connect(self.database)) as db,db:
            db.execute("UPDATE camera_inventory SET catalog_id=? WHERE device_id=?",("c540s-v1",self.device_id))
        model=dict(id="c540s-v1",model="VIGI C540S",hardware_version="1",region="UN")
        with patch("vigi_provisioner.vigi_test_gui.load_catalog",return_value=[model]), patch("vigi_provisioner.vigi_test_gui.approved_image",return_value=Path("approved.bin")), patch("vigi_provisioner.vigi_c540s_upgrade.inspect_latest_image") as inspect, patch("vigi_provisioner.vigi_c540s_upgrade.inspect_package"), patch("vigi_provisioner.vigi_test_gui.subprocess.Popen") as launch, patch("vigi_provisioner.vigi_test_gui.threading.Thread"):
            app.start(self.device_id,firmware_mode="approved")
            inspect.assert_called_once()
            self.assertNotIn("--skip-firmware",launch.call_args.args[0])
            self.assertIn("--firmware-file",launch.call_args.args[0])

    def test_failed_upgrade_stops_site_configuration(self):
        from vigi_provisioner import vigi_c540s_upgrade as upgrade
        self.args.skip_firmware=False
        self.args.firmware_file="approved.bin"
        observation=dict(ip="192.168.0.60",mac="c0-3a-55-55-ba-40",model="VIGI C540S",factory_flag=0,serial="TP1"+self.device_id+"040")
        with ExitStack() as stack:
            for name,value in dict(discover=[observation],approve_observed_pin="00"*32,CameraHTTPS=Mock(),confirm_factory=None,detect_activation_format="modern",input="192.168.0.170",getpass="offline-test",login="/test").items():
                stack.enter_context(patch.object(workflow,name,return_value=value))
            stack.enter_context(patch.object(upgrade,"inspect_latest_image",return_value=b"image"))
            stack.enter_context(patch.object(upgrade,"read_identity",return_value=({"FirmwareVersion":upgrade.SOURCE},80)))
            upload=stack.enter_context(patch.object(upgrade,"upgrade_stage",side_effect=workflow.ProvisioningError("Upgrade unverified")))
            site=stack.enter_context(patch.object(workflow,"configure_device_alias"))
            network=stack.enter_context(patch.object(workflow,"configure_network"))
            with self.assertRaises(workflow.ProvisioningError):workflow.provision(self.args)
            upload.assert_called_once()
            site.assert_not_called()
            network.assert_not_called()

    def test_bridge_chain_and_direct_routes(self):
        from vigi_provisioner import vigi_c540s_upgrade as upgrade
        cases = (("2.0.4 Build 240913 Rel.123n",["bridge","latest"]),
                 ("2.5.0 Build 250304 Rel.47276n",["latest"]),
                 (upgrade.STAGES["bridge"].target,["latest"]),
                 (upgrade.SOURCE,["latest"]),
                 (upgrade.STAGES["latest"].target,[]))
        for version, expected in cases:
            with self.subTest(version=version), ExitStack() as stack:
                state={"version":version}
                self.args.skip_firmware=False
                self.args.firmware_file="approved.bin"
                self.args.c540s_bridge_package="bridge.zip"
                observation=dict(ip="192.168.0.60",mac="c0-3a-55-55-ba-40",model="VIGI C540S",factory_flag=0,serial="TP1"+self.device_id+"040")
                for name,value in dict(discover=[observation],approve_observed_pin="00"*32,CameraHTTPS=Mock(),confirm_factory=None,detect_activation_format="legacy-2024" if expected==["bridge","latest"] else "modern",input="192.168.0.170",getpass="offline-test",login="/test",pin_after_network_move="11"*32).items():
                    stack.enter_context(patch.object(workflow,name,return_value=value))
                stack.enter_context(patch.object(upgrade,"inspect_latest_image",return_value=b"latest"))
                stack.enter_context(patch.object(upgrade,"inspect_package",return_value=b"bridge"))
                stack.enter_context(patch.object(upgrade,"read_identity",side_effect=lambda *a: ({"FirmwareVersion":state["version"]},80)))
                calls=[]
                def upload(camera,path,password,mac,device_id,stage,image,confirm):
                    name=next(n for n,spec in upgrade.STAGES.items() if spec==stage)
                    self.assertEqual(upgrade.upgrade_route(state["version"])[0],name)
                    calls.append(name)
                    state["version"]=stage.target
                    return True
                stack.enter_context(patch.object(upgrade,"upgrade_stage",side_effect=upload))
                steps={name:stack.enter_context(patch.object(workflow,name)) for name in (
                    "configure_device_alias","configure_region","configure_video","configure_platform_access","configure_osd","configure_audio",
                    "configure_motion_detection","configure_login_error","configure_network","configure_dns")}
                workflow.provision(self.args)
                self.assertEqual(calls,expected)
                self.assertEqual(workflow.login.call_count,1+len(expected))
                self.assertFalse(steps["configure_region"].call_args.kwargs["legacy_clock"])
                self.assertEqual(steps["configure_network"].call_args.args[0]["onvif_port"],80)
                steps["configure_dns"].assert_called_once()
