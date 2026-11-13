"""
VIGI HTTPS initialization transport.

TLS configuration is prepared locally.

Live camera transmission remains disabled.
"""

import ssl
from urllib.parse import urlsplit

from .vigi_https_init import PreparedInitialization
from .vigi_tls import create_vigi_ssl_context


class TransmissionDisabledError(RuntimeError):
    pass


class VigiHttpsTransport:

    def __init__(self, dry_run=True, ssl_context=None):
        if dry_run is not True:
            raise TransmissionDisabledError(
                "Live HTTPS transmission is not implemented"
            )

        if ssl_context is None:
            ssl_context = create_vigi_ssl_context()

        if not isinstance(ssl_context, ssl.SSLContext):
            raise TypeError(
                "Expected ssl.SSLContext"
            )

        if ssl_context.verify_mode != ssl.CERT_REQUIRED:
            raise ValueError(
                "TLS certificate verification is required"
            )

        if (
            ssl_context.minimum_version
            < ssl.TLSVersion.TLSv1_2
        ):
            raise ValueError(
                "TLS 1.2 or newer is required"
            )

        self.dry_run = True
        self.ssl_context = ssl_context

    def execute(self, prepared):
        if not isinstance(prepared, PreparedInitialization):
            raise TypeError(
                "Expected PreparedInitialization"
            )

        parsed = urlsplit(prepared.url)

        if parsed.scheme != "https":
            raise ValueError("HTTPS is required")

        if parsed.hostname is None:
            raise ValueError("Missing camera hostname")

        if prepared.method != "POST":
            raise ValueError("Initialization requires POST")

        if not prepared.body:
            raise ValueError("Empty initialization body")

        result = prepared.summary()

        result["transport_mode"] = "DRY_RUN"
        result["transmitted"] = False

        return result
