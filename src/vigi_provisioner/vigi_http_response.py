"""
Restricted offline HTTP/1.1 response parser.

No sockets, no network transmission.
"""

import json
import re
from dataclasses import dataclass


class HttpResponseError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedHttpResponse:
    status_code: int
    headers: dict
    body: bytes
    json_body: object


def parse_http_response(
    data,
    *,
    max_body_bytes=65536,
):
    if not isinstance(data, bytes):
        raise HttpResponseError(
            "HTTP response must be bytes"
        )

    if (
        type(max_body_bytes) is not int
        or not 1 <= max_body_bytes <= 1048576
    ):
        raise HttpResponseError(
            "Invalid body size limit"
        )

    if len(data) > max_body_bytes + 16384:
        raise HttpResponseError(
            "HTTP response too large"
        )

    head, separator, body = data.partition(
        b"\r\n\r\n"
    )

    if not separator:
        raise HttpResponseError(
            "Missing HTTP header separator"
        )

    if len(head) > 16384:
        raise HttpResponseError(
            "HTTP headers too large"
        )

    try:
        lines = head.decode("ascii").split(
            "\r\n"
        )
    except UnicodeDecodeError as exc:
        raise HttpResponseError(
            "Non-ASCII HTTP headers"
        ) from exc

    status = re.fullmatch(
        r"HTTP/1\.1 ([0-9]{3})(?: [ -~]*)?",
        lines[0],
    )

    if status is None:
        raise HttpResponseError(
            "Invalid HTTP status line"
        )

    status_code = int(status.group(1))

    if not 100 <= status_code <= 599:
        raise HttpResponseError(
            "Invalid HTTP status code"
        )

    headers = {}

    for line in lines[1:]:
        if not line or ":" not in line:
            raise HttpResponseError(
                "Malformed HTTP header"
            )

        name, value = line.split(":", 1)

        if name != name.strip():
            raise HttpResponseError(
                "Whitespace in HTTP header name"
            )

        if not re.fullmatch(
            r"[A-Za-z0-9-]+",
            name,
        ):
            raise HttpResponseError(
                "Invalid HTTP header name"
            )

        name = name.lower()

        if any(
            ord(char) < 32 or ord(char) == 127
            for char in value
            if char != " " and char != "\t"
        ):
            raise HttpResponseError(
                "Invalid HTTP header value"
            )

        value = value.strip(" \t")

        if name in headers:
            raise HttpResponseError(
                "Duplicate HTTP header"
            )

        headers[name] = value

    if "transfer-encoding" in headers:
        raise HttpResponseError(
            "Transfer-Encoding unsupported"
        )

    if "trailer" in headers:
        raise HttpResponseError(
            "HTTP trailers unsupported"
        )

    connection = headers.get("connection")

    if (
        connection is not None
        and connection.lower() != "close"
    ):
        raise HttpResponseError(
            "Unsupported Connection header"
        )

    encoding = headers.get("content-encoding")

    if (
        encoding is not None
        and encoding.lower() != "identity"
    ):
        raise HttpResponseError(
            "Compressed responses unsupported"
        )

    if 100 <= status_code < 200:
        raise HttpResponseError(
            "Informational responses unsupported"
        )

    if "content-length" not in headers:
        raise HttpResponseError(
            "Content-Length required"
        )

    length_text = headers["content-length"]

    if not re.fullmatch(
        r"[0-9]+",
        length_text,
    ):
        raise HttpResponseError(
            "Invalid Content-Length"
        )

    if len(length_text) > 10:
        raise HttpResponseError(
            "Excessive Content-Length digits"
        )

    expected_length = int(length_text)

    if expected_length > max_body_bytes:
        raise HttpResponseError(
            "HTTP body exceeds limit"
        )

    if len(body) != expected_length:
        raise HttpResponseError(
            "HTTP body length mismatch"
        )

    content_type = headers.get(
        "content-type",
        "",
    ).lower()

    if content_type not in (
        "application/json",
        "application/json;charset=utf-8",
        "application/json; charset=utf-8",
    ):
        raise HttpResponseError(
            "Unexpected response content type"
        )

    def unique_object(pairs):
        result = {}

        for key, value in pairs:
            if key in result:
                raise ValueError(
                    "Duplicate JSON key"
                )
            result[key] = value

        return result

    def reject_constant(value):
        raise ValueError(
            "Nonstandard JSON constant"
        )

    try:
        json_body = json.loads(
            body.decode("utf-8"),
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
        )
    except (UnicodeError, ValueError) as exc:
        raise HttpResponseError(
            "Invalid response JSON"
        ) from exc

    return ParsedHttpResponse(
        status_code=status_code,
        headers=headers,
        body=body,
        json_body=json_body,
    )
