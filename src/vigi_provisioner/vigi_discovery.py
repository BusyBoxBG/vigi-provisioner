import socket
import struct

REQUEST = bytes.fromhex(
    "01020e00e12b83c78bdf0015000000050011"
    "0000000000000000000000000000000000"
)

MAGIC = bytes.fromhex("e12b83c7")


def parse_discovery(data, source_ip):
    if len(data) < 14 or data[4:8] != MAGIC:
        return None

    if data[1] != 1:
        return None

    payload_length = int.from_bytes(data[10:12], "big")

    if len(data) != 14 + payload_length:
        return None

    fields = {}
    offset = 14

    while offset + 4 <= len(data):
        tag, length = struct.unpack_from(">HH", data, offset)
        offset += 4

        if offset + length > len(data):
            return None

        fields[tag] = data[offset:offset + length]
        offset += length

    if offset != len(data):
        return None

    mac = fields.get(0x0005)
    factory = fields.get(0x0011)

    if mac is None or factory is None or len(factory) != 4:
        return None

    state = int.from_bytes(factory, "big")

    def text_field(tag):
        value = fields.get(tag)
        return value.decode("utf-8", errors="replace") if value else None

    return {
        "ip": source_ip,
        "mac": mac.decode("ascii"),
        "factory_flag": state if state in (0, 1) else None,
        "manufacturer": "TP-Link",
        "model": text_field(0x0006),
        "serial": text_field(0x0018),
        "firmware": text_field(0x001A),
        "device_name": text_field(0x000E),
        "onvif_endpoint": text_field(0x0012),
        "password_type": text_field(0x0029),
        "digest_type": (
            int.from_bytes(fields[0x0047], "big")
            if fields.get(0x0047)
            else None
        ),
    }


def discover(local_ip="192.168.0.10", timeout=5):
    devices = []

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind((local_ip, 0))
        sock.settimeout(timeout)
        sock.sendto(REQUEST, ("255.255.255.255", 5001))

        while True:
            try:
                data, addr = sock.recvfrom(8192)
            except socket.timeout:
                break

            device = parse_discovery(data, addr[0])

            if device is not None:
                devices.append(device)

    return devices
