# ABOUTME: Checks capture of provider-exposed reasoning and normalised per-response usage.
# ABOUTME: Proves opaque data is not exported and ordinary assistant text keeps its meaning.

from pathlib import Path

from pydantic_ai.messages import ModelResponse, TextPart, ThinkingPart
from pydantic_ai.usage import RequestUsage

from aec_bench.adapters.tool_loop_local import emit_pydantic_ai_messages_to_trajectory
from aec_bench.contracts.trajectory import read_trajectory
from aec_bench.evaluation.behavioral import _parse_trajectory_to_turns
from aec_bench.harness.atif import to_atif
from aec_bench.trajectory.writer import TrajectoryWriter


def test_opaque_reasoning_is_recorded_without_exposing_its_payload(tmp_path: Path) -> None:
    source = tmp_path / "trajectory.jsonl"
    thinking = ThinkingPart(
        content="", id="redacted_thinking", signature="opaque-test-payload", provider_name="anthropic"
    )
    writer = TrajectoryWriter(str(source))
    try:
        emit_pydantic_ai_messages_to_trajectory(
            [
                ModelResponse(parts=[thinking, TextPart("The result is 25 mm2.")]),
            ],
            writer,
        )
    finally:
        writer.close()

    entries = read_trajectory(source)
    assert entries[0].model_response is not None
    assert entries[0].model_response.usage is None
    assert entries[1].reasoning is not None
    assert entries[1].reasoning.has_signature is True
    assert "opaque-test-payload" not in source.read_text()
    assert thinking.signature == "opaque-test-payload"

    trajectory = to_atif(entries, agent_name="tool_loop", agent_version="1")
    step = trajectory.steps[0]
    assert step.message == "The result is 25 mm2."
    assert step.reasoning_content is None
    assert step.metrics is None
    assert step.llm_call_count == 1
    assert "opaque-test-payload" not in trajectory.model_dump_json()
    assert _parse_trajectory_to_turns(source)[0].content == "The result is 25 mm2."


def test_reasoning_text_and_token_details_have_distinct_atif_fields(tmp_path: Path) -> None:
    source = tmp_path / "trajectory.jsonl"
    writer = TrajectoryWriter(str(source))
    try:
        emit_pydantic_ai_messages_to_trajectory(
            [
                ModelResponse(
                    parts=[
                        ThinkingPart(content="Check the units.", provider_name="openai"),
                        TextPart("I think the result needs a unit check."),
                    ],
                    usage=RequestUsage(
                        input_tokens=200, output_tokens=100, cache_write_tokens=50, details={"reasoning_tokens": 60}
                    ),
                    model_name="reported-model",
                    provider_name="openai",
                    provider_response_id="response-1",
                ),
            ],
            writer,
        )
    finally:
        writer.close()

    trajectory = to_atif(read_trajectory(source), agent_name="tool_loop", agent_version="1")
    step = trajectory.steps[0]
    assert step.reasoning_content == "Check the units."
    assert step.message == "I think the result needs a unit check."
    assert step.model_name == "reported-model"
    assert step.extra is not None
    assert step.extra["aec_bench"]["model_response"]["response_id"] == "response-1"
    assert step.metrics is not None and step.metrics.extra is not None
    assert step.metrics.prompt_tokens == 200
    assert step.metrics.completion_tokens == 100
    assert step.metrics.cached_tokens is None
    assert step.metrics.cost_usd is None
    assert step.metrics.extra["aec_bench"]["cache_write_tokens"] == 50
    assert step.metrics.extra["aec_bench"]["details"]["reasoning_tokens"] == 60
    assert trajectory.final_metrics is None
