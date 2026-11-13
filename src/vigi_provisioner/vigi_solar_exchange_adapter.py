"""JSON exchange adapter for Solar authentication."""

import json


class SolarExchangeAdapter:
    """Adapt SolarHTTPTransport.send to exchange(uri, request)."""

    def __init__(self, transport):
        if not callable(getattr(transport, "send", None)):
            raise TypeError("transport must provide send()")
        self.transport = transport

    def __call__(self, uri, request):
        if not isinstance(request, dict):
            raise TypeError("Solar exchange request must be a dictionary")

        body = json.dumps(
            request,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

        response_body, response_headers = self.transport.send(
            uri,
            body,
            {
                "Content-Type": "application/json",
                "If-encrypt": "0",
            },
        )

        if not isinstance(response_body, bytes):
            raise TypeError("Solar exchange response must be bytes")

        try:
            result = json.loads(response_body)
        except (UnicodeDecodeError, ValueError) as exc:
            raise ValueError(
                "Invalid Solar exchange JSON response"
            ) from exc

        if not isinstance(result, dict):
            raise ValueError(
                "Solar exchange response must be a dictionary"
            )

        return result
