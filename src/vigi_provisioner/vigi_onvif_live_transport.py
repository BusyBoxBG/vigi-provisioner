import ipaddress
import xml.etree.ElementTree as ET

import requests
from requests.adapters import HTTPAdapter
from requests.auth import HTTPDigestAuth
from urllib3 import PoolManager
from urllib3.util.retry import Retry


SOURCE_IP = "192.168.0.10"
CAMERA_IP = "192.168.0.60"
ENDPOINT = (
    "http://192.168.0.60:80/onvif/device_service"
)

SOAP_NS = "http://www.w3.org/2003/05/soap-envelope"
DEVICE_NS = "http://www.onvif.org/ver10/device/wsdl"

ALLOWED_OPERATIONS = frozenset((
    "SetNetworkDefaultGateway",
    "SetNetworkInterfaces",
))


class LiveONVIFTransportError(ValueError):
    pass


class SourceBoundAdapter(HTTPAdapter):
    def __init__(self, source_ip, *args, **kwargs):
        self.source_ip = str(
            ipaddress.IPv4Address(source_ip)
        )
        super().__init__(*args, **kwargs)

    def init_poolmanager(
        self,
        connections,
        maxsize,
        block=False,
        **pool_kwargs,
    ):
        pool_kwargs["source_address"] = (
            self.source_ip,
            0,
        )
        pool_kwargs["retries"] = Retry(
            total=False,
            redirect=0,
        )

        self.poolmanager = PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            **pool_kwargs,
        )


def validate_operation(operation, soap):
    if operation not in ALLOWED_OPERATIONS:
        raise LiveONVIFTransportError(
            "Unsupported configuration operation"
        )

    if not isinstance(soap, (bytes, str)):
        raise LiveONVIFTransportError(
            "SOAP must be bytes or text"
        )

    payload = (
        soap.encode("utf-8")
        if isinstance(soap, str)
        else soap
    )

    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise LiveONVIFTransportError(
            "Invalid SOAP XML"
        ) from exc

    if root.tag != f"{{{SOAP_NS}}}Envelope":
        raise LiveONVIFTransportError(
            "Unexpected SOAP envelope"
        )

    body = root.find(f"{{{SOAP_NS}}}Body")
    expected = f"{{{DEVICE_NS}}}{operation}"

    if (
        body is None
        or len(body) != 1
        or body[0].tag != expected
    ):
        raise LiveONVIFTransportError(
            "SOAP operation mismatch"
        )

    return payload


def make_live_transport(
    *,
    username,
    password,
    source_ip=SOURCE_IP,
    endpoint=ENDPOINT,
):
    """
    Construct a source-bound HTTP Digest transport.

    Factory construction is offline.

    Calling the returned transport transmits ONVIF SOAP.
    Authorization, identity verification, and strict plan
    validation are the responsibility of the caller.
    """

    if source_ip != SOURCE_IP:
        raise LiveONVIFTransportError(
            "Unexpected source IP"
        )

    if endpoint != ENDPOINT:
        raise LiveONVIFTransportError(
            "Unexpected camera endpoint"
        )

    if username != "admin" or not password:
        raise LiveONVIFTransportError(
            "Invalid camera credentials"
        )

    def transport(operation, soap):
        payload = validate_operation(
            operation,
            soap,
        )

        session = requests.Session()

        try:
            session.trust_env = False
            session.auth = HTTPDigestAuth(
                username,
                password,
            )

            adapter = SourceBoundAdapter(
                SOURCE_IP,
                max_retries=0,
            )

            session.mount(
                "http://",
                adapter,
            )

            response = session.post(
                ENDPOINT,
                data=payload,
                headers={
                    "Content-Type": (
                        "application/soap+xml; charset=utf-8"
                    ),
                },
                timeout=(5, 10),
                allow_redirects=False,
            )

            return {
                "http_status": response.status_code,
                "response_body": response.content,
            }

        finally:
            session.close()

    return transport
