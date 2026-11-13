"""Identity descriptor for an externally established transport.

This module does not connect, send, receive, or verify TLS.
"""

from dataclasses import dataclass

from .vigi_pin_inventory import normalize_mac
from .vigi_camera_binding import normalize_ipv4


@dataclass(frozen=True)
class IdentityBoundTransport:
    approved_mac: str
    destination_ip: str
    destination_port: int
    source_ip: str
    transport: object

    def __post_init__(self):
        mac = normalize_mac(self.approved_mac)
        ip = normalize_ipv4(self.destination_ip)
        source = normalize_ipv4(self.source_ip)

        if (
            type(self.destination_port) is not int
            or not 1 <= self.destination_port <= 65535
        ):
            raise ValueError(
                "Invalid destination port"
            )

        if self.transport is None:
            raise ValueError(
                "Transport reference is required"
            )

        object.__setattr__(
            self, "approved_mac", mac
        )
        object.__setattr__(
            self, "destination_ip", ip
        )
        object.__setattr__(
            self, "source_ip", source
        )

    @property
    def approved_identity(self):
        return (
            self.approved_mac,
            self.destination_ip,
            self.destination_port,
        )
