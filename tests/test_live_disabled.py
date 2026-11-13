def test_existing_checks():
    from vigi_provisioner.live_transport import LiveUdpTransport
    from vigi_provisioner.packets import encode_packet

    t = LiveUdpTransport()
    try:
        t.exchange(encode_packet(8, b""), ("192.0.2.1", 20002))
    except RuntimeError as exc:
        assert str(exc) == "Live UDP transmission disabled"
        print("Default-disabled protection: PASSED")
    else:
        raise AssertionError("Transport unexpectedly enabled")

    print("Network operations: NONE")
