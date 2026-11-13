"""
Bounded HTTP response assembly from offline byte chunks.

Does not create sockets or perform network operations.
"""

from .vigi_http_response import (
    HttpResponseError,
    parse_http_response,
)


class HttpReadError(ValueError):
    pass


def assemble_http_response(
    chunks,
    *,
    max_header_bytes=16384,
    max_body_bytes=65536,
):
    if (
        type(max_header_bytes) is not int
        or not 1 <= max_header_bytes <= 16384
    ):
        raise HttpReadError(
            "Invalid header limit"
        )

    if (
        type(max_body_bytes) is not int
        or not 1 <= max_body_bytes <= 1048576
    ):
        raise HttpReadError(
            "Invalid body limit"
        )

    buffer = bytearray()
    maximum = max_header_bytes + 4 + max_body_bytes

    for chunk in chunks:
        if not isinstance(chunk, bytes):
            raise HttpReadError(
                "HTTP chunks must be bytes"
            )

        if len(buffer) + len(chunk) > maximum:
            raise HttpReadError(
                "HTTP response exceeds total limit"
            )

        buffer.extend(chunk)

        separator = buffer.find(
            b"\r\n\r\n"
        )

        if separator < 0:
            if len(buffer) > max_header_bytes + 3:
                raise HttpReadError(
                    "HTTP headers exceed limit"
                )
            continue

        if separator > max_header_bytes:
            raise HttpReadError(
                "HTTP headers exceed limit"
            )

        if (
            len(buffer) - separator - 4
            > max_body_bytes
        ):
            raise HttpReadError(
                "HTTP body exceeds limit"
            )

    if not buffer:
        raise HttpReadError(
            "Empty HTTP response"
        )

    try:
        return parse_http_response(
            bytes(buffer),
            max_body_bytes=max_body_bytes,
        )
    except HttpResponseError as exc:
        raise HttpReadError(
            "Invalid or incomplete HTTP response"
        ) from exc
