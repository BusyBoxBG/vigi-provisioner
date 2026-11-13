import re
import base64
import binascii
"""Restricted HTTP transport for VIGI Solar requests."""

from urllib.parse import urlsplit, parse_qsl, urlencode
import ipaddress

import requests


class SolarHTTPTransport:
    def __init__(self, allowed_ip, timeout=5, allowed_port=None):
        self.allowed_ip = str(
            ipaddress.ip_address(allowed_ip)
        )

        if allowed_port is None:
            raise ValueError("An approved port is required")

        if type(allowed_port) is not int or not (1 <= allowed_port <= 65535):
            raise ValueError("Invalid approved port")

        self.allowed_port = allowed_port

        if timeout <= 0:
            raise ValueError("Timeout must be positive")

        self.timeout = timeout
        self.session = requests.Session()
        self.session.trust_env = False

    @staticmethod
    def validate_headers(headers):
        """Validate and normalize caller-controlled Solar headers."""

        if not isinstance(headers, dict):
            raise ValueError("HTTP headers must be a dictionary")

        allowed = {
            "content-type": "Content-Type",
            "accept": "Accept",
            "connection": "Connection",
            "if-encrypt": "If-encrypt",
            "auth-tag": "Auth-Tag",
        }

        result = {}

        for name, value in headers.items():
            if not isinstance(name, str):
                raise ValueError("Invalid HTTP header name")

            normalized = name.lower()

            if normalized not in allowed:
                raise ValueError(
                    "Unauthorized HTTP header: " + name
                )

            canonical = allowed[normalized]

            if canonical in result:
                raise ValueError("Duplicate HTTP header")

            if not isinstance(value, str):
                raise ValueError("HTTP header value must be a string")

            if "\r" in value or "\n" in value:
                raise ValueError("Invalid HTTP header value")

            if canonical == "Content-Type":
                if value.lower() != "application/json;charset=utf-8" and value.lower() != "application/json":
                    raise ValueError("Unsupported Content-Type")

            elif canonical == "Accept":
                if value.lower() != "application/json":
                    raise ValueError("Unsupported Accept")

            elif canonical == "Connection":
                if value.lower() != "close":
                    raise ValueError("Only Connection: close is permitted")

            elif canonical == "If-encrypt":
                if value not in ("0", "1"):
                    raise ValueError("Invalid If-encrypt value")

            elif canonical == "Auth-Tag":
                try:
                    decoded = base64.b64decode(
                        value,
                        validate=True,
                    )
                except (ValueError, binascii.Error):
                    raise ValueError("Invalid Auth-Tag encoding")

                if len(decoded) != 16:
                    raise ValueError("Invalid Auth-Tag length")

            result[canonical] = value

        if "Auth-Tag" in result and result.get("If-encrypt") != "1":
            raise ValueError(
                "Auth-Tag requires If-encrypt: 1"
            )

        return result

    def send(self, uri, body, headers):
        parsed = urlsplit(uri)

        if parsed.scheme != "http":
            raise ValueError("Only HTTP Solar URIs are permitted")

        if parsed.username is not None or parsed.password is not None:
            raise ValueError("URI credentials are prohibited")

        if parsed.hostname != self.allowed_ip:
            raise ValueError("Solar URI host is not authorized")

        if parsed.path not in ("", "/"):
            raise ValueError("Unexpected Solar URI path")

        if parsed.port != self.allowed_port:
            raise ValueError("Solar URI port is not authorized")

        if parsed.fragment:
            raise ValueError("URI fragments are prohibited")

        # Canonical Solar endpoints only.
        canonical_base = (
            f"http://{self.allowed_ip}:{self.allowed_port}/"
        )

        if uri != canonical_base:
            prefix = canonical_base + "?sid="

            if not uri.startswith(prefix):
                raise ValueError("Noncanonical Solar endpoint")

            session_query = parse_qsl(
                parsed.query,
                keep_blank_values=True,
                strict_parsing=True,
            )

            if (
                len(session_query) != 1
                or session_query[0][0] != "sid"
            ):
                raise ValueError("Invalid Solar session query")

            session_id = session_query[0][1]

            if (
                not session_id
                or len(session_id) > 256
                or not re.fullmatch(
                    r"[A-Za-z0-9._~+/=%:-]+",
                    session_id,
                    flags=re.ASCII,
                )
            ):
                raise ValueError("Invalid Solar session ID")

            canonical_uri = canonical_base + "?" + urlencode(
                {"sid": session_id}
            )

            if uri != canonical_uri:
                raise ValueError("Noncanonical Solar session URI")

        query = parse_qsl(
            parsed.query,
            keep_blank_values=True,
        )

        if query:
            if (
                len(query) != 1
                or query[0][0] != "sid"
                or not query[0][1]
            ):
                raise ValueError("Invalid Solar URI query")

        if not isinstance(body, bytes):
            raise TypeError("Solar request body must be bytes")

        safe_headers = self.validate_headers(headers)

        response = self.session.post(
            uri,
            data=body,
            headers=safe_headers,
            timeout=self.timeout,
            allow_redirects=False,
        )

        if 300 <= response.status_code < 400:
            raise ValueError("Solar HTTP redirects are prohibited")

        response.raise_for_status()

        return response.content, dict(response.headers)

    def close(self):
        self.session.close()
