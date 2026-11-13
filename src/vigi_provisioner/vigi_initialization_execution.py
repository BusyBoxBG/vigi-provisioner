"""
Disabled gateway-owned initialization execution boundary.

No socket connections.
No HTTP transmission.
No database modifications.
Live initialization is deliberately unavailable.
"""

from .vigi_authorized_gateway import VigiAuthorizedGateway
from .vigi_pin_inventory import normalize_mac
from .vigi_camera_binding import normalize_ipv4
from .vigi_initialization_execution_plan import InitializationExecutionPlan
from .vigi_initialization_authorization import (
    InitializationAuthorization,
)


class InitializationExecutionDisabled(Exception):
    pass


class VigiInitializationExecution:
    __slots__ = (
        "__gateway",
        "__authorization",
        "__approved_identity",
        "__source_ip",
        "__execution_plan",
        "__attempted",
    )

    def __init__(
        self,
        gateway,
        authorization,
        *,
        approved_mac,
        approved_ip,
        approved_port=443,
        source_ip="192.168.0.10",
    ):
        if not isinstance(gateway, VigiAuthorizedGateway):
            raise TypeError(
                "Expected VigiAuthorizedGateway"
            )

        if not isinstance(
            authorization,
            InitializationAuthorization,
        ):
            raise TypeError(
                "Expected InitializationAuthorization"
            )

        if authorization.consumed:
            raise ValueError(
                "Authorization already consumed"
            )

        expected_identity = (
            normalize_mac(approved_mac),
            normalize_ipv4(approved_ip),
            approved_port,
        )

        if (
            type(approved_port) is not int
            or not 1 <= approved_port <= 65535
        ):
            raise ValueError(
                "Invalid approved HTTPS port"
            )

        if authorization.approved_identity != expected_identity:
            raise PermissionError(
                "Initialization authorization identity mismatch"
            )

        verified_identity = gateway.require_approved_identity(
            mac=expected_identity[0],
            camera_ip=expected_identity[1],
            camera_port=expected_identity[2],
            source_ip=source_ip,
        )

        if verified_identity != expected_identity:
            raise PermissionError(
                "Gateway preflight identity mismatch"
            )

        self.__gateway = gateway
        self.__authorization = authorization
        self.__approved_identity = expected_identity
        self.__source_ip = normalize_ipv4(source_ip)
        self.__execution_plan = InitializationExecutionPlan(
            approved_mac=expected_identity[0],
            destination_ip=expected_identity[1],
            destination_port=expected_identity[2],
            source_ip=self.__source_ip,
        )
        self.__attempted = False

        authorization.reserve(self)

    @property
    def attempted(self):
        return self.__attempted

    @property
    def approved_identity(self):
        return self.__approved_identity

    @property
    def execution_plan(self):
        return self.__execution_plan

    def execute(self):
        if self.__attempted:
            raise InitializationExecutionDisabled(
                "Execution boundary already invoked"
            )

        self.__attempted = True

        self.__gateway.require_approved_identity(
            mac=self.__approved_identity[0],
            camera_ip=self.__approved_identity[1],
            camera_port=self.__approved_identity[2],
            source_ip=self.__source_ip,
        )

        self.__authorization.mark_ready(self)

        raise InitializationExecutionDisabled(
            "Live initialization is disabled"
        )

    def consume_approved_request(self):
        """Consume only after renewed gateway approval.

        This method does not open a socket or transmit data.
        """
        if not self.__attempted:
            raise InitializationExecutionDisabled(
                "Execution preflight has not been invoked"
            )

        if not self.__authorization.ready:
            raise InitializationExecutionDisabled(
                "Initialization authorization is not ready"
            )

        self.__gateway.require_approved_identity(
            mac=self.__approved_identity[0],
            camera_ip=self.__approved_identity[1],
            camera_port=self.__approved_identity[2],
            source_ip=self.__source_ip,
        )

        return self.__authorization.consume(self)

    def _validate_initialization_consumption(self):
        """Revalidate current binding before releasing request bytes."""
        if not self.__attempted:
            raise InitializationExecutionDisabled(
                "Execution preflight has not been invoked"
            )

        self.__gateway.require_approved_identity(
            mac=self.__approved_identity[0],
            camera_ip=self.__approved_identity[1],
            camera_port=self.__approved_identity[2],
            source_ip=self.__source_ip,
        )
