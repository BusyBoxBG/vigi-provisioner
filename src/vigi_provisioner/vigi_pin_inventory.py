"""
VIGI approved certificate pin inventory.

SQLite-backed.
No automatic certificate enrollment.
No camera network operations.
"""

import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from .vigi_certificate_pin import normalize_sha256_pin


def normalize_mac(mac):
    """
    Normalize a 48-bit MAC address.

    Accepted formats:
      02:11:22:33:44:55
      02-11-22-33-44-55
      0211.2233.4455
      021122334455
    """

    if not isinstance(mac, str):
        raise ValueError("MAC must be a string")

    patterns = (
        r"[0-9a-fA-F]{12}",
        r"[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5}",
        r"[0-9a-fA-F]{2}(?:-[0-9a-fA-F]{2}){5}",
        r"[0-9a-fA-F]{4}(?:\.[0-9a-fA-F]{4}){2}",
    )

    if not any(
        re.fullmatch(pattern, mac)
        for pattern in patterns
    ):
        raise ValueError(
            "Invalid MAC address format"
        )

    return re.sub(
        r"[:-]|\.",
        "",
        mac,
    ).lower()


class VigiPinInventory:
    def __init__(self, database_path):
        self.database_path = Path(database_path)

        with closing(self._connect()) as db, db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS camera_pins (
                    mac TEXT PRIMARY KEY,
                    certificate_sha256 TEXT NOT NULL,
                    enrollment_method TEXT NOT NULL,
                    approved_at TEXT NOT NULL
                )
            """)

    def _connect(self):
        return sqlite3.connect(
            self.database_path
        )

    def approve_pin(
        self,
        mac,
        certificate_pin,
        enrollment_method,
    ):
        normalized_mac = normalize_mac(mac)

        normalized_pin = normalize_sha256_pin(
            certificate_pin
        )

        if not isinstance(
            enrollment_method,
            str,
        ) or not enrollment_method.strip():
            raise ValueError(
                "Enrollment method is required"
            )

        approved_at = datetime.now(
            timezone.utc
        ).isoformat()

        with closing(self._connect()) as db, db:
            existing = db.execute(
                """
                SELECT certificate_sha256
                FROM camera_pins
                WHERE mac = ?
                """,
                (normalized_mac,),
            ).fetchone()

            if existing is not None:
                if existing[0] != normalized_pin:
                    raise ValueError(
                        "Existing certificate pin differs; "
                        "automatic replacement prohibited"
                    )

                return False

            db.execute(
                """
                INSERT INTO camera_pins (
                    mac,
                    certificate_sha256,
                    enrollment_method,
                    approved_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    normalized_mac,
                    normalized_pin,
                    enrollment_method.strip(),
                    approved_at,
                ),
            )

        return True

    def get_approved_pin(self, mac):
        normalized_mac = normalize_mac(mac)

        with closing(self._connect()) as db, db:
            row = db.execute(
                """
                SELECT certificate_sha256
                FROM camera_pins
                WHERE mac = ?
                """,
                (normalized_mac,),
            ).fetchone()

        return row[0] if row else None
