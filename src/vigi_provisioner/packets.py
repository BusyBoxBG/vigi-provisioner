
from __future__ import annotations

import struct

MAGIC = bytes.fromhex("E1 2B 83 C7")
HEADER_SIZE = 14


def checksum(data: bytes) -> int:
    """Match TP-Link's F.a(byte[], int) checksum."""
    total = 0

    for i in range(0, len(data) - 1, 2):
        total += (data[i] << 8) | data[i + 1]

    if len(data) % 2:
        total += data[-1]

    while total >> 16:
        total = (total & 0xFFFF) + (total >> 16)

    return (~total) & 0xFFFF


def encode_tlv(field_id: int, value: bytes) -> bytes:
    if not 0 <= field_id <= 0xFFFF:
        raise ValueError("Invalid TLV field ID")

    if len(value) > 0xFFFF:
        raise ValueError("TLV value too large")

    return struct.pack(">HH", field_id, len(value)) + value


def decode_tlvs(data: bytes) -> list[tuple[int, bytes]]:
    result = []
    offset = 0

    while offset < len(data):
        if len(data) - offset < 4:
            raise ValueError("Truncated TLV header")

        field_id, length = struct.unpack_from(">HH", data, offset)
        offset += 4

        if offset + length > len(data):
            raise ValueError("Truncated TLV value")

        result.append((field_id, data[offset:offset + length]))
        offset += length

    return result


def encode_packet(packet_type: int, payload: bytes) -> bytes:
    if not 0 <= packet_type <= 255:
        raise ValueError("Invalid packet type")

    if len(payload) > 0xFFFF:
        raise ValueError("Payload too large")

    header = bytearray([
        0x01,
        packet_type,
        HEADER_SIZE,
        0x00,
        *MAGIC,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
    ])

    struct.pack_into(">H", header, 10, len(payload))

    packet = header + payload
    struct.pack_into(">H", packet, 8, checksum(packet))

    return bytes(packet)


def decode_packet(data: bytes) -> tuple[int, bytes]:
    if len(data) < HEADER_SIZE:
        raise ValueError("Packet too short")

    if data[0] != 1 or data[2] != HEADER_SIZE:
        raise ValueError("Invalid packet header")

    if data[3] != 0 or data[12:14] != bytes(2):
        raise ValueError("Invalid reserved header bytes")

    if data[4:8] != MAGIC:
        raise ValueError("Invalid protocol magic")

    payload_length = struct.unpack_from(">H", data, 10)[0]

    if len(data) != HEADER_SIZE + payload_length:
        raise ValueError("Packet length mismatch")

    received_checksum = struct.unpack_from(">H", data, 8)[0]

    copy = bytearray(data)
    copy[8:10] = b"\x00\x00"

    if checksum(copy) != received_checksum:
        raise ValueError("Invalid packet checksum")

    return data[1], data[HEADER_SIZE:]
