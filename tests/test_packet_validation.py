def test_existing_checks():
    from vigi_provisioner.packets import encode_packet, decode_packet
    original = encode_packet(9, b"test-payload")
    assert decode_packet(original) == (9, b"test-payload")
    print("Valid packet: PASSED")
    cases = {
        "Reserved byte 3": (3, 1),
        "Reserved byte 12": (12, 1),
        "Reserved byte 13": (13, 1),
        "Invalid magic": (4, 0),
        "Invalid payload length": (11, 0),
        "Invalid checksum": (8, original[8] ^ 1),
    }
    for name, (offset, value) in cases.items():
        packet = bytearray(original)
        packet[offset] = value
        try:
            decode_packet(bytes(packet))
        except ValueError:
            print(name + ": REJECTED")
        else:
            raise AssertionError(name + " was accepted")
    print("Network operations: NONE")
