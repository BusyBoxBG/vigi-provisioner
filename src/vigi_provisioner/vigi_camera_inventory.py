import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from . import vigi_discovery
from . import vigi_onvif

from .vigi_device_record import build_device_record
from .vigi_inventory import normalize_mac


DEFAULT_DB = Path(__file__).with_name("vigi_cameras.sqlite3")

FIELDS = (
    "mac",
    "ip",
    "factory_flag",
    "manufacturer",
    "model",
    "firmware",
    "device_id",
    "onvif_serial",
    "hardware_id",
    "device_name",
    "onvif_endpoint",
)


def save_camera_record(record, db_path=DEFAULT_DB):
    data = {
        "mac": normalize_mac(record["mac"]),
        "ip": record["ip"],
        "factory_flag": record.get("factory_flag"),
        "manufacturer": record.get("manufacturer"),
        "model": record.get("model"),
        "firmware": record.get("firmware"),
        "device_id": record.get("device_id", record.get("serial")),
        "onvif_serial": record.get("onvif_serial"),
        "hardware_id": record.get("hardware_id"),
        "device_name": record.get("device_name"),
        "onvif_endpoint": record.get("onvif_endpoint"),
    }

    timestamp = datetime.now(timezone.utc).isoformat()

    connection = sqlite3.connect(db_path)

    try:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                mac TEXT PRIMARY KEY,
                ip TEXT NOT NULL,
                factory_flag INTEGER,
                manufacturer TEXT,
                model TEXT,
                firmware TEXT,
                device_id TEXT,
                onvif_serial TEXT,
                hardware_id TEXT,
                device_name TEXT,
                onvif_endpoint TEXT,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL
            )
        """)

        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(inventory)"
            )
        }

        required = set(FIELDS) | {
            "first_seen",
            "last_seen",
        }

        if not required.issubset(columns):
            raise RuntimeError(
                "Camera inventory schema is incompatible"
            )

        # Serialize the check and UPSERT against concurrent writers.
        connection.execute("BEGIN IMMEDIATE")

        assignment = connection.execute(
            """
            SELECT target_ip
            FROM static_ip_assignments
            WHERE mac = ?
            """,
            (data["mac"],),
        ).fetchone() if (
            "static_ip_assignments" in {
                row[0] for row in connection.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'table'"
                )
            }
        ) else None

        current = connection.execute(
            "SELECT ip FROM inventory WHERE mac = ?",
            (data["mac"],),
        ).fetchone()

        # Once inventory matches the approved assignment,
        # discovery must not silently move it elsewhere.
        if (
            assignment is not None
            and current is not None
            and current[0] == assignment[0]
            and data["ip"] != assignment[0]
        ):
            raise RuntimeError(
                "Static-IP drift detected for "
                f"{data['mac']}: approved={assignment[0]}, "
                f"discovered={data['ip']}"
            )

        connection.execute("""
            INSERT INTO inventory (
                mac, ip, factory_flag, manufacturer,
                model, firmware, device_id, onvif_serial,
                hardware_id, device_name, onvif_endpoint,
                first_seen, last_seen
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(mac) DO UPDATE SET
                ip = excluded.ip,
                factory_flag = excluded.factory_flag,
                manufacturer = COALESCE(
                    NULLIF(TRIM(excluded.manufacturer), ''),
                    inventory.manufacturer
                ),
                model = COALESCE(
                    NULLIF(TRIM(excluded.model), ''),
                    inventory.model
                ),
                firmware = COALESCE(
                    NULLIF(TRIM(excluded.firmware), ''),
                    inventory.firmware
                ),
                device_id = COALESCE(
                    NULLIF(TRIM(excluded.device_id), ''),
                    inventory.device_id
                ),
                onvif_serial = COALESCE(
                    NULLIF(TRIM(excluded.onvif_serial), ''),
                    inventory.onvif_serial
                ),
                hardware_id = COALESCE(
                    NULLIF(TRIM(excluded.hardware_id), ''),
                    inventory.hardware_id
                ),
                device_name = COALESCE(
                    NULLIF(TRIM(excluded.device_name), ''),
                    inventory.device_name
                ),
                onvif_endpoint = excluded.onvif_endpoint,
                last_seen = excluded.last_seen
        """, (
            *(data[field] for field in FIELDS),
            timestamp,
            timestamp,
        ))

        connection.commit()

        connection.row_factory = sqlite3.Row

        row = connection.execute(
            "SELECT * FROM inventory WHERE mac = ?",
            (data["mac"],),
        ).fetchone()

        return dict(row)

    finally:
        connection.close()


def discover_enrich_save(
    target_mac,
    password=None,
    source_ip="192.168.0.10",
    db_path=DEFAULT_DB,
):
    expected_mac = normalize_mac(target_mac)

    devices = vigi_discovery.discover(
        local_ip=source_ip,
        timeout=5,
    )

    matches = [
        device for device in devices
        if normalize_mac(device["mac"]) == expected_mac
    ]

    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one matching camera; found {len(matches)}"
        )

    udp = matches[0]
    onvif = None

    if udp.get("factory_flag") == 1 and password:
        endpoint = udp.get("onvif_endpoint")

        expected_endpoint = (
            f"http://{udp['ip']}:80/onvif/device_service"
        )

        if endpoint != expected_endpoint:
            raise RuntimeError(
                "Unexpected ONVIF endpoint"
            )

        onvif = vigi_onvif.get_device_information(
            endpoint=endpoint,
            username="admin",
            password=password,
        )

    record = build_device_record(
        udp=udp,
        onvif=onvif,
    )

    return save_camera_record(
        record=record,
        db_path=db_path,
    )


def sync_discovered_cameras(
    approved_macs,
    password=None,
    source_ip="192.168.0.10",
    db_path=DEFAULT_DB,
):
    approved = {
        normalize_mac(mac)
        for mac in approved_macs
    }

    devices = vigi_discovery.discover(
        local_ip=source_ip,
        timeout=5,
    )

    results = {
        "discovered": len(devices),
        "saved": [],
        "skipped": [],
        "errors": [],
    }

    seen = set()

    for udp in devices:
        try:
            mac = normalize_mac(udp["mac"])

            if mac in seen:
                results["skipped"].append({
                    "mac": mac,
                    "reason": "Duplicate discovery",
                })
                continue

            seen.add(mac)

            if mac not in approved:
                results["skipped"].append({
                    "mac": mac,
                    "reason": "Not in approved inventory",
                })
                continue

            onvif = None

            if udp.get("factory_flag") == 1 and password:
                endpoint = udp.get("onvif_endpoint")

                expected_endpoint = (
                    f"http://{udp['ip']}:80/onvif/device_service"
                )

                if endpoint != expected_endpoint:
                    raise RuntimeError(
                        "Unexpected ONVIF endpoint"
                    )

                onvif = vigi_onvif.get_device_information(
                    endpoint=endpoint,
                    username="admin",
                    password=password,
                )

            record = build_device_record(
                udp=udp,
                onvif=onvif,
            )

            saved = save_camera_record(
                record,
                db_path=db_path,
            )

            results["saved"].append(saved)

        except Exception as exc:
            results["errors"].append({
                "mac": udp.get("mac"),
                "error": str(exc),
            })

    return results
