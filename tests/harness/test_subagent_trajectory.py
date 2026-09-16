# ABOUTME: Checks native child isolation and valid embedded ATIF relationships.
# ABOUTME: Covers concurrent siblings, nesting, incomplete calls, and invalid ancestry.

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from pydantic import ValidationError

from aec_bench.contracts.trajectory import TrajectoryEntry, read_trajectory
from aec_bench.evaluation.behavioral import _parse_trajectory_to_turns
from aec_bench.harness.atif import to_atif
from aec_bench.trajectory.writer import TrajectoryWriter


def test_children_are_independent_and_preserve_parent_behavior(tmp_path: Path) -> None:
    source = tmp_path / "trajectory.jsonl"
    writer = TrajectoryWriter(str(source))
    writer.user("Check the design.")
    writer.new_step()
    writer.assistant("Request checks.")
    for call_id in ("a", "b"):
        writer.tool_call("advisor", "", tool_call_id=call_id)
    before = _parse_trajectory_to_turns(source)

    def run_child(call_id: str) -> None:
        child = writer.subagent(parent_tool_call_id=call_id, agent_name="advisor", model_name="child-model")
        child.user(f"Check {call_id}.")
        child.new_step()
        child.tool_call("verify", "", tool_call_id="grandchild-call")
        grandchild = child.subagent(
            parent_tool_call_id="grandchild-call", agent_name="verifier", model_name="verify-model"
        )
        grandchild.user("Verify the units.")
        grandchild.new_step()
        grandchild.assistant("Units match.")
        grandchild.close()
        child.tool_result("verify", "Verified.", tool_call_id="grandchild-call")
        child.assistant(f"Checked {call_id}.")
        child.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(run_child, ("a", "b")))
    assert _parse_trajectory_to_turns(source) == before
    preview = to_atif(read_trajectory(source), agent_name="tool_loop", agent_version="1", session_id="run")
    assert preview.subagent_trajectories is not None
    assert len(preview.subagent_trajectories) == 2
    assert len({child.trajectory_id for child in preview.subagent_trajectories}) == 2
    observation = preview.steps[-1].observation
    assert observation is not None
    assert all(result.content is None for result in observation.results)
    for result, child in zip(observation.results, preview.subagent_trajectories, strict=True):
        assert result.subagent_trajectory_ref is not None
        assert result.subagent_trajectory_ref[0].trajectory_id == child.trajectory_id
        assert child.steps[0].message == f"Check {result.source_call_id}."
        assert child.session_id == "run"
        assert child.subagent_trajectories is not None
        assert child.subagent_trajectories[0].agent.name == "verifier"

    # A later parent step does not prevent explicit call/result association.
    writer.new_step()
    writer.assistant("Checks returned.")
    for call_id in ("b", "a"):
        writer.tool_result("advisor", f"Result {call_id}.", tool_call_id=call_id)
    writer.close()
    final = to_atif(read_trajectory(source), agent_name="tool_loop", agent_version="1")
    observation = final.steps[1].observation
    assert observation is not None
    assert len(observation.results) == 2
    assert {result.content for result in observation.results} == {"Result a.", "Result b."}


@pytest.mark.parametrize("invalid", ["missing_parent", "changed_identity"])
def test_invalid_child_attribution_is_rejected(tmp_path: Path, invalid: str) -> None:
    source = tmp_path / "trajectory.jsonl"
    writer = TrajectoryWriter(str(source))
    writer.new_step()
    writer.tool_call("advisor", "", tool_call_id="a")
    child = writer.subagent(parent_tool_call_id="a", agent_name="advisor", model_name="model")
    child.user("Question")
    child.new_step()
    child.assistant("Answer")
    writer.close()
    entries = read_trajectory(source)
    assert entries[-1].subagent is not None
    if invalid == "missing_parent":
        entries = entries[1:]
    else:
        assert entries[-1].subagent is not None
        entries[-1].subagent.agent_name = "different"
    with pytest.raises(ValueError, match="unknown parent|conflicting subagent"):
        to_atif(entries, agent_name="root", agent_version="1")


def test_child_payload_is_required_and_cannot_label_parent_text() -> None:
    with pytest.raises(ValidationError, match="subagent payload"):
        TrajectoryEntry(step=1, role="subagent")
    with pytest.raises(ValidationError, match="subagent payload"):
        TrajectoryEntry.model_validate(
            {
                "step": 1,
                "role": "assistant",
                "subagent": {
                    "trajectory_id": "child",
                    "agent_name": "advisor",
                    "entry": {"step": 0, "role": "user", "content": "question"},
                },
            }
        )
