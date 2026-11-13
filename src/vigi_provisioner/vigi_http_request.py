from urllib.parse import urlsplit

from .vigi_initialization_validator import validate_initialization


class HttpRequestSerializationError(ValueError):
    pass


def serialize_initialization_request(
    prepared,
    *,
    approved_ip,
    approved_port=443,
):
    """
    Serialize a validated initialization request.

    No network activity occurs here.
    """

    validation = validate_initialization(
        prepared,
        approved_ip=approved_ip,
        approved_port=approved_port,
    )

    if validation.get("valid") is not True:
        raise HttpRequestSerializationError(
            "Initialization request not validated"
        )

    parsed = urlsplit(prepared.url)

    if parsed.hostname != approved_ip:
        raise HttpRequestSerializationError(
            "Destination mismatch"
        )

    if parsed.port != approved_port:
        raise HttpRequestSerializationError(
            "Port mismatch"
        )

    body = prepared.body

    if type(body) is not bytes:
        raise HttpRequestSerializationError(
            "Body must be bytes"
        )

    request_head = (
        "POST / HTTP/1.1\r\n"
        f"Host: {approved_ip}:{approved_port}\r\n"
        "Content-Type: application/json\r\n"
        "Accept: application/json\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Connection: close\r\n"
        "\r\n"
    ).encode("ascii")

    return request_head + body
