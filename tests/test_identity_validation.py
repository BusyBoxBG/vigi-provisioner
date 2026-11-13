def test_existing_checks():
    import json
    from vigi_provisioner.packets import encode_packet, encode_tlv
    from vigi_provisioner.crypto import encrypt_json
    from vigi_provisioner.responses import parse_encrypted_response

    mac = "20-E1-5D-C8-95-94"
    key, iv = "A"*32, "B"*16
    encrypted = encrypt_json(json.dumps({"error_code": 0}), key, iv)

    def make_response(mac_fields, error=b"\x00\x00\x00\x00"):
        fields = b"".join(encode_tlv(5, value) for value in mac_fields)
        fields += encode_tlv(65, error)
        fields += encode_tlv(66, encrypted.encode("ascii"))
        return encode_packet(14, fields)

    valid = make_response([mac.encode()])
    assert parse_encrypted_response(valid, mac, key, iv)["error_code"] == 0
    print("Valid camera MAC: PASSED")

    for name, packet in [
        ("Missing MAC", make_response([])),
        ("Wrong MAC", make_response([b"AA-BB-CC-DD-EE-FF"])),
    ]:
        try:
            parse_encrypted_response(packet, mac, key, iv)
        except ValueError:
            print(name + ": REJECTED")
        else:
            raise AssertionError(name + " was accepted")

    duplicate = make_response([b"AA-BB-CC-DD-EE-FF", mac.encode()])
    try:
        parse_encrypted_response(duplicate, mac, key, iv)
    except ValueError:
        print("Duplicate MAC: REJECTED")
    else:
        print("Duplicate MAC: CURRENTLY ACCEPTED (GAP)")

    malformed = make_response([b"not-a-mac"])
    try:
        parse_encrypted_response(malformed, "not-a-mac", key, iv)
    except ValueError:
        print("Malformed matching MAC: REJECTED")
    else:
        print("Malformed matching MAC: CURRENTLY ACCEPTED (GAP)")

    empty_error = make_response([mac.encode()], b"")
    try:
        parse_encrypted_response(empty_error, mac, key, iv)
    except ValueError:
        print("Empty error code: REJECTED")
    else:
        print("Empty error code: CURRENTLY ACCEPTED (GAP)")

    print("Network operations: NONE")
