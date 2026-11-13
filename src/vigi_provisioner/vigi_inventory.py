import re
import sqlite3


def normalize_mac(mac: str) -> str:
    value = re.sub(r"[^0-9a-fA-F]", "", mac).lower()

    if len(value) != 12:
        raise ValueError("Invalid MAC address length")

    return ":".join(value[i:i + 2] for i in range(0, 12, 2))


def inventory_contains_mac(connection, mac: str) -> bool:
    target = normalize_mac(mac)

    rows = connection.execute(
        "SELECT mac FROM inventory"
    ).fetchall()

    return any(normalize_mac(row[0]) == target for row in rows)
