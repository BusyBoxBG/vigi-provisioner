"""
Application-level gateway for explicitly approved
camera connections.

Discovery data alone never authorizes TLS.
"""

from .vigi_camera_binding import (
    CameraBindingRegistry,
    connect_bound_camera,
)
from .vigi_enrollment_binding import (
    approve_discovered_binding,
)
from .vigi_pin_inventory import VigiPinInventory


class VigiAuthorizedGateway:
    def __init__(
        self,
        pin_inventory,
        *,
        ttl_seconds=30,
        clock=None,
        provisioning_source_ip="192.168.0.10",
        https_port=443,
    ):
        if not isinstance(
            pin_inventory,
            VigiPinInventory,
        ):
            raise TypeError(
                "Expected VigiPinInventory"
            )

        from .vigi_camera_binding import normalize_ipv4

        self.__source_ip = normalize_ipv4(
            provisioning_source_ip
        )

        if (
            type(https_port) is not int
            or not 1 <= https_port <= 65535
        ):
            raise ValueError(
                "Invalid configured HTTPS port"
            )

        self.__https_port = https_port

        self.__inventory = pin_inventory
        self.__registry = CameraBindingRegistry(
            ttl_seconds=ttl_seconds,
            clock=clock,
        )

        self.__approved = set()

    def approve(
        self,
        evidence,
        *,
        approved_mac,
        approved_ip,
        approved_pin,
        operator_confirmed,
        now=None,
        max_age_seconds=60,
    ):
        from .vigi_pin_inventory import normalize_mac
        from .vigi_camera_binding import normalize_ipv4

        mac = normalize_mac(approved_mac)
        ip = normalize_ipv4(approved_ip)

        result = approve_discovered_binding(
            registry=self.__registry,
            pin_inventory=self.__inventory,
            evidence=evidence,
            approved_mac=mac,
            approved_ip=ip,
            approved_pin=approved_pin,
            operator_confirmed=operator_confirmed,
            now=now,
            max_age_seconds=max_age_seconds,
        )

        self.__approved.add((mac, ip))
        return result

    def require_approved_identity(
        self,
        *,
        mac,
        camera_ip,
        camera_port,
        source_ip,
    ):
        """
        Validate current approval without opening a connection.

        No network activity or database writes occur here.
        """
        from .vigi_pin_inventory import normalize_mac
        from .vigi_camera_binding import normalize_ipv4

        normalized_mac = normalize_mac(mac)
        normalized_ip = normalize_ipv4(camera_ip)
        normalized_source = normalize_ipv4(source_ip)

        if normalized_source != self.__source_ip:
            raise PermissionError(
                "Connection source is not provisioning interface"
            )

        if (
            type(camera_port) is not int
            or camera_port != self.__https_port
        ):
            raise PermissionError(
                "Destination HTTPS port not approved"
            )

        if (
            normalized_mac,
            normalized_ip,
        ) not in self.__approved:
            raise PermissionError(
                "Camera not approved through gateway"
            )

        self.__registry.require_binding(
            normalized_mac,
            normalized_ip,
        )

        return (
            normalized_mac,
            normalized_ip,
            camera_port,
        )

    def connect(
        self,
        *,
        mac,
        camera_ip,
        camera_port,
        source_ip,
        timeout=5,
    ):
        from .vigi_pin_inventory import normalize_mac
        from .vigi_camera_binding import normalize_ipv4

        normalized_mac = normalize_mac(mac)
        normalized_ip = normalize_ipv4(camera_ip)
        normalized_source = normalize_ipv4(source_ip)

        if normalized_source != self.__source_ip:
            raise PermissionError(
                "Connection source is not provisioning interface"
            )

        if (
            type(camera_port) is not int
            or camera_port != self.__https_port
        ):
            raise PermissionError(
                "Destination HTTPS port not approved"
            )

        if (
            normalized_mac,
            normalized_ip,
        ) not in self.__approved:
            raise PermissionError(
                "Camera not approved through gateway"
            )

        self.__registry.require_binding(
            normalized_mac,
            normalized_ip,
        )

        return connect_bound_camera(
            registry=self.__registry,
            pin_inventory=self.__inventory,
            mac=normalized_mac,
            camera_ip=normalized_ip,
            camera_port=camera_port,
            source_ip=source_ip,
            timeout=timeout,
        )
