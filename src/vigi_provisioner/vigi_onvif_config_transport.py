from unittest.mock import Mock
from urllib.parse import urlsplit

from requests.auth import HTTPDigestAuth


ALLOWED_OPERATIONS = frozenset({
    "SetNetworkDefaultGateway",
    "SetNetworkInterfaces",
})


class ONVIFTransportError(ValueError):
    pass


def make_test_configuration_transport(
    *,
    endpoint,
    username,
    password,
    session_factory,
):
    """
    Construct a transport for controlled testing.

    Requires an injected session factory. This module never
    creates a requests.Session or opens a connection itself.

    Do not inject a real network session without separate
    authorization for configuration-changing requests.
    """

    parsed = urlsplit(endpoint)

    if (
        parsed.scheme != "http"
        or not parsed.hostname
        or parsed.port != 80
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path != "/onvif/device_service"
    ):
        raise ONVIFTransportError(
            "Unexpected ONVIF endpoint"
        )

    if not username or not password:
        raise ONVIFTransportError(
            "ONVIF credentials required"
        )

    if not callable(session_factory):
        raise ONVIFTransportError(
            "Injected session factory required"
        )

    def transport(operation, soap):
        if operation not in ALLOWED_OPERATIONS:
            raise ONVIFTransportError(
                "Unsupported configuration operation"
            )

        if not isinstance(soap, (str, bytes)):
            raise ONVIFTransportError(
                "SOAP must be text or bytes"
            )

        payload = (
            soap.encode("utf-8")
            if isinstance(soap, str)
            else soap
        )

        session = session_factory()

        if not isinstance(session, Mock):
            try:
                session.close()
            finally:
                raise ONVIFTransportError(
                    "Only unittest.mock.Mock sessions are permitted"
                )

        try:
            session.trust_env = False
            session.auth = HTTPDigestAuth(
                username,
                password,
            )

            response = session.post(
                endpoint,
                data=payload,
                headers={
                    "Content-Type":
                        "application/soap+xml; charset=utf-8"
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
