# ABOUTME: Verifies ATIF export preserves ordered AEC-Bench interactions and tool evidence.
# ABOUTME: Checks upstream validation, explicit call linkage, ambiguous results, and atomic export.

from pathlib import Path

import pytest
from harbor.models.trajectories.trajectory import Trajectory

from aec_bench.contracts.trajectory import TrajectoryEntry
from aec_bench.harness.atif import export_atif, to_atif


def test_atif_groups_calls_and_results_without_losing_domain_metadata() -> None:
    entries = [
        TrajectoryEntry(step=0, role="system", content="Use the supplied evidence."),
        TrajectoryEntry(step=0, role="user", content="Size a cable."),
        TrajectoryEntry(step=1, role="assistant", content="Read the table.", call_type="main"),
        TrajectoryEntry(
            step=1,
            role="tool_call",
            tool_name="bash",
            command="cat table.csv",
            arguments={"command": "cat table.csv"},
            tool_call_id="call-1",
            call_type="main",
        ),
        TrajectoryEntry(
            step=1,
            role="tool_result",
            tool_name="bash",
            stdout="25 mm²",
            stderr="warning",
            exit_code=1,
            duration_ms=42,
            tool_call_id="call-1",
            call_type="main",
            metadata={"template_progress": {"checked": True}},
        ),
        TrajectoryEntry(step=2, role="assistant", content="Check the warning."),
    ]
    trajectory = to_atif(entries, agent_name="tool_loop", agent_version="0.1.0", model_name="model-a")
    validated = Trajectory.model_validate(trajectory.to_json_dict())
    assert [step.source for step in validated.steps] == ["system", "user", "agent", "agent"]
    step = validated.steps[2]
    assert step.tool_calls is not None and step.observation is not None
    assert step.tool_calls[0].arguments == {"command": "cat table.csv"}
    result = step.observation.results[0]
    assert result.source_call_id == "call-1"
    assert result.extra is not None
    assert result.extra["aec_bench"]["exit_code"] == 1
    assert result.extra["aec_bench"]["duration_ms"] == 42
    assert result.extra["aec_bench"]["metadata"] == {"template_progress": {"checked": True}}
    assert validated.final_metrics is None
    assert step.reasoning_content is None


def test_atif_does_not_guess_between_calls_to_the_same_tool() -> None:
    entries = [
        TrajectoryEntry(step=1, role="tool_call", tool_name="bash", command="one"),
        TrajectoryEntry(step=1, role="tool_call", tool_name="bash", command="two"),
        TrajectoryEntry(step=1, role="tool_result", tool_name="bash", stdout="unattributed"),
    ]
    trajectory = to_atif(entries, agent_name="rlm", agent_version="1")
    assert trajectory.steps[0].observation is not None
    assert trajectory.steps[0].observation.results[0].source_call_id is None


def test_atif_preserves_file_order_when_step_numbers_restart() -> None:
    entries = [
        TrajectoryEntry(step=2, role="assistant", content="Parent", call_type="main"),
        TrajectoryEntry(step=1, role="assistant", content="Child", call_type="subagent"),
        TrajectoryEntry(step=2, role="assistant", content="Parent again", call_type="main"),
    ]
    trajectory = to_atif(entries, agent_name="rlm", agent_version="1")
    assert [step.message for step in trajectory.steps] == ["Parent", "Child", "Parent again"]
    assert [step.step_id for step in trajectory.steps] == [1, 2, 3]
    assert trajectory.subagent_trajectories is None


def test_atif_export_leaves_source_unchanged_and_validates_output(tmp_path: Path) -> None:
    source = tmp_path / "trajectory.jsonl"
    original = b'{"step":0,"role":"user","content":"Size a cable."}\n'
    source.write_bytes(original)
    destination = tmp_path / "trajectory.json"
    export_atif(source, destination, agent_name="tool_loop", agent_version="1", session_id="run-1")
    assert source.read_bytes() == original
    assert Trajectory.model_validate_json(destination.read_text()).session_id == "run-1"
    with pytest.raises(ValueError, match="different"):
        export_atif(source, source, agent_name="tool_loop", agent_version="1")


@pytest.mark.parametrize("entries", [[], [TrajectoryEntry(step=1, role="unknown")]])
def test_atif_rejects_unrepresentable_input(entries: list[TrajectoryEntry]) -> None:
    with pytest.raises(ValueError):
        to_atif(entries, agent_name="test", agent_version="1")


def test_atif_rejects_duplicate_model_response_records() -> None:
    from aec_bench.contracts.trajectory import TrajectoryModelResponse, TrajectoryUsage

    entry = TrajectoryEntry(
        step=1,
        role="model_response",
        model_response=TrajectoryModelResponse(source="pydantic_ai", usage=TrajectoryUsage(input_tokens=10)),
    )
    with pytest.raises(ValueError, match="two model_response records"):
        to_atif([entry, entry], agent_name="tool_loop", agent_version="1")
