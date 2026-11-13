import ipaddress
import xml.etree.ElementTree as ET


SOAP_NS = "http://www.w3.org/2003/05/soap-envelope"
DEVICE_NS = "http://www.onvif.org/ver10/device/wsdl"
SCHEMA_NS = "http://www.onvif.org/ver10/schema"


class StaticIPExecutionPlanError(ValueError):
    pass


def validate_static_ip_execution_plan(plan):
    """
    Validate prepared ONVIF configuration operations.

    This function performs no network activity.
    """

    if plan.get("transmitted") is not False:
        raise StaticIPExecutionPlanError(
            "Plan must not have been transmitted"
        )

    try:
        current_ip = ipaddress.IPv4Address(
            plan["current_ip"]
        )

        target_ip = ipaddress.IPv4Address(
            plan["target_ip"]
        )

        gateway = ipaddress.IPv4Address(
            plan["gateway"]
        )

        prefix = plan["prefix_length"]

        if (
            isinstance(prefix, bool)
            or not isinstance(prefix, int)
            or not 1 <= prefix <= 30
        ):
            raise ValueError("Invalid prefix")

        network = ipaddress.IPv4Network(
            f"{target_ip}/{prefix}",
            strict=False,
        )

        if target_ip not in network.hosts():
            raise ValueError("Invalid target host")

        if gateway not in network.hosts():
            raise ValueError("Gateway outside subnet")

        if target_ip == gateway:
            raise ValueError("Target equals gateway")

        if plan["dhcp"] is not False:
            raise ValueError("DHCP must be disabled")

        interface_root = ET.fromstring(
            plan["set_network_interfaces_soap"]
        )

        gateway_root = ET.fromstring(
            plan["set_network_default_gateway_soap"]
        )

    except (KeyError, ValueError, TypeError, ET.ParseError) as exc:
        raise StaticIPExecutionPlanError(
            "Invalid static IP execution plan"
        ) from exc

    ns = {
        "s": SOAP_NS,
        "tds": DEVICE_NS,
        "tt": SCHEMA_NS,
    }

    interface_operation = interface_root.find(
        ".//tds:SetNetworkInterfaces",
        ns,
    )

    gateway_operation = gateway_root.find(
        ".//tds:SetNetworkDefaultGateway",
        ns,
    )

    if interface_operation is None:
        raise StaticIPExecutionPlanError(
            "Missing SetNetworkInterfaces"
        )

    if gateway_operation is None:
        raise StaticIPExecutionPlanError(
            "Missing SetNetworkDefaultGateway"
        )

    token = interface_operation.find(
        "tds:InterfaceToken",
        ns,
    )

    if (
        token is None
        or token.text != plan["interface_token"]
    ):
        raise StaticIPExecutionPlanError(
            "Interface token mismatch"
        )

    address = interface_operation.find(
        ".//tt:Manual/tt:Address",
        ns,
    )

    prefix_element = interface_operation.find(
        ".//tt:Manual/tt:PrefixLength",
        ns,
    )

    dhcp = interface_operation.find(
        ".//tt:IPv4/tt:DHCP",
        ns,
    )

    if (
        address is None
        or address.text != str(target_ip)
        or prefix_element is None
        or prefix_element.text != str(prefix)
        or dhcp is None
        or dhcp.text.lower() != "false"
    ):
        raise StaticIPExecutionPlanError(
            "Static IPv4 SOAP content mismatch"
        )

    gateway_element = gateway_operation.find(
        "tds:IPv4Address",
        ns,
    )

    if (
        gateway_element is None
        or gateway_element.text != str(gateway)
    ):
        raise StaticIPExecutionPlanError(
            "Gateway SOAP content mismatch"
        )

    return {
        "current_ip": str(current_ip),
        "target_ip": str(target_ip),
        "prefix_length": prefix,
        "gateway": str(gateway),
        "interface_token": plan["interface_token"],
        "operations": [
            "SetNetworkDefaultGateway",
            "SetNetworkInterfaces",
        ],
        "transmitted": False,
        "validated": True,
    }
