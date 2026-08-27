# ABOUTME: Provides the thread-safe cooperative cancellation contract for AVO calls.
# ABOUTME: Carries a typed reason from direct variation loops through swarm workers.

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from threading import Event, Lock


class AVOCancellationCode(StrEnum):
    """Stable categories for a cooperative AVO cancellation request."""

    REQUESTED = "requested"
    TIMEOUT = "timeout"


@dataclass(frozen=True)
class AVOCancellationReason:
    """The typed reason propagated when an AVO call is cancelled."""

    code: AVOCancellationCode = AVOCancellationCode.REQUESTED
    detail: str = "AVO cancellation requested."

    def __post_init__(self) -> None:
        code = AVOCancellationCode(self.code)
        object.__setattr__(self, "code", code)
        if not isinstance(self.detail, str) or not self.detail.strip():
            raise ValueError("cancellation reason detail must not be blank")
        object.__setattr__(self, "detail", self.detail.strip())

    def __str__(self) -> str:
        return self.detail


class AVOCancellationError(RuntimeError):
    """Raised after an AVO cancellation has been durably reconciled."""

    def __init__(self, reason: AVOCancellationReason) -> None:
        if not isinstance(reason, AVOCancellationReason):
            raise TypeError("reason must be an AVOCancellationReason")
        self.reason = reason
        super().__init__(reason.detail)


class AVOCancellationSignal:
    """Thread-safe one-way cancellation signal shared by one AVO worker only."""

    def __init__(self) -> None:
        self._event = Event()
        self._lock = Lock()
        self._reason: AVOCancellationReason | None = None

    def cancel(self, reason: AVOCancellationReason | str | None = None) -> None:
        """Request cancellation, retaining the first reason deterministically."""
        if reason is None:
            selected = AVOCancellationReason()
        elif isinstance(reason, AVOCancellationReason):
            selected = reason
        elif isinstance(reason, str):
            selected = AVOCancellationReason(detail=reason)
        else:
            raise TypeError("reason must be an AVOCancellationReason, string, or None")
        with self._lock:
            if self._reason is None:
                self._reason = selected
            self._event.set()

    @property
    def cancelled(self) -> bool:
        """Return whether cancellation was requested."""
        return self._event.is_set()

    @property
    def reason(self) -> AVOCancellationReason | None:
        """Return the first cancellation reason, if cancellation was requested."""
        with self._lock:
            return self._reason

    def wait(self, timeout: float | None = None) -> bool:
        """Wait for cancellation using the underlying thread-safe event."""
        return self._event.wait(timeout)

    def raise_if_cancelled(self) -> None:
        """Raise the typed cancellation error when the signal is set."""
        if self._event.is_set():
            reason = self.reason or AVOCancellationReason()
            raise AVOCancellationError(reason)


__all__ = (
    "AVOCancellationCode",
    "AVOCancellationError",
    "AVOCancellationReason",
    "AVOCancellationSignal",
)
