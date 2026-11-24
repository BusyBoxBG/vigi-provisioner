import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from vigi_provisioner.vigi_model_catalog import load_catalog, save_catalog, official_url, FirmwareLinks, check_firmware

ROOT = Path(__file__).resolve().parents[1]

class ModelCatalogTests(unittest.TestCase):
    def setUp(self):
        self.rows = load_catalog(ROOT / "models.example.toml")

    def test_seed_and_atomic_roundtrip(self):
        self.assertEqual(len(self.rows), 12)
        self.assertEqual(len({r["id"] for r in self.rows}), 12)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "models.toml"
            save_catalog(path, self.rows)
            self.assertEqual(load_catalog(path), self.rows)
            changed = copy.deepcopy(self.rows)
            changed[0]["model"] = "Quoted \"model\""
            save_catalog(path, changed)
            self.assertEqual(load_catalog(path), changed)

    def test_unofficial_and_local_urls_rejected(self):
        for url in ("http://www.tp-link.com/en/support/download/x/", "https://127.0.0.1/support/download/x/", "https://www.tp-link.com.evil.test/support/download/x/", "https://user@www.tp-link.com/en/support/download/x/"):
            with self.assertRaises(ValueError): official_url(url)

    def test_parser_ignores_software_and_keeps_ampersands(self):
        parser = FirmwareLinks(self.rows[0]["support_url"])
        url = self.rows[4]["firmware_url"]
        parser.feed('<a href="'+url.replace('&', '&amp;')+'">Firmware</a><a href="https://static.tp-link.com/upload/software/app.zip">App</a>')
        self.assertEqual(parser.links, [url])

    def test_check_preserves_recorded_firmware(self):
        row = self.rows[0]
        candidate = self.rows[1]["firmware_url"]
        response = Mock()
        response.is_redirect = False
        response.iter_content.return_value = [('<a href="'+candidate+'">Firmware</a>').encode()]
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with patch("vigi_provisioner.vigi_model_catalog.requests.Session") as factory:
            factory.return_value.__enter__.return_value.get.return_value = response
            checked = check_firmware(row)
        self.assertEqual(checked["firmware_url"], row["firmware_url"])
        self.assertEqual(checked["available_firmware_urls"], [candidate])
        self.assertTrue(checked["last_checked"])
        self.assertEqual(row["available_firmware_urls"], self.rows[0]["available_firmware_urls"])
