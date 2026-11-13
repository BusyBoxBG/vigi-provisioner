"""
VIGI pinned TLS connection helper.

Requires an explicitly supplied certificate fingerprint.

Does not send HTTP requests.
Does not automatically enroll certificates.
Does not modify the existing HTTPS transport.
"""

import socket
import ssl

from .vigi_certificate_pin import (
    normalize_sha256_pin,
    verify_certificate_pin,
)


class VigiPinnedTLSError(RuntimeError):
    pass


def connect_pinned_tls(
    camera_ip,
    camera_port,
    source_ip,
    expected_pin,
    timeout=5,
):
    """
    Return an open TLS socket only after its
    certificate matches the expected SHA-256 pin.

    Caller owns the returned socket and must close it.
    """

    if not isinstance(camera_ip, str):
        raise TypeError("camera_ip must be a string")

    if not isinstance(source_ip, str):
        raise TypeError("source_ip must be a string")

    if not isinstance(camera_port, int) or isinstance(camera_port, bool):
        raise TypeError("camera_port must be an integer")

    if not 1 <= camera_port <= 65535:
        raise ValueError("Invalid camera port")

    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool):
        raise TypeError("timeout must be numeric")

    if not 0 < timeout <= 30:
        raise ValueError("Invalid timeout")

    normalized_pin = normalize_sha256_pin(
        expected_pin
    )

    context = ssl.SSLContext(
        ssl.PROTOCOL_TLS_CLIENT
    )

    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    raw_socket = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    )

    tls_socket = None

    try:
        raw_socket.settimeout(timeout)
        raw_socket.bind((source_ip, 0))
        raw_socket.connect(
            (camera_ip, camera_port)
        )

        tls_socket = context.wrap_socket(
            raw_socket,
            server_hostname=None,
        )

        der = tls_socket.getpeercert(
            binary_form=True
        )

        if not der:
            raise VigiPinnedTLSError(
                "Camera provided no TLS certificate"
            )

        verify_certificate_pin(
            der,
            normalized_pin,
        )

        return tls_socket

    except Exception:
        if tls_socket is not None:
            tls_socket.close()
        else:
            raw_socket.close()

        raise
