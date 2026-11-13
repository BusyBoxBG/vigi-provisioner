import ipaddress
import sqlite3
from contextlib import closing
from pathlib import Path

from .vigi_inventory import normalize_mac
from .vigi_onvif_static_ip import prepare_static_ipv4
from .vigi_onvif_gateway_config import prepare_default_gateway
from .vigi_static_ip_assignments import DEFAULT_DB


class StaticIPPlanError(ValueError):
    pass


def prepare_inventory_static_ip_plan(
    *,
    mac,
    interface_token,
    db_path=DEFAULT_DB,
):
    """
    Read an approved assignment and prepare two ONVIF requests.

    No camera connection.
    No database modification.
    No request transmission.
    """

    normalized_mac = normalize_mac(mac)
    database = Path(db_path)

    if not database.is_file():
        raise StaticIPPlanError(
            "Camera inventory database not found"
        )

    with closing(sqlite3.connect(database)) as db:
        db.row_factory = sqlite3.Row

        camera = db.execute(
            "SELECT ip FROM inventory WHERE mac = ?",
            (normalized_mac,),
        ).fetchone()

        if camera is None:
            raise StaticIPPlanError(
                "Camera not found in inventory"
            )

        assignment = db.execute(
            """
            SELECT target_ip, prefix_length, gateway, approved_at
            FROM static_ip_assignments
            WHERE mac = ?
            """,
            (normalized_mac,),
        ).fetchone()

        if assignment is None:
            raise StaticIPPlanError(
                "No approved static IP assignment"
            )

        current_ip = camera["ip"]

        target_ip = assignment["target_ip"]
        prefix_length = assignment["prefix_length"]
        gateway = assignment["gateway"]
        approved_at = assignment["approved_at"]

    try:
        current_address = ipaddress.IPv4Address(
            current_ip
        )

        interface_request = prepare_static_ipv4(
            interface_token=interface_token,
            ip_address=target_ip,
            prefix_length=prefix_length,
            gateway=gateway,
        )

        gateway_request = prepare_default_gateway(
            gateway=gateway
        )

    except ValueError as exc:
        raise StaticIPPlanError(
            "Invalid stored network configuration"
        ) from exc

    if interface_request["gateway"] != gateway_request["gateway"]:
        raise StaticIPPlanError(
            "Gateway mismatch between prepared requests"
        )

    if (
        interface_request["transmitted"] is not False
        or gateway_request["transmitted"] is not False
    ):
        raise StaticIPPlanError(
            "Unexpected transmission state"
        )

    return {
        "mac": normalized_mac,
        "current_ip": str(current_address),
        "target_ip": interface_request["ip_address"],
        "prefix_length": interface_request["prefix_length"],
        "subnet_mask": interface_request["subnet_mask"],
        "gateway": gateway_request["gateway"],
        "interface_token": interface_request["interface_token"],
        "dhcp": False,
        "approved_at": approved_at,
        "set_network_interfaces_soap": interface_request["soap"],
        "set_network_default_gateway_soap": gateway_request["soap"],
        "transmitted": False,
    }
