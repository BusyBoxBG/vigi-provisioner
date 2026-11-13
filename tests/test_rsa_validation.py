def test_existing_checks():
    import base64

    from cryptography.hazmat.primitives.asymmetric import rsa, ec, padding
    from cryptography.hazmat.primitives import serialization

    from vigi_provisioner.crypto import encrypt_session_key, encrypt_ipc_password


    def make_rsa(bits):
        return rsa.generate_private_key(
            public_exponent=65537,
            key_size=bits
        )


    def pem(public):
        return public.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode("ascii")


    def der(public):
        return public.public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo
        )


    def must_reject(function, *args):
        try:
            function(*args)
        except ValueError:
            return
        raise AssertionError("Invalid input was accepted")


    for bits in (2048, 3072):
        private = make_rsa(bits)
        public = private.public_key()

        session_key = bytes(range(32))
        encrypted = encrypt_session_key(session_key, pem(public))

        recovered = private.decrypt(
            base64.b64decode(encrypted),
            padding.PKCS1v15()
        )
        assert recovered == session_key

        encrypted = encrypt_ipc_password(
            "VIGI-OFFLINE-TEST", der(public)
        )

        recovered = private.decrypt(
            base64.b64decode(encrypted),
            padding.PKCS1v15()
        )
        assert recovered == b"VIGI-OFFLINE-TEST"

        print(f"RSA {bits}-bit encryption/decryption: PASSED")


    weak = make_rsa(1024)
    must_reject(encrypt_session_key, b"A"*32, pem(weak.public_key()))
    must_reject(encrypt_ipc_password, "test", der(weak.public_key()))
    print("RSA 1024-bit rejection: PASSED")


    ec_private = ec.generate_private_key(ec.SECP256R1())
    ec_public = ec_private.public_key()

    ec_pem = ec_public.public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode("ascii")

    ec_der = ec_public.public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo
    )

    must_reject(encrypt_session_key, b"A"*32, ec_pem)
    must_reject(encrypt_ipc_password, "test", ec_der)
    print("Non-RSA key rejection: PASSED")


    must_reject(encrypt_session_key, b"A"*32, "invalid PEM")
    must_reject(encrypt_ipc_password, "test", b"invalid DER")
    print("Malformed key rejection: PASSED")


    must_reject(
        encrypt_ipc_password, "",
        der(make_rsa(2048).public_key())
    )
    must_reject(
        encrypt_session_key, b"short",
        pem(make_rsa(2048).public_key())
    )
    print("Invalid input rejection: PASSED")


    private = make_rsa(2048)
    password = "A"*500

    encrypted = base64.b64decode(
        encrypt_ipc_password(password, der(private.public_key()))
    )

    block_size = private.key_size // 8

    assert len(encrypted) % block_size == 0

    recovered = b"".join(
        private.decrypt(
            encrypted[i:i+block_size],
            padding.PKCS1v15()
        )
        for i in range(0, len(encrypted), block_size)
    )

    assert recovered == password.encode("utf-8")
    print("Long-password chunking: PASSED")

    print("ALL RSA TESTS PASSED")
    print("Network operations: NONE")
