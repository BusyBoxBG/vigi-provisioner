from dataclasses import dataclass

from .vigi_http_request import serialize_initialization_request


class InitializationTransmissionDisabled(RuntimeError):
    pass


@dataclass(frozen=True)
class InitializationSendPlan:
    destination_ip: str
    destination_port: int
    request_bytes: int
    transmitted: bool


def prepare_initialization_send(
    prepared,
    *,
    approved_ip,
    approved_port=443,
):
    """
    Validate and serialize without transmitting.

    The serialized request is deliberately not returned
    to prevent accidental logging of credential material.
    """

    wire = serialize_initialization_request(
        prepared,
        approved_ip=approved_ip,
        approved_port=approved_port,
    )

    return InitializationSendPlan(
        destination_ip=approved_ip,
        destination_port=approved_port,
        request_bytes=len(wire),
        transmitted=False,
    )


def send_initialization(*args, **kwargs):
    """
    Live transmission is deliberately unavailable.
    """

    raise InitializationTransmissionDisabled(
        "Live initialization transmission is disabled"
    )
