from .vigi_inventory import normalize_mac


class StaticIPVerificationError(ValueError):
    pass


def verify_static_ip_readback(
    *,
    plan,
    discovered_device,
    interfaces,
    gateways,
):
    """
    Verify observations collected AFTER a configuration attempt.

    Does not discover devices, contact cameras, or update SQLite.
    """

    failures = []

    expected_mac = normalize_mac(plan["mac"])
    expected_ip = plan["target_ip"]
    expected_prefix = plan["prefix_length"]
    expected_gateway = plan["gateway"]
    expected_token = plan["interface_token"]

    if not discovered_device:
        failures.append("camera_not_rediscovered")
    else:
        try:
            actual_mac = normalize_mac(
                discovered_device["mac"]
            )
        except (KeyError, TypeError, ValueError):
            actual_mac = None

        if actual_mac != expected_mac:
            failures.append("camera_mac_mismatch")

        if discovered_device.get("ip") != expected_ip:
            failures.append("camera_ip_mismatch")

    matching = [
        interface
        for interface in (interfaces or [])
        if interface.get("token") == expected_token
    ]

    if len(matching) != 1:
        failures.append("interface_not_found")
    else:
        interface = matching[0]

        try:
            interface_mac = normalize_mac(
                interface["mac"]
            )
        except (KeyError, TypeError, ValueError):
            interface_mac = None

        if interface_mac != expected_mac:
            failures.append("interface_mac_mismatch")

        if interface.get("enabled") is not True:
            failures.append("interface_not_enabled")

        if interface.get("dhcp") is not False:
            failures.append("dhcp_not_disabled")

        expected_address = {
            "address": expected_ip,
            "prefix_length": expected_prefix,
        }

        if expected_address not in (
            interface.get("manual") or []
        ):
            failures.append("static_address_mismatch")

    if expected_gateway not in (gateways or []):
        failures.append("gateway_mismatch")

    return {
        "verified": len(failures) == 0,
        "mac": expected_mac,
        "target_ip": expected_ip,
        "failures": failures,
        "inventory_updated": False,
    }
