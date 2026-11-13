from .vigi_static_ip_execution_plan import (
    validate_static_ip_execution_plan,
)
from .vigi_onvif_config_response import (
    classify_configuration_response,
)
from .vigi_onvif_soap_strict import (
    validate_strict_soap,
)


class StaticIPCoordinatorError(ValueError):
    pass


def execute_with_transport(*, plan, transport):
    """
    Execute an approved plan using an injected transport.

    The caller controls the transport. This module does not
    implement HTTP, ONVIF authentication, or camera access.

    The result is NOT proof that camera settings were applied.
    """

    validated = validate_static_ip_execution_plan(plan)
    validate_strict_soap(plan)

    operations = [
        (
            "SetNetworkDefaultGateway",
            plan["set_network_default_gateway_soap"],
        ),
        (
            "SetNetworkInterfaces",
            plan["set_network_interfaces_soap"],
        ),
    ]

    if validated["operations"] != [
        name for name, _ in operations
    ]:
        raise StaticIPCoordinatorError(
            "Unexpected operation sequence"
        )

    history = []
    reboot_needed = None

    for operation, soap in operations:
        try:
            response = transport(operation, soap)

            if not isinstance(response, dict):
                raise TypeError(
                    "Transport must return a dictionary"
                )

            classification = classify_configuration_response(
                operation=operation,
                http_status=response.get("http_status"),
                response_body=response.get("response_body"),
            )

        except Exception:
            classification = classify_configuration_response(
                operation=operation,
                connection_error="transport_exception",
            )

        history.append(classification)

        if operation == "SetNetworkInterfaces":
            reboot_needed = classification.get(
                "reboot_needed"
            )

        if not classification["confirmed"]:
            return {
                "status": "stopped",
                "failed_or_unknown_operation": operation,
                "history": history,
                "reboot_needed": reboot_needed,
                "requires_rediscovery": (
                    operation == "SetNetworkInterfaces"
                    or classification["status"] == "unknown"
                ),
                "settings_verified": False,
                "inventory_updated": False,
            }

    return {
        "status": "acknowledged",
        "failed_or_unknown_operation": None,
        "history": history,
        "reboot_needed": reboot_needed,
        "requires_rediscovery": True,
        "settings_verified": False,
        "inventory_updated": False,
    }
