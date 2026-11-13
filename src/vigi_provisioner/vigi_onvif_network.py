import ipaddress
import xml.etree.ElementTree as ET

import requests
from requests.auth import HTTPDigestAuth


SOAP_NS = "http://www.w3.org/2003/05/soap-envelope"
DEVICE_NS = "http://www.onvif.org/ver10/device/wsdl"
SCHEMA_NS = "http://www.onvif.org/ver10/schema"

NAMESPACES = {
    "s": SOAP_NS,
    "tds": DEVICE_NS,
    "tt": SCHEMA_NS,
}

GET_NETWORK_INTERFACES_SOAP = f"""\
<s:Envelope xmlns:s="{SOAP_NS}"
            xmlns:tds="{DEVICE_NS}">
  <s:Body>
    <tds:GetNetworkInterfaces/>
  </s:Body>
</s:Envelope>"""


class ONVIFNetworkError(RuntimeError):
    pass


def _text(parent, path):
    element = parent.find(path, NAMESPACES)
    if element is None:
        return None
    return element.text


def _parse_network_interfaces(content):
    root = ET.fromstring(content)

    fault = root.find(".//s:Fault", NAMESPACES)
    if fault is not None:
        raise ONVIFNetworkError(
            "Camera returned ONVIF SOAP fault"
        )

    interfaces = root.findall(
        ".//tds:GetNetworkInterfacesResponse/"
        "tds:NetworkInterfaces",
        NAMESPACES,
    )

    results = []

    for interface in interfaces:
        token = interface.get("token")

        mac = _text(
            interface,
            "tt:Info/tt:HwAddress",
        )

        enabled_text = _text(
            interface,
            "tt:Enabled",
        )

        dhcp_text = _text(
            interface,
            "tt:IPv4/tt:Config/tt:DHCP",
        )

        manual_addresses = []

        for address in interface.findall(
            "tt:IPv4/tt:Config/tt:Manual",
            NAMESPACES,
        ):
            ip = _text(address, "tt:Address")
            prefix = _text(address, "tt:PrefixLength")

            if ip is not None and prefix is not None:
                manual_addresses.append({
                    "address": str(
                        ipaddress.IPv4Address(ip)
                    ),
                    "prefix_length": int(prefix),
                })

        dhcp_addresses = []

        for address in interface.findall(
            "tt:IPv4/tt:Config/tt:FromDHCP",
            NAMESPACES,
        ):
            ip = _text(address, "tt:Address")
            prefix = _text(address, "tt:PrefixLength")

            if ip is not None and prefix is not None:
                dhcp_addresses.append({
                    "address": str(
                        ipaddress.IPv4Address(ip)
                    ),
                    "prefix_length": int(prefix),
                })

        results.append({
            "token": token,
            "mac": mac,
            "enabled": (
                enabled_text.lower() == "true"
                if enabled_text is not None
                else None
            ),
            "dhcp": (
                dhcp_text.lower() == "true"
                if dhcp_text is not None
                else None
            ),
            "manual": manual_addresses,
            "from_dhcp": dhcp_addresses,
        })

    return results


def get_network_interfaces(
    endpoint,
    username,
    password,
):
    """
    Read ONVIF network interfaces.

    This function sends only GetNetworkInterfaces.
    It does not modify camera settings.
    """

    session = requests.Session()
    session.trust_env = False
    session.auth = HTTPDigestAuth(
        username,
        password,
    )

    try:
        response = session.post(
            endpoint,
            data=GET_NETWORK_INTERFACES_SOAP.encode(
                "utf-8"
            ),
            headers={
                "Content-Type":
                    "application/soap+xml; charset=utf-8"
            },
            timeout=(5, 10),
            allow_redirects=False,
        )

        response.raise_for_status()

        return _parse_network_interfaces(
            response.content
        )

    finally:
        session.close()


GET_NETWORK_DEFAULT_GATEWAY_SOAP = f"""\\
<s:Envelope xmlns:s="{SOAP_NS}"
            xmlns:tds="{DEVICE_NS}">
  <s:Body>
    <tds:GetNetworkDefaultGateway/>
  </s:Body>
</s:Envelope>"""


def _parse_network_default_gateway(content):
    root = ET.fromstring(content)

    fault = root.find(".//s:Fault", NAMESPACES)

    if fault is not None:
        raise ONVIFNetworkError(
            "Camera returned ONVIF SOAP fault"
        )

    response = root.find(
        ".//tds:GetNetworkDefaultGatewayResponse",
        NAMESPACES,
    )

    if response is None:
        raise ONVIFNetworkError(
            "Missing GetNetworkDefaultGatewayResponse"
        )

    gateways = []

    for element in response.findall(
        "tds:NetworkGateway/tt:IPv4Address",
        NAMESPACES,
    ):
        if element.text:
            gateways.append(
                str(ipaddress.IPv4Address(element.text))
            )

    return gateways


def get_network_default_gateway(
    endpoint,
    username,
    password,
):
    """
    Read the ONVIF default IPv4 gateway.

    No camera configuration changes.
    """

    session = requests.Session()
    session.trust_env = False
    session.auth = HTTPDigestAuth(
        username,
        password,
    )

    try:
        response = session.post(
            endpoint,
            data=GET_NETWORK_DEFAULT_GATEWAY_SOAP.encode(
                "utf-8"
            ),
            headers={
                "Content-Type":
                    "application/soap+xml; charset=utf-8"
            },
            timeout=(5, 10),
            allow_redirects=False,
        )

        response.raise_for_status()

        return _parse_network_default_gateway(
            response.content
        )

    finally:
        session.close()
