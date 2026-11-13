"""
Explicit enrollment authorization for discovered cameras.

An approved certificate pin and an explicit operator
decision are required before registering an IP/MAC
binding.

Offline policy enforcement only.
"""

import hmac

from .vigi_certificate_pin import normalize_sha256_pin
from .vigi_pin_inventory import (
    VigiPinInventory,
    normalize_mac,
)
from .vigi_camera_binding import (
    CameraBindingRegistry,
    normalize_ipv4,
)
from .vigi_discovery_evidence import (
    DiscoveryEvidence,
    validate_discovery_evidence,
)


class EnrollmentBindingError(PermissionError):
    pass


def approve_discovered_binding(
    registry,
    pin_inventory,
    evidence,
    *,
    approved_mac,
    approved_ip,
    approved_pin,
    operator_confirmed,
    now=None,
    max_age_seconds=60,
):
    if not isinstance(registry, CameraBindingRegistry):
        raise TypeError("Expected CameraBindingRegistry")

    if not isinstance(pin_inventory, VigiPinInventory):
        raise TypeError("Expected VigiPinInventory")

    if not isinstance(evidence, DiscoveryEvidence):
        raise TypeError("Expected DiscoveryEvidence")

    if operator_confirmed is not True:
        raise EnrollmentBindingError(
            "Explicit operator confirmation required"
        )

    observed_mac = normalize_mac(evidence.mac)
    observed_ip = normalize_ipv4(evidence.camera_ip)

    expected_mac = normalize_mac(approved_mac)
    expected_ip = normalize_ipv4(approved_ip)
    expected_pin = normalize_sha256_pin(approved_pin)

    if observed_mac != expected_mac:
        raise EnrollmentBindingError(
            "Approved MAC differs from discovery"
        )

    if observed_ip != expected_ip:
        raise EnrollmentBindingError(
            "Approved IP differs from discovery"
        )

    stored_pin = pin_inventory.get_approved_pin(
        expected_mac
    )

    if stored_pin is None:
        raise EnrollmentBindingError(
            "No enrolled certificate pin"
        )

    if not hmac.compare_digest(
        stored_pin,
        expected_pin,
    ):
        raise EnrollmentBindingError(
            "Approved certificate pin mismatch"
        )

    # Discovery remains unauthenticated.
    # Validate its structure and freshness without
    # claiming that it proves camera identity.
    from dataclasses import replace

    policy_evidence = replace(
        evidence,
        trusted=True,
    )

    validated_mac, validated_ip = (
        validate_discovery_evidence(
            policy_evidence,
            now=now,
            max_age_seconds=max_age_seconds,
        )
    )

    if (
        validated_mac != expected_mac
        or validated_ip != expected_ip
    ):
        raise EnrollmentBindingError(
            "Validated discovery identity mismatch"
        )

    return registry.register(
        expected_mac,
        expected_ip,
    )
