# ABOUTME: Tests for serialized backend execution payloads in aec-bench Python.
# ABOUTME: Covers deterministic roundtrips for execution bundles and adapter results.

import json
from pathlib import Path

import pytest

from aec_bench.adapters.base import (
    AdapterCompletionReason,
    AdapterFailureKind,
    AdapterResult,
    AdapterStopReason,
    OutputCompletionAssistance,
    SerializedAdapterExecution,
)
from aec_bench.adapters.transcript import TranscriptEntry, TranscriptRole
from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.harness.execution_payload import (
    AdapterRequestPayload,
    ExecutionBundle,
    build_entrypoint_execution_bundle,
    execution_request_sha256,
    read_execution_bundle,
    read_execution_result,
    write_execution_bundle,
    write_execution_result,
)
from tests.support.output_completion import make_output_commit_attestation


def test_execution_bundle_roundtrips_through_json(tmp_path: Path) -> None:
    bundle = ExecutionBundle(
        execution=SerializedAdapterExecution(
            adapter_kind="direct",
            adapter_name="direct",
            resolved_model="gpt-5.4",
            payload={"temperature": 0},
        ),
        request=AdapterRequestPayload(
            instruction="Review the task.",
            system_prompt="Be precise.",
            tools=[],
            configuration={"max_tokens": 200},
            output_path="/workspace/output.jsonl",
            output_format="jsonl",
        ),
    )

    path = write_execution_bundle(path=tmp_path / "bundle.json", bundle=bundle)
    loaded = read_execution_bundle(path)

    assert loaded == bundle


def test_entrypoint_execution_bundle_canonically_materializes_harbor_inputs() -> None:
    harbor_kwargs = {
        "adapter": "rlm",
        "system_prompt": "Inspect the evidence.\n",
        "tools": [
            {
                "name": "bash",
                "source": "environment/tools/bash.sh",
                "description": "Run one declared command.",
                "returns_image": False,
            }
        ],
        "client": {"client_kind": "replay", "payload": {"responses": []}},
        "max_turns": 8,
    }

    bundle = build_entrypoint_execution_bundle(
        instruction="Solve the exact task.\n",
        adapter_name="entrypoint",
        model_name="replay-rlm",
        harbor_kwargs=harbor_kwargs,
    )
    repeated = build_entrypoint_execution_bundle(
        instruction="Solve the exact task.\n",
        adapter_name="entrypoint",
        model_name="replay-rlm",
        harbor_kwargs=dict(reversed(tuple(harbor_kwargs.items()))),
    )

    assert bundle.execution.adapter_kind == "rlm"
    assert bundle.execution.payload == {"client": harbor_kwargs["client"]}
    assert bundle.request.instruction == "Solve the exact task.\n"
    assert bundle.request.system_prompt == "Inspect the evidence.\n"
    assert bundle.request.tools == harbor_kwargs["tools"]
    assert bundle.request.configuration == harbor_kwargs
    assert bundle.request.output_path == "/workspace/output.md"
    assert bundle.request.output_format == "markdown"
    assert execution_request_sha256(bundle) == execution_request_sha256(repeated)


def test_execution_result_roundtrips_through_json(tmp_path: Path) -> None:
    result = AdapterResult(
        adapter_name="tool_loop",
        resolved_model="gpt-5.4-mini",
        configuration_record={"max_turns": 4},
        agent_output=AgentOutput(
            status=AgentOutputStatus.PARTIAL,
            output_path="/workspace/output.jsonl",
            output_format="jsonl",
        ),
        transcript=[TranscriptEntry(role=TranscriptRole.USER, content="Review the task.")],
        failure_kind=AdapterFailureKind.TURN_LIMIT_REACHED,
        stop_reason=AdapterStopReason.ITERATION_CAP,
        turns_used=4,
        max_turns=4,
        raw_output_text='{"findings": []}',
        usage_model_calls=4,
        usage_input_tokens=120,
        usage_output_tokens=45,
        usage_cache_read_tokens=30,
        usage_cache_write_tokens=12,
        usage_advisor_calls=2,
        usage_advisor_input_tokens=80,
        usage_advisor_output_tokens=20,
    )

    path = write_execution_result(path=tmp_path / "result.json", result=result)
    loaded = read_execution_result(path)

    assert loaded == result


def test_execution_result_roundtrips_typed_completion_reason(tmp_path: Path) -> None:
    result = AdapterResult(
        adapter_name="rlm",
        resolved_model="test-model",
        configuration_record={"output_completion_contract": {"schema_version": "test"}},
        agent_output=AgentOutput(
            status=AgentOutputStatus.COMPLETED,
            output_path="/workspace/output.md",
            output_format="markdown",
        ),
        transcript=[],
        completion_reason=AdapterCompletionReason.OUTPUT_CONTRACT_SATISFIED,
        completion_assistance=OutputCompletionAssistance(
            contract_satisfied=True,
            reminder_sent=True,
            reminder_turn=2,
            explicit_final_turn=3,
        ),
        turns_used=3,
        max_turns=32,
    )

    path = write_execution_result(path=tmp_path / "completed-result.json", result=result)
    loaded = read_execution_result(path)

    assert loaded == result


def test_execution_result_roundtrips_typed_output_commit_attestation(tmp_path: Path) -> None:
    attestation = make_output_commit_attestation()
    result = AdapterResult(
        adapter_name="rlm",
        resolved_model="test-model",
        configuration_record={"output_completion_commit": True},
        agent_output=AgentOutput(
            status=AgentOutputStatus.COMPLETED,
            output_path=attestation.output_path,
            output_format="markdown",
        ),
        transcript=[],
        completion_reason=AdapterCompletionReason.OUTPUT_CONTRACT_COMMITTED,
        completion_commit=attestation,
        turns_used=attestation.commit_turn,
        max_turns=32,
    )

    path = write_execution_result(path=tmp_path / "committed-result.json", result=result)
    payload = json.loads(path.read_text(encoding="utf-8"))
    loaded = read_execution_result(path)

    assert payload["completion_commit"] == attestation.model_dump(mode="json")
    assert loaded == result


def test_execution_result_rejects_unknown_completion_reason(tmp_path: Path) -> None:
    result = AdapterResult(
        adapter_name="rlm",
        resolved_model="test-model",
        configuration_record={},
        agent_output=AgentOutput(
            status=AgentOutputStatus.COMPLETED,
            output_path="/workspace/output.md",
            output_format="markdown",
        ),
        transcript=[],
    )
    path = write_execution_result(path=tmp_path / "unknown-completion.json", result=result)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["completion_reason"] = "future_unrecognised_completion"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="future_unrecognised_completion"):
        read_execution_result(path)


def test_execution_result_reads_legacy_json_without_typed_stop_evidence(tmp_path: Path) -> None:
    result = AdapterResult(
        adapter_name="rlm",
        resolved_model="test-model",
        configuration_record={"max_turns": 4},
        agent_output=AgentOutput(
            status=AgentOutputStatus.PARTIAL,
            output_path="/workspace/output.md",
            output_format="markdown",
        ),
        transcript=[],
        failure_kind=AdapterFailureKind.TURN_LIMIT_REACHED,
    )
    path = write_execution_result(path=tmp_path / "legacy-result.json", result=result)
    payload = json.loads(path.read_text(encoding="utf-8"))
    for field in ("stop_reason", "turns_used", "max_turns", "completion_commit"):
        payload.pop(field, None)
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = read_execution_result(path)

    assert loaded.stop_reason is None
    assert loaded.turns_used is None
    assert loaded.max_turns is None
    assert loaded.completion_commit is None


def test_execution_result_rejects_malformed_output_commit_attestation(tmp_path: Path) -> None:
    result = AdapterResult(
        adapter_name="rlm",
        resolved_model="test-model",
        configuration_record={},
        agent_output=AgentOutput(
            status=AgentOutputStatus.COMPLETED,
            output_path="/workspace/output.md",
            output_format="markdown",
        ),
        transcript=[],
    )
    path = write_execution_result(path=tmp_path / "malformed-commit.json", result=result)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["completion_commit"] = {
        "schema_version": "aecbench.output-commit-attestation.v1",
        "unexpected": True,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError):
        read_execution_result(path)


def test_execution_result_rejects_unknown_typed_stop_reason(tmp_path: Path) -> None:
    result = AdapterResult(
        adapter_name="rlm",
        resolved_model="test-model",
        configuration_record={"max_turns": 4},
        agent_output=AgentOutput(
            status=AgentOutputStatus.PARTIAL,
            output_path="/workspace/output.md",
            output_format="markdown",
        ),
        transcript=[],
    )
    path = write_execution_result(path=tmp_path / "unknown-stop.json", result=result)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["stop_reason"] = "future_unrecognised_limit"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="future_unrecognised_limit"):
        read_execution_result(path)
