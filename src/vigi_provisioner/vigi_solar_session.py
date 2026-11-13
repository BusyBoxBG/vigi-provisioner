from dataclasses import dataclass
from time import monotonic
from threading import Lock, RLock
from weakref import WeakValueDictionary


SESSION_TTL_SECONDS = 59 * 60


@dataclass(frozen=True, repr=False)
class SolarAuthContext:
    device_id: str
    solar_uri: str
    aes_key: bytes
    aes_iv: bytes
    addition: bytes | None
    digest_type: int | None
    token: str
    session_id: str | None

    def __post_init__(self):
        if not self.device_id:
            raise ValueError("Device ID is required")

        if not self.solar_uri:
            raise ValueError("Solar URI is required")

        if len(self.aes_key) not in (16, 24, 32):
            raise ValueError("Invalid AES key length")

        if len(self.aes_iv) != 16:
            raise ValueError("Invalid Solar AES IV length")

        if not self.token:
            raise ValueError("Solar token is required")

        if self.digest_type == 17 and self.addition is None:
            raise ValueError(
                "AES-GCM authentication data is required"
            )

    def __repr__(self):
        return (
            "SolarAuthContext("
            f"device_id={self.device_id!r}, "
            "credentials=<redacted>)"
        )


class SolarSessionCache:
    def __init__(self, ttl_seconds=SESSION_TTL_SECONDS):
        if ttl_seconds <= 0:
            raise ValueError("TTL must be positive")

        self.ttl_seconds = ttl_seconds
        self._sessions = {}
        self._lockouts = {}
        self._device_locks = WeakValueDictionary()
        self._device_locks_guard = Lock()

    def put(self, context):
        if not isinstance(context, SolarAuthContext):
            raise TypeError(
                "Expected SolarAuthContext"
            )

        self._sessions[context.device_id] = (
            context,
            monotonic() + self.ttl_seconds,
        )

    def get(self, device_id):
        entry = self._sessions.get(str(device_id))

        if entry is None:
            return None

        context, expires_at = entry

        if monotonic() >= expires_at:
            self._sessions.pop(str(device_id), None)
            return None

        return context

    def invalidate(self, device_id):
        self._sessions.pop(str(device_id), None)

    def device_lock(self, device_id):
        device_id = str(device_id)

        with self._device_locks_guard:
            lock = self._device_locks.get(device_id)

            if lock is None:
                lock = RLock()
                self._device_locks[device_id] = lock

            return lock

    def set_lockout(self, device_id, seconds):
        if type(seconds) is not int or seconds <= 0:
            raise ValueError(
                "Lockout duration must be a positive integer"
            )

        self._lockouts[str(device_id)] = (
            monotonic() + seconds
        )

    def lockout_remaining(self, device_id):
        device_id = str(device_id)
        deadline = self._lockouts.get(device_id)

        if deadline is None:
            return 0.0

        remaining = deadline - monotonic()

        if remaining <= 0:
            self._lockouts.pop(device_id, None)
            return 0.0

        return remaining

    def clear(self):
        self._sessions.clear()
        self._lockouts.clear()
