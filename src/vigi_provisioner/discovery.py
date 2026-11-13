from __future__ import annotations

from dataclasses import dataclass, field

from .packets import decode_packet, decode_tlvs


@dataclass
class DiscoveryPacket:
    packet_type: int
    fields: dict[int, list[bytes]] = field(default_factory=dict)

    def text(self, field_id: int) -> str | None:
        values = self.fields.get(field_id, [])
        if len(values) != 1:
            return None
        try:
            return values[0].decode("utf-8").rstrip("\x00")
        except UnicodeDecodeError:
            return None

    def hex(self, field_id: int) -> list[str]:
        return [value.hex(" ") for value in self.fields.get(field_id, [])]


def parse_discovery(data: bytes) -> DiscoveryPacket:
    packet_type, payload = decode_packet(data)

    if packet_type != 1:
        raise ValueError(
            f"Expected discovery packet type 1, got {packet_type}"
        )

    result = DiscoveryPacket(packet_type=packet_type)

    for field_id, value in decode_tlvs(payload):
        result.fields.setdefault(field_id, []).append(value)

    return result

@dataclass
class DiscoveredCamera:
    mac_address: str | None
    model: str | None
    ip_address: str | None
    serial_number: str | None
    device_uuid: str | None
    device_identifier: str | None
    onvif_endpoint: str | None
    password_algorithm: str | None


def extract_camera(packet: DiscoveryPacket) -> DiscoveredCamera:
    if packet.packet_type != 1:
        raise ValueError("Not a discovery packet")

    return DiscoveredCamera(
        mac_address=packet.text(0x0005),
        model=packet.text(0x0006),
        ip_address=packet.text(0x0008),
        serial_number=packet.text(0x0018),
        device_uuid=packet.text(0x000D),
        device_identifier=packet.text(0x000E),
        onvif_endpoint=packet.text(0x0012),
        password_algorithm=packet.text(0x0029),
    )
