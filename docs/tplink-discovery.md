# TP-Link VIGI discovery over UDP

The active implementation is [vigi_discovery.py](../src/vigi_provisioner/vigi_discovery.py). It discovers devices and extracts their reported identity, factory state, and ONVIF endpoint. All of the offsets and tags below describe this implementation's observed format. Camera firmware variants may differ.

## Request and receive loop

`discover(local_ip, timeout)` opens an IPv4 datagram socket, enables broadcast, binds to the supplied local IPv4 address and an OS-selected source port, then sends the fixed `REQUEST` bytes to `255.255.255.255:5001`. The UDP source address of each reply becomes the returned camera IP. Use the address of the Ubuntu interface connected to the camera LAN. Limited broadcast normally stays on that LAN.

The fixed probe begins with the byte sequence `01 02 0e 00 e1 2b 83 c7 8b df 00 15 00 00`. The remainder is the fixed request payload in the source. The code does not construct this probe through the legacy packet encoder. The socket reads up to 8192 bytes per datagram and collects each accepted response, including duplicates. It stops after a socket receive timeout. A continuing stream of datagrams can extend the collection past the nominal timeout because the timeout is per receive.

## Response layout

Offsets are zero-based. All multibyte fields decoded by the parser are big-endian.

| Byte offsets | Interpretation in this parser |
| --- | --- |
| 0 | Unchecked |
| 1 | Response type, required to be 1 |
| 2–3 | Unchecked |
| 4–7 | Magic, required to be `e1 2b 83 c7` |
| 8–9 | Unchecked by this parser |
| 10–11 | Declared payload byte count |
| 12–13 | Unchecked |
| 14 onwards | Consecutive TLV fields |

The datagram must have exactly 14 plus the declared payload length bytes. Each field begins with a two-byte tag and two-byte length. A value that runs past the end or leftover bytes too short to form a field cause rejection. Duplicate tags overwrite earlier values and unknown tags do not affect the returned mapping. The parser does not verify a reply checksum. Malformed ASCII in the MAC field can raise a decoding exception. The parser returns `None` for its explicit framing and required-field rejections.

| Tag | Field | Handling |
| --- | --- | --- |
| `0x0005` | MAC | Required ASCII text. Normalization occurs downstream. |
| `0x0011` | Factory state | Required four-byte unsigned integer. `0` is the factory state used by activation checks, `1` fails that check, and other values become `None`. |
| `0x0006` | Model | Optional UTF-8 text |
| `0x0018` | Serial | Optional UTF-8 text |
| `0x001A` | Firmware | Optional UTF-8 text |
| `0x000E` | Device name | Optional UTF-8 text |
| `0x0012` | ONVIF endpoint | Optional UTF-8 text |
| `0x0029` | Password type | Optional UTF-8 text |
| `0x0047` | Digest type | Optional big-endian integer |

Optional text fields decode invalid UTF-8 with replacement. Empty optional fields become `None`. The manufacturer label is supplied by the implementation.

## From observation to approved binding

`adapt_udp_discovery` normalizes MAC and IPv4 values, compares the advertised adapter input with the actual packet source passed by the caller, and tags the observation `TPLINK_UDP_5001` with a monotonic timestamp. UDP evidence is explicitly untrusted. Use the enrollment and pin inventory path for an independently approved identity. The binding registry has a TTL, so an observation cannot serve indefinitely as the basis for a connection. Treat model, serial, and endpoint strings as device-supplied data.

## Older packet implementation

[discovery.py](../src/vigi_provisioner/discovery.py) is the separate legacy decoder built on [packets.py](../src/vigi_provisioner/packets.py). The legacy codec checks version, header length, reserved bytes, magic, length, and checksum. It zeroes bytes 8–9 for checksum verification, sums big-endian 16-bit words with end-around carry, adds an odd final byte as an unshifted value, and complements the result. The UDP 5001 parser above implements its own checks and does not use this decoder. Legacy key exchange and encrypted request modules are listed in the [Python reference](python-reference.md).

## C340S discovery observation

A factory-new VIGI C340S was observed at 192.168.0.60 with ONVIF port 2020 and QR TLV `TP1` + 17 hexadecimal Device ID characters + `040`. Earlier C320I observations used suffix `020`. The GUI discovery decoder now recognizes both exact wrapper shapes and retains the raw QR value and suffix. The suffix meaning is not established; it is not used to infer firmware generation or authorize provisioning. Label serial remains a separate scanned field. The decoded ID must still match the printed/scanned inventory identity. C340S activation and configuration remain untested and blocked by the existing provisioning engine.
