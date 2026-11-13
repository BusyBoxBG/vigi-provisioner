"""
VIGI inventory IP/MAC binding.

Offline registry for authorization tests.
No discovery, HTTP, or camera modifications.
"""

import ipaddress

from .vigi_pin_inventory import normalize_mac
from .vigi_tls_authorization import (
    CameraNotApprovedError,
    connect_approved_camera,
)


class CameraBindingError(PermissionError):
    pass


def normalize_ipv4(value):
    if not isinstance(value, str):
        raise ValueError("IPv4 address must be a string")

    try:
        address = ipaddress.IPv4Address(value)
    except ipaddress.AddressValueError as exc:
        raise ValueError("Invalid IPv4 address") from exc

    if str(address) != value:
        raise ValueError("Noncanonical IPv4 address")

    if (
        address.is_unspecified
        or address.is_multicast
        or address.is_loopback
        or address.is_reserved
        or int(address) == 0xFFFFFFFF
    ):
        raise ValueError("Disallowed camera IPv4 address")

    return str(address)


class CameraBindingRegistry:
    """
    In-memory camera IP/MAC binding registry.

    Bindings expire after ttl_seconds.
    The clock is injectable for deterministic tests.
    """

    def __init__(self, ttl_seconds=300, clock=None):
        import time

        if (
            isinstance(ttl_seconds, bool)
            or not isinstance(ttl_seconds, (int, float))
            or not 0 < ttl_seconds <= 86400
        ):
            raise ValueError(
                "TTL must be between 0 and 86400 seconds"
            )

        self.ttl_seconds = ttl_seconds
        self._clock = clock if clock is not None else time.monotonic
        if not callable(self._clock):
            raise TypeError("Clock must be callable")

        self._by_mac = {}
        self._by_ip = {}

    def _expire(self):
        now = self._clock()

        expired = [
            mac
            for mac, (ip, expires_at) in self._by_mac.items()
            if now >= expires_at
        ]

        for mac in expired:
            ip, _ = self._by_mac.pop(mac)
            if self._by_ip.get(ip) == mac:
                del self._by_ip[ip]

    def register(self, mac, camera_ip):
        normalized_mac = normalize_mac(mac)
        normalized_ip = normalize_ipv4(camera_ip)

        self._expire()

        existing = self._by_mac.get(normalized_mac)
        existing_mac = self._by_ip.get(normalized_ip)

        if existing is not None:
            if existing[0] != normalized_ip:
                raise CameraBindingError(
                    "MAC already bound to another IP"
                )
            return False

        if existing_mac is not None:
            raise CameraBindingError(
                "IP already bound to another MAC"
            )

        expires_at = self._clock() + self.ttl_seconds

        self._by_mac[normalized_mac] = (
            normalized_ip,
            expires_at,
        )
        self._by_ip[normalized_ip] = normalized_mac

        return True

    def require_binding(self, mac, camera_ip):
        normalized_mac = normalize_mac(mac)
        normalized_ip = normalize_ipv4(camera_ip)

        self._expire()

        existing = self._by_mac.get(normalized_mac)

        if existing is None or existing[0] != normalized_ip:
            raise CameraBindingError(
                "Camera MAC/IP binding missing or expired"
            )

        if self._by_ip.get(normalized_ip) != normalized_mac:
            raise CameraBindingError(
                "Ambiguous camera IP assignment"
            )

        return True

    def revoke(self, mac):
        normalized_mac = normalize_mac(mac)

        self._expire()

        existing = self._by_mac.pop(
            normalized_mac,
            None,
        )

        if existing is None:
            return False

        ip, _ = existing

        if self._by_ip.get(ip) == normalized_mac:
            del self._by_ip[ip]

        return True


def connect_bound_camera(
    registry,
    pin_inventory,
    mac,
    camera_ip,
    camera_port,
    source_ip,
    timeout=5,
):
    if not isinstance(registry, CameraBindingRegistry):
        raise TypeError("Expected CameraBindingRegistry")

    registry.require_binding(mac, camera_ip)

    return connect_approved_camera(
        inventory=pin_inventory,
        mac=mac,
        camera_ip=camera_ip,
        camera_port=camera_port,
        source_ip=source_ip,
        timeout=timeout,
    )
