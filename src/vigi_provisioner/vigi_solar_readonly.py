"""Strict read-only guard for initial VIGI Solar tests."""

from collections.abc import Mapping


def validate_readonly_solar_request(request):
    """Allow only the explicitly approved system.basic GET."""

    if not isinstance(request, Mapping):
        raise ValueError("Solar request must be an object")

    if set(request.keys()) != {"method", "system"}:
        raise ValueError("Solar request contains unsupported fields")

    if request["method"] != "get":
        raise ValueError("Only GET requests are permitted")

    system = request["system"]

    if not isinstance(system, Mapping):
        raise ValueError("Invalid system request")

    if set(system.keys()) != {"basic"}:
        raise ValueError("Only system.basic is permitted")

    basic = system["basic"]

    if not isinstance(basic, Mapping) or len(basic) != 0:
        raise ValueError("system.basic must be empty")

    return True
