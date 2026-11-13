import ipaddress
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from .vigi_inventory import normalize_mac


DEFAULT_DB = Path(__file__).with_name(
    "vigi_cameras.sqlite3"
)


class StaticIPAssignmentError(ValueError):
    pass


def approve_static_ip_assignment(
    *,
    mac,
    target_ip,
    prefix_length,
    gateway,
    confirmation,
    db_path=DEFAULT_DB,
    provisioning_ip="192.168.0.10",
):
    """
    Validate and persist an operator-approved static IP assignment.

    This function does not connect to a camera.
    """

    normalized_mac = normalize_mac(mac)

    try:
        address = ipaddress.IPv4Address(target_ip)
        gateway_address = ipaddress.IPv4Address(gateway)
        provisioning_address = ipaddress.IPv4Address(
            provisioning_ip
        )

        if (
            isinstance(prefix_length, bool)
            or not isinstance(prefix_length, int)
            or not 1 <= prefix_length <= 30
        ):
            raise ValueError("Invalid prefix length")

        network = ipaddress.IPv4Network(
            f"{address}/{prefix_length}",
            strict=False,
        )

        if address not in network.hosts():
            raise ValueError("Invalid target host address")

        if gateway_address not in network.hosts():
            raise ValueError("Gateway outside usable subnet")

        if address == gateway_address:
            raise ValueError("Target IP equals gateway")

        if address == provisioning_address:
            raise ValueError("Target IP equals provisioning PC")

    except ValueError as exc:
        raise StaticIPAssignmentError(str(exc)) from exc

    expected_confirmation = (
        f"ASSIGN {normalized_mac} "
        f"{address}/{prefix_length} "
        f"{gateway_address}"
    )

    if confirmation != expected_confirmation:
        raise StaticIPAssignmentError(
            "Exact operator confirmation required"
        )

    database = Path(db_path)

    if not database.is_file():
        raise StaticIPAssignmentError(
            "Camera inventory database not found"
        )

    with closing(sqlite3.connect(database)) as db, db:
        db.execute("PRAGMA foreign_keys = ON")

        db.execute("BEGIN IMMEDIATE")

        camera = db.execute(
            "SELECT ip FROM inventory WHERE mac = ?",
            (normalized_mac,),
        ).fetchone()

        if camera is None:
            raise StaticIPAssignmentError(
                "Camera MAC not found in inventory"
            )

        existing = db.execute(
            "SELECT target_ip "
            "FROM static_ip_assignments "
            "WHERE mac = ?",
            (normalized_mac,),
        ).fetchone()

        if existing is not None:
            raise StaticIPAssignmentError(
                "Camera already has an approved assignment"
            )

        conflict = db.execute(
            "SELECT mac FROM inventory "
            "WHERE ip = ? AND mac <> ?",
            (str(address), normalized_mac),
        ).fetchone()

        if conflict is not None:
            raise StaticIPAssignmentError(
                "Target IP belongs to another discovered camera"
            )

        conflict = db.execute(
            "SELECT mac FROM static_ip_assignments "
            "WHERE target_ip = ?",
            (str(address),),
        ).fetchone()

        if conflict is not None:
            raise StaticIPAssignmentError(
                "Target IP already assigned"
            )

        approved_at = datetime.now(
            timezone.utc
        ).isoformat()

        db.execute(
            """
            INSERT INTO static_ip_assignments (
                mac,
                target_ip,
                prefix_length,
                gateway,
                approved_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                normalized_mac,
                str(address),
                prefix_length,
                str(gateway_address),
                approved_at,
            ),
        )

        db.commit()

    return {
        "mac": normalized_mac,
        "target_ip": str(address),
        "prefix_length": prefix_length,
        "gateway": str(gateway_address),
        "approved_at": approved_at,
        "camera_modified": False,
    }
