# ABOUTME: Tests for serialized backend execution payloads in aec-bench Python.
# ABOUTME: Covers deterministic roundtrips for execution bundles and adapter results.

from pathlib import Path

from aec_bench.adapters.base import AdapterResult, SerializedAdapterExecution
from aec_bench.adapters.transcript import TranscriptEntry, TranscriptRole
from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.harness.execution_payload import (
    AdapterRequestPayload,
    ExecutionBundle,
    read_execution_bundle,
    read_execution_result,
    write_execution_bundle,
    write_execution_result,
)


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


def test_execution_result_roundtrips_through_json(tmp_path: Path) -> None:
    result = AdapterResult(
        adapter_name="tool_loop",
        resolved_model="gpt-5.4-mini",
        configuration_record={"max_turns": 4},
        agent_output=AgentOutput(
            status=AgentOutputStatus.COMPLETED,
            output_path="/workspace/output.jsonl",
            output_format="jsonl",
        ),
        transcript=[TranscriptEntry(role=TranscriptRole.USER, content="Review the task.")],
        raw_output_text='{"findings": []}',
        usage_input_tokens=120,
        usage_output_tokens=45,
    )

    path = write_execution_result(path=tmp_path / "result.json", result=result)
    loaded = read_execution_result(path)

    assert loaded == result
