import hashlib
import io
import tempfile
import unittest
import zipfile
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from vigi_provisioner import vigi_c340s_upgrade as upgrade
from vigi_provisioner.vigi_factory_workflow import ProvisioningError

class C340SUpgradeTests(unittest.TestCase):
    def args(self, stage="bridge", execute=False):
        return SimpleNamespace(stage=stage, execute=execute, device_id="3B27D0E000E0AF692", inventory="inventory.sqlite3", package="package.zip")

    def test_package_and_image_checksums(self):
        image = b"offline image"
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as package: package.writestr("folder/image.bin", image)
        data = stream.getvalue()
        stage = replace(upgrade.STAGES["bridge"], filename="image.bin", zip_sha256=hashlib.sha256(data).hexdigest(), image_sha256=hashlib.sha256(image).hexdigest())
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory)/"test.zip"
            file.write_bytes(data)
            self.assertEqual(upgrade.inspect_package(file, stage), image)
            with self.assertRaises(ProvisioningError): upgrade.inspect_package(file, replace(stage,image_sha256="0"*64))
            file.write_bytes(data+b"changed")
            with self.assertRaises(ProvisioningError): upgrade.inspect_package(file, stage)

    def test_preflight_never_opens_https_or_uploads(self):
        with patch.object(upgrade,"inspect_package",return_value=b"image"), patch.object(upgrade,"inventory_camera",return_value="30689353CC93"), patch.object(upgrade,"confirm_discovery"), patch.object(upgrade,"getpass",return_value="offline"), patch.object(upgrade,"read_identity",return_value=({"FirmwareVersion":upgrade.SOURCE,"HardwareId":"1.0"},2020)), patch.object(upgrade,"CameraHTTPS") as camera, patch.object(upgrade,"upload_file") as upload:
            upgrade.run(self.args())
            camera.assert_not_called()
            upload.assert_not_called()

    def test_latest_rejects_old_firmware_before_upload(self):
        with patch.object(upgrade,"inspect_package",return_value=b"image"), patch.object(upgrade,"inventory_camera",return_value="30689353CC93"), patch.object(upgrade,"confirm_discovery"), patch.object(upgrade,"getpass",return_value="offline"), patch.object(upgrade,"read_identity",return_value=({"FirmwareVersion":upgrade.SOURCE},2020)), patch.object(upgrade,"CameraHTTPS") as camera, patch.object(upgrade,"upload_file") as upload:
            with self.assertRaises(ProvisioningError): upgrade.run(self.args(stage="latest",execute=True))
            camera.assert_not_called()
            upload.assert_not_called()

    def test_cancelled_confirmation_never_uploads(self):
        with patch.object(upgrade,"inspect_package",return_value=b"image"), patch.object(upgrade,"inventory_camera",return_value="30689353CC93"), patch.object(upgrade,"confirm_discovery"), patch.object(upgrade,"getpass",return_value="offline"), patch.object(upgrade,"read_identity",return_value=({"FirmwareVersion":upgrade.SOURCE},2020)), patch.object(upgrade,"approve_observed_pin",return_value="pin"), patch.object(upgrade,"CameraHTTPS"), patch.object(upgrade,"login",return_value="/test"), patch.object(upgrade,"input",return_value="cancel"), patch.object(upgrade,"upload_file") as upload:
            with self.assertRaises(ProvisioningError): upgrade.run(self.args(execute=True))
            upload.assert_not_called()

    def test_identity_mismatch_rejected(self):
        with patch.object(upgrade,"get_device_information",return_value={"Model":"VIGI C320I","HardwareId":"1.0"}), patch.object(upgrade,"get_network_interfaces",return_value=[{"mac":"30689353CC93"}]):
            with self.assertRaises(ProvisioningError): upgrade.read_identity("offline","30689353CC93")

    def test_target_version_readback(self):
        stage=upgrade.STAGES["bridge"]
        with patch.object(upgrade.time,"monotonic",side_effect=[0,0]), patch.object(upgrade.time,"sleep"), patch.object(upgrade,"read_identity",return_value=({"FirmwareVersion":stage.target},80)):
            upgrade.wait_for_target("offline","30689353CC93",stage)
