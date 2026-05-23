# ABOUTME: Three-level error capture with recovery tracking for the RLM adapter.
# ABOUTME: Records REPL, sub-call, and template errors with recovery attempts.

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ErrorLevel(StrEnum):
    REPL = "repl"
    SUBCALL = "subcall"
    TEMPLATE = "template"


@dataclass  # Intentionally mutable: record_recovery() updates fields after creation.
class ErrorRecord:
    """A single error occurrence with optional recovery tracking."""

    level: ErrorLevel
    iteration: int
    error: str
    code_attempted: str | None = None
    recovery_iteration: int | None = None
    recovery_succeeded: bool | None = None


class ErrorTracker:
    """Tracks errors across all three levels and their recovery attempts."""

    def __init__(self) -> None:
        self._errors: list[ErrorRecord] = []

    def record(
        self,
        *,
        level: ErrorLevel,
        iteration: int,
        error: str,
        code_attempted: str | None = None,
    ) -> None:
        self._errors.append(
            ErrorRecord(
                level=level,
                iteration=iteration,
                error=error,
                code_attempted=code_attempted,
            )
        )

    def record_recovery(self, *, iteration: int, succeeded: bool) -> None:
        for err in reversed(self._errors):
            if err.recovery_iteration is None:
                err.recovery_iteration = iteration
                err.recovery_succeeded = succeeded
                return

    @property
    def errors(self) -> list[ErrorRecord]:
        return list(self._errors)

    @property
    def unrecovered_errors(self) -> list[ErrorRecord]:
        return [e for e in self._errors if e.recovery_iteration is None]

    def summary(self) -> dict[str, Any]:
        recovered = sum(1 for e in self._errors if e.recovery_succeeded is True)
        return {
            "total_errors": len(self._errors),
            "recovered": recovered,
            "unrecovered": len(self._errors) - recovered,
            "by_level": {
                level.value: sum(1 for e in self._errors if e.level == level)
                for level in ErrorLevel
                if any(e.level == level for e in self._errors)
            },
        }
