"""Bounded, thread-safe login limiting for the single-process backend."""

import math
import time
from collections import deque
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import Lock

from app.core.config import get_settings
from app.core.errors import AppError


@dataclass
class _Window:
    seconds: int
    attempts: deque[float] = field(default_factory=deque)
    pending: int = 0

    def expire(self, now: float) -> None:
        while self.attempts and self.attempts[0] <= now - self.seconds:
            self.attempts.popleft()

    def retry_after(self, now: float) -> int:
        # In-flight verification reserves a slot but has not failed yet.
        oldest = self.attempts[0] if self.attempts else now
        return max(1, math.ceil(oldest + self.seconds - now))


def _reject(retry_after: int) -> None:
    raise AppError(
        status_code=429,
        code="AUTH_RATE_LIMITED",
        message="Too many login attempts. Please try again later.",
        headers={"Retry-After": str(retry_after)},
    )


class LoginRateLimiter:
    def __init__(
        self,
        *,
        max_failed_attempts: int,
        failed_window_seconds: int,
        ip_max_requests: int,
        ip_window_seconds: int,
        clock: Callable[[], float] = time.monotonic,
        max_keys: int = 10_000,
    ) -> None:
        self.max_failed_attempts = max_failed_attempts
        self.failed_window_seconds = failed_window_seconds
        self.ip_max_requests = ip_max_requests
        self.ip_window_seconds = ip_window_seconds
        self._clock = clock
        self._max_keys = max_keys
        self._windows: dict[tuple[str, ...], _Window] = {}
        self._lock = Lock()
        self._next_cleanup = 0.0

    def _cleanup(self, now: float) -> None:
        for key, window in list(self._windows.items()):
            window.expire(now)
            if not window.attempts and not window.pending:
                del self._windows[key]
        self._next_cleanup = now + 60

    def _window(self, key: tuple[str, ...], seconds: int, now: float) -> _Window:
        # Called only under the lock. Never evict live limits to admit new keys.
        if now >= self._next_cleanup:
            self._cleanup(now)
        window = self._windows.get(key)
        if window is None:
            if len(self._windows) >= self._max_keys:
                self._cleanup(now)
                if len(self._windows) >= self._max_keys:
                    _reject(
                        min(item.retry_after(now) for item in self._windows.values())
                    )
            window = self._windows[key] = _Window(seconds)
        window.expire(now)
        return window

    def check_ip(self, client_ip: str) -> None:
        """Count body-parsed login requests, including schema-invalid payloads."""
        with self._lock:
            now = self._clock()
            window = self._window(("ip", client_ip), self.ip_window_seconds, now)
            if len(window.attempts) >= self.ip_max_requests:
                _reject(window.retry_after(now))
            window.attempts.append(now)

    @contextmanager
    def attempt(self, email: str, client_ip: str) -> Iterator[None]:
        key = ("credentials", email.strip().lower(), client_ip)
        with self._lock:
            now = self._clock()
            window = self._window(key, self.failed_window_seconds, now)
            if len(window.attempts) + window.pending >= self.max_failed_attempts:
                _reject(window.retry_after(now))
            # Reserve before hashing so concurrent failures cannot exceed the limit.
            window.pending += 1
        failed = False
        try:
            yield
        except AppError as error:
            failed = (
                error.status_code == 401 and error.code == "AUTH_INVALID_CREDENTIALS"
            )
            raise
        finally:
            with self._lock:
                window.pending -= 1
                if failed:
                    window.attempts.append(self._clock())
                if not window.pending and not window.attempts:
                    del self._windows[key]


_limiter: LoginRateLimiter | None = None
_limiter_lock = Lock()


def get_login_rate_limiter() -> LoginRateLimiter:
    # Initialize once even when the first requests arrive simultaneously.
    global _limiter
    with _limiter_lock:
        if _limiter is None:
            settings = get_settings()
            _limiter = LoginRateLimiter(
                max_failed_attempts=settings.login_max_failed_attempts,
                failed_window_seconds=settings.login_failed_window_seconds,
                ip_max_requests=settings.login_ip_max_requests,
                ip_window_seconds=settings.login_ip_window_seconds,
            )
        return _limiter
