"""
TP-Link VIGI HTTPS initialization client.

Step 690: dry-run implementation only.

No network transmission functionality is implemented.
"""

import json
from dataclasses import dataclass
from urllib.parse import urlsplit

from .vigi_activation import build_activation_request


@dataclass(frozen=True)
class PreparedInitialization:
    url: str
    method: str
    headers: dict
    body: bytes

    def summary(self):
        payload = json.loads(self.body)

        settings = payload.get("set_password", {})

        return {
            "url": self.url,
            "method": self.method,
            "content_type": self.headers.get("Content-Type"),
            "body_bytes": len(self.body),
            "request_method": payload.get("method"),
            "username": settings.get("username"),
            "password_type": settings.get("passwdType"),
            "email_present": bool(
                settings.get("reset_pwd_email")
            ),
            "ciphertext_present": bool(
                settings.get("ciphertext")
            ),
            "network_transmission": False,
        }


def prepare_initialization(
    ip,
    password,
    email,
    username="admin",
    language="English",
    port=443,
):
    """
    Construct an HTTPS initialization request.

    This function never opens a network connection.
    """

    if not isinstance(ip, str) or not ip:
        raise ValueError("Invalid camera IP")

    import ipaddress

    address = ipaddress.IPv4Address(ip)

    if not isinstance(port, int) or isinstance(port, bool):
        raise ValueError("Invalid HTTPS port")

    if not 1 <= port <= 65535:
        raise ValueError("Invalid HTTPS port")

    if not isinstance(password, str) or not password:
        raise ValueError("Password must not be empty")

    if not isinstance(email, str):
        raise ValueError("Email must be a string")

    payload = build_activation_request(
        password=password,
        username=username,
        email=email,
        language=language,
    )

    body = json.dumps(
        payload,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")

    return PreparedInitialization(
        url=f"https://{address}:{port}/",
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        body=body,
    )


def dry_run(
    ip,
    password,
    email,
    username="admin",
    language="English",
    port=443,
):
    prepared = prepare_initialization(
        ip=ip,
        password=password,
        email=email,
        username=username,
        language=language,
        port=port,
    )

    return prepared.summary()
