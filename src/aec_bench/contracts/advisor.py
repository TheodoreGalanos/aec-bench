# ABOUTME: Boundary contracts for the advisor tool — config, request/response, usage stats.
# ABOUTME: Defines the AdvisorContextStrategy protocol for per-adapter context curation.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class AdvisorConfig:
    """Configuration for the advisor tool, parsed from [advisor] in TOML."""

    model: str
    max_uses: int = 5
    max_response_tokens: int = 500
    context_window: int = 10
    enabled: bool = True


@dataclass(frozen=True)
class AdvisorRequest:
    """Structured input the executor provides when calling the advisor."""

    goal: str
    problem: str
    attempt: str | None = None


@dataclass(frozen=True)
class AdvisorResponse:
    """Structured output from the advisor model."""

    advice: str
    suggested_action: str
    confidence: float
    reasoning: str


@dataclass(frozen=True)
class AdvisorUsageStats:
    """Separated cost tracking for advisor calls."""

    calls_made: int
    calls_remaining: int
    advisor_input_tokens: int = 0
    advisor_output_tokens: int = 0
    advisor_cost_usd: float = 0.0


@runtime_checkable
class AdvisorContextStrategy(Protocol):
    """Per-adapter strategy for building the advisor's context messages."""

    def build_advisor_context(
        self,
        request: AdvisorRequest,
        conversation_state: Any,
    ) -> list[dict[str, str]]: ...
