"""
Offline HTTP response reading from a recv-like stream.

Does not create sockets or establish connections.
"""

import re
import time
import math

from .vigi_http_reader import (
    HttpReadError,
    assemble_http_response,
)


class HttpStreamError(ValueError):
    pass


def read_http_stream(
    stream,
    *,
    chunk_size=4096,
    max_header_bytes=16384,
    max_body_bytes=65536,
    deadline_seconds=10.0,
    clock=None,
):
    if (
        not hasattr(stream, "recv")
        or not callable(stream.recv)
    ):
        raise HttpStreamError(
            "Stream must provide recv()"
        )

    if (
        type(chunk_size) is not int
        or not 1 <= chunk_size <= 65536
    ):
        raise HttpStreamError(
            "Invalid chunk size"
        )

    if (
        type(max_header_bytes) is not int
        or not 1 <= max_header_bytes <= 16384
    ):
        raise HttpStreamError(
            "Invalid header limit"
        )

    if (
        type(max_body_bytes) is not int
        or not 1 <= max_body_bytes <= 1048576
    ):
        raise HttpStreamError(
            "Invalid body limit"
        )

    if (
        type(deadline_seconds) not in (int, float)
        or not 0 < deadline_seconds <= 300
    ):
        raise HttpStreamError(
            "Invalid deadline"
        )

    if clock is None:
        clock = time.monotonic

    if not callable(clock):
        raise HttpStreamError(
            "Invalid clock"
        )

    def read_clock():
        try:
            value = clock()
        except Exception as exc:
            raise HttpStreamError(
                "Clock read failed"
            ) from exc

        if (
            type(value) not in (int, float)
            or not math.isfinite(value)
        ):
            raise HttpStreamError(
                "Invalid clock reading"
            )

        return value

    start_time = read_clock()
    last_time = start_time

    def check_deadline():
        nonlocal last_time

        current = read_clock()

        if current < last_time:
            raise HttpStreamError(
                "Clock moved backward"
            )

        last_time = current
        elapsed = current - start_time

        if not math.isfinite(elapsed):
            raise HttpStreamError(
                "Invalid elapsed time"
            )

        if elapsed >= deadline_seconds:
            raise HttpStreamError(
                "HTTP read deadline exceeded"
            )

    buffer = bytearray()

    # Read headers without consuming body or subsequent data.
    while not buffer.endswith(b"\r\n\r\n"):
        if len(buffer) >= max_header_bytes + 4:
            raise HttpStreamError(
                "HTTP headers exceed limit"
            )

        check_deadline()

        try:
            chunk = stream.recv(1)
        except Exception as exc:
            raise HttpStreamError(
                "Stream read failed"
            ) from exc

        check_deadline()

        if type(chunk) is not bytes or len(chunk) > 1:
            raise HttpStreamError(
                "Invalid stream data"
            )

        if not chunk:
            raise HttpStreamError(
                "HTTP headers incomplete"
            )

        buffer.extend(chunk)

    separator = len(buffer) - 4

    if separator > max_header_bytes:
        raise HttpStreamError(
            "HTTP headers exceed limit"
        )

    header = bytes(buffer[:separator])

    # Validate framing before trusting Content-Length.
    try:
        lines = header.decode("ascii").split("\r\n")
    except UnicodeDecodeError as exc:
        raise HttpStreamError(
            "Non-ASCII HTTP headers"
        ) from exc

    if not lines or not re.fullmatch(
        r"HTTP/1\.1 [1-5][0-9]{2}(?: [ -~]*)?",
        lines[0],
    ):
        raise HttpStreamError(
            "Invalid HTTP status line"
        )

    headers = {}

    for line in lines[1:]:
        if ":" not in line:
            raise HttpStreamError(
                "Malformed HTTP header"
            )

        name, value = line.split(":", 1)

        if not re.fullmatch(
            r"[A-Za-z0-9-]+",
            name,
        ):
            raise HttpStreamError(
                "Invalid HTTP header name"
            )

        if any(
            ord(char) < 32 or ord(char) == 127
            for char in value
            if char not in (" ", "\t")
        ):
            raise HttpStreamError(
                "Invalid HTTP header value"
            )

        name = name.lower()
        value = value.strip(" \t")

        if name in headers:
            raise HttpStreamError(
                "Duplicate HTTP header"
            )

        headers[name] = value

    if "transfer-encoding" in headers:
        raise HttpStreamError(
            "Transfer-Encoding unsupported"
        )

    if "trailer" in headers:
        raise HttpStreamError(
            "HTTP trailers unsupported"
        )

    connection = headers.get("connection")

    if (
        connection is not None
        and connection.lower() != "close"
    ):
        raise HttpStreamError(
            "Unsupported Connection header"
        )

    encoding = headers.get("content-encoding")

    if (
        encoding is not None
        and encoding.lower() != "identity"
    ):
        raise HttpStreamError(
            "Compressed responses unsupported"
        )

    length_text = headers.get("content-length")

    if (
        length_text is None
        or len(length_text) > 10
        or not re.fullmatch(r"[0-9]+", length_text)
    ):
        raise HttpStreamError(
            "Invalid Content-Length"
        )

    body_length = int(length_text)

    if body_length > max_body_bytes:
        raise HttpStreamError(
            "HTTP body exceeds limit"
        )

    # Read exactly the declared body length.
    remaining = body_length

    while remaining:
        requested = min(
            chunk_size,
            remaining,
        )

        check_deadline()

        try:
            chunk = stream.recv(requested)
        except Exception as exc:
            raise HttpStreamError(
                "Stream read failed"
            ) from exc

        check_deadline()

        if (
            type(chunk) is not bytes
            or len(chunk) > requested
        ):
            raise HttpStreamError(
                "Invalid stream data"
            )

        if not chunk:
            raise HttpStreamError(
                "HTTP body incomplete"
            )

        buffer.extend(chunk)
        remaining -= len(chunk)

    chunks = [bytes(buffer)]

    try:
        return assemble_http_response(
            chunks,
            max_header_bytes=max_header_bytes,
            max_body_bytes=max_body_bytes,
        )
    except HttpReadError as exc:
        raise HttpStreamError(
            "Invalid HTTP stream response"
        ) from exc
