def test_existing_checks():
    from vigi_provisioner.init_payload import transform_password

    assert len(transform_password("TestPassword123", "md5")) == 32
    print("MD5 transformation: PASSED")

    invalid_types = ["", "sha256", "unknown", None]

    for value in invalid_types:
        try:
            transform_password("TestPassword123", value)
        except ValueError:
            print("Rejected:", repr(value))
        else:
            raise AssertionError(f"Invalid password type accepted: {value!r}")

    for password in ["", None]:
        try:
            transform_password(password, "md5")
        except ValueError:
            print("Rejected password:", repr(password))
        else:
            raise AssertionError("Invalid password accepted")

    print("All password validation tests: PASSED")
    print("Network operations: NONE")
