import importlib
import pkgutil
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vigi_provisioner


def main():
    suite = unittest.TestSuite()
    with patch("socket.socket.connect", side_effect=AssertionError("Offline check attempted a connection")), patch(
        "socket.socket.sendto", side_effect=AssertionError("Offline check attempted a datagram")
    ):
        for module in pkgutil.iter_modules(vigi_provisioner.__path__, "vigi_provisioner."):
            importlib.import_module(module.name)
        suite.addTests(unittest.defaultTestLoader.discover(str(ROOT / "tests")))
        for path in sorted((ROOT / "tests").glob("test_*.py")):
            sys.path.insert(0, str(path.parent))
            try:
                check = getattr(importlib.import_module(path.stem), "test_existing_checks", None)
            finally:
                sys.path.pop(0)
            if check is not None:
                suite.addTest(unittest.FunctionTestCase(check, description=path.stem))
        return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
