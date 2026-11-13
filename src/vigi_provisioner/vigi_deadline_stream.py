"""
Deadline-aware adapter for socket-like streams.

Does not create sockets or establish connections.
"""

import math
import time

from .vigi_socket_deadline import (
    SocketDeadlineError,
    configure_read_timeout,
)


class DeadlineStreamError(RuntimeError):
    pass


class DeadlineStream:
    def __init__(
        self,
        sock,
        *,
        deadline,
        per_read_timeout=5.0,
        clock=None,
    ):
        if (
            not hasattr(sock, "recv")
            or not callable(sock.recv)
        ):
            raise DeadlineStreamError(
                "Socket must provide recv()"
            )

        if (
            not hasattr(sock, "settimeout")
            or not callable(sock.settimeout)
        ):
            raise DeadlineStreamError(
                "Socket must provide settimeout()"
            )

        if (
            type(deadline) not in (int, float)
            or not math.isfinite(deadline)
        ):
            raise DeadlineStreamError(
                "Invalid deadline"
            )

        if (
            type(per_read_timeout) not in (int, float)
            or not math.isfinite(per_read_timeout)
            or not 0 < per_read_timeout <= 30
        ):
            raise DeadlineStreamError(
                "Invalid per-read timeout"
            )

        if clock is None:
            clock = time.monotonic

        if not callable(clock):
            raise DeadlineStreamError(
                "Invalid clock"
            )

        self._sock = sock
        self._deadline = deadline
        self._per_read_timeout = per_read_timeout
        self._clock = clock
        self._last_clock = None

    def _read_clock(self):
        try:
            now = self._clock()
        except Exception as exc:
            raise DeadlineStreamError(
                "Clock read failed"
            ) from exc

        if (
            type(now) not in (int, float)
            or not math.isfinite(now)
        ):
            raise DeadlineStreamError(
                "Invalid clock reading"
            )

        if (
            self._last_clock is not None
            and now < self._last_clock
        ):
            raise DeadlineStreamError(
                "Clock moved backward"
            )

        self._last_clock = now
        return now

    def recv(self, size):
        if (
            type(size) is not int
            or size <= 0
        ):
            raise DeadlineStreamError(
                "Invalid recv size"
            )

        try:
            configure_read_timeout(
                self._sock,
                deadline=self._deadline,
                per_read_timeout=self._per_read_timeout,
                clock=self._read_clock,
            )
        except SocketDeadlineError as exc:
            raise DeadlineStreamError(
                "Read deadline configuration failed"
            ) from exc

        try:
            data = self._sock.recv(size)
        except Exception as exc:
            raise DeadlineStreamError(
                "Socket read failed"
            ) from exc

        now = self._read_clock()

        if now >= self._deadline:
            raise DeadlineStreamError(
                "Read deadline expired"
            )

        return data
