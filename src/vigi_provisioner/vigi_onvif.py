import requests
import xml.etree.ElementTree as ET
from requests.auth import HTTPDigestAuth

SOAP = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
  <s:Body>
    <tds:GetDeviceInformation/>
  </s:Body>
</s:Envelope>"""


def get_device_information(endpoint, username, password):
    session = requests.Session()
    session.trust_env = False
    session.auth = HTTPDigestAuth(username, password)

    try:
        response = session.post(
            endpoint,
            data=SOAP.encode("utf-8"),
            headers={
                "Content-Type": "application/soap+xml; charset=utf-8"
            },
            timeout=(5, 10),
            allow_redirects=False,
        )

        response.raise_for_status()
        root = ET.fromstring(response.content)

        namespace = {
            "tds": "http://www.onvif.org/ver10/device/wsdl"
        }

        fields = (
            "Manufacturer",
            "Model",
            "FirmwareVersion",
            "SerialNumber",
            "HardwareId",
        )

        result = {}

        for field in fields:
            element = root.find(f".//tds:{field}", namespace)
            result[field] = (
                element.text if element is not None else None
            )

        return result

    finally:
        session.close()
