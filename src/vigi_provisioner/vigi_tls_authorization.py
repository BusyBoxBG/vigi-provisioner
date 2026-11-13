"""
VIGI inventory-backed pinned TLS authorization.

Requires a previously approved certificate pin.
Does not automatically enroll or replace pins.
Does not send HTTP requests.
"""

from .vigi_pin_inventory import VigiPinInventory
from .vigi_pinned_tls import connect_pinned_tls


class CameraNotApprovedError(PermissionError):
    pass


def connect_approved_camera(
    inventory,
    mac,
    camera_ip,
    camera_port,
    source_ip,
    timeout=5,
):
    if not isinstance(inventory, VigiPinInventory):
        raise TypeError("Expected VigiPinInventory")

    approved_pin = inventory.get_approved_pin(mac)

    if approved_pin is None:
        raise CameraNotApprovedError(
            "Camera has no approved TLS certificate pin"
        )

    return connect_pinned_tls(
        camera_ip=camera_ip,
        camera_port=camera_port,
        source_ip=source_ip,
        expected_pin=approved_pin,
        timeout=timeout,
    )
