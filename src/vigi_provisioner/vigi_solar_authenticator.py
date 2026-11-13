"""VIGI Solar authentication coordinator.

The transport callback is supplied externally.
No network implementation is included.
"""

import json
from urllib.parse import urlencode

from .vigi_password import vigi_md5_password
from .vigi_solar_auth import (
    build_exchange_key,
    build_solar_exchange_request,
)
from .vigi_solar_response import (
    parse_solar_response,
    validate_solar_response,
)
from .vigi_solar_crypto import (
    derive_aes_key,
    derive_aes_iv,
    derive_addition,
)
from .vigi_solar_login import build_solar_login
from .vigi_solar_login_response import parse_solar_login_response
from .vigi_solar_session import SolarAuthContext


def authenticate_solar(
    device_id,
    ip,
    port,
    username,
    password,
    exchange,
):
    """Authenticate using an injected exchange(uri, request) callback.

    The callback receives a URI and a JSON-compatible request dictionary,
    and returns a decoded response dictionary.
    """

    if not callable(exchange):
        raise TypeError("exchange must be callable")

    password_hash = vigi_md5_password(password)

    initial = build_solar_exchange_request(
        username,
        password_hash,
        encrypted=True,
    )

    exchange_data = initial["access"]["exchange_key"]
    cnonce = exchange_data["cnonce"]
    realm = exchange_data["realm"]

    base_uri = f"http://{ip}:{int(port)}/"

    response_data = exchange(base_uri, initial)

    if not isinstance(response_data, dict):
        raise ValueError("Invalid Solar exchange response")

    access = response_data.get("access")

    if not isinstance(access, dict):
        raise ValueError("Solar exchange response has no access object")

    encrypted = access.get("encrypt") is not None

    if not encrypted:
        legacy = build_exchange_key(
            cnonce,
            realm,
            username,
            password_hash,
            encrypted=False,
        )

        response_data = exchange(base_uri, legacy)

    response = parse_solar_response(response_data)

    if not validate_solar_response(
        response,
        password_hash,
        encrypted=encrypted,
    ):
        raise ValueError("Solar server digest verification failed")

    aes_key = derive_aes_key(
        cnonce,
        response.server_nonce,
        password_hash,
        encrypted=encrypted,
    )

    aes_iv = derive_aes_iv(
        response.server_nonce,
        username,
        encrypted=encrypted,
    )

    addition = (
        derive_addition(cnonce, response.server_nonce)
        if encrypted
        else None
    )

    login_request = build_solar_login(
        username=username,
        password_hash=password_hash,
        aes_key=aes_key,
        aes_iv=aes_iv,
        addition=addition,
        encrypted=encrypted,
    )

    solar_uri = (
        base_uri
        + "?"
        + urlencode({"sid": response.session_id})
    )

    login_data = exchange(solar_uri, login_request)
    login_result = parse_solar_login_response(login_data)

    return SolarAuthContext(
        device_id=str(device_id),
        solar_uri=solar_uri,
        aes_key=aes_key,
        aes_iv=aes_iv,
        addition=addition,
        digest_type=17 if encrypted else None,
        token=login_result.token,
        session_id=response.session_id,
    )
