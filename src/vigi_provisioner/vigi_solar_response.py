import re
from dataclasses import dataclass

from .vigi_solar_crypto import verify_response_digest


@dataclass(frozen=True)
class SolarAuthResponse:
    error_code: int
    session_id: str
    server_nonce: str
    digest: str
    encrypt: list


def parse_solar_response(data):
    if not isinstance(data, dict):
        raise ValueError("Response must be a JSON object")

    error_code = data.get("errorCode")

    if type(error_code) is not int:
        raise ValueError("Missing or invalid errorCode")

    if error_code != 0:
        raise ValueError(
            f"Solar authentication error: {error_code}"
        )

    access = data.get("access")

    if not isinstance(access, dict):
        raise ValueError("Missing access object")

    session_id = access.get("sessionId")

    # Reject malformed device-provided session IDs early.
    if (
        not isinstance(session_id, str)
        or not session_id
        or len(session_id) > 256
        or not re.fullmatch(
            r"[A-Za-z0-9._~+/=%:-]+",
            session_id,
            flags=re.ASCII,
        )
    ):
        raise ValueError("Invalid Solar session ID")
    server_nonce = access.get("nonce")
    digest = access.get("digest")
    encrypt = access.get("encrypt")

    for name, value in (
        ("sessionId", session_id),
        ("nonce", server_nonce),
        ("digest", digest),
    ):
        if not isinstance(value, str) or not value:
            raise ValueError(
                f"Missing or invalid access.{name}"
            )

    if encrypt is not None and not isinstance(encrypt, list):
        raise ValueError("Invalid access.encrypt")

    return SolarAuthResponse(
        error_code=error_code,
        session_id=session_id,
        server_nonce=server_nonce,
        digest=digest,
        encrypt=encrypt,
    )


def validate_solar_response(
    response,
    password_hash,
    encrypted=True,
):
    return verify_response_digest(
        server_nonce=response.server_nonce,
        password_hash=password_hash,
        received_digest=response.digest,
        encrypted=encrypted,
    )
