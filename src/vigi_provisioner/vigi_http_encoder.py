"""
Offline HTTP/1.1 initialization request encoder.

Never opens sockets and never transmits data.
"""

from .vigi_initialization_validator import (
    validate_initialization,
)


class HttpEncodingError(ValueError):
    pass


def encode_initialization_http(
    prepared,
    *,
    approved_ip,
    approved_port=443,
):
    validated = validate_initialization(
        prepared,
        approved_ip=approved_ip,
        approved_port=approved_port,
    )

    body = prepared.body

    if b"\r" in body or b"\n" in body:
        # JSON whitespace is legal, but this encoder
        # deliberately requires compact JSON.
        raise HttpEncodingError(
            "Initialization body must be compact"
        )

    host = (
        f"{validated['camera_ip']}:"
        f"{validated['https_port']}"
    )

    header_lines = [
        "POST / HTTP/1.1",
        f"Host: {host}",
        "Content-Type: " +
            prepared.headers["Content-Type"],
        "Accept: application/json",
        f"Content-Length: {len(body)}",
        "Connection: close",
    ]

    head = (
        "\r\n".join(header_lines)
        + "\r\n\r\n"
    ).encode("ascii")

    return head + body
