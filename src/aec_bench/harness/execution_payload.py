# ABOUTME: Serialization helpers for backend-owned adapter execution in aec-bench Python.
# ABOUTME: Converts adapter execution bundles and results to deterministic JSON files.

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from aec_bench.adapters.base import (
    AdapterFailureKind,
    AdapterRequest,
    AdapterResult,
    SerializedAdapterExecution,
)
from aec_bench.adapters.transcript import (
    TokenUsage,
    TranscriptEntry,
    TranscriptEvent,
    TranscriptRole,
)
from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus


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


def write_execution_result(*, path: Path, result: AdapterResult) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_result_payload(result), sort_keys=True), encoding="utf-8")
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
        raw_output_text=cast(str | None, payload.get("raw_output_text")),
        provider_error=cast(str | None, payload.get("provider_error")),
        usage_input_tokens=cast(int | None, payload.get("usage_input_tokens")),
        usage_output_tokens=cast(int | None, payload.get("usage_output_tokens")),
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


def _result_payload(result: AdapterResult) -> dict[str, Any]:
    return {
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
        "raw_output_text": result.raw_output_text,
        "provider_error": result.provider_error,
        "usage_input_tokens": result.usage_input_tokens,
        "usage_output_tokens": result.usage_output_tokens,
    }


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
