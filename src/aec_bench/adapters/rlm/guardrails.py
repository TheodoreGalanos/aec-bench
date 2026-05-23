# ABOUTME: Token budget, iteration cap, and sub-call depth tracking for the RLM adapter.
# ABOUTME: Three-layer protection against runaway recursion and cost escalation.

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GuardrailVerdict:
    """Result of checking guardrail state."""

    can_continue: bool
    stop_reason: str = ""
    budget_warning: bool = False
    budget_consumed_pct: float = 0.0


class GuardrailState:
    """Tracks token consumption, iteration count, and sub-call depth."""

    def __init__(
        self,
        *,
        token_budget: int,
        max_iterations: int,
        max_subcall_depth: int,
        budget_warning_pct: float = 80.0,
        max_subcalls: int = 0,
        max_budget_usd: float = 0.0,
        billable_input_budget: int = 0,
    ) -> None:
        self._token_budget = token_budget
        self._max_iterations = max_iterations
        self._max_subcall_depth = max_subcall_depth
        self._budget_warning_pct = budget_warning_pct
        self._max_subcalls = max_subcalls
        self._max_budget_usd = max_budget_usd
        self._billable_input_budget = billable_input_budget
        self._total_tokens: int = 0
        self._iteration_count: int = 0
        self._subcall_count: int = 0
        self._total_cost_usd: float = 0.0
        self._billable_input_tokens: int = 0

    def record_iteration(
        self,
        *,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float = 0.0,
        cache_read_tokens: int = 0,
    ) -> None:
        """Add tokens from one agent iteration to the running total."""
        self._total_tokens += input_tokens + output_tokens
        self._total_cost_usd += cost_usd
        self._billable_input_tokens += max(input_tokens - cache_read_tokens, 0)
        self._iteration_count += 1

    def record_subcall_tokens(
        self,
        *,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float = 0.0,
        cache_read_tokens: int = 0,
    ) -> None:
        """Add tokens consumed by a sub-call without incrementing iteration count."""
        self._total_tokens += input_tokens + output_tokens
        self._total_cost_usd += cost_usd
        self._billable_input_tokens += max(input_tokens - cache_read_tokens, 0)
        self._subcall_count += 1

    def can_subcall(self, current_depth: int) -> bool:
        """Return True if another level of recursion is allowed at current_depth."""
        return current_depth < self._max_subcall_depth

    def check(self) -> GuardrailVerdict:
        """Evaluate current state and return a verdict."""
        consumed_pct = self._total_tokens / self._token_budget * 100 if self._token_budget > 0 else 0.0

        if self._iteration_count >= self._max_iterations:
            return GuardrailVerdict(
                can_continue=False,
                stop_reason=(f"Iteration cap reached ({self._iteration_count}/{self._max_iterations})"),
                budget_consumed_pct=consumed_pct,
            )

        if self._total_tokens >= self._token_budget:
            return GuardrailVerdict(
                can_continue=False,
                stop_reason=(f"Token budget exceeded ({self._total_tokens}/{self._token_budget})"),
                budget_consumed_pct=consumed_pct,
            )

        if self._max_subcalls > 0 and self._subcall_count >= self._max_subcalls:
            return GuardrailVerdict(
                can_continue=False,
                stop_reason=(f"Subcall limit reached ({self._subcall_count}/{self._max_subcalls})"),
                budget_consumed_pct=consumed_pct,
            )

        if self._max_budget_usd > 0 and self._total_cost_usd >= self._max_budget_usd:
            return GuardrailVerdict(
                can_continue=False,
                stop_reason=(f"USD budget exceeded (${self._total_cost_usd:.4f}/${self._max_budget_usd:.2f})"),
                budget_consumed_pct=consumed_pct,
            )

        if self._billable_input_budget > 0 and self._billable_input_tokens >= self._billable_input_budget:
            return GuardrailVerdict(
                can_continue=False,
                stop_reason=(
                    f"Billable input budget exceeded ({self._billable_input_tokens:,}/{self._billable_input_budget:,})"
                ),
                budget_consumed_pct=consumed_pct,
            )

        return GuardrailVerdict(
            can_continue=True,
            budget_warning=consumed_pct >= self._budget_warning_pct,
            budget_consumed_pct=consumed_pct,
        )

    @property
    def iteration_count(self) -> int:
        """Number of iterations recorded so far."""
        return self._iteration_count

    @property
    def subcall_count(self) -> int:
        """Number of sub-calls recorded so far."""
        return self._subcall_count

    @property
    def total_cost_usd(self) -> float:
        """Total USD cost consumed across all iterations and sub-calls."""
        return self._total_cost_usd

    @property
    def total_tokens(self) -> int:
        """Total tokens consumed across all iterations and sub-calls."""
        return self._total_tokens

    @property
    def billable_input_tokens(self) -> int:
        """Total billable input tokens (input minus cache reads)."""
        return self._billable_input_tokens
