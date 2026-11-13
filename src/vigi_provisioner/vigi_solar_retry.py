"""Controlled retry for authenticated VIGI Solar requests."""

import json

from .vigi_solar_request import build_authenticated_solar_request


DEVICE_NO_AUTH = -40401


def execute_with_solar_retry(
    request,
    authenticate,
    send,
    invalidate,
    retry_allowed=None,
):
    """Execute a Solar request, retrying once after DEVICE_NO_AUTH.

    authenticate() returns an authentication context with a .token
    attribute. send(context, request_json) returns decoded JSON text
    or a response dictionary. invalidate() clears the current session.

    This helper does not perform network I/O itself.
    """

    for attempt in range(2):
        context = authenticate()

        request_json = build_authenticated_solar_request(
            request,
            context.token,
        )

        response = send(context, request_json)

        if isinstance(response, str):
            response = json.loads(response)

        if not isinstance(response, dict):
            raise ValueError("Solar response must be a JSON object")

        error_code = response.get("errorCode")

        if type(error_code) is not int:
            raise ValueError("Solar response has invalid errorCode")

        if error_code != DEVICE_NO_AUTH:
            return response

        if attempt == 0:
            allowed = (
                True
                if retry_allowed is None
                else retry_allowed()
            )
            invalidate()
            if allowed:
                continue
            return response

        invalidate()
        return response

    raise RuntimeError("Unexpected Solar retry state")
