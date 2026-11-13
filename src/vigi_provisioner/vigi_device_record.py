import getpass

from .vigi_discovery import discover
from .vigi_onvif import get_device_information


def build_device_record(udp, onvif=None):
    onvif = onvif or {}

    return {
        "ip": udp["ip"],
        "mac": udp["mac"],
        "factory_flag": udp["factory_flag"],
        "manufacturer": (
            onvif.get("Manufacturer")
            or udp.get("manufacturer")
        ),
        "model": (
            onvif.get("Model")
            or udp.get("model")
        ),
        "firmware": (
            onvif.get("FirmwareVersion")
            or udp.get("firmware")
        ),
        "serial": udp.get("serial"),
        "onvif_serial": onvif.get("SerialNumber"),
        "hardware_id": onvif.get("HardwareId"),
        "device_name": udp.get("device_name"),
        "onvif_endpoint": udp.get("onvif_endpoint"),
    }
