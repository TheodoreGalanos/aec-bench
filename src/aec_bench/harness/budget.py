# ABOUTME: Accounts observable Hx runtime, token, and cost usage across every RunPlan invocation.
# ABOUTME: Fails closed when declared evidence is missing or a content-pinned harness budget is breached.

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Literal, Self

from pydantic import NonNegativeFloat, NonNegativeInt, model_validator

from aec_bench.contracts.harness_instance import HarnessBudget
from aec_bench.contracts.harness_kernel import FrozenStrictModel
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.contracts.validators import NonEmptyStr


class HarnessBudgetError(RuntimeError):
    """Stable fail-closed budget error propagated through the px operation boundary."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class HarnessBudgetObservation(FrozenStrictModel):
    """Cumulative observable usage, completeness, and the first terminal budget breach."""

    status: Literal["within_budget", "breached"]
    reserved_agent_turns: NonNegativeInt
    reserved_tool_calls: NonNegativeInt
    reserved_context_tokens: NonNegativeInt
    unaccounted_dispatches: NonNegativeInt
    imported_trials: NonNegativeInt
    recorded_stage_executions: NonNegativeInt = 0
    observed_tokens: NonNegativeInt
    token_evidence_complete: bool
    observed_cost_usd: NonNegativeFloat
    cost_evidence_complete: bool
    observed_trial_seconds: NonNegativeFloat
    elapsed_wall_seconds: NonNegativeFloat
    breach_code: NonEmptyStr | None = None
    breach_message: NonEmptyStr | None = None

    @model_validator(mode="after")
    def validate_breach(self) -> Self:
        if self.status == "breached" and (self.breach_code is None or self.breach_message is None):
            raise ValueError("breached budget observation requires code and message")
        if self.status == "within_budget" and (self.breach_code is not None or self.breach_message is not None):
            raise ValueError("within-budget observation cannot contain breach evidence")
        return self


class HarnessBudgetLedger:
    """Thread-safe aggregate guard shared by every invocation in one px execution."""

    def __init__(
        self,
        budget: HarnessBudget,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._budget = budget
        self._clock = clock
        self._started_at = clock()
        self._lock = threading.Lock()
        self._reserved_agent_turns = 0
        self._reserved_tool_calls = 0
        self._reserved_context_tokens = 0
        self._unaccounted_dispatches = 0
        self._imported_trials = 0
        self._recorded_stage_executions = 0
        self._observed_tokens = 0
        self._token_evidence_complete = True
        self._observed_cost_usd = 0.0
        self._cost_evidence_complete = True
        self._observed_trial_seconds = 0.0
        self._breach: tuple[str, str] | None = None

    def before_dispatch(self) -> int:
        """Return a positive remaining wall-clock allowance or reject the invocation."""
        with self._lock:
            self._raise_existing_breach()
            remaining = self._budget.max_runtime_seconds - self._elapsed()
            if remaining <= 0:
                self._breach_and_raise(
                    "harness_runtime_budget_exceeded",
                    "harness wall-clock runtime budget was exhausted before dispatch",
                )
            return max(1, int(remaining))

    def record_trial(self, record: TrialRecord) -> None:
        """Account one already-incurred trial and reject missing or excessive observations."""
        cost = record.cost
        tokens_known = cost is not None and cost.tokens_in is not None and cost.tokens_out is not None
        observed_tokens = 0
        if tokens_known:
            assert cost is not None and cost.tokens_in is not None and cost.tokens_out is not None
            observed_tokens = cost.tokens_in + cost.tokens_out
        cost_known = cost is not None and cost.estimated_cost_usd is not None
        observed_cost = 0.0
        if cost is not None and cost.estimated_cost_usd is not None:
            observed_cost = float(cost.estimated_cost_usd)

        self._record_observation(
            label=f"trial {record.trial_id!r}",
            observed_tokens=observed_tokens,
            tokens_known=tokens_known,
            observed_cost=observed_cost,
            cost_known=cost_known,
            total_seconds=float(record.timing.total_seconds),
            imported_trial=True,
        )

    def record_stage_execution(
        self,
        *,
        input_tokens: int | None,
        output_tokens: int | None,
        estimated_cost_usd: float | None,
        total_seconds: float,
    ) -> None:
        """Account one unscored stage invocation without creating TrialRecord evidence."""

        for name, value in (("input_tokens", input_tokens), ("output_tokens", output_tokens)):
            if value is not None and (isinstance(value, bool) or value < 0):
                raise ValueError(f"{name} must be a non-negative integer when provided")
        if estimated_cost_usd is not None and (isinstance(estimated_cost_usd, bool) or estimated_cost_usd < 0):
            raise ValueError("estimated_cost_usd must be non-negative when provided")
        if isinstance(total_seconds, bool) or total_seconds < 0:
            raise ValueError("total_seconds must be non-negative")
        tokens_known = input_tokens is not None and output_tokens is not None
        self._record_observation(
            label="intermediate stage execution",
            observed_tokens=(input_tokens or 0) + (output_tokens or 0),
            tokens_known=tokens_known,
            observed_cost=estimated_cost_usd or 0.0,
            cost_known=estimated_cost_usd is not None,
            total_seconds=total_seconds,
            imported_trial=False,
        )

    def _record_observation(
        self,
        *,
        label: str,
        observed_tokens: int,
        tokens_known: bool,
        observed_cost: float,
        cost_known: bool,
        total_seconds: float,
        imported_trial: bool,
    ) -> None:
        with self._lock:
            if imported_trial:
                self._imported_trials += 1
            else:
                self._recorded_stage_executions += 1
            self._observed_trial_seconds += total_seconds
            self._observed_tokens += observed_tokens
            self._observed_cost_usd += observed_cost
            self._token_evidence_complete = self._token_evidence_complete and tokens_known
            self._cost_evidence_complete = self._cost_evidence_complete and cost_known

            if self._budget.max_tokens is not None and not tokens_known:
                self._breach_and_raise(
                    "harness_token_evidence_missing",
                    f"{label} lacks token evidence required by the Hx budget",
                )
            if self._budget.max_cost_usd is not None and not cost_known:
                self._breach_and_raise(
                    "harness_cost_evidence_missing",
                    f"{label} lacks cost evidence required by the Hx budget",
                )
            if self._budget.max_tokens is not None and self._observed_tokens > self._budget.max_tokens:
                self._breach_and_raise(
                    "harness_token_budget_exceeded",
                    f"observed {self._observed_tokens} tokens exceeds Hx budget {self._budget.max_tokens}",
                )
            if self._budget.max_cost_usd is not None and self._observed_cost_usd > self._budget.max_cost_usd:
                self._breach_and_raise(
                    "harness_cost_budget_exceeded",
                    f"observed cost {self._observed_cost_usd:.8f} USD exceeds Hx budget "
                    f"{self._budget.max_cost_usd:.8f} USD",
                )
            if total_seconds > self._budget.max_runtime_seconds:
                self._breach_and_raise(
                    "harness_runtime_budget_exceeded",
                    f"{label} duration exceeds the Hx runtime budget",
                )
            self._raise_if_wall_time_exceeded()

    def reserve_invocation_capacity(
        self,
        *,
        agent_turns: int,
        tool_calls: int,
        context_tokens: int,
    ) -> None:
        """Reserve the maximum execution capacity exposed by one lowered Harbor invocation."""
        requested = {
            "agent_turns": agent_turns,
            "tool_calls": tool_calls,
            "context_tokens": context_tokens,
        }
        if any(isinstance(value, bool) or value < 0 for value in requested.values()):
            raise ValueError("invocation capacity reservations must be non-negative integers")

        with self._lock:
            self._raise_existing_breach()
            next_agent_turns = self._reserved_agent_turns + agent_turns
            next_tool_calls = self._reserved_tool_calls + tool_calls
            next_context_tokens = self._reserved_context_tokens + context_tokens
            if next_agent_turns > self._budget.max_agent_turns:
                self._breach_and_raise(
                    "harness_agent_turn_capacity_exceeded",
                    f"reserved agent-turn capacity {next_agent_turns} exceeds Hx budget {self._budget.max_agent_turns}",
                )
            if next_tool_calls > self._budget.max_tool_calls:
                self._breach_and_raise(
                    "harness_tool_call_capacity_exceeded",
                    f"reserved tool-call capacity {next_tool_calls} exceeds Hx budget {self._budget.max_tool_calls}",
                )
            if next_context_tokens > self._budget.max_context_tokens:
                self._breach_and_raise(
                    "harness_context_capacity_exceeded",
                    f"reserved context capacity {next_context_tokens} exceeds Hx budget "
                    f"{self._budget.max_context_tokens}",
                )
            self._reserved_agent_turns = next_agent_turns
            self._reserved_tool_calls = next_tool_calls
            self._reserved_context_tokens = next_context_tokens

    def after_dispatch(self) -> None:
        """Reject a completed invocation that crossed the aggregate wall-clock deadline."""
        with self._lock:
            self._raise_existing_breach()
            self._raise_if_wall_time_exceeded()

    def mark_unaccounted_dispatch(self) -> None:
        """Record a started dispatch that returned no complete, auditable trial plan."""
        with self._lock:
            self._unaccounted_dispatches += 1
            self._token_evidence_complete = False
            self._cost_evidence_complete = False
            if self._breach is None:
                self._breach = (
                    "harness_dispatch_evidence_incomplete",
                    "a started Harbor dispatch did not produce a complete auditable trial plan",
                )

    def snapshot(self) -> HarnessBudgetObservation:
        """Return immutable evidence even when execution failed after spending resources."""
        with self._lock:
            breach_code = self._breach[0] if self._breach is not None else None
            breach_message = self._breach[1] if self._breach is not None else None
            return HarnessBudgetObservation(
                status="breached" if self._breach is not None else "within_budget",
                reserved_agent_turns=self._reserved_agent_turns,
                reserved_tool_calls=self._reserved_tool_calls,
                reserved_context_tokens=self._reserved_context_tokens,
                unaccounted_dispatches=self._unaccounted_dispatches,
                imported_trials=self._imported_trials,
                recorded_stage_executions=self._recorded_stage_executions,
                observed_tokens=self._observed_tokens,
                token_evidence_complete=self._token_evidence_complete,
                observed_cost_usd=self._observed_cost_usd,
                cost_evidence_complete=self._cost_evidence_complete,
                observed_trial_seconds=self._observed_trial_seconds,
                elapsed_wall_seconds=self._elapsed(),
                breach_code=breach_code,
                breach_message=breach_message,
            )

    def _raise_if_wall_time_exceeded(self) -> None:
        if self._elapsed() > self._budget.max_runtime_seconds:
            self._breach_and_raise(
                "harness_runtime_budget_exceeded",
                "harness wall-clock runtime exceeded the declared Hx budget",
            )

    def _raise_existing_breach(self) -> None:
        if self._breach is not None:
            raise HarnessBudgetError(*self._breach)

    def _breach_and_raise(self, code: str, message: str) -> None:
        if self._breach is None:
            self._breach = (code, message)
        raise HarnessBudgetError(*self._breach)

    def _elapsed(self) -> float:
        return max(0.0, self._clock() - self._started_at)
