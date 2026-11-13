import ipaddress
import sqlite3

from .vigi_camera_inventory import DEFAULT_DB
from .vigi_inventory import normalize_mac
from .vigi_https_init import prepare_initialization
from .vigi_initialization_validator import validate_initialization


class InventoryInitializationError(RuntimeError):
    pass


def prepare_inventory_initialization(
    mac,
    password,
    email,
    db_path=DEFAULT_DB,
):
    normalized_mac = normalize_mac(mac)

    connection = sqlite3.connect(db_path)

    try:
        connection.row_factory = sqlite3.Row

        row = connection.execute(
            "SELECT mac, ip, factory_flag "
            "FROM inventory WHERE mac = ?",
            (normalized_mac,),
        ).fetchone()

        if row is None:
            raise InventoryInitializationError(
                "Camera not found in approved inventory"
            )

        camera = dict(row)

    finally:
        connection.close()

    if camera["factory_flag"] != 0:
        raise InventoryInitializationError(
            "Camera is not marked uninitialized"
        )

    camera_ip = str(
        ipaddress.IPv4Address(camera["ip"])
    )

    prepared = prepare_initialization(
        ip=camera_ip,
        password=password,
        email=email,
        username="admin",
        language="English",
        port=443,
    )

    validation = validate_initialization(
        prepared,
        approved_ip=camera_ip,
        approved_port=443,
    )

    return {
        "mac": normalized_mac,
        "camera_ip": camera_ip,
        "factory_flag": camera["factory_flag"],
        "prepared": prepared,
        "validation": validation,
    }


def safe_initialization_summary(result):
    validation = result["validation"]

    return {
        "mac": result["mac"],
        "camera_ip": result["camera_ip"],
        "factory_flag": result["factory_flag"],
        "request_valid": validation["valid"],
        "method": validation["method"],
        "path": validation["path"],
        "body_bytes": validation["body_bytes"],
        "transmitted": False,
    }


def authorize_inventory_initialization(
    result,
    confirmation,
):
    expected = (
        f"INITIALIZE {result['mac']} "
        f"{result['camera_ip']}"
    )

    if not isinstance(confirmation, str):
        raise InventoryInitializationError(
            "Operator confirmation required"
        )

    if confirmation != expected:
        raise InventoryInitializationError(
            "Operator confirmation does not match camera"
        )

    validation = result.get("validation")

    if not isinstance(validation, dict):
        raise InventoryInitializationError(
            "Initialization validation missing"
        )

    if validation.get("valid") is not True:
        raise InventoryInitializationError(
            "Initialization request not validated"
        )

    if validation.get("camera_ip") != result["camera_ip"]:
        raise InventoryInitializationError(
            "Initialization destination mismatch"
        )

    return {
        "authorized": True,
        "mac": result["mac"],
        "camera_ip": result["camera_ip"],
        "prepared": result["prepared"],
        "transmitted": False,
    }


def dry_run_inventory_initialization(
    authorization,
    coordinator,
):
    from .vigi_initialization_coordinator import (
        VigiInitializationCoordinator,
    )

    if not isinstance(authorization, dict):
        raise InventoryInitializationError(
            "Initialization authorization missing"
        )

    if authorization.get("authorized") is not True:
        raise InventoryInitializationError(
            "Initialization not authorized"
        )

    if authorization.get("transmitted") is not False:
        raise InventoryInitializationError(
            "Unexpected transmission state"
        )

    if not isinstance(
        coordinator,
        VigiInitializationCoordinator,
    ):
        raise InventoryInitializationError(
            "Invalid initialization coordinator"
        )

    prepared = authorization.get("prepared")

    if prepared is None:
        raise InventoryInitializationError(
            "Prepared request missing"
        )

    result = coordinator.dry_run(prepared)

    if (
        result.get("request_valid") is not True
        or result.get("camera_ip") != authorization.get("camera_ip")
        or result.get("transmitted") is not False
    ):
        raise InventoryInitializationError(
            "Coordinator dry-run validation failed"
        )

    return {
        "authorized": True,
        "mac": authorization["mac"],
        "camera_ip": authorization["camera_ip"],
        "mode": "DRY_RUN",
        "request_valid": True,
        "body_bytes": result["body_bytes"],
        "transmitted": False,
    }


def verify_live_initialization_target(
    authorization,
    source_ip="192.168.0.10",
):
    from . import vigi_discovery

    if not isinstance(authorization, dict):
        raise InventoryInitializationError(
            "Authorization missing"
        )

    if authorization.get("authorized") is not True:
        raise InventoryInitializationError(
            "Camera initialization not authorized"
        )

    if authorization.get("transmitted") is not False:
        raise InventoryInitializationError(
            "Unexpected transmission state"
        )

    expected_mac = normalize_mac(
        authorization["mac"]
    )
    expected_ip = str(
        ipaddress.IPv4Address(
            authorization["camera_ip"]
        )
    )

    devices = vigi_discovery.discover(
        local_ip=source_ip,
        timeout=5,
    )

    matches = [
        device
        for device in devices
        if normalize_mac(device["mac"]) == expected_mac
    ]

    if len(matches) != 1:
        raise InventoryInitializationError(
            "Expected exactly one matching camera"
        )

    camera = matches[0]

    if camera["ip"] != expected_ip:
        raise InventoryInitializationError(
            "Camera IP changed since authorization"
        )

    if camera.get("factory_flag") != 0:
        raise InventoryInitializationError(
            "Camera is no longer uninitialized"
        )

    return {
        "verified": True,
        "mac": expected_mac,
        "camera_ip": expected_ip,
        "factory_flag": 0,
        "source_ip": source_ip,
        "transmitted": False,
    }
