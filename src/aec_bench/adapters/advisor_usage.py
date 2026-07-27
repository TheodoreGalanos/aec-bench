# ABOUTME: Tracks advisor provider effects independently from any adapter implementation.
# ABOUTME: Preserves exact call and token evidence while failing unknown token dimensions closed.

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class AdvisorUsageResult(Protocol):
    """Token evidence exposed by one completed advisor provider effect."""

    @property
    def input_tokens(self) -> int: ...

    @property
    def output_tokens(self) -> int: ...


@dataclass(slots=True)
class AdvisorUsageAccumulator:
    """Track every advisor provider effect and whether its token evidence is exact."""

    calls: int = 0
    input_tokens: int | None = 0
    output_tokens: int | None = 0

    def begin_call(self) -> None:
        """Record a provider effect before dispatch so failures still consume budget."""
        self.calls += 1

    def record_result(self, result: AdvisorUsageResult) -> None:
        """Add exact token evidence returned by one completed provider effect."""
        if self.input_tokens is not None:
            self.input_tokens += result.input_tokens
        if self.output_tokens is not None:
            self.output_tokens += result.output_tokens

    def mark_tokens_unknown(self) -> None:
        """Fail token evidence closed when a provider effect raises before reporting usage."""
        self.input_tokens = None
        self.output_tokens = None

    def snapshot(self) -> tuple[int, int | None, int | None]:
        """Return immutable usage values for a terminal adapter result."""
        return self.calls, self.input_tokens, self.output_tokens
