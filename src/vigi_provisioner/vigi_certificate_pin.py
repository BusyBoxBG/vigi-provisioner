"""
VIGI certificate fingerprint verification.

Offline helper only.
Does not establish TLS connections.
Does not automatically trust observed certificates.
"""

import hashlib
import hmac
import re


class CertificatePinError(ValueError):
    pass


def normalize_sha256_pin(pin):
    if not isinstance(pin, str):
        raise CertificatePinError(
            "Certificate pin must be a string"
        )

    normalized = pin.replace(":", "").lower()

    if not re.fullmatch(r"[0-9a-f]{64}", normalized):
        raise CertificatePinError(
            "Invalid SHA-256 certificate fingerprint"
        )

    return normalized


def certificate_sha256(der_certificate):
    if not isinstance(
        der_certificate,
        bytes
    ):
        raise TypeError(
            "DER certificate must be bytes"
        )

    if not der_certificate:
        raise CertificatePinError(
            "Empty DER certificate"
        )

    return hashlib.sha256(
        der_certificate
    ).hexdigest()


def verify_certificate_pin(
    der_certificate,
    expected_pin,
):
    actual = certificate_sha256(
        der_certificate
    )

    expected = normalize_sha256_pin(
        expected_pin
    )

    if not hmac.compare_digest(
        actual,
        expected
    ):
        raise CertificatePinError(
            "Camera certificate fingerprint mismatch"
        )

    return True
