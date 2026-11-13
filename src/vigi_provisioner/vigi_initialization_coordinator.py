"""
Offline initialization coordinator.

Validates prepared initialization requests and
returns metadata without opening a network connection.

This module deliberately does not transmit HTTP.
"""

from .vigi_authorized_gateway import VigiAuthorizedGateway
from .vigi_initialization_validator import (
    validate_initialization,
)


class InitializationCoordinatorError(PermissionError):
    pass


class VigiInitializationCoordinator:
    def __init__(
        self,
        gateway,
        *,
        camera_ip,
        camera_port=443,
    ):
        from .vigi_camera_binding import normalize_ipv4

        if not isinstance(
            gateway,
            VigiAuthorizedGateway,
        ):
            raise TypeError(
                "Expected VigiAuthorizedGateway"
            )

        if (
            type(camera_port) is not int
            or not 1 <= camera_port <= 65535
        ):
            raise ValueError(
                "Invalid camera HTTPS port"
            )

        self.__gateway = gateway
        self.__camera_ip = normalize_ipv4(camera_ip)
        self.__camera_port = camera_port

    def dry_run(self, prepared):
        result = validate_initialization(
            prepared,
            approved_ip=self.__camera_ip,
            approved_port=self.__camera_port,
        )

        return {
            "mode": "DRY_RUN",
            "request_valid": result["valid"],
            "camera_ip": result["camera_ip"],
            "https_port": result["https_port"],
            "method": result["method"],
            "path": result["path"],
            "body_bytes": result["body_bytes"],
            "gateway_connection_attempted": False,
            "transmitted": False,
        }


    def prepare_send_plan(self, prepared):
        """
        Prepare a validated HTTP send plan.

        No gateway connection or transmission occurs.
        """
        from .vigi_http_sender import (
            prepare_initialization_send,
        )

        plan = prepare_initialization_send(
            prepared,
            approved_ip=self.__camera_ip,
            approved_port=self.__camera_port,
        )

        return {
            "mode": "DRY_RUN",
            "camera_ip": plan.destination_ip,
            "https_port": plan.destination_port,
            "request_bytes": plan.request_bytes,
            "gateway_connection_attempted": False,
            "transmitted": False,
        }

    def execute(self, prepared):
        raise InitializationCoordinatorError(
            "Live initialization is disabled"
        )
