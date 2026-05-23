# ABOUTME: Base request and result types for provider-neutral adapters in aec-bench Python.
# ABOUTME: Defines the stable harness-facing surface shared by direct and tool-loop adapters.

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

from aec_bench.adapters.transcript import TranscriptEntry
from aec_bench.contracts.agent_output import AgentOutput
from aec_bench.contracts.task_definition import ToolSpec


class AdapterFailureKind(StrEnum):
    PROVIDER_ERROR = "provider_error"
    TURN_LIMIT_REACHED = "turn_limit_reached"
    TIMEOUT = "timeout"
    UNDECLARED_TOOL_REQUEST = "undeclared_tool_request"
    TOOL_EXECUTION_FAILED = "tool_execution_failed"
    MISSING_OUTPUT = "missing_output"


@dataclass(frozen=True)
class AdapterRequest:
    instruction: str
    system_prompt: str | None = None
    tools: list[ToolSpec] = field(default_factory=list)
    configuration: dict[str, Any] = field(default_factory=dict)
    output_path: str = "/workspace/output.jsonl"
    output_format: str = "jsonl"


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
    raw_output_text: str | None = None
    provider_error: str | None = None
    usage_input_tokens: int | None = None
    usage_output_tokens: int | None = None
    usage_cache_read_tokens: int | None = None
    usage_cache_write_tokens: int | None = None
    usage_advisor_calls: int | None = None
    usage_advisor_input_tokens: int | None = None
    usage_advisor_output_tokens: int | None = None


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
