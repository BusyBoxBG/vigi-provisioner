"""
Socket timeout helper for a bounded read deadline.

Does not create or connect sockets.
"""

import math
import time


class SocketDeadlineError(ValueError):
    pass


def configure_read_timeout(
    sock,
    *,
    deadline,
    per_read_timeout=5.0,
    clock=None,
):
    if (
        not hasattr(sock, "settimeout")
        or not callable(sock.settimeout)
    ):
        raise SocketDeadlineError(
            "Socket must support settimeout()"
        )

    if (
        type(deadline) not in (int, float)
        or not math.isfinite(deadline)
    ):
        raise SocketDeadlineError(
            "Invalid absolute deadline"
        )

    if (
        type(per_read_timeout) not in (int, float)
        or not math.isfinite(per_read_timeout)
        or not 0 < per_read_timeout <= 30
    ):
        raise SocketDeadlineError(
            "Invalid per-read timeout"
        )

    if clock is None:
        clock = time.monotonic

    if not callable(clock):
        raise SocketDeadlineError(
            "Invalid clock"
        )

    try:
        now = clock()
    except Exception as exc:
        raise SocketDeadlineError(
            "Clock read failed"
        ) from exc

    if (
        type(now) not in (int, float)
        or not math.isfinite(now)
    ):
        raise SocketDeadlineError(
            "Invalid clock reading"
        )

    remaining = deadline - now

    if (
        not math.isfinite(remaining)
        or remaining <= 0
    ):
        raise SocketDeadlineError(
            "Socket deadline expired"
        )

    timeout = min(
        float(per_read_timeout),
        remaining,
    )

    try:
        sock.settimeout(timeout)
    except Exception as exc:
        raise SocketDeadlineError(
            "Failed to configure socket timeout"
        ) from exc

    return timeout
