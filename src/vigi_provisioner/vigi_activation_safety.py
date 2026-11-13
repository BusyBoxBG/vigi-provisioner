from dataclasses import dataclass


@dataclass
class DeviceObservation:
    mac: str
    inventory_match: bool
    factory_flag: int | None
    https_error: int | None


def activation_allowed(device: DeviceObservation) -> tuple[bool, str]:
    if not device.inventory_match:
        return False, "MAC address not matched in inventory"

    if device.factory_flag is None:
        return False, "UDP initialization state unavailable"

    if device.factory_flag != 0:
        return False, "UDP discovery does not report factory state"

    if device.https_error != -40405:
        return False, "HTTPS does not confirm uninitialized state"

    return True, "Activation prerequisites satisfied"
