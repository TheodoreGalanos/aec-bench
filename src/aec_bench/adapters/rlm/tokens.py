# ABOUTME: Per-call token tracking with compaction threshold detection for the RLM adapter.
# ABOUTME: Tracks per-run and cross-compaction totals, matching the script's per-call checks.

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TurnMetrics:
    """Token metrics snapshot for a single main-loop turn."""

    call_input_tokens: int
    call_output_tokens: int
    cumulative_input_tokens: int
    cumulative_output_tokens: int
    grand_total_tokens: int
    subcall_tokens: int
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


class TokenTracker:
    """Tracks per-call and cumulative token usage across compaction restarts.

    The compaction threshold check uses per-call input context size
    (how many input tokens the LLM saw on one call), not the cumulative
    total across all calls.  In the library, ``RlmCompletionResponse.input_tokens``
    is already per-call, so it can be passed directly to ``needs_compaction()``.
    """

    def __init__(self, *, context_limit: int = 1_000_000) -> None:
        self._context_limit = context_limit
        self._grand_total: int = 0
        self._run_input: int = 0
        self._run_output: int = 0
        self._subcall_total: int = 0
        # Depth-level counters
        self._main_calls: int = 0
        self._main_input: int = 0
        self._main_output: int = 0
        self._main_cost: float = 0.0
        self._main_cache_read: int = 0
        self._main_cache_write: int = 0
        self._subcall_calls: int = 0
        self._subcall_input: int = 0
        self._subcall_output: int = 0
        self._subcall_cost: float = 0.0
        self._subcall_cache_read: int = 0
        self._subcall_cache_write: int = 0
        self._compaction_calls: int = 0
        self._compaction_input: int = 0
        self._compaction_output: int = 0
        self._compaction_cost: float = 0.0
        self._compaction_cache_read: int = 0
        self._compaction_cache_write: int = 0

    def record_turn(
        self,
        *,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float = 0.0,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
    ) -> TurnMetrics:
        """Record a main-loop turn and return per-call metrics."""
        self._run_input += input_tokens
        self._run_output += output_tokens
        self._main_calls += 1
        self._main_input += input_tokens
        self._main_output += output_tokens
        self._main_cost += cost_usd
        self._main_cache_read += cache_read_tokens
        self._main_cache_write += cache_write_tokens

        run_total = self._run_input + self._run_output + self._subcall_total
        return TurnMetrics(
            call_input_tokens=input_tokens,
            call_output_tokens=output_tokens,
            cumulative_input_tokens=self._run_input,
            cumulative_output_tokens=self._run_output,
            grand_total_tokens=self._grand_total + run_total,
            subcall_tokens=self._subcall_total,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
        )

    def record_subcall(
        self,
        *,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float = 0.0,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
    ) -> None:
        """Record tokens from a sub-call (no iteration increment)."""
        self._subcall_total += input_tokens + output_tokens
        self._subcall_calls += 1
        self._subcall_input += input_tokens
        self._subcall_output += output_tokens
        self._subcall_cost += cost_usd
        self._subcall_cache_read += cache_read_tokens
        self._subcall_cache_write += cache_write_tokens

    def record_compaction(
        self,
        *,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float = 0.0,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
    ) -> None:
        """Record tokens from a compaction call."""
        self._compaction_calls += 1
        self._compaction_input += input_tokens
        self._compaction_output += output_tokens
        self._compaction_cost += cost_usd
        self._compaction_cache_read += cache_read_tokens
        self._compaction_cache_write += cache_write_tokens

    def depth_summary(self) -> dict[str, dict[str, int | float]]:
        """Return per-depth aggregation of calls, tokens, and cost."""
        total_input = self._main_input + self._subcall_input + self._compaction_input
        total_output = self._main_output + self._subcall_output + self._compaction_output
        total_cost = self._main_cost + self._subcall_cost + self._compaction_cost
        total_cache_read = self._main_cache_read + self._subcall_cache_read + self._compaction_cache_read
        total_cache_write = self._main_cache_write + self._subcall_cache_write + self._compaction_cache_write
        return {
            "main": {
                "calls": self._main_calls,
                "input_tokens": self._main_input,
                "output_tokens": self._main_output,
                "cost_usd": self._main_cost,
                "cache_read_tokens": self._main_cache_read,
                "cache_write_tokens": self._main_cache_write,
            },
            "subcalls": {
                "calls": self._subcall_calls,
                "input_tokens": self._subcall_input,
                "output_tokens": self._subcall_output,
                "cost_usd": self._subcall_cost,
                "cache_read_tokens": self._subcall_cache_read,
                "cache_write_tokens": self._subcall_cache_write,
            },
            "compaction": {
                "calls": self._compaction_calls,
                "input_tokens": self._compaction_input,
                "output_tokens": self._compaction_output,
                "cost_usd": self._compaction_cost,
                "cache_read_tokens": self._compaction_cache_read,
                "cache_write_tokens": self._compaction_cache_write,
            },
            "total": {
                "calls": self._main_calls + self._subcall_calls + self._compaction_calls,
                "input_tokens": total_input,
                "output_tokens": total_output,
                "cost_usd": total_cost,
                "cache_read_tokens": total_cache_read,
                "cache_write_tokens": total_cache_write,
            },
        }

    def needs_compaction(self, call_input: int, threshold_pct: float) -> bool:
        """Return True if per-call context exceeds compaction threshold."""
        threshold = int(self._context_limit * threshold_pct)
        return call_input > threshold

    def hit_hard_ceiling(self, call_input: int, ceiling_pct: float) -> bool:
        """Return True if per-call context exceeds hard ceiling."""
        ceiling = int(self._context_limit * ceiling_pct)
        return call_input > ceiling

    def reset_for_compaction(self) -> None:
        """Accumulate grand total and reset run-level counters."""
        run_total = self._run_input + self._run_output + self._subcall_total
        self._grand_total += run_total
        self._run_input = 0
        self._run_output = 0
        self._subcall_total = 0

    @property
    def grand_total(self) -> int:
        """Total tokens consumed across all compaction restarts."""
        run_total = self._run_input + self._run_output + self._subcall_total
        return self._grand_total + run_total
