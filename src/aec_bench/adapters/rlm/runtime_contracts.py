# ABOUTME: Defines typed configuration and mutable state for one RLM execution lifecycle.
# ABOUTME: Centralizes accounting, trajectory, and terminal result construction invariants.

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

from aec_bench.adapters.advisor_usage import AdvisorUsageAccumulator
from aec_bench.adapters.base import (
    AdapterCompletionReason,
    AdapterFailureKind,
    AdapterRequest,
    AdapterResult,
    AdapterStopReason,
    OutputCompletionAssistance,
)
from aec_bench.adapters.config import record_effective_configuration
from aec_bench.adapters.rlm.client import (
    RlmClient,
    RlmCompletionResponse,
    RlmMessage,
    ToolCapableRlmClient,
)
from aec_bench.adapters.rlm.config import ExecutionConfig, GuardrailConfig, SubcallConfig
from aec_bench.adapters.rlm.context_filter import ContextFilter
from aec_bench.adapters.rlm.engine import ReplEnvironment
from aec_bench.adapters.rlm.errors import ErrorTracker
from aec_bench.adapters.rlm.guardrails import GuardrailState
from aec_bench.adapters.rlm.output_commit import OutputCompletionState
from aec_bench.adapters.rlm.request_runtime import ResolvedRlmRequest
from aec_bench.adapters.rlm.scaffolding import ScaffoldingState
from aec_bench.adapters.rlm.scratchpad import Scratchpad
from aec_bench.adapters.rlm.template import ReportTemplate
from aec_bench.adapters.rlm.tokens import TokenTracker, TurnMetrics
from aec_bench.contracts.adapter_execution import TranscriptEntry
from aec_bench.contracts.advisor import AdvisorConfig
from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.constitution import ConstitutionManifest
from aec_bench.contracts.output_completion import OutputCommitAttestation


class RlmTrajectory(Protocol):
    """Trajectory operations used by the RLM execution runtime."""

    def system(self, content: str) -> None: ...

    def user(self, content: str) -> None: ...

    def new_step(self, call_type: str | None = None) -> int: ...

    def tool_call(
        self,
        tool_name: str,
        command: str,
        arguments: dict[str, Any] | None = None,
    ) -> None: ...

    def tool_result(
        self,
        tool_name: str,
        stdout: str,
        stderr: str = "",
        exit_code: int = 0,
        duration_ms: int | None = None,
        media: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        output_summary: str | None = None,
    ) -> None: ...

    def close(self) -> None: ...


@dataclass(frozen=True, slots=True)
class RlmRuntimeConfig:
    """All adapter-owned dependencies required for one RLM execution."""

    adapter_name: str
    model_name: str
    client: RlmClient
    guardrails: GuardrailConfig
    execution: ExecutionConfig
    hints: list[str] | None = None
    prohibited: list[str] | None = None
    subcall_client: RlmClient | None = None
    subcall_model: str | None = None
    subcall_configs: dict[str, SubcallConfig] | None = None
    template: ReportTemplate | None = None
    compaction_client: RlmClient | None = None
    trajectory: RlmTrajectory | None = None
    scratchpad_path: str | None = None
    external_system_prompt: str = ""
    workspace_path: str | None = None
    advisor_client: RlmClient | None = None
    advisor_config: AdvisorConfig | None = None
    constitution: ConstitutionManifest | None = None


class LifecycleAction(StrEnum):
    """Control transition produced after one model turn."""

    CONTINUE = "continue"
    COMPACT = "compact"
    TERMINAL = "terminal"


@dataclass(frozen=True, slots=True)
class LifecycleTransition:
    """One typed transition from the per-turn reducer."""

    action: LifecycleAction
    result: AdapterResult | None = None

    def __post_init__(self) -> None:
        terminal = self.action is LifecycleAction.TERMINAL
        if terminal != (self.result is not None):
            raise ValueError("terminal lifecycle transitions require exactly one adapter result")

    @classmethod
    def continue_execution(cls) -> LifecycleTransition:
        return cls(action=LifecycleAction.CONTINUE)

    @classmethod
    def compact(cls) -> LifecycleTransition:
        return cls(action=LifecycleAction.COMPACT)

    @classmethod
    def terminal(cls, result: AdapterResult) -> LifecycleTransition:
        return cls(action=LifecycleAction.TERMINAL, result=result)


@dataclass(slots=True)
class RlmExecutionState:
    """Mutable state advanced atomically by the execution lifecycle."""

    runtime: RlmRuntimeConfig
    resolved: ResolvedRlmRequest
    output: OutputCompletionState
    repl: ReplEnvironment
    errors: ErrorTracker
    guardrails: GuardrailState
    tokens: TokenTracker
    scaffolding: ScaffoldingState
    context_filter: ContextFilter
    transcript: list[TranscriptEntry]
    system_prompt: str
    scaffolds: dict[str, object]
    scratchpad: Scratchpad | None
    advisor_usage: AdvisorUsageAccumulator | None
    conversation: list[RlmMessage]
    tool_client: ToolCapableRlmClient | None
    repl_tool_description: str
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    previous_variable_names: set[str] = field(default_factory=set)
    compaction_count: int = 0
    iteration_budget_warning_sent: bool = False

    @property
    def request(self) -> AdapterRequest:
        return self.resolved.request

    @property
    def trajectory(self) -> RlmTrajectory | None:
        return self.runtime.trajectory

    def record_response(self, response: RlmCompletionResponse, *, cost_usd: float) -> TurnMetrics:
        """Record one provider response in every public accounting plane."""
        self.total_input_tokens += response.input_tokens
        self.total_output_tokens += response.output_tokens
        self.guardrails.record_iteration(
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cost_usd=cost_usd,
            cache_read_tokens=response.cache_read_tokens,
        )
        return self.tokens.record_turn(
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cache_read_tokens=response.cache_read_tokens,
            cache_write_tokens=response.cache_write_tokens,
        )

    def close_trajectory(self) -> None:
        if self.trajectory is not None:
            self.trajectory.close()

    def build_result(
        self,
        *,
        status: AgentOutputStatus,
        failure_kind: AdapterFailureKind | None = None,
        stop_reason: AdapterStopReason | None = None,
        completion_reason: AdapterCompletionReason | None = None,
        completion_assistance: OutputCompletionAssistance | None = None,
        completion_commit: OutputCommitAttestation | None = None,
        error_message: str | None = None,
        raw_output_text: str | None = None,
    ) -> AdapterResult:
        """Build the stable adapter result from the current execution state."""
        request = self.request
        total_usage = self.tokens.depth_summary()["total"]
        advisor_calls: int | None = None
        advisor_input_tokens: int | None = None
        advisor_output_tokens: int | None = None
        if self.advisor_usage is not None:
            advisor_calls, advisor_input_tokens, advisor_output_tokens = self.advisor_usage.snapshot()
        return AdapterResult(
            adapter_name=self.runtime.adapter_name,
            resolved_model=self.runtime.model_name,
            configuration_record=record_effective_configuration(
                resolved_model=self.runtime.model_name,
                configuration=dict(request.configuration),
            ),
            agent_output=AgentOutput(
                status=status,
                output_path=request.output_path,
                output_format=request.output_format,
                error_message=error_message,
            ),
            transcript=self.transcript,
            failure_kind=failure_kind,
            stop_reason=stop_reason,
            completion_reason=completion_reason,
            completion_assistance=completion_assistance,
            completion_commit=completion_commit,
            turns_used=self.guardrails.iteration_count,
            max_turns=self.resolved.max_iterations,
            raw_output_text=raw_output_text,
            provider_error=error_message,
            usage_model_calls=int(total_usage["calls"]),
            usage_input_tokens=int(total_usage["input_tokens"]),
            usage_output_tokens=int(total_usage["output_tokens"]),
            usage_cache_read_tokens=int(total_usage["cache_read_tokens"]),
            usage_cache_write_tokens=int(total_usage["cache_write_tokens"]),
            usage_advisor_calls=advisor_calls,
            usage_advisor_input_tokens=advisor_input_tokens,
            usage_advisor_output_tokens=advisor_output_tokens,
        )
