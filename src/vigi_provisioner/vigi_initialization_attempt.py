from dataclasses import dataclass
from enum import Enum


class AttemptStatus(str, Enum):
    NOT_SENT = "NOT_SENT"
    UNKNOWN_OUTCOME = "UNKNOWN_OUTCOME"
    SUCCESS = "SUCCESS"


@dataclass(frozen=True)
class AttemptResult:
    status: AttemptStatus
    transmission_attempted: bool
    response_validated: bool
    cleanup_failed: bool = False


def perform_single_attempt(
    transport,
    request,
    response_validator,
):
    """
    Offline-testable single-attempt state machine.

    The supplied transport is always closed.

    Any failure after entering sendall() is classified
    UNKNOWN_OUTCOME.

    Cleanup failures are reported without overriding
    the transmission outcome.

    This is not an authorized live camera sender.
    """

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

        valid_validator = callable(response_validator)

        valid_send = callable(
            getattr(transport, "sendall", None)
        )

        valid_recv = callable(
            getattr(transport, "recv", None)
        )

        if (
            valid_request
            and valid_validator
            and valid_send
            and valid_recv
        ):
            attempted = True
            status = AttemptStatus.UNKNOWN_OUTCOME

            try:
                transport.sendall(request)

                response = response_validator(transport)

                if response is True:
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
