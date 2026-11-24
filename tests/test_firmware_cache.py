import copy
import hashlib
import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch
from vigi_provisioner.vigi_model_catalog import load_catalog
from vigi_provisioner.vigi_firmware_cache import approve_download, approved_image, version_from_url

class FirmwareCacheTests(unittest.TestCase):
    def setUp(self):
        self.row = load_catalog(Path(__file__).resolve().parents[1] / "models.example.toml")[1]

    def download(self, data, root):
        response = MagicMock()
        response.is_redirect = False
        response.iter_content.return_value = [data]
        response.__enter__.return_value = response
        with patch("vigi_provisioner.vigi_firmware_cache.requests.Session") as session:
            session.return_value.__enter__.return_value.get.return_value = response
            return approve_download(self.row, self.row["firmware_url"], "2.2.1 Build 260605", root)

    def test_download_approval_and_tamper_detection(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("folder/image.bin", b"offline firmware fixture")
        original = copy.deepcopy(self.row)
        with tempfile.TemporaryDirectory() as root:
            row = self.download(stream.getvalue(), root)
            image = approved_image(row, root)
            self.assertEqual(image.read_bytes(), b"offline firmware fixture")
            self.assertTrue(Path(row["approved_zip"]).is_file())
            self.assertEqual(row["approved_sha256"], hashlib.sha256(image.read_bytes()).hexdigest())
            self.assertEqual(self.row, original)
            image.write_bytes(b"changed")
            with self.assertRaises(ValueError): approved_image(row, root)

    def test_multiple_images_do_not_create_approval(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("first.bin", b"first")
            archive.writestr("second.bin", b"second")
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError): self.download(stream.getvalue(), root)
            self.assertFalse(list(Path(root).rglob("*.bin")))

    def test_unselected_url_rejected_before_download(self):
        with tempfile.TemporaryDirectory() as root, patch("vigi_provisioner.vigi_firmware_cache.requests.Session") as session:
            with self.assertRaises(ValueError):
                approve_download(self.row, "https://static.tp-link.com/upload/firmware/other.zip", "other", root)
            session.assert_not_called()

    def test_version_from_filename(self):
        self.assertEqual(version_from_url(self.row["firmware_url"]), "2.2.1 Build 260605")
