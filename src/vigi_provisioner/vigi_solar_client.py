"""Authenticated VIGI Solar client orchestration.

No network transport is implemented here. A caller must explicitly
provide a sender callback.
"""

import json

from .vigi_solar_session import SolarSessionCache
from .vigi_solar_transport import (
    prepare_solar_request,
    decrypt_solar_response,
)
from .vigi_solar_retry import execute_with_solar_retry
from .vigi_solar_readonly import validate_readonly_solar_request



class SolarLockoutError(RuntimeError):
    """Camera authentication is temporarily locked."""

    def __init__(self, device_id, seconds_remaining):
        self.device_id = device_id
        self.seconds_remaining = seconds_remaining

        super().__init__(
            "Solar authentication temporarily locked "
            f"for device {device_id!r}; "
            f"approximately {seconds_remaining:.0f}s remaining"
        )


class SolarClient:
    def __init__(self, authenticate, sender, cache=None):
        if not callable(authenticate):
            raise TypeError("authenticate must be callable")

        if not callable(sender):
            raise TypeError("sender must be callable")

        self.authenticate_callback = authenticate
        self.sender = sender
        self.cache = (
            cache if cache is not None
            else SolarSessionCache()
        )

    def execute(self, device_id, request):
        validate_readonly_solar_request(request)
        device_id = str(device_id)

        with self.cache.device_lock(device_id):
            return self._execute_locked(device_id, request)

    def _execute_locked(self, device_id, request):
        remaining = self.cache.lockout_remaining(device_id)

        if remaining > 0:
            raise SolarLockoutError(device_id, remaining)

        first_context_from_cache = False
        authentication_count = 0

        def authenticate():
            nonlocal first_context_from_cache
            nonlocal authentication_count

            context = self.cache.get(device_id)

            if authentication_count == 0:
                first_context_from_cache = context is not None

            authentication_count += 1

            if context is None:
                context = self.authenticate_callback(device_id)

                if context.device_id != device_id:
                    raise ValueError(
                        "Authentication context device ID mismatch"
                    )

                self.cache.put(context)

            return context

        def invalidate():
            self.cache.invalidate(device_id)

        def send(context, request_json):
            prepared = prepare_solar_request(
                request_json,
                encrypted=True,
                digest_type=context.digest_type,
                aes_key=context.aes_key,
                aes_iv=context.aes_iv,
                addition=context.addition,
            )

            response_body, response_headers = self.sender(
                context.solar_uri,
                prepared.body,
                prepared.headers,
            )

            headers = {
                str(key).lower(): value
                for key, value in response_headers.items()
            }

            plaintext = decrypt_solar_response(
                response_body,
                if_encrypt=headers.get("if-encrypt", "0"),
                auth_tag=headers.get("auth-tag"),
                aes_key=context.aes_key,
                aes_iv=context.aes_iv,
                addition=context.addition,
            )

            return json.loads(plaintext)

        response = execute_with_solar_retry(
            request,
            authenticate,
            send,
            invalidate,
            retry_allowed=lambda: first_context_from_cache,
        )

        if response.get("errorCode") == -40404:
            details = response.get("loginError")

            seconds = (
                details.get("secLeft")
                if isinstance(details, dict)
                else None
            )

            if type(seconds) is not int or seconds <= 0:
                seconds = 60
            else:
                seconds = min(seconds, 3600)

            self.cache.set_lockout(device_id, seconds)

        return response
