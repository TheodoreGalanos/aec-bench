# ABOUTME: Base request and result types for provider-neutral adapters in aec-bench Python.
# ABOUTME: Defines the stable harness-facing surface shared by direct and tool-loop adapters.

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

from aec_bench.contracts.adapter_execution import TranscriptEntry, TranscriptRole
from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.output_completion import OutputCommitAttestation
from aec_bench.contracts.task_definition import ToolSpec


class AdapterFailureKind(StrEnum):
    PROVIDER_ERROR = "provider_error"
    TURN_LIMIT_REACHED = "turn_limit_reached"
    TOKEN_BUDGET_REACHED = "token_budget_reached"
    SUBCALL_LIMIT_REACHED = "subcall_limit_reached"
    COST_BUDGET_REACHED = "cost_budget_reached"
    BILLABLE_INPUT_BUDGET_REACHED = "billable_input_budget_reached"
    CONTEXT_LIMIT_REACHED = "context_limit_reached"
    TOOL_CALL_LIMIT_REACHED = "tool_call_limit_reached"
    TIMEOUT = "timeout"
    UNDECLARED_TOOL_REQUEST = "undeclared_tool_request"
    TOOL_EXECUTION_FAILED = "tool_execution_failed"
    MISSING_OUTPUT = "missing_output"


class AdapterStopReason(StrEnum):
    """Typed reason why an adapter stopped before ordinary completion."""

    ITERATION_CAP = "iteration_cap"
    TOKEN_BUDGET = "token_budget"
    SUBCALL_LIMIT = "subcall_limit"
    COST_BUDGET = "cost_budget"
    BILLABLE_INPUT_BUDGET = "billable_input_budget"
    CONTEXT_LIMIT = "context_limit"


class AdapterCompletionReason(StrEnum):
    """Typed reason why an adapter declared ordinary completion."""

    OUTPUT_CONTRACT_SATISFIED = "output_contract_satisfied"
    OUTPUT_CONTRACT_COMMITTED = "output_contract_committed"


@dataclass(frozen=True)
class OutputCompletionAssistance:
    """Typed evidence that a structural completion reminder preceded finalization."""

    contract_satisfied: bool
    reminder_sent: bool
    reminder_turn: int | None
    explicit_final_turn: int | None

    def __post_init__(self) -> None:
        if self.reminder_sent != (self.reminder_turn is not None):
            raise ValueError("reminder_sent must agree with reminder_turn presence")
        for field_name, turn in (
            ("reminder_turn", self.reminder_turn),
            ("explicit_final_turn", self.explicit_final_turn),
        ):
            if turn is not None and turn < 1:
                raise ValueError(f"{field_name} must be positive when present")
        if (
            self.reminder_turn is not None
            and self.explicit_final_turn is not None
            and self.reminder_turn >= self.explicit_final_turn
        ):
            raise ValueError("reminder_turn must precede explicit_final_turn")

    @property
    def supports_output_contract_completion(self) -> bool:
        """Return whether evidence proves reminder-assisted explicit completion."""
        return (
            self.contract_satisfied
            and self.reminder_sent
            and self.reminder_turn is not None
            and self.explicit_final_turn is not None
            and self.reminder_turn < self.explicit_final_turn
        )


@dataclass(frozen=True)
class AdapterRequest:
    instruction: str
    system_prompt: str | None = None
    tools: list[ToolSpec] = field(default_factory=list)
    configuration: dict[str, Any] = field(default_factory=dict)
    output_path: str = "/workspace/output.jsonl"
    output_format: str = "jsonl"


def initialize_transcript(request: AdapterRequest) -> list[TranscriptEntry]:
    """Build the opening transcript entries from an adapter request."""
    transcript: list[TranscriptEntry] = []
    if request.system_prompt is not None:
        transcript.append(TranscriptEntry(role=TranscriptRole.SYSTEM, content=request.system_prompt))
    transcript.append(TranscriptEntry(role=TranscriptRole.USER, content=request.instruction))
    return transcript


@dataclass(frozen=True)
class SerializedAdapterExecution:
    adapter_kind: str
    adapter_name: str
    resolved_model: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SerializedClientSpec:
    client_kind: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AdapterResult:
    adapter_name: str
    resolved_model: str
    configuration_record: dict[str, Any]
    agent_output: AgentOutput
    transcript: list[TranscriptEntry]
    failure_kind: AdapterFailureKind | None = None
    stop_reason: AdapterStopReason | None = None
    completion_reason: AdapterCompletionReason | None = None
    completion_assistance: OutputCompletionAssistance | None = None
    completion_commit: OutputCommitAttestation | None = None
    turns_used: int | None = None
    max_turns: int | None = None
    raw_output_text: str | None = None
    provider_error: str | None = None
    usage_model_calls: int | None = None
    usage_input_tokens: int | None = None
    usage_output_tokens: int | None = None
    usage_cache_read_tokens: int | None = None
    usage_cache_write_tokens: int | None = None
    maximum_input_tokens_in_one_call: int | None = None
    maximum_output_tokens_in_one_call: int | None = None
    usage_advisor_calls: int | None = None
    usage_advisor_input_tokens: int | None = None
    usage_advisor_output_tokens: int | None = None

    def __post_init__(self) -> None:
        if self.completion_reason is AdapterCompletionReason.OUTPUT_CONTRACT_SATISFIED and (
            self.completion_assistance is None or not self.completion_assistance.supports_output_contract_completion
        ):
            raise ValueError("output_contract_satisfied requires prior reminder-assisted explicit completion evidence")
        if self.completion_reason is AdapterCompletionReason.OUTPUT_CONTRACT_COMMITTED:
            if self.completion_commit is None:
                raise ValueError("output_contract_committed requires an output commit attestation")
            if self.completion_assistance is not None:
                raise ValueError("output_contract_committed cannot carry reminder-assistance evidence")
            if self.agent_output.status is not AgentOutputStatus.COMPLETED:
                raise ValueError("output_contract_committed requires completed agent output")
            if self.agent_output.output_path != self.completion_commit.output_path:
                raise ValueError("output commit attestation path must match agent output path")
            if self.turns_used != self.completion_commit.commit_turn:
                raise ValueError("output commit turn must equal adapter turns_used")
        elif self.completion_commit is not None:
            raise ValueError("output commit attestation requires output_contract_committed completion reason")


@dataclass(frozen=True)
class AdapterCapabilities:
    """Declaration of which constitutional mechanisms an adapter supports.

    Used by the constitutional inference engine to know what parameters
    can be derived, and by capability validation to catch cases where
    an enabled principle has no enforcement mechanism available.
    """

    has_context_filtering: bool = False
    has_state_persistence: bool = False
    has_compaction: bool = False
    has_scaffolding: bool = False
    has_review_phase: bool = False
    has_source_tracing: bool = False

    def supports_principle(self, principle_name: str) -> bool:
        """Return True if this adapter can enforce the named principle."""
        mapping: dict[str, bool] = {
            "information_minimality": self.has_context_filtering,
            "state_persistence": self.has_state_persistence and self.has_compaction,
            "progress_obligation": self.has_scaffolding,
            "source_fidelity": self.has_source_tracing,
            "earned_autonomy": self.has_scaffolding,
        }
        if principle_name not in mapping:
            raise ValueError(f"unknown principle: {principle_name!r}")
        return mapping[principle_name]


class Adapter(Protocol):
    def execute(self, request: AdapterRequest) -> AdapterResult: ...

    def adapter_name(self) -> str: ...

    def resolved_model(self) -> str: ...


class RemoteExecutableAdapter(Protocol):
    def serialize_execution(self) -> SerializedAdapterExecution: ...

    def adapter_name(self) -> str: ...

    def resolved_model(self) -> str: ...


def client_spec_to_payload(client_spec: SerializedClientSpec) -> dict[str, Any]:
    return {
        "client_kind": client_spec.client_kind,
        "payload": client_spec.payload,
    }
