def test_existing_checks():
    from vigi_provisioner.workflow import InitializationWorkflow
    from vigi_provisioner.responses import UdpResponse

    mac = "20-E1-5D-C8-95-94"
    w = InitializationWorkflow(mac, "AA-BB-CC-DD-EE-FF", "A"*32, "B"*16)

    for packet_type in (9, 11):
        response = UdpResponse(packet_type=packet_type, mac_address=mac, error_code=0)
        w._validate_handshake(response)
        print(f"Type {packet_type} valid MAC: PASSED")

        response = UdpResponse(packet_type=packet_type, mac_address=mac.lower(), error_code=0)
        try:
            w._validate_handshake(response)
        except ValueError:
            print(f"Type {packet_type} lowercase MAC: CURRENTLY REJECTED")
        else:
            print(f"Type {packet_type} lowercase MAC: ACCEPTED")

    bad = InitializationWorkflow("not-a-mac", "AA-BB-CC-DD-EE-FF", "A"*32, "B"*16)
    response = UdpResponse(packet_type=9, mac_address="not-a-mac", error_code=0)
    try:
        bad._validate_handshake(response)
    except ValueError:
        print("Malformed matching MAC: REJECTED")
    else:
        print("Malformed matching MAC: CURRENTLY ACCEPTED (GAP)")

    print("Network operations: NONE")
