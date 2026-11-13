
# responses.py
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Optional

from .packets import decode_packet, decode_tlvs


@dataclass
class UdpResponse:
    packet_type: int
    mac_address: Optional[str] = None
    client_mac: Optional[str] = None
    symmetric_encryption: list[str] = field(default_factory=list)
    asymmetric_encryption: Optional[str] = None
    public_key: Optional[str] = None
    error_code: Optional[int] = None
    json_payload: Optional[str] = None



def validate_camera_mac(actual: str | None, expected: str) -> None:
    pattern = r"^[0-9A-Fa-f]{2}(?:-[0-9A-Fa-f]{2}){5}$"
    if not isinstance(expected, str) or re.fullmatch(pattern, expected) is None:
        raise ValueError("Invalid expected camera MAC address")
    if not isinstance(actual, str) or re.fullmatch(pattern, actual) is None:
        raise ValueError("Missing or malformed camera MAC address")
    if actual.upper() != expected.upper():
        raise ValueError("Camera MAC mismatch")


def parse_response(data: bytes, expected_type: int) -> UdpResponse:
    packet_type, payload = decode_packet(data)

    if packet_type != expected_type:
        raise ValueError(
            f"Unexpected packet type: {packet_type}, expected {expected_type}"
        )

    response = UdpResponse(packet_type=packet_type)
    seen_fields = set()
    critical_fields = {5, 61, 63, 64, 65, 66}

    for field_id, value in decode_tlvs(payload):
        if field_id in critical_fields:
            if field_id in seen_fields:
                raise ValueError(f"Duplicate critical TLV field: {field_id}")
            seen_fields.add(field_id)

        if field_id == 5:
            response.mac_address = value.decode("utf-8")

        elif field_id == 61:
            response.client_mac = value.decode("utf-8")

        elif field_id == 62:
            response.symmetric_encryption.append(value.decode("utf-8"))

        elif field_id == 63:
            response.asymmetric_encryption = value.decode("utf-8")

        elif field_id == 64:
            response.public_key = value.decode("utf-8")

        elif field_id == 65:
            if len(value) != 4:
                raise ValueError("Protocol error code must be exactly 4 bytes")
            response.error_code = int.from_bytes(value, "big")

        elif field_id == 66:
            response.json_payload = value.decode("utf-8")

        else:
            raise ValueError(f"Unsupported TLV field: {field_id}")

    if response.error_code is None:
        raise ValueError("Missing protocol error code")

    return response

import json

def parse_json_response(payload: str) -> dict:
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError('Expected JSON object')
    error = data.get('error_code')
    if type(error) is not int:
        raise ValueError('Missing or invalid JSON error_code')
    if error != 0:
        raise ValueError(f'Camera JSON error: {error}')
    return data


def parse_encrypted_response(
    packet: bytes,
    expected_camera_mac: str,
    aes_key: str,
    aes_iv: str,
) -> dict:
    """Decode and validate an encrypted UDP type 14 response."""

    from .crypto import decrypt_json

    response = parse_response(packet, expected_type=14)

    validate_camera_mac(response.mac_address, expected_camera_mac)

    if response.error_code != 0:
        raise ValueError(
            f"UDP protocol error: {response.error_code}"
        )

    if response.json_payload is None:
        raise ValueError("Missing encrypted JSON payload")

    plaintext = decrypt_json(
        response.json_payload,
        aes_key,
        aes_iv,
    )

    return parse_json_response(plaintext)
