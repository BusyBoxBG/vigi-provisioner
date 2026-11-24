import hashlib
import sqlite3
import tempfile
import unittest
from contextlib import closing, ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from vigi_provisioner import vigi_factory_workflow as workflow
from vigi_provisioner.vigi_test_gui import Application, initialize_inventory

class C540SInitializationTests(unittest.TestCase):
    def test_initialize_only_and_gui_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            database=str(Path(directory)/"inventory.sqlite3")
            initialize_inventory(database)
            device_id="CB7516E6763362E22"
            with closing(sqlite3.connect(database)) as db,db:
                db.execute("INSERT INTO camera_inventory (device_id,mac_address,model,hardware_version,label_serial,approved_ipv4,prefix_length,gateway_ipv4) VALUES (?,?,?,?,?,?,?,?)",
                           (device_id,"C03A5555BA40","VIGI C540S","1","2264481000089","192.168.0.170",24,"192.168.0.1"))
            args=SimpleNamespace(inventory=database,device_id=device_id,pin=None,config=str(Path(__file__).resolve().parents[1]/"provisioning.example.toml"))
            camera=Mock()
            camera.post.return_value=(200,{"device_info":{"info":{"device_model":"VIGI%20C540S","hw_version":"1.0","sw_version":"fixture firmware"}}})
            observation=dict(ip="192.168.0.60",mac="c0-3a-55-55-ba-40",model="VIGI C540S",factory_flag=0,serial="TP1"+device_id+"040")
            with ExitStack() as stack:
                for name,value in dict(discover=[observation],CameraHTTPS=camera,approve_observed_pin="pin",confirm_factory=None,detect_activation_format="modern",getpass="offline-test",input="INITIALIZE "+device_id,login="/test").items():
                    stack.enter_context(patch.object(workflow,name,return_value=value))
                site=stack.enter_context(patch.object(workflow,"configure_region"))
                network=stack.enter_context(patch.object(workflow,"configure_network"))
                result=workflow.initialize_only(args)
                self.assertEqual(result["onvif_model"],"VIGI C540S")
                self.assertEqual([c.args[0] for c in camera.post.call_args_list],["Factory activation","Read initialized device metadata"])
                site.assert_not_called();network.assert_not_called()
            app=Application(database,args.config)
            with self.assertRaises(ValueError):app.start(device_id,firmware_mode="approved")
            with patch("vigi_provisioner.vigi_test_gui.subprocess.Popen") as launch,patch("vigi_provisioner.vigi_test_gui.threading.Thread"):
                app.start(device_id,firmware_mode="initialize")
                command=launch.call_args.args[0]
                self.assertIn("--initialize-only",command)
                self.assertIn("--skip-firmware",command)

    def test_known_resource_larger_than_four_megabytes_is_bounded(self):
        raw=b"x"*5_068_929
        camera=Mock()
        response=Mock(status=200)
        response.read.return_value=raw
        camera.getresponse.return_value=response
        with patch.object(workflow,"ACTIVATION_RESOURCES",(("/bundle.js",hashlib.sha256(raw).hexdigest(),"modern"),)):
            self.assertEqual(workflow.detect_activation_format(camera),"modern")
        response.read.assert_called_once_with(8_000_001)

    def test_oversized_resource_is_not_recognized(self):
        raw=b"x"*8_000_001
        camera=Mock()
        camera.getresponse.return_value=Mock(status=200,read=Mock(return_value=raw))
        with patch.object(workflow,"ACTIVATION_RESOURCES",(("/bundle.js",hashlib.sha256(raw).hexdigest(),"modern"),)):
            with self.assertRaises(workflow.ProvisioningError):workflow.detect_activation_format(camera)
