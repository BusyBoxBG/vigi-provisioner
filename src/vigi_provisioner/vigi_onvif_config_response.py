import xml.etree.ElementTree as ET

SOAP_NS = "http://www.w3.org/2003/05/soap-envelope"
DEVICE_NS = "http://www.onvif.org/ver10/device/wsdl"

OPERATIONS = {
    "SetNetworkInterfaces",
    "SetNetworkDefaultGateway",
}


class ONVIFConfigurationResponseError(ValueError):
    pass


def classify_configuration_response(
    *,
    operation,
    http_status=None,
    response_body=None,
    connection_error=None,
):
    """
    Classify a configuration response without network activity.

    A missing response after transmission is an unknown outcome,
    not proof that the configuration failed.
    """

    if operation not in OPERATIONS:
        raise ONVIFConfigurationResponseError(
            "Unsupported ONVIF operation"
        )

    if connection_error is not None:
        return {
            "operation": operation,
            "status": "unknown",
            "confirmed": False,
            "reason": "connection_interrupted",
        }

    if http_status is None:
        return {
            "operation": operation,
            "status": "unknown",
            "confirmed": False,
            "reason": "missing_http_response",
        }

    try:
        status_code = int(http_status)
    except (TypeError, ValueError) as exc:
        raise ONVIFConfigurationResponseError(
            "Invalid HTTP status"
        ) from exc

    if not 100 <= status_code <= 599:
        raise ONVIFConfigurationResponseError(
            "HTTP status outside valid range"
        )

    if not response_body:
        return {
            "operation": operation,
            "status": (
                "unknown"
                if status_code == 200
                else "http_error"
            ),
            "confirmed": False,
            "reason": "empty_response",
        }

    try:
        root = ET.fromstring(response_body)
    except (ET.ParseError, TypeError):
        return {
            "operation": operation,
            "status": (
                "unknown"
                if status_code == 200
                else "http_error"
            ),
            "confirmed": False,
            "reason": "invalid_soap",
        }

    ns = {
        "s": SOAP_NS,
        "tds": DEVICE_NS,
    }

    fault = root.find(
        "./s:Body/s:Fault",
        ns,
    )

    if fault is not None:
        return {
            "operation": operation,
            "status": "soap_fault",
            "confirmed": False,
            "reason": "soap_fault_returned",
        }

    if status_code != 200:
        return {
            "operation": operation,
            "status": "http_error",
            "confirmed": False,
            "reason": f"http_{status_code}",
        }

    if root.tag != f"{{{SOAP_NS}}}Envelope":
        return {
            "operation": operation,
            "status": "unknown",
            "confirmed": False,
            "reason": "unexpected_soap_envelope",
        }

    body = root.find("./s:Body", ns)

    expected = (
        f"{{{DEVICE_NS}}}{operation}Response"
    )

    if body is None or len(body) != 1:
        return {
            "operation": operation,
            "status": "unknown",
            "confirmed": False,
            "reason": "unexpected_soap_body",
        }

    if body[0].tag != expected:
        return {
            "operation": operation,
            "status": "unknown",
            "confirmed": False,
            "reason": "unexpected_response_operation",
        }

    if operation == "SetNetworkInterfaces":
        reboot_elements = list(body[0])

        if not reboot_elements:
            reboot_needed = None
        elif (
            len(reboot_elements) == 1
            and reboot_elements[0].tag
            == f"{{{DEVICE_NS}}}RebootNeeded"
            and not reboot_elements[0].attrib
            and len(reboot_elements[0]) == 0
        ):
            reboot_text = (
                reboot_elements[0].text or ""
            ).strip()

            if reboot_text in ("true", "1"):
                reboot_needed = True
            elif reboot_text in ("false", "0"):
                reboot_needed = False
            else:
                return {
                    "operation": operation,
                    "status": "unknown",
                    "confirmed": False,
                    "reason": "invalid_reboot_needed",
                    "reboot_needed": None,
                }
        else:
            return {
                "operation": operation,
                "status": "unknown",
                "confirmed": False,
                "reason": "unexpected_interface_response",
                "reboot_needed": None,
            }

        return {
            "operation": operation,
            "status": "success",
            "confirmed": True,
            "reason": "expected_soap_response",
            "reboot_needed": reboot_needed,
        }

    if len(body[0]) or body[0].attrib:
        return {
            "operation": operation,
            "status": "unknown",
            "confirmed": False,
            "reason": "unexpected_gateway_response",
        }

    return {
        "operation": operation,
        "status": "success",
        "confirmed": True,
        "reason": "expected_soap_response",
    }
