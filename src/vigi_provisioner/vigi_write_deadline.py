"""
Bounded write helper.

Does not create or connect sockets.
Does not authorize camera initialization.
"""

import math
import time


class WriteDeadlineError(Exception):
    pass


def send_with_deadline(
    transport,
    data,
    *,
    deadline_seconds=10.0,
    per_write_timeout=2.0,
    clock=None,
):
    if type(data) is not bytes or not data:
        raise WriteDeadlineError("Invalid request bytes")

    if (
        type(deadline_seconds) not in (int, float)
        or not math.isfinite(deadline_seconds)
        or not 0 < deadline_seconds <= 60
    ):
        raise WriteDeadlineError("Invalid write deadline")

    if (
        type(per_write_timeout) not in (int, float)
        or not math.isfinite(per_write_timeout)
        or not 0 < per_write_timeout <= 30
    ):
        raise WriteDeadlineError("Invalid per-write timeout")

    if not callable(getattr(transport, "send", None)):
        raise WriteDeadlineError("Transport must support send()")

    if not callable(getattr(transport, "settimeout", None)):
        raise WriteDeadlineError(
            "Transport must support settimeout()"
        )

    if clock is None:
        clock = time.monotonic

    if not callable(clock):
        raise WriteDeadlineError("Invalid clock")

    try:
        started = clock()
    except Exception as exc:
        raise WriteDeadlineError(
            "Clock read failed"
        ) from exc

    if (
        type(started) not in (int, float)
        or not math.isfinite(started)
    ):
        raise WriteDeadlineError("Invalid clock reading")

    deadline = started + deadline_seconds

    if not math.isfinite(deadline):
        raise WriteDeadlineError("Invalid absolute deadline")

    sent_total = 0

    while sent_total < len(data):
        try:
            now = clock()
        except Exception as exc:
            raise WriteDeadlineError(
                "Clock read failed during write"
            ) from exc

        if (
            type(now) not in (int, float)
            or not math.isfinite(now)
        ):
            raise WriteDeadlineError(
                "Invalid clock reading during write"
            )

        remaining = deadline - now

        if remaining <= 0:
            raise WriteDeadlineError(
                "Write deadline expired"
            )

        timeout = min(
            float(per_write_timeout),
            remaining,
        )

        try:
            transport.settimeout(timeout)

            count = transport.send(
                memoryview(data)[sent_total:]
            )

        except Exception as exc:
            raise WriteDeadlineError(
                "Transport write failed"
            ) from exc

        if (
            type(count) is not int
            or count <= 0
            or count > len(data) - sent_total
        ):
            raise WriteDeadlineError(
                "Invalid transport send count"
            )

        sent_total += count

    return sent_total
