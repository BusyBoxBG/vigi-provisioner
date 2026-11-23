from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vigi_provisioner.vigi_test_gui import Application, initialize_inventory


class GuiFirmwareModeTests(unittest.TestCase):
    def test_worker_preserves_firmware_by_default_and_upgrades_only_when_selected(self):
        with tempfile.TemporaryDirectory() as directory:
            database = str(Path(directory) / "inventory.sqlite3")
            initialize_inventory(database)
            with closing(sqlite3.connect(database)) as db, db:
                db.execute("INSERT INTO camera_inventory (device_id,mac_address,model,approved_ipv4,prefix_length,gateway_ipv4) VALUES (?,?,?,?,?,?)",
                           ("TEST", "1869459F31F7", "VIGI C320I", "192.168.0.150", 24, "192.168.0.1"))
            for choice in (None, False, True):
                app = Application(database, "profile.toml")
                with patch("vigi_provisioner.vigi_test_gui.subprocess.Popen") as launch, patch("vigi_provisioner.vigi_test_gui.threading.Thread"):
                    if choice is None:
                        app.start("TEST")
                    else:
                        app.start("TEST", choice)
                    self.assertEqual("--skip-firmware" in launch.call_args.args[0], choice is not True)

    def test_non_boolean_upgrade_choice_rejected(self):
        app = Application("unused", "unused")
        with self.assertRaises(ValueError):
            app.start("TEST", "false")
