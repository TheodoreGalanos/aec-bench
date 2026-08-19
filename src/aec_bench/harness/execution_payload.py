# ABOUTME: Serialization helpers for backend-owned adapter execution in aec-bench Python.
# ABOUTME: Converts adapter execution bundles and results to deterministic JSON files.

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import Field, field_validator

from aec_bench.adapters.base import (
    AdapterCompletionReason,
    AdapterFailureKind,
    AdapterRequest,
    AdapterResult,
    AdapterStopReason,
    OutputCompletionAssistance,
    SerializedAdapterExecution,
)
from aec_bench.adapters.provider_routing import provider_for_execution
from aec_bench.contracts.adapter_execution import (
    TokenUsage,
    TranscriptEntry,
    TranscriptEvent,
    TranscriptRole,
)
from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.harness_kernel import (
    canonical_json_sha256,
    validate_sha256,
)
from aec_bench.contracts.legacy_content_address import LegacyContentAddressedModel
from aec_bench.contracts.output_completion import OutputCommitAttestation
from aec_bench.contracts.task_definition import ToolSpec
from aec_bench.contracts.trajectory import MetaHarnessTrajectoryContext
from aec_bench.contracts.validators import NonEmptyStr


class RuntimeExecutionAttestation(LegacyContentAddressedModel):
    """Kernel-owned evidence of the driver and request that actually executed."""

    schema_version: Literal[
        "aecbench.runtime-execution-attestation.v1",
        "aecbench.runtime-execution-attestation.v2",
    ] = "aecbench.runtime-execution-attestation.v2"
    adapter_kind: NonEmptyStr
    adapter_name: NonEmptyStr
    requested_model: NonEmptyStr
    resolved_model: NonEmptyStr
    execution_request_sha256: str
    evidence_manifest_sha256: str | None = Field(default=None, exclude_if=lambda value: value is None)
    provider_evidence_role: Literal["provider_evidence"] | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    meta_harness_context: MetaHarnessTrajectoryContext | None = None

    @field_validator("execution_request_sha256", "evidence_manifest_sha256")
    @classmethod
    def validate_bound_hash(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_sha256(value)

    def model_post_init(self, _context: Any) -> None:
        if self.schema_version.endswith(".v1") and self.provider_evidence_role is not None:
            raise ValueError("runtime attestation v1 cannot use provider_evidence_role")
        if self.schema_version.endswith(".v2") and self.evidence_manifest_sha256 is not None:
            raise ValueError("runtime attestation v2 cannot use evidence_manifest_sha256")


@dataclass(frozen=True)
class AdapterRequestPayload:
    instruction: str
    system_prompt: str | None
    tools: list[dict[str, Any]]
    configuration: dict[str, Any]
    output_path: str
    output_format: str


@dataclass(frozen=True)
class ExecutionBundle:
    execution: SerializedAdapterExecution
    request: AdapterRequestPayload


def build_entrypoint_execution_bundle(
    *,
    instruction: str,
    adapter_name: str,
    model_name: str,
    harbor_kwargs: Mapping[str, Any],
    output_path: str = "/workspace/output.md",
    output_format: str = "markdown",
) -> ExecutionBundle:
    """Materialize the exact adapter request executed by the Harbor entrypoint agent."""
    configuration = dict(harbor_kwargs)
    adapter_kind = configuration.get("adapter", "rlm")
    if not isinstance(adapter_kind, str) or not adapter_kind.strip():
        raise ValueError("adapter must be a non-empty string when provided")
    system_prompt = _entrypoint_system_prompt(configuration.get("system_prompt"))
    tools = _entrypoint_tool_payloads(configuration.get("tools", []))
    execution_payload: dict[str, Any] = {}
    client_payload = configuration.get("client")
    if isinstance(client_payload, dict):
        execution_payload["client"] = client_payload
    provider = provider_for_execution(
        adapter_kind=adapter_kind,
        model_name=model_name,
        client_payload=client_payload,
    )
    if provider is not None:
        execution_payload["provider"] = provider
    return ExecutionBundle(
        execution=SerializedAdapterExecution(
            adapter_kind=adapter_kind,
            adapter_name=adapter_name,
            resolved_model=model_name,
            payload=execution_payload,
        ),
        request=AdapterRequestPayload(
            instruction=instruction,
            system_prompt=system_prompt,
            tools=tools,
            configuration=configuration,
            output_path=output_path,
            output_format=output_format,
        ),
    )


def build_execution_bundle(
    *,
    execution: SerializedAdapterExecution,
    request: AdapterRequest,
) -> ExecutionBundle:
    return ExecutionBundle(
        execution=execution,
        request=AdapterRequestPayload(
            instruction=request.instruction,
            system_prompt=request.system_prompt,
            tools=[tool.model_dump(mode="json") for tool in request.tools],
            configuration=request.configuration,
            output_path=request.output_path,
            output_format=request.output_format,
        ),
    )


def write_execution_bundle(*, path: Path, bundle: ExecutionBundle) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_bundle_payload(bundle), sort_keys=True), encoding="utf-8")
    return path


def execution_request_sha256(bundle: ExecutionBundle) -> str:
    """Hash the exact canonical execution request bytes used by runtime attestation."""
    return canonical_json_sha256(_bundle_payload(bundle))


def read_execution_bundle(path: Path) -> ExecutionBundle:
    payload = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    execution_payload = cast(dict[str, Any], payload["execution"])
    request_payload = cast(dict[str, Any], payload["request"])
    return ExecutionBundle(
        execution=SerializedAdapterExecution(
            adapter_kind=cast(str, execution_payload["adapter_kind"]),
            adapter_name=cast(str, execution_payload["adapter_name"]),
            resolved_model=cast(str, execution_payload["resolved_model"]),
            payload=cast(dict[str, Any], execution_payload.get("payload", {})),
        ),
        request=AdapterRequestPayload(
            instruction=cast(str, request_payload["instruction"]),
            system_prompt=cast(str | None, request_payload.get("system_prompt")),
            tools=cast(list[dict[str, Any]], request_payload.get("tools", [])),
            configuration=cast(dict[str, Any], request_payload.get("configuration", {})),
            output_path=cast(str, request_payload["output_path"]),
            output_format=cast(str, request_payload["output_format"]),
        ),
    )


def write_execution_result(
    *,
    path: Path,
    result: AdapterResult,
    runtime_attestation: RuntimeExecutionAttestation | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_result_payload(result, runtime_attestation=runtime_attestation), sort_keys=True),
        encoding="utf-8",
    )
    return path


def read_execution_result(path: Path) -> AdapterResult:
    payload = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    transcript_payload = cast(list[dict[str, Any]], payload.get("transcript", []))
    agent_output_payload = cast(dict[str, Any], payload["agent_output"])
    return AdapterResult(
        adapter_name=cast(str, payload["adapter_name"]),
        resolved_model=cast(str, payload["resolved_model"]),
        configuration_record=cast(dict[str, Any], payload.get("configuration_record", {})),
        agent_output=AgentOutput(
            status=AgentOutputStatus(cast(str, agent_output_payload["status"])),
            output_path=cast(str, agent_output_payload["output_path"]),
            output_format=cast(str, agent_output_payload["output_format"]),
            error_message=cast(
                str | None,
                agent_output_payload.get("error_message"),
            ),
        ),
        transcript=[_transcript_entry(record) for record in transcript_payload],
        failure_kind=_failure_kind(payload.get("failure_kind")),
        stop_reason=_stop_reason(payload.get("stop_reason")),
        completion_reason=_completion_reason(payload.get("completion_reason")),
        completion_assistance=_completion_assistance(payload.get("completion_assistance")),
        completion_commit=_completion_commit(payload.get("completion_commit")),
        turns_used=cast(int | None, payload.get("turns_used")),
        max_turns=cast(int | None, payload.get("max_turns")),
        raw_output_text=cast(str | None, payload.get("raw_output_text")),
        provider_error=cast(str | None, payload.get("provider_error")),
        usage_model_calls=cast(int | None, payload.get("usage_model_calls")),
        usage_input_tokens=cast(int | None, payload.get("usage_input_tokens")),
        usage_output_tokens=cast(int | None, payload.get("usage_output_tokens")),
        usage_cache_read_tokens=cast(int | None, payload.get("usage_cache_read_tokens")),
        usage_cache_write_tokens=cast(int | None, payload.get("usage_cache_write_tokens")),
        usage_advisor_calls=cast(int | None, payload.get("usage_advisor_calls")),
        usage_advisor_input_tokens=cast(
            int | None,
            payload.get("usage_advisor_input_tokens"),
        ),
        usage_advisor_output_tokens=cast(
            int | None,
            payload.get("usage_advisor_output_tokens"),
        ),
    )


def _bundle_payload(bundle: ExecutionBundle) -> dict[str, Any]:
    return {
        "execution": {
            "adapter_kind": bundle.execution.adapter_kind,
            "adapter_name": bundle.execution.adapter_name,
            "resolved_model": bundle.execution.resolved_model,
            "payload": bundle.execution.payload,
        },
        "request": {
            "instruction": bundle.request.instruction,
            "system_prompt": bundle.request.system_prompt,
            "tools": bundle.request.tools,
            "configuration": bundle.request.configuration,
            "output_path": bundle.request.output_path,
            "output_format": bundle.request.output_format,
        },
    }


def _result_payload(
    result: AdapterResult,
    *,
    runtime_attestation: RuntimeExecutionAttestation | None,
) -> dict[str, Any]:
    payload = {
        "adapter_name": result.adapter_name,
        "resolved_model": result.resolved_model,
        "configuration_record": result.configuration_record,
        "agent_output": {
            "status": result.agent_output.status.value,
            "output_path": result.agent_output.output_path,
            "output_format": result.agent_output.output_format,
            "error_message": result.agent_output.error_message,
        },
        "transcript": [_transcript_payload(entry) for entry in result.transcript],
        "failure_kind": result.failure_kind.value if result.failure_kind is not None else None,
        "stop_reason": result.stop_reason.value if result.stop_reason is not None else None,
        "completion_reason": result.completion_reason.value if result.completion_reason is not None else None,
        "completion_assistance": (
            {
                "contract_satisfied": result.completion_assistance.contract_satisfied,
                "reminder_sent": result.completion_assistance.reminder_sent,
                "reminder_turn": result.completion_assistance.reminder_turn,
                "explicit_final_turn": result.completion_assistance.explicit_final_turn,
            }
            if result.completion_assistance is not None
            else None
        ),
        "completion_commit": (
            result.completion_commit.model_dump(mode="json") if result.completion_commit is not None else None
        ),
        "turns_used": result.turns_used,
        "max_turns": result.max_turns,
        "raw_output_text": result.raw_output_text,
        "provider_error": result.provider_error,
        "usage_input_tokens": result.usage_input_tokens,
        "usage_output_tokens": result.usage_output_tokens,
        "usage_cache_read_tokens": result.usage_cache_read_tokens,
        "usage_cache_write_tokens": result.usage_cache_write_tokens,
        "usage_advisor_calls": result.usage_advisor_calls,
        "usage_advisor_input_tokens": result.usage_advisor_input_tokens,
        "usage_advisor_output_tokens": result.usage_advisor_output_tokens,
    }
    if result.usage_model_calls is not None:
        payload["usage_model_calls"] = result.usage_model_calls
    if runtime_attestation is not None:
        payload["runtime_execution_attestation"] = runtime_attestation.model_dump(mode="json")
    return payload


def build_runtime_execution_attestation(
    *,
    bundle: ExecutionBundle,
    result: AdapterResult,
) -> RuntimeExecutionAttestation:
    """Attest one result after the execution driver has resolved and returned."""
    context_payload = bundle.request.configuration.get("meta_harness_context")
    context = None if context_payload is None else MetaHarnessTrajectoryContext.model_validate(context_payload)
    provider_evidence_payload = result.configuration_record.get("provider_evidence_manifest")
    if provider_evidence_payload is not None:
        ArtifactRef.model_validate(provider_evidence_payload)
    return RuntimeExecutionAttestation(
        adapter_kind=bundle.execution.adapter_kind,
        adapter_name=result.adapter_name,
        requested_model=bundle.execution.resolved_model,
        resolved_model=result.resolved_model,
        execution_request_sha256=execution_request_sha256(bundle),
        provider_evidence_role=("provider_evidence" if provider_evidence_payload is not None else None),
        meta_harness_context=context,
    )


def _entrypoint_system_prompt(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("system_prompt must be a non-empty string when provided")
    return value


def _entrypoint_tool_payloads(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("tools must be a list of ToolSpec payloads")
    return [ToolSpec.model_validate(tool).model_dump(mode="json") for tool in value]


def _transcript_payload(entry: TranscriptEntry) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "role": entry.role.value,
        "content": entry.content,
        "event": entry.event.value,
        "tool_name": entry.tool_name,
        "tool_call_id": entry.tool_call_id,
        "occurred_at": entry.occurred_at.isoformat() if entry.occurred_at is not None else None,
    }
    if entry.usage is not None:
        payload["usage"] = {
            "input_tokens": entry.usage.input_tokens,
            "output_tokens": entry.usage.output_tokens,
        }
    return payload


def _transcript_entry(payload: dict[str, Any]) -> TranscriptEntry:
    usage_payload = cast(dict[str, Any] | None, payload.get("usage"))
    occurred_at = cast(str | None, payload.get("occurred_at"))
    return TranscriptEntry(
        role=TranscriptRole(cast(str, payload["role"])),
        content=cast(str, payload["content"]),
        event=TranscriptEvent(cast(str, payload.get("event", TranscriptEvent.MESSAGE.value))),
        tool_name=cast(str | None, payload.get("tool_name")),
        tool_call_id=cast(str | None, payload.get("tool_call_id")),
        usage=(
            None
            if usage_payload is None
            else TokenUsage(
                input_tokens=cast(int | None, usage_payload.get("input_tokens")),
                output_tokens=cast(int | None, usage_payload.get("output_tokens")),
            )
        ),
        occurred_at=None if occurred_at is None else datetime.fromisoformat(occurred_at),
    )


def _failure_kind(value: Any) -> AdapterFailureKind | None:
    if value is None:
        return None
    return AdapterFailureKind(cast(str, value))


def _stop_reason(value: Any) -> AdapterStopReason | None:
    if value is None:
        return None
    return AdapterStopReason(cast(str, value))


def _completion_reason(value: Any) -> AdapterCompletionReason | None:
    if value is None:
        return None
    return AdapterCompletionReason(cast(str, value))


def _completion_assistance(value: Any) -> OutputCompletionAssistance | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("completion_assistance must be an object when present")
    expected_keys = {
        "contract_satisfied",
        "reminder_sent",
        "reminder_turn",
        "explicit_final_turn",
    }
    if set(value) != expected_keys:
        raise ValueError("completion_assistance must contain exactly the declared evidence fields")
    contract_satisfied = value["contract_satisfied"]
    reminder_sent = value["reminder_sent"]
    reminder_turn = value["reminder_turn"]
    explicit_final_turn = value["explicit_final_turn"]
    if not isinstance(contract_satisfied, bool) or not isinstance(reminder_sent, bool):
        raise ValueError("completion_assistance flags must be booleans")
    for field_name, turn in (
        ("reminder_turn", reminder_turn),
        ("explicit_final_turn", explicit_final_turn),
    ):
        if turn is not None and (not isinstance(turn, int) or isinstance(turn, bool)):
            raise ValueError(f"completion_assistance {field_name} must be an integer or null")
    return OutputCompletionAssistance(
        contract_satisfied=contract_satisfied,
        reminder_sent=reminder_sent,
        reminder_turn=reminder_turn,
        explicit_final_turn=explicit_final_turn,
    )


def _completion_commit(value: Any) -> OutputCommitAttestation | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("completion_commit must be an object when present")
    return OutputCommitAttestation.model_validate(value)
