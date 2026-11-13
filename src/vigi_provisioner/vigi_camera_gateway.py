from dataclasses import replace
from pathlib import Path

from . import vigi_discovery

from .vigi_inventory import normalize_mac
from .vigi_pin_inventory import VigiPinInventory
from .vigi_discovery_adapter import adapt_udp_discovery
from .vigi_authorized_gateway import VigiAuthorizedGateway


DEFAULT_PIN_DB = Path(__file__).with_name(
    "vigi_camera_pins.sqlite3"
)


class CameraGatewayError(RuntimeError):
    pass


def connect_inventory_camera(
    mac,
    camera_ip,
    *,
    source_ip="192.168.0.10",
    pin_db_path=DEFAULT_PIN_DB,
    operator_confirmed=False,
    timeout=5,
):
    """
    Discover and connect to an approved camera using
    the existing authorized, certificate-pinned gateway.

    Returns an open TLS socket. The caller must close it.

    This function does not send HTTP requests.
    """

    if operator_confirmed is not True:
        raise CameraGatewayError(
            "Explicit operator confirmation required"
        )

    normalized_mac = normalize_mac(mac)

    pin_db_path = Path(pin_db_path)

    if not pin_db_path.is_file():
        raise CameraGatewayError(
            "Approved certificate inventory not found"
        )

    pin_inventory = VigiPinInventory(pin_db_path)

    approved_pin = pin_inventory.get_approved_pin(
        normalized_mac
    )

    if approved_pin is None:
        raise CameraGatewayError(
            "Camera certificate is not enrolled"
        )

    devices = vigi_discovery.discover(
        local_ip=source_ip,
        timeout=5,
    )

    matches = [
        device
        for device in devices
        if normalize_mac(device["mac"]) == normalized_mac
    ]

    if len(matches) != 1:
        raise CameraGatewayError(
            "Expected exactly one matching camera"
        )

    camera = matches[0]

    if camera["ip"] != camera_ip:
        raise CameraGatewayError(
            "Discovered camera IP does not match approved IP"
        )

    evidence = adapt_udp_discovery(
        camera,
        packet_source_ip=camera_ip,
    )

    # Operator-approved application-level discovery trust.
    # This does not cryptographically authenticate UDP.
    trusted_evidence = replace(
        evidence,
        trusted=True,
    )

    gateway = VigiAuthorizedGateway(
        pin_inventory=pin_inventory,
        provisioning_source_ip=source_ip,
        https_port=443,
    )

    gateway.approve(
        trusted_evidence,
        approved_mac=normalized_mac,
        approved_ip=camera_ip,
        approved_pin=approved_pin,
        operator_confirmed=True,
    )

    return gateway.connect(
        mac=normalized_mac,
        camera_ip=camera_ip,
        camera_port=443,
        source_ip=source_ip,
        timeout=timeout,
    )
