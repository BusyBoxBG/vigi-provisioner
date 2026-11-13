import ipaddress
import xml.etree.ElementTree as ET

SOAP = "http://www.w3.org/2003/05/soap-envelope"
DEVICE = "http://www.onvif.org/ver10/device/wsdl"
SCHEMA = "http://www.onvif.org/ver10/schema"


class StrictSOAPValidationError(ValueError):
    pass


def tag(namespace, name):
    return f"{{{namespace}}}{name}"


def require_structure(element, expected_tag, children):
    if element.tag != expected_tag:
        raise StrictSOAPValidationError(
            f"Unexpected element: {element.tag}"
        )

    if element.attrib:
        raise StrictSOAPValidationError(
            "Unexpected XML attributes"
        )

    actual = [child.tag for child in element]

    if actual != children:
        raise StrictSOAPValidationError(
            f"Unexpected child structure in {element.tag}: {actual}"
        )

    if element.text and element.text.strip():
        raise StrictSOAPValidationError(
            "Unexpected text content"
        )


def require_text(element, expected):
    if len(element) or element.attrib:
        raise StrictSOAPValidationError(
            "Unexpected content in leaf element"
        )

    if (element.text or "").strip() != str(expected):
        raise StrictSOAPValidationError(
            f"Unexpected value in {element.tag}"
        )


def soap_operation(xml, operation):
    try:
        root = ET.fromstring(xml)
    except (ET.ParseError, TypeError) as exc:
        raise StrictSOAPValidationError(
            "Invalid SOAP XML"
        ) from exc

    require_structure(
        root,
        tag(SOAP, "Envelope"),
        [tag(SOAP, "Body")],
    )

    body = root[0]

    require_structure(
        body,
        tag(SOAP, "Body"),
        [tag(DEVICE, operation)],
    )

    return body[0]


def validate_strict_soap(plan):
    """
    Validate the exact SOAP structures emitted by our builders.
    Performs no network activity.

    This is structural validation, not full ONVIF XSD validation.
    """

    try:
        if plan["transmitted"] is not False:
            raise StrictSOAPValidationError(
                "Plan is not marked untransmitted"
            )

        if plan["dhcp"] is not False:
            raise StrictSOAPValidationError(
                "DHCP must be disabled"
            )

        target = ipaddress.IPv4Address(plan["target_ip"])
        gateway = ipaddress.IPv4Address(plan["gateway"])

        prefix = plan["prefix_length"]

        if (
            type(prefix) is not int
            or not 1 <= prefix <= 30
        ):
            raise StrictSOAPValidationError(
                "Invalid prefix length"
            )

        network = ipaddress.IPv4Network(
            f"{target}/{prefix}",
            strict=False,
        )

        if (
            target not in network.hosts()
            or gateway not in network.hosts()
            or target == gateway
        ):
            raise StrictSOAPValidationError(
                "Invalid target or gateway"
            )

        gateway_op = soap_operation(
            plan["set_network_default_gateway_soap"],
            "SetNetworkDefaultGateway",
        )

        require_structure(
            gateway_op,
            tag(DEVICE, "SetNetworkDefaultGateway"),
            [tag(DEVICE, "IPv4Address")],
        )

        require_text(gateway_op[0], gateway)

        interface_op = soap_operation(
            plan["set_network_interfaces_soap"],
            "SetNetworkInterfaces",
        )

        require_structure(
            interface_op,
            tag(DEVICE, "SetNetworkInterfaces"),
            [
                tag(DEVICE, "InterfaceToken"),
                tag(DEVICE, "NetworkInterface"),
            ],
        )

        require_text(
            interface_op[0],
            plan["interface_token"],
        )

        network_interface = interface_op[1]

        require_structure(
            network_interface,
            tag(DEVICE, "NetworkInterface"),
            [tag(SCHEMA, "IPv4")],
        )

        ipv4 = network_interface[0]

        require_structure(
            ipv4,
            tag(SCHEMA, "IPv4"),
            [
                tag(SCHEMA, "Enabled"),
                tag(SCHEMA, "Manual"),
                tag(SCHEMA, "DHCP"),
            ],
        )

        require_text(ipv4[0], "true")

        manual = ipv4[1]

        require_structure(
            manual,
            tag(SCHEMA, "Manual"),
            [
                tag(SCHEMA, "Address"),
                tag(SCHEMA, "PrefixLength"),
            ],
        )

        require_text(manual[0], target)
        require_text(manual[1], prefix)
        require_text(ipv4[2], "false")

    except (
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        if isinstance(exc, StrictSOAPValidationError):
            raise

        raise StrictSOAPValidationError(
            "Invalid execution plan"
        ) from exc

    return {
        "validated": True,
        "gateway_structure": "valid",
        "interface_structure": "valid",
        "target_ip": str(target),
        "prefix_length": prefix,
        "gateway": str(gateway),
        "transmitted": False,
    }
