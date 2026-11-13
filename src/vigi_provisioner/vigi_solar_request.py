"""Build authenticated TP-Link VIGI Solar request JSON."""

import json
from collections.abc import Mapping


def build_authenticated_solar_request(request, token):
    """Insert the Solar token into the top-level JSON object.

    Returns a JSON string suitable for the Solar encryption layer.
    Does not modify the original request.
    """
    if not isinstance(token, str) or not token:
        raise ValueError("Solar token must be a nonempty string")

    if not isinstance(request, Mapping):
        raise ValueError("Solar request must be a JSON object")

    if not all(isinstance(key, str) for key in request):
        raise ValueError("Solar request keys must be strings")

    result = dict(request)
    result["token"] = token

    return json.dumps(
        result,
        ensure_ascii=False,
        separators=(",", ":"),
    )
