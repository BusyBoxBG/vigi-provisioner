def test_existing_checks():
    from vigi_provisioner.transport import MockUdpTransport
    destination = ("192.0.2.1", 20002)
    payload = b"simulated-response"
    valid = MockUdpTransport([(payload, destination)])
    assert valid.exchange(b"request", destination) == payload
    print("Matching source: PASSED")
    for source in [("192.0.2.2", 20002), ("192.0.2.1", 20003), ("192.0.2.2", 20003)]:
        mock = MockUdpTransport([(payload, source)])
        try:
            mock.exchange(b"request", destination)
        except ValueError:
            print("Rejected unexpected source:", source)
        else:
            raise AssertionError("Unexpected source accepted")
    legacy = MockUdpTransport([payload])
    assert legacy.exchange(b"request", destination) == payload
    print("Legacy mock compatibility: PASSED")
    print("Network operations: NONE")
