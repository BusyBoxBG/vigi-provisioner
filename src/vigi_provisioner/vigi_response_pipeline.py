"""
Offline-compatible VIGI HTTP response pipeline.

Accepts an existing socket-like stream.
Does not create connections or send requests.
"""

import math
import time

from .vigi_deadline_stream import DeadlineStream
from .vigi_http_stream import read_http_stream
from .vigi_initialization_result import (
    validate_initialization_result,
)


class ResponsePipelineError(RuntimeError):
    pass


def read_initialization_response(
    sock,
    *,
    deadline_seconds=10.0,
    per_read_timeout=5.0,
    clock=None,
):
    if (
        type(deadline_seconds) not in (int, float)
        or not math.isfinite(deadline_seconds)
        or not 0 < deadline_seconds <= 300
    ):
        raise ResponsePipelineError(
            "Invalid deadline duration"
        )

    if clock is None:
        clock = time.monotonic

    if not callable(clock):
        raise ResponsePipelineError(
            "Invalid clock"
        )

    last_clock = None

    def checked_clock():
        nonlocal last_clock

        try:
            now = clock()
        except Exception as exc:
            raise ResponsePipelineError(
                "Clock read failed"
            ) from exc

        if (
            type(now) not in (int, float)
            or not math.isfinite(now)
        ):
            raise ResponsePipelineError(
                "Invalid clock reading"
            )

        if (
            last_clock is not None
            and now < last_clock
        ):
            raise ResponsePipelineError(
                "Clock moved backward"
            )

        last_clock = now
        return now

    start = checked_clock()
    absolute_deadline = start + deadline_seconds

    if not math.isfinite(absolute_deadline):
        raise ResponsePipelineError(
            "Invalid absolute deadline"
        )

    stream = DeadlineStream(
        sock,
        deadline=absolute_deadline,
        per_read_timeout=per_read_timeout,
        clock=checked_clock,
    )

    response = read_http_stream(
        stream,
        deadline_seconds=deadline_seconds,
        clock=checked_clock,
    )

    return validate_initialization_result(
        response
    )
