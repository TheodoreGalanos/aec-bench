# ABOUTME: Tests for the AgentOutput contract used at the adapter-to-evaluation boundary.
# ABOUTME: These tests define the minimal output envelope semantics for task execution.

import pytest
from pydantic import ValidationError

from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus


def test_agent_output_accepts_valid_payload() -> None:
    output = AgentOutput(
        status=AgentOutputStatus.COMPLETED,
        output_path="/workspace/output.jsonl",
        output_format="jsonl",
    )

    assert output.status is AgentOutputStatus.COMPLETED


def test_agent_output_rejects_invalid_status() -> None:
    with pytest.raises(ValidationError):
        AgentOutput.model_validate(
            {"status": "done", "output_path": "/workspace/output.jsonl", "output_format": "jsonl"}
        )


def test_agent_output_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        AgentOutput(
            status=AgentOutputStatus.COMPLETED,
            output_path="/workspace/output.jsonl",
            output_format="jsonl",
            surprise_field="oops",  # type: ignore[call-arg]
        )


def test_agent_output_rejects_blank_output_path() -> None:
    with pytest.raises(ValidationError):
        AgentOutput(
            status=AgentOutputStatus.COMPLETED,
            output_path="   ",
            output_format="jsonl",
        )


def test_agent_output_accepts_error_message_for_failed_status() -> None:
    output = AgentOutput(
        status=AgentOutputStatus.FAILED,
        output_path="/workspace/output.jsonl",
        output_format="jsonl",
        error_message="Agent timed out",
    )

    assert output.error_message == "Agent timed out"


def test_agent_output_roundtrip_serialization() -> None:
    original = AgentOutput(
        status=AgentOutputStatus.PARTIAL,
        output_path="/workspace/output.jsonl",
        output_format="jsonl",
        error_message="Truncated",
    )

    serialized = original.model_dump(mode="json")
    restored = AgentOutput.model_validate(serialized)

    assert restored == original
