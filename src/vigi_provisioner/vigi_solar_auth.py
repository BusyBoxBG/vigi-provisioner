import hashlib
import secrets
import string


ALPHABET = string.ascii_uppercase + string.digits


def random_nonce(length=32):
    return "".join(
        secrets.choice(ALPHABET)
        for _ in range(length)
    )


def uppercase_hash(value, algorithm):
    return hashlib.new(
        algorithm,
        value.encode("utf-8")
    ).hexdigest().upper()


def build_exchange_key(
    cnonce,
    realm,
    username,
    password_hash,
    encrypted=True,
):
    algorithm = "sha256" if encrypted else "md5"

    first = uppercase_hash(
        cnonce + "=:!" + username,
        algorithm,
    )

    digest = uppercase_hash(
        first + realm + "=:#" + password_hash,
        algorithm,
    )

    exchange_key = {
        "cnonce": cnonce,
        "realm": realm,
        "digest": digest,
    }

    if encrypted:
        exchange_key["encrypt"] = 1

    return {
        "method": "do",
        "access": {
            "exchange_key": exchange_key
        },
    }


def build_solar_exchange_request(
    username,
    password_hash,
    encrypted=True,
):
    return build_exchange_key(
        cnonce=random_nonce(),
        realm=random_nonce(),
        username=username,
        password_hash=password_hash,
        encrypted=encrypted,
    )


def build_solar_login_request(
    username,
    password,
    encrypted=True,
):
    from .vigi_password import vigi_md5_password

    password_hash = vigi_md5_password(password)

    return build_solar_exchange_request(
        username=username,
        password_hash=password_hash,
        encrypted=encrypted,
    )
