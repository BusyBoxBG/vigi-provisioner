"""Immutable metadata-only initialization execution plan.

This module does not authorize camera access, consume credentials,
open sockets, or transmit initialization requests.
"""

from dataclasses import dataclass

from .vigi_pin_inventory import normalize_mac
from .vigi_camera_binding import normalize_ipv4


@dataclass(frozen=True)
class InitializationExecutionPlan:
    approved_mac: str
    destination_ip: str
    destination_port: int
    source_ip: str

    def __post_init__(self):
        normalized_mac = normalize_mac(self.approved_mac)
        normalized_ip = normalize_ipv4(self.destination_ip)
        normalized_source = normalize_ipv4(self.source_ip)

        if (
            type(self.destination_port) is not int
            or not 1 <= self.destination_port <= 65535
        ):
            raise ValueError(
                "Invalid destination HTTPS port"
            )

        object.__setattr__(
            self,
            "approved_mac",
            normalized_mac,
        )

        object.__setattr__(
            self,
            "destination_ip",
            normalized_ip,
        )

        object.__setattr__(
            self,
            "source_ip",
            normalized_source,
        )
