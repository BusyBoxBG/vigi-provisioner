"""
Single-use initialization request authorization.

No network activity.
No database access.
Does not authorize live camera initialization.
"""

from dataclasses import dataclass

from .vigi_pin_inventory import normalize_mac
from .vigi_camera_binding import normalize_ipv4

from .vigi_http_request import (
    serialize_initialization_request,
)


class InitializationAuthorizationError(Exception):
    pass


@dataclass(frozen=True)
class ConsumedInitializationRequest:
    approved_mac: str
    destination_ip: str
    destination_port: int
    request_bytes: bytes


class InitializationAuthorization:
    __slots__ = (
        "__approved_mac",
        "__destination_ip",
        "__destination_port",
        "__request",
        "__consumed",
        "__owner",
        "__ready",
    )

    def __init__(
        self,
        prepared,
        *,
        approved_mac,
        approved_ip,
        approved_port=443,
    ):
        normalized_mac = normalize_mac(approved_mac)
        normalized_ip = normalize_ipv4(approved_ip)

        request = serialize_initialization_request(
            prepared,
            approved_ip=normalized_ip,
            approved_port=approved_port,
        )

        self.__approved_mac = normalized_mac
        self.__destination_ip = normalized_ip
        self.__destination_port = approved_port
        self.__request = request
        self.__consumed = False
        self.__owner = None
        self.__ready = False

    @property
    def consumed(self):
        return self.__consumed

    @property
    def approved_identity(self):
        return (
            self.__approved_mac,
            self.__destination_ip,
            self.__destination_port,
        )

    @property
    def reserved(self):
        return self.__owner is not None

    def reserve(self, owner):
        if owner is None:
            raise ValueError(
                "Authorization owner cannot be None"
            )

        if self.__consumed:
            raise InitializationAuthorizationError(
                "Consumed authorization cannot be reserved"
            )

        if self.__owner is not None:
            raise InitializationAuthorizationError(
                "Initialization authorization already reserved"
            )

        self.__owner = owner

    @property
    def ready(self):
        return self.__ready

    def mark_ready(self, owner):
        if self.__consumed:
            raise InitializationAuthorizationError(
                "Consumed authorization cannot become ready"
            )

        if self.__owner is None:
            raise InitializationAuthorizationError(
                "Unreserved authorization cannot become ready"
            )

        if owner is not self.__owner:
            raise InitializationAuthorizationError(
                "Initialization authorization owner mismatch"
            )

        if self.__ready:
            raise InitializationAuthorizationError(
                "Initialization authorization already ready"
            )

        self.__ready = True

    def consume(self, owner):
        if self.__consumed:
            raise InitializationAuthorizationError(
                "Initialization authorization already consumed"
            )

        if self.__owner is None:
            raise InitializationAuthorizationError(
                "Initialization authorization is not reserved"
            )

        if owner is not self.__owner:
            raise InitializationAuthorizationError(
                "Initialization authorization owner mismatch"
            )

        if not self.__ready:
            raise InitializationAuthorizationError(
                "Initialization authorization is not ready"
            )

        validator = getattr(
            self.__owner,
            "_validate_initialization_consumption",
            None,
        )

        if not callable(validator):
            raise InitializationAuthorizationError(
                "Authorization owner has no consumption validator"
            )

        validator()

        self.__consumed = True

        request = self.__request
        self.__request = None

        return ConsumedInitializationRequest(
            approved_mac=self.__approved_mac,
            destination_ip=self.__destination_ip,
            destination_port=self.__destination_port,
            request_bytes=request,
        )
