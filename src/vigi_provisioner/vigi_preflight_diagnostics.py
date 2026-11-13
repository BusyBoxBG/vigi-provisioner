from .vigi_preflight import inspect_device
from .vigi_discovery import discover

def diagnostic_checks(result):
    return {
        "Inventory match": False,
        "Factory state": result["factory_flag"] == 0,
        "HTTPS initialization state": result["https_error"] == -40405,
    }
