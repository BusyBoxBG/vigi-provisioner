"""
Validate the result of a VIGI initialization request.

This module does not open sockets or transmit HTTP.
"""

from dataclasses import dataclass

from .vigi_http_response import ParsedHttpResponse


class InitializationResultError(ValueError):
    pass


@dataclass(frozen=True)
class InitializationResult:
    http_status: int
    camera_error_code: int
    success: bool


def validate_initialization_result(response):
    if not isinstance(
        response,
        ParsedHttpResponse,
    ):
        raise InitializationResultError(
            "Expected ParsedHttpResponse"
        )

    if response.status_code != 200:
        raise InitializationResultError(
            "Initialization HTTP status not successful"
        )

    payload = response.json_body

    if not isinstance(payload, dict):
        raise InitializationResultError(
            "Expected camera JSON object"
        )

    if "error_code" not in payload:
        raise InitializationResultError(
            "Camera error_code missing"
        )

    error_code = payload["error_code"]

    if type(error_code) is not int:
        raise InitializationResultError(
            "Camera error_code must be integer"
        )

    if error_code != 0:
        raise InitializationResultError(
            "Camera reported initialization failure"
        )

    return InitializationResult(
        http_status=response.status_code,
        camera_error_code=error_code,
        success=True,
    )
