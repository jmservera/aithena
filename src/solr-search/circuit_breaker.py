"""Generic circuit breaker for graceful degradation of external services.

Implements the classic three-state pattern:

    CLOSED  ->  OPEN  ->  HALF_OPEN  ->  CLOSED (or back to OPEN)

Usage::

    cb = CircuitBreaker(name="redis", failure_threshold=5, recovery_timeout=30.0)

    try:
        result = cb.call(some_risky_function, arg1, arg2)
    except CircuitOpenError:
        # Service is known-down -- use fallback
        ...

Environment-variable configuration is handled externally (see ``config.py``).
"""

from __future__ import annotations

import enum
import logging
import threading
import time
from collections.abc import Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(enum.StrEnum):
    """Possible states for a circuit breaker."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """Raised when a call is attempted while the circuit is open."""

    def __init__(self, name: str, remaining_seconds: float) -> None:
        self.name = name
        self.remaining_seconds = remaining_seconds
        super().__init__(
            f"Circuit '{name}' is OPEN -- retry in {remaining_seconds:.1f}s"
        )


class CircuitBreaker:
    """Thread-safe circuit breaker.

    Parameters
    ----------
    name:
        Human-readable identifier used in logs and error messages.
    failure_threshold:
        Consecutive failures before the circuit opens.
    recovery_timeout:
        Seconds to wait in OPEN state before moving to HALF_OPEN.
    expected_exceptions:
        Exception types considered service failures (trigger the breaker).
        Any exception *not* in this tuple propagates without affecting state.
    success_threshold:
        Successful calls required in HALF_OPEN to close the circuit.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        expected_exceptions: tuple[type[BaseException], ...] = (Exception,),
        success_threshold: int = 1,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exceptions = expected_exceptions
        self.success_threshold = success_threshold

        self._lock = threading.Lock()
        self._state = CircuitState.CLOSED
        self._failure_count: int = 0
        self._success_count: int = 0
        self._last_failure_time: float = 0.0
        self._opened_at: float = 0.0

    @property
    def state(self) -> CircuitState:
        """Return the current state, promoting OPEN -> HALF_OPEN if timeout elapsed."""
        with self._lock:
            self._maybe_promote()
            return self._state

    @property
    def failure_count(self) -> int:
        with self._lock:
            return self._failure_count

    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute *func* through the circuit breaker.

        Raises ``CircuitOpenError`` if the circuit is OPEN and the
        recovery timeout has not yet elapsed.
        """
        with self._lock:
            self._maybe_promote()
            if self._state is CircuitState.OPEN:
                elapsed = time.monotonic() - self._opened_at
                remaining = max(self.recovery_timeout - elapsed, 0.0)
                raise CircuitOpenError(self.name, remaining)

        try:
            result = func(*args, **kwargs)
        except BaseException as exc:
            if isinstance(exc, self.expected_exceptions):
                self._record_failure()
                raise
            raise
        else:
            self._record_success()
            return result

    def reset(self) -> None:
        """Force the circuit back to CLOSED (e.g. manual recovery)."""
        with self._lock:
            old = self._state
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
        if old is not CircuitState.CLOSED:
            logger.info(
                "circuit_breaker.reset",
                extra={"circuit": self.name, "old_state": old.value},
            )

    def get_status(self) -> dict[str, Any]:
        """Return a JSON-serialisable snapshot for health endpoints."""
        with self._lock:
            self._maybe_promote()
            return {
                "name": self.name,
                "state": self._state.value,
                "failure_count": self._failure_count,
                "failure_threshold": self.failure_threshold,
                "recovery_timeout_seconds": self.recovery_timeout,
                "success_threshold": self.success_threshold,
            }

    def _maybe_promote(self) -> None:
        """Promote OPEN -> HALF_OPEN when recovery timeout elapsed. Requires lock."""
        if (
            self._state is CircuitState.OPEN
            and time.monotonic() - self._opened_at >= self.recovery_timeout
        ):
            logger.info(
                "circuit_breaker.state_change",
                extra={
                    "circuit": self.name,
                    "from": CircuitState.OPEN.value,
                    "to": CircuitState.HALF_OPEN.value,
                },
            )
            self._state = CircuitState.HALF_OPEN
            self._success_count = 0

    def _record_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._state is CircuitState.HALF_OPEN or (
                self._state is CircuitState.CLOSED
                and self._failure_count >= self.failure_threshold
            ):
                self._transition_to_open()

    def _record_success(self) -> None:
        with self._lock:
            if self._state is CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    logger.info(
                        "circuit_breaker.state_change",
                        extra={
                            "circuit": self.name,
                            "from": CircuitState.HALF_OPEN.value,
                            "to": CircuitState.CLOSED.value,
                        },
                    )
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
            elif self._state is CircuitState.CLOSED:
                self._failure_count = 0

    def _transition_to_open(self) -> None:
        """Move to OPEN state. Requires lock."""
        logger.info(
            "circuit_breaker.state_change",
            extra={
                "circuit": self.name,
                "from": self._state.value,
                "to": CircuitState.OPEN.value,
                "failure_count": self._failure_count,
            },
        )
        self._state = CircuitState.OPEN
        self._opened_at = time.monotonic()
        self._success_count = 0
