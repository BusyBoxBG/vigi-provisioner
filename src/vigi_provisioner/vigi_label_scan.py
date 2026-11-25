"""Parse one camera label stream; no inventory or camera writes.

Initial label format: TP1 + 17 hex Device ID + 020/040, 12 hex MAC,
13 alphanumeric serial starting with a digit. Ambiguity is never guessed.
"""
import re

QR = re.compile(r"TP1([0-9A-F]{17})(020|040)")
MAC = re.compile(r"[0-9A-F]{12}")
SERIAL = re.compile(r"[0-9][A-Z0-9]{12}")
SEPARATORS = " \t\r\n|"


def parse_label_stream(raw):
    if not isinstance(raw, str) or len(raw) > 4096:
        raise ValueError("Scan buffer limit reached. Clear and scan one label again.")
    raw = raw.upper()
    # Each state holds position and the distinct identity values collected so far.
    states = [(0, (None, None, None))]
    seen = set()
    complete, partial = set(), set()
    conflicts = False
    while states:
        pos, values = states.pop()
        while pos < len(raw) and raw[pos] in SEPARATORS:
            pos += 1
        state = (pos, values)
        if state in seen:
            continue
        seen.add(state)
        if len(seen) > 8192:
            raise ValueError("Scan is too ambiguous. Clear and scan codes separately.")
        if pos == len(raw):
            complete.add(values)
            continue
        end = pos
        while end < len(raw) and raw[end] not in SEPARATORS:
            end += 1
        chunk = raw[pos:end]
        tokens = []
        match = QR.match(chunk)
        if match:
            tokens.append((23, 0, match[1]))
        if len(chunk) >= 12 and MAC.fullmatch(chunk[:12]):
            tokens.append((12, 1, chunk[:12]))
        if len(chunk) >= 13 and SERIAL.fullmatch(chunk[:13]):
            tokens.append((13, 2, chunk[:13].lower()))
        for length, index, value in tokens:
            if values[index] is not None and values[index] != value:
                conflicts = True
                continue
            updated = list(values)
            updated[index] = value
            states.append((pos + length, tuple(updated)))
        if end == len(raw):
            qr_prefix = ("TP1".startswith(chunk) or
                (chunk.startswith("TP1") and len(chunk) < 23
                 and re.fullmatch(r"[0-9A-F]*", chunk[3:]) is not None))
            qr_prefix = qr_prefix and (values[0] is None or any(
                ("TP1" + values[0] + suffix).startswith(chunk) for suffix in ("020", "040")))
            mac_prefix = (len(chunk) < 12 and re.fullmatch(r"[0-9A-F]+", chunk)
                          and (values[1] is None or values[1].startswith(chunk)))
            serial_prefix = (len(chunk) < 13 and re.fullmatch(r"[0-9][A-Z0-9]*", chunk)
                             and (values[2] is None or values[2].upper().startswith(chunk)))
            if qr_prefix or mac_prefix or serial_prefix:
                partial.add(values)
    candidates = complete or partial
    fields = {}
    for i, name in enumerate(("device_id", "mac_address", "label_serial")):
        possible = {v[i] for v in candidates if v[i] is not None}
        if len(possible) == 1:
            fields[name] = next(iter(possible))
    full = {v for v in complete if all(v)}
    ready = len(complete) == 1 and len(full) == 1 and not partial
    if ready:
        status = "All three fields detected. Review and accept this camera."
    elif len(complete) > 1:
        status = "Ambiguous input. Scan codes separately or use manual entry."
    elif partial:
        status = "Collecting; a code may be incomplete. Continue scanning."
    elif complete:
        status = "Collecting; scan the remaining codes."
    elif conflicts:
        status = "Conflicting codes detected. Clear and scan one camera only."
    else:
        status = "Unrecognized input. Clear and rescan, or enter fields manually."
    return dict(fields=fields, ready=ready, status=status)


def crosscheck_discovery(fields, cameras):
    """Compare label identity with factory-state UDP observations; serial stays unverified."""
    from .vigi_discovery import decode_device_id
    from .vigi_pin_inventory import normalize_mac
    expected_id = fields["device_id"].upper()
    expected_mac = normalize_mac(fields["mac_address"])
    matches, related = [], []
    for camera in cameras:
        if camera.get("factory_flag") != 0:
            continue
        try:
            mac = normalize_mac(camera.get("mac") or "")
        except ValueError:
            continue
        device_id = camera.get("device_id") or decode_device_id(camera.get("serial"))
        same_mac, same_id = mac == expected_mac, device_id == expected_id
        if same_mac and same_id:
            matches.append(camera)
        elif same_mac or same_id:
            related.append(camera)
    if related:
        return dict(matched=False, status="Discovery identity conflict. Device ID and MAC must both match.")
    if not matches:
        return dict(matched=False, status="No factory-state camera confirmed both scanned Device ID and MAC. Check connection and retry.")
    signatures = {(c.get("ip"), c.get("model")) for c in matches}
    if len(signatures) != 1 or any(
        c.get("factory_flag") == 0 and c.get("ip") == matches[0].get("ip") and c not in matches
        for c in cameras
    ):
        return dict(matched=False, status="Discovery reported conflicting addresses, models or devices at the same IP.")
    camera = matches[0]
    return dict(matched=True, status="Discovery matched Device ID and MAC. Label serial is scanner-only; discovery does not verify it.",
                camera={key: camera.get(key) for key in ("ip","model","device_name","onvif_endpoint","factory_flag")})
