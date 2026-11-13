import ipaddress
import xml.etree.ElementTree as ET


SOAP_NS = "http://www.w3.org/2003/05/soap-envelope"
DEVICE_NS = "http://www.onvif.org/ver10/device/wsdl"
SCHEMA_NS = "http://www.onvif.org/ver10/schema"


class StaticIPPreparationError(ValueError):
    pass


def prepare_static_ipv4(
    *,
    interface_token,
    ip_address,
    prefix_length,
    gateway,
):
    """
    Validate and prepare a static IPv4 configuration.

    No network connection is made.
    No camera settings are changed.
    """

    if (
        not isinstance(interface_token, str)
        or not interface_token
        or len(interface_token) > 128
    ):
        raise StaticIPPreparationError(
            "Invalid network interface token"
        )

    try:
        address = ipaddress.IPv4Address(ip_address)

        if (
            isinstance(prefix_length, bool)
            or not isinstance(prefix_length, int)
            or not 1 <= prefix_length <= 30
        ):
            raise ValueError(
                "Invalid IPv4 prefix length"
            )

        network = ipaddress.IPv4Network(
            f"{address}/{prefix_length}",
            strict=False,
        )

        gateway_address = ipaddress.IPv4Address(
            gateway
        )

        if address not in network.hosts():
            raise ValueError(
                "Camera IP is not a usable host address"
            )

        if gateway_address not in network.hosts():
            raise ValueError(
                "Gateway is not in the usable subnet"
            )

        if gateway_address == address:
            raise ValueError(
                "Gateway cannot equal camera IP"
            )

    except (ipaddress.AddressValueError, ValueError) as exc:
        raise StaticIPPreparationError(str(exc)) from exc

    ET.register_namespace("s", SOAP_NS)
    ET.register_namespace("tds", DEVICE_NS)
    ET.register_namespace("tt", SCHEMA_NS)

    envelope = ET.Element(
        f"{{{SOAP_NS}}}Envelope"
    )

    body = ET.SubElement(
        envelope,
        f"{{{SOAP_NS}}}Body"
    )

    operation = ET.SubElement(
        body,
        f"{{{DEVICE_NS}}}SetNetworkInterfaces"
    )

    token = ET.SubElement(
        operation,
        f"{{{DEVICE_NS}}}InterfaceToken"
    )

    token.text = interface_token

    network_interface = ET.SubElement(
        operation,
        f"{{{DEVICE_NS}}}NetworkInterface"
    )

    ipv4 = ET.SubElement(
        network_interface,
        f"{{{SCHEMA_NS}}}IPv4"
    )

    enabled = ET.SubElement(
        ipv4,
        f"{{{SCHEMA_NS}}}Enabled"
    )

    enabled.text = "true"

    manual = ET.SubElement(
        ipv4,
        f"{{{SCHEMA_NS}}}Manual"
    )

    manual_address = ET.SubElement(
        manual,
        f"{{{SCHEMA_NS}}}Address"
    )

    manual_address.text = str(address)

    manual_prefix = ET.SubElement(
        manual,
        f"{{{SCHEMA_NS}}}PrefixLength"
    )

    manual_prefix.text = str(prefix_length)

    dhcp = ET.SubElement(
        ipv4,
        f"{{{SCHEMA_NS}}}DHCP"
    )

    dhcp.text = "false"

    soap = ET.tostring(
        envelope,
        encoding="utf-8",
        xml_declaration=True,
    )

    return {
        "interface_token": interface_token,
        "ip_address": str(address),
        "prefix_length": prefix_length,
        "subnet_mask": str(
            network.netmask
        ),
        "gateway": str(gateway_address),
        "dhcp": False,
        "soap": soap,
        "transmitted": False,
    }
