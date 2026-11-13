from dataclasses import dataclass


@dataclass(frozen=True)
class SolarLoginResult:
    error_code: int
    token: str
    session_id: str | None


def parse_solar_login_response(data):
    if not isinstance(data, dict):
        raise ValueError(
            "Solar login response must be a JSON object"
        )

    error_code = data.get("errorCode", 0)

    if type(error_code) is not int:
        raise ValueError(
            "Solar login response has invalid errorCode"
        )

    if error_code != 0:
        raise ValueError(
            f"Solar login failed with errorCode {error_code}"
        )

    access = data.get("access")

    if not isinstance(access, dict):
        raise ValueError(
            "Solar login response has no access object"
        )

    token = access.get("token")

    if not isinstance(token, str) or not token:
        raise ValueError(
            "Solar login response has no valid token"
        )

    session_id = access.get("sessionId")

    if session_id is not None:
        if not isinstance(session_id, str):
            raise ValueError(
                "Solar login sessionId must be a string"
            )

    return SolarLoginResult(
        error_code=error_code,
        token=token,
        session_id=session_id,
    )
