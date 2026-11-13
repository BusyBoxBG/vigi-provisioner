import ipaddress
import xml.etree.ElementTree as ET


SOAP_NS = "http://www.w3.org/2003/05/soap-envelope"
DEVICE_NS = "http://www.onvif.org/ver10/device/wsdl"
SCHEMA_NS = "http://www.onvif.org/ver10/schema"


class GatewayPreparationError(ValueError):
    pass


def prepare_default_gateway(*, gateway):
    """
    Prepare ONVIF SetNetworkDefaultGateway.

    This function does not transmit the request.
    """

    try:
        address = ipaddress.IPv4Address(gateway)
    except (ipaddress.AddressValueError, ValueError) as exc:
        raise GatewayPreparationError(
            "Invalid IPv4 gateway"
        ) from exc

    if (
        address.is_unspecified
        or address.is_multicast
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or int(address) == 0xFFFFFFFF
    ):
        raise GatewayPreparationError(
            "Gateway is not a usable unicast address"
        )

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
        f"{{{DEVICE_NS}}}SetNetworkDefaultGateway"
    )

    ipv4 = ET.SubElement(
        operation,
        f"{{{DEVICE_NS}}}IPv4Address"
    )

    ipv4.text = str(address)

    soap = ET.tostring(
        envelope,
        encoding="utf-8",
        xml_declaration=True,
    )

    return {
        "gateway": str(address),
        "soap": soap,
        "transmitted": False,
    }
