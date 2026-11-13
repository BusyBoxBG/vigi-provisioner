"""
VIGI discovery evidence validation.

Offline policy validation only.
Discovery metadata is not cryptographically authenticated.
No network requests or camera modifications.
"""

from dataclasses import dataclass
import math
import time

from .vigi_pin_inventory import normalize_mac
from .vigi_camera_binding import (
    CameraBindingRegistry,
    normalize_ipv4,
)


class DiscoveryEvidenceError(ValueError):
    pass


ALLOWED_METHODS = frozenset({
    "ONVIF_WS_DISCOVERY",
    "TPLINK_UDP_5001",
})


@dataclass(frozen=True)
class DiscoveryEvidence:
    mac: str
    camera_ip: str
    method: str
    observed_at: float
    successful: bool
    trusted: bool


def validate_discovery_evidence(
    evidence,
    *,
    now=None,
    max_age_seconds=60,
):
    if not isinstance(evidence, DiscoveryEvidence):
        raise DiscoveryEvidenceError(
            "Expected DiscoveryEvidence"
        )

    if evidence.method not in ALLOWED_METHODS:
        raise DiscoveryEvidenceError(
            "Unsupported discovery method"
        )

    if evidence.successful is not True:
        raise DiscoveryEvidenceError(
            "Discovery did not succeed"
        )

    if evidence.trusted is not True:
        raise DiscoveryEvidenceError(
            "Discovery source not approved"
        )

    if (
        isinstance(max_age_seconds, bool)
        or not isinstance(max_age_seconds, (int, float))
        or not math.isfinite(max_age_seconds)
        or not 0 < max_age_seconds <= 3600
    ):
        raise ValueError("Invalid discovery maximum age")

    if (
        isinstance(evidence.observed_at, bool)
        or not isinstance(evidence.observed_at, (int, float))
        or not math.isfinite(evidence.observed_at)
    ):
        raise DiscoveryEvidenceError(
            "Invalid discovery timestamp"
        )

    if now is None:
        now = time.monotonic()

    if (
        isinstance(now, bool)
        or not isinstance(now, (int, float))
        or not math.isfinite(now)
    ):
        raise ValueError("Invalid current timestamp")

    age = now - evidence.observed_at

    if age < 0:
        raise DiscoveryEvidenceError(
            "Discovery timestamp is in the future"
        )

    if age >= max_age_seconds:
        raise DiscoveryEvidenceError(
            "Discovery evidence expired"
        )

    try:
        mac = normalize_mac(evidence.mac)
        camera_ip = normalize_ipv4(evidence.camera_ip)
    except ValueError as exc:
        raise DiscoveryEvidenceError(
            "Invalid discovery identity"
        ) from exc

    return mac, camera_ip


def register_discovered_camera(
    registry,
    evidence,
    *,
    now=None,
    max_age_seconds=60,
):
    if not isinstance(registry, CameraBindingRegistry):
        raise TypeError("Expected CameraBindingRegistry")

    mac, camera_ip = validate_discovery_evidence(
        evidence,
        now=now,
        max_age_seconds=max_age_seconds,
    )

    return registry.register(mac, camera_ip)
