
import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from .vigi_inventory import normalize_mac
from .vigi_provisioning_evidence import (
    validate_bound_application_evidence,
    validate_readback_evidence,
)

class ProvisioningStateError(ValueError):
    pass

SCHEMA = """
CREATE TABLE static_ip_provisioning_state (
    mac TEXT PRIMARY KEY,
    target_ip TEXT NOT NULL,
    status TEXT NOT NULL
        CHECK(status IN ('pending', 'applied', 'verified')),
    applied_at TEXT,
    verified_at TEXT,
    verification_reference TEXT,
    FOREIGN KEY(mac) REFERENCES static_ip_assignments(mac),
    CHECK(
        (status = 'pending'
         AND applied_at IS NULL
         AND verified_at IS NULL
         AND verification_reference IS NULL)
        OR
        (status = 'applied'
         AND applied_at IS NOT NULL
         AND verified_at IS NULL
         AND verification_reference IS NULL)
        OR
        (status = 'verified'
         AND applied_at IS NOT NULL
         AND verified_at IS NOT NULL
         AND verification_reference IS NOT NULL
         AND LENGTH(TRIM(verification_reference)) > 0)
    )
)
"""

def _timestamp():
    return datetime.now(timezone.utc).isoformat()

def _connect(db_path):
    if db_path is None:
        raise ProvisioningStateError(
            "Explicit database path required"
        )
    path = Path(db_path)
    if not path.is_file():
        raise ProvisioningStateError(
            "Database does not exist"
        )
    db = sqlite3.connect(
        path.resolve().as_uri() + "?mode=rw",
        uri=True,
    )
    db.execute("PRAGMA foreign_keys = ON")
    return db

def _approved(db, mac):
    row = db.execute(
        """
        SELECT mac, target_ip, prefix_length, gateway
        FROM static_ip_assignments WHERE mac = ?
        """,
        (normalize_mac(mac),),
    ).fetchone()
    if row is None:
        raise ProvisioningStateError(
            "No approved assignment"
        )
    return dict(zip(
        ("mac", "target_ip", "prefix_length", "gateway"),
        row,
    ))

def _state(db, mac):
    row = db.execute(
        """
        SELECT status, target_ip, applied_at,
               verified_at, verification_reference
        FROM static_ip_provisioning_state WHERE mac = ?
        """,
        (normalize_mac(mac),),
    ).fetchone()
    return row

def initialize_pending(*, db_path, mac):
    with closing(_connect(db_path)) as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            approved = _approved(db, mac)
            if _state(db, mac) is not None:
                raise ProvisioningStateError(
                    "Provisioning state already exists"
                )
            db.execute(
                """
                INSERT INTO static_ip_provisioning_state
                    (mac, target_ip, status)
                VALUES (?, ?, 'pending')
                """,
                (approved["mac"], approved["target_ip"]),
            )
            db.commit()
            return "pending"
        except BaseException:
            db.rollback()
            raise

def record_applied(*, db_path, plan, evidence):
    with closing(_connect(db_path)) as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            approved = _approved(db, plan["mac"])
            current = _state(db, plan["mac"])
            if current is None or current[:2] != (
                "pending", approved["target_ip"]
            ):
                raise ProvisioningStateError(
                    "Expected pending state"
                )

            validate_bound_application_evidence(
                plan=plan,
                evidence=evidence,
                approved_assignment=approved,
            )

            db.execute(
                """
                UPDATE static_ip_provisioning_state
                SET status = 'applied', applied_at = ?
                WHERE mac = ? AND status = 'pending'
                """,
                (_timestamp(), approved["mac"]),
            )
            db.commit()
            return "applied"
        except BaseException:
            db.rollback()
            raise

def record_verified(
    *,
    db_path,
    plan,
    discovered_device,
    interfaces,
    gateways,
):
    with closing(_connect(db_path)) as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            approved = _approved(db, plan["mac"])
            current = _state(db, plan["mac"])

            if current is None or current[:2] != (
                "applied", approved["target_ip"]
            ):
                raise ProvisioningStateError(
                    "Expected applied state"
                )

            if normalize_mac(plan["mac"]) != approved["mac"]:
                raise ProvisioningStateError(
                    "Plan MAC mismatch"
                )

            for field in ("target_ip", "prefix_length", "gateway"):
                if plan[field] != approved[field]:
                    raise ProvisioningStateError(
                        "Plan approval mismatch: " + field
                    )

            result = validate_readback_evidence(
                plan=plan,
                discovered_device=discovered_device,
                interfaces=interfaces,
                gateways=gateways,
            )

            # A reproducible fingerprint of supplied observations,
            # NOT proof of their origin or freshness.
            payload = {
                "plan": {
                    key: plan[key]
                    for key in (
                        "mac", "target_ip", "prefix_length",
                        "gateway", "interface_token"
                    )
                },
                "discovered_device": discovered_device,
                "interfaces": interfaces,
                "gateways": gateways,
                "verification": result["verification"],
            }
            encoded = json.dumps(
                payload, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            reference = "sha256:" + hashlib.sha256(
                encoded
            ).hexdigest()

            db.execute(
                """
                UPDATE static_ip_provisioning_state
                SET status = 'verified',
                    verified_at = ?,
                    verification_reference = ?
                WHERE mac = ? AND status = 'applied'
                """,
                (_timestamp(), reference, approved["mac"]),
            )
            db.commit()
            return {
                "status": "verified",
                "verification_reference": reference,
            }
        except BaseException:
            db.rollback()
            raise
