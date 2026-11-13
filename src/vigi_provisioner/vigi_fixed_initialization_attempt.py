"""
Offline-testable fixed-validation initialization attempt.

This module does not open network connections.
It is not an authorized live initialization API.
"""

import time

from .vigi_write_deadline import send_with_deadline
from .vigi_deadline_stream import DeadlineStream

from .vigi_initialization_attempt import (
    AttemptResult,
    AttemptStatus,
)
from .vigi_http_stream import read_http_stream
from .vigi_initialization_result import (
    validate_initialization_result,
)


def perform_fixed_initialization_attempt(
    transport,
    request,
):
    if not callable(getattr(transport, "close", None)):
        raise TypeError("Transport must support close()")

    status = AttemptStatus.NOT_SENT
    attempted = False
    validated = False
    cleanup_failed = False

    try:
        valid_request = (
            type(request) is bytes
            and len(request) > 0
        )

        valid_transport = (
            callable(getattr(transport, "send", None))
            and callable(getattr(transport, "recv", None))
            and callable(getattr(transport, "settimeout", None))
        )

        if valid_request and valid_transport:
            attempted = True
            status = AttemptStatus.UNKNOWN_OUTCOME

            try:
                send_with_deadline(
                    transport,
                    request,
                    deadline_seconds=10.0,
                    per_write_timeout=2.0,
                )

                read_deadline = time.monotonic() + 10.0

                response_stream = DeadlineStream(
                    transport,
                    deadline=read_deadline,
                    per_read_timeout=5.0,
                )

                response = read_http_stream(
                    response_stream,
                    deadline_seconds=10.0,
                )

                result = validate_initialization_result(
                    response
                )

                if result.success is True:
                    status = AttemptStatus.SUCCESS
                    validated = True

            except Exception:
                status = AttemptStatus.UNKNOWN_OUTCOME
                validated = False

    finally:
        try:
            transport.close()
        except Exception:
            cleanup_failed = True

    return AttemptResult(
        status=status,
        transmission_attempted=attempted,
        response_validated=validated,
        cleanup_failed=cleanup_failed,
    )
