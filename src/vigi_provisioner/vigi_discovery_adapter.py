"""
Adapter for TP-Link VIGI UDP discovery observations.

Parsing a discovery response does not authenticate
the identity of the responding camera.

No sockets, HTTP requests, or camera changes.
"""

import math
import time

from .vigi_pin_inventory import normalize_mac
from .vigi_camera_binding import normalize_ipv4
from .vigi_discovery_evidence import DiscoveryEvidence


class DiscoveryAdapterError(ValueError):
    pass


def adapt_udp_discovery(
    device,
    *,
    packet_source_ip,
    observed_at=None,
):
    if not isinstance(device, dict):
        raise DiscoveryAdapterError(
            "Expected UDP discovery dictionary"
        )

    try:
        mac = normalize_mac(device["mac"])
        camera_ip = normalize_ipv4(device["ip"])
        source_ip = normalize_ipv4(packet_source_ip)
    except (KeyError, ValueError, TypeError) as exc:
        raise DiscoveryAdapterError(
            "Invalid UDP discovery identity"
        ) from exc

    if camera_ip != source_ip:
        raise DiscoveryAdapterError(
            "Discovery IP differs from packet source"
        )

    if observed_at is None:
        observed_at = time.monotonic()

    if (
        isinstance(observed_at, bool)
        or not isinstance(observed_at, (int, float))
        or not math.isfinite(observed_at)
    ):
        raise DiscoveryAdapterError(
            "Invalid observation timestamp"
        )

    return DiscoveryEvidence(
        mac=mac,
        camera_ip=camera_ip,
        method="TPLINK_UDP_5001",
        observed_at=observed_at,
        successful=True,
        trusted=False,
    )
