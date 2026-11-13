from .vigi_https_client import VigiHttpsClient
from .vigi_activation_safety import DeviceObservation, activation_allowed


def inspect_device(device, *, authorized_macs=()):
    authorized_macs = {mac.lower().replace(":", "-") for mac in authorized_macs}
    result = {
        "ip": device["ip"],
        "mac": device["mac"],
        "factory_flag": device["factory_flag"],
        "http_status": None,
        "https_error": None,
    }

    try:
        client = VigiHttpsClient(device["ip"])
        response = client.post({
            "method": "get",
            "system": {"basic": {}},
        })

        result["http_status"] = response.get("http_status")
        data = response.get("data")

        if isinstance(data, dict):
            nested = data.get("data")
            if isinstance(nested, dict):
                result["https_error"] = nested.get("code")

    except Exception as exc:
        result["https_failure"] = type(exc).__name__

    normalized_mac = result["mac"].lower().replace(":", "-")

    observation = DeviceObservation(
        mac=result["mac"],
        inventory_match=normalized_mac in authorized_macs,
        factory_flag=result["factory_flag"],
        https_error=result["https_error"],
    )

    allowed, reason = activation_allowed(observation)

    result["activation_allowed"] = allowed
    result["reason"] = reason

    return result
