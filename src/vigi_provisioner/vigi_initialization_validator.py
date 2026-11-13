"""
Validate a prepared VIGI initialization request.

This module never opens a network connection.
It does not authorize transmission.
"""

import base64
import binascii
import ipaddress
import json
import re
from urllib.parse import urlsplit

from .vigi_https_init import PreparedInitialization


class InitializationValidationError(ValueError):
    pass


def validate_initialization(
    prepared,
    *,
    approved_ip,
    approved_port=443,
):
    if not isinstance(prepared, PreparedInitialization):
        raise InitializationValidationError(
            "Expected PreparedInitialization"
        )

    try:
        expected_ip = str(
            ipaddress.IPv4Address(approved_ip)
        )
    except (ValueError, TypeError) as exc:
        raise InitializationValidationError(
            "Invalid approved camera IP"
        ) from exc

    if (
        type(approved_port) is not int
        or not 1 <= approved_port <= 65535
    ):
        raise InitializationValidationError(
            "Invalid approved HTTPS port"
        )

    if not isinstance(prepared.url, str):
        raise InitializationValidationError(
            "Invalid initialization URL"
        )

    try:
        parsed = urlsplit(prepared.url)
        port = parsed.port
    except ValueError as exc:
        raise InitializationValidationError(
            "Malformed initialization URL"
        ) from exc

    canonical_url = (
        f"https://{expected_ip}:{approved_port}/"
    )

    if (
        prepared.url != canonical_url
        or parsed.scheme != "https"
        or parsed.hostname != expected_ip
        or port != approved_port
        or parsed.path != "/"
        or parsed.query
        or parsed.fragment
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise InitializationValidationError(
            "Initialization destination not approved"
        )

    if prepared.method != "POST":
        raise InitializationValidationError(
            "Initialization requires POST"
        )

    if not isinstance(prepared.headers, dict):
        raise InitializationValidationError(
            "Invalid HTTP headers"
        )

    content_type = prepared.headers.get(
        "Content-Type"
    )

    if content_type not in (
        "application/json",
        "application/json;charset=UTF-8",
    ):
        raise InitializationValidationError(
            "Unexpected content type"
        )

    if prepared.headers.get("Accept") != "application/json":
        raise InitializationValidationError(
            "Unexpected Accept header"
        )

    if set(prepared.headers) != {
        "Content-Type",
        "Accept",
    }:
        raise InitializationValidationError(
            "Unexpected HTTP headers"
        )

    if (
        not isinstance(prepared.body, bytes)
        or not prepared.body
        or len(prepared.body) > 65536
    ):
        raise InitializationValidationError(
            "Invalid initialization body"
        )

    try:
        def unique_object(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError(
                        "Duplicate JSON key"
                    )
                result[key] = value
            return result

        payload = json.loads(
            prepared.body.decode("utf-8"),
            object_pairs_hook=unique_object,
        )
    except (UnicodeError, ValueError) as exc:
        raise InitializationValidationError(
            "Invalid initialization JSON"
        ) from exc

    if not isinstance(payload, dict):
        raise InitializationValidationError(
            "Expected JSON object"
        )

    if set(payload) != {
        "method",
        "set_password",
    } or payload["method"] != "do":
        raise InitializationValidationError(
            "Unexpected initialization operation"
        )

    settings = payload["set_password"]

    if not isinstance(settings, dict):
        raise InitializationValidationError(
            "Invalid password settings"
        )

    required = {
        "password",
        "username",
        "passwdType",
        "reset_pwd_email",
        "preset_ipc_passwd",
        "preset_ipc_email",
        "ciphertext",
        "language",
    }

    if set(settings) != required:
        raise InitializationValidationError(
            "Unexpected initialization fields"
        )

    for name in (
        "password",
        "username",
        "passwdType",
        "ciphertext",
        "language",
    ):
        if (
            not isinstance(settings[name], str)
            or not settings[name]
        ):
            raise InitializationValidationError(
                "Missing required initialization value"
            )

    if not isinstance(
        settings["reset_pwd_email"], str
    ):
        raise InitializationValidationError(
            "Invalid recovery email"
        )

    if (
        settings["username"] != "admin"
        or settings["passwdType"] != "md5"
        or settings["preset_ipc_passwd"] is not None
        or settings["preset_ipc_email"] is not None
    ):
        raise InitializationValidationError(
            "Unexpected initialization settings"
        )

    if not re.fullmatch(
        r"[0-9A-F]{32}",
        settings["password"],
    ):
        raise InitializationValidationError(
            "Invalid password digest"
        )

    try:
        ciphertext_bytes = base64.b64decode(
            settings["ciphertext"],
            validate=True,
        )
    except (ValueError, binascii.Error) as exc:
        raise InitializationValidationError(
            "Invalid RSA ciphertext encoding"
        ) from exc

    if not ciphertext_bytes:
        raise InitializationValidationError(
            "Empty RSA ciphertext"
        )

    return {
        "valid": True,
        "camera_ip": expected_ip,
        "https_port": approved_port,
        "method": "POST",
        "path": "/",
        "body_bytes": len(prepared.body),
        "transmitted": False,
    }
