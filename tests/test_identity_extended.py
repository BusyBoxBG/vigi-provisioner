def test_existing_checks():
    import json
    from vigi_provisioner.packets import encode_packet, encode_tlv
    from vigi_provisioner.crypto import encrypt_json
    from vigi_provisioner.responses import parse_encrypted_response

    mac = "20-E1-5D-C8-95-94"
    key, iv = "A"*32, "B"*16
    encrypted = encrypt_json(json.dumps({"error_code": 0}), key, iv).encode("ascii")

    def make(fields):
        return encode_packet(14, b"".join(encode_tlv(i,v) for i,v in fields))

    base = [(5,mac.encode()),(65,bytes(4)),(66,encrypted)]

    cases = [
        ("Duplicate client MAC", base + [(61,b"AA-BB-CC-DD-EE-FF"),(61,b"AA-BB-CC-DD-EE-FF")]),
        ("Duplicate error code", base + [(65,bytes(4))]),
        ("Duplicate encrypted JSON", base + [(66,encrypted)]),
        ("Error code length 0", [(5,mac.encode()),(65,b""),(66,encrypted)]),
        ("Error code length 1", [(5,mac.encode()),(65,b"\x00"),(66,encrypted)]),
        ("Error code length 3", [(5,mac.encode()),(65,bytes(3)),(66,encrypted)]),
        ("Error code length 5", [(5,mac.encode()),(65,bytes(5)),(66,encrypted)]),
    ]

    for name, fields in cases:
        try:
            parse_encrypted_response(make(fields),mac,key,iv)
        except ValueError:
            print(name + ": REJECTED")
        else:
            raise AssertionError(name + " was accepted")

    lower = make([(5,mac.lower().encode()),(65,bytes(4)),(66,encrypted)])
    assert parse_encrypted_response(lower,mac,key,iv)["error_code"] == 0
    print("Lowercase MAC normalization: PASSED")
    print("Network operations: NONE")
