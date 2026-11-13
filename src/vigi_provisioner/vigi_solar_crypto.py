import hashlib
import hmac


def hash_upper(value, algorithm):
    return hashlib.new(
        algorithm,
        value.encode("utf-8"),
    ).hexdigest().upper()


def verify_response_digest(
    server_nonce,
    password_hash,
    received_digest,
    encrypted=True,
):
    algorithm = "sha256" if encrypted else "md5"

    expected = hash_upper(
        server_nonce + ":" + password_hash,
        algorithm,
    )

    return hmac.compare_digest(
        expected,
        received_digest,
    )


def derive_aes_key(
    cnonce,
    server_nonce,
    password_hash,
    encrypted=True,
):
    if encrypted:
        return hashlib.pbkdf2_hmac(
            "sha256",
            password_hash.encode("utf-8"),
            (cnonce + "+" + server_nonce).encode("utf-8"),
            5000,
            dklen=16,
        )

    return hashlib.md5(
        (
            cnonce + "+" + server_nonce
            + "+" + password_hash
        ).encode("utf-8")
    ).digest()


def derive_aes_iv(
    server_nonce,
    username,
    encrypted=True,
):
    if encrypted:
        return hashlib.pbkdf2_hmac(
            "sha256",
            username.encode("utf-8"),
            server_nonce.encode("utf-8"),
            5000,
            dklen=16,
        )

    return hashlib.md5(
        (
            server_nonce + "+" + username
        ).encode("utf-8")
    ).digest()


def derive_addition(cnonce, server_nonce):
    client_bytes = cnonce.encode("utf-8")
    server_bytes = server_nonce.encode("utf-8")

    if len(client_bytes) < 8 or len(server_bytes) < 8:
        raise ValueError(
            "Both nonces must contain at least 8 UTF-8 bytes"
        )

    return client_bytes[:8] + server_bytes[:8]
