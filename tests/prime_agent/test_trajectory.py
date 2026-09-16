# ABOUTME: Checks Prime session ancestry conversion against the installed version 3 session format.
# ABOUTME: Covers nested children, source timestamps, unknown call links, and invalid external references.

import json
from pathlib import Path

import pytest

from aec_bench.contracts.trajectory import read_trajectory
from aec_bench.harness.atif import to_atif
from aec_bench.prime_agent.session_evidence import PrimeSessionEvidenceError
from aec_bench.prime_agent.trajectory import prime_session_trajectory, write_prime_trajectory


def _session(directory: Path, identity: str, parent: Path | None = None, depth: int = 0) -> Path:
    path = directory / f"{identity}.jsonl"
    events = [
        {
            "type": "session",
            "version": 3,
            "id": identity,
            "rlmDepth": depth,
            "timestamp": "2026-09-15T01:00:00Z",
            **({"parentSession": str(parent)} if parent else {}),
        },
        {
            "type": "message",
            "id": f"{identity}-user",
            "timestamp": "2026-09-15T01:00:01Z",
            "message": {"role": "user", "content": "Check units"},
        },
        {
            "type": "message",
            "id": f"{identity}-assistant",
            "timestamp": "2026-09-15T01:00:02Z",
            "message": {
                "role": "assistant",
                "model": "test-model",
                "provider": "test-provider",
                "content": [
                    {"type": "thinking", "thinking": "Check the units.", "thinkingSignature": "opaque"},
                    {"type": "text", "text": f"Result from {identity}"},
                    {
                        "type": "toolCall",
                        "id": "same-call-id-per-session",
                        "name": "ipython",
                        "arguments": {"code": "1"},
                    },
                ],
                "usage": {"input": 10, "output": 5, "cacheRead": 2, "cacheWrite": 3},
                "stopReason": "toolUse",
            },
        },
        {
            "type": "message",
            "id": f"{identity}-tool",
            "timestamp": "2026-09-15T01:00:03Z",
            "message": {
                "role": "toolResult",
                "toolCallId": "same-call-id-per-session",
                "toolName": "ipython",
                "content": [{"type": "text", "text": "1"}],
                "isError": False,
            },
        },
    ]
    path.write_text("".join(json.dumps(event) + "\n" for event in events))
    return path


def test_prime_tree_preserves_explicit_ancestry_without_guessing_a_tool_call(tmp_path: Path) -> None:
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    root = _session(sessions, "root")
    first = _session(sessions, "first", root, 1)
    _session(sessions, "second", root, 1)
    _session(sessions, "grandchild", first, 2)
    raw = {path: path.read_bytes() for path in sessions.iterdir()}
    destination = tmp_path / "trajectory.jsonl"
    write_prime_trajectory(sessions, destination)
    entries = read_trajectory(destination)
    assert entries[0].timestamp == "2026-09-15T01:00:00Z"
    assert "opaque" not in destination.read_text()
    exported = to_atif(entries, agent_name="prime-agent", agent_version="0.7.0", session_id="root")
    assert exported.subagent_trajectories is not None
    assert [child.trajectory_id for child in exported.subagent_trajectories] == ["first", "second"]
    first_child = exported.subagent_trajectories[0]
    assert first_child.subagent_trajectories is not None
    assert first_child.subagent_trajectories[0].trajectory_id == "grandchild"
    assert first_child.agent.model_name == "test-model"
    assert first_child.steps[2].reasoning_content == "Check the units."
    assert first_child.steps[2].metrics is not None
    assert first_child.steps[2].metrics.prompt_tokens == 15
    assert first_child.steps[2].metrics.completion_tokens == 5
    assert first_child.steps[2].observation is not None
    assert first_child.steps[2].observation.results[0].source_call_id == "same-call-id-per-session"
    assert exported.steps[2].observation is not None
    assert exported.steps[2].observation.results[0].subagent_trajectory_ref is None
    assert {path: path.read_bytes() for path in sessions.iterdir()} == raw


@pytest.mark.parametrize("invalid", ["absent_parent", "same_depth_fork", "duplicate_id", "outside_symlink"])
def test_prime_rejects_unproven_or_invalid_child_relationships(tmp_path: Path, invalid: str) -> None:
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    root = _session(sessions, "root")
    if invalid == "absent_parent":
        _session(sessions, "child", tmp_path / "unread-external.jsonl", 1)
    elif invalid == "same_depth_fork":
        _session(sessions, "child", root, 0)
    elif invalid == "duplicate_id":
        (sessions / "copy.jsonl").write_bytes(root.read_bytes())
    else:
        outside = _session(tmp_path, "outside")
        (sessions / "linked.jsonl").symlink_to(outside)
    with pytest.raises(PrimeSessionEvidenceError):
        prime_session_trajectory(sessions)
    destination = tmp_path / "trajectory.jsonl"
    write_prime_trajectory(sessions, destination)
    assert not destination.exists()


def test_prime_empty_child_session_retains_identity_without_fake_output(tmp_path: Path) -> None:
    root = _session(tmp_path, "root")
    child = _session(tmp_path, "child", root, 1)
    child.write_text(child.read_text().splitlines()[0] + "\n")
    exported = to_atif(prime_session_trajectory(tmp_path), agent_name="prime-agent", agent_version="0.7.0")
    assert exported.subagent_trajectories is not None
    child_trace = exported.subagent_trajectories[0]
    assert child_trace.trajectory_id == "child"
    assert len(child_trace.steps) == 1
    assert child_trace.steps[0].message == ""
    assert child_trace.steps[0].llm_call_count is None
    assert child_trace.steps[0].extra is not None
    assert child_trace.steps[0].extra["aec_bench"]["session"]["session_id"] == "child"


def test_prime_spawn_evidence_links_siblings_and_nested_children_to_calls(tmp_path: Path) -> None:
    root = _session(tmp_path, "root")
    for identity, parent, depth, parent_id in (
        ("first", root, 1, "root"),
        ("second", root, 1, "root"),
        ("nested", tmp_path / "first/first.jsonl", 2, "first"),
    ):
        directory = tmp_path / identity
        directory.mkdir()
        _session(directory, identity, parent, depth)
        (directory / "aec-spawn.json").write_text(
            json.dumps(
                {
                    "parent_session_id": parent_id,
                    "parent_tool_call_id": "same-call-id-per-session",
                    "rlm_child_id": identity,
                }
            )
        )
    exported = to_atif(prime_session_trajectory(tmp_path), agent_name="prime-agent", agent_version="0.7.0")
    assert exported.steps[2].observation is not None
    refs = exported.steps[2].observation.results[0].subagent_trajectory_ref
    assert refs is not None
    assert [ref.trajectory_id for ref in refs] == ["first", "second"]
    assert exported.subagent_trajectories is not None
    nested_observation = exported.subagent_trajectories[0].steps[2].observation
    assert nested_observation is not None
    nested_refs = nested_observation.results[0].subagent_trajectory_ref
    assert nested_refs is not None
    assert [ref.trajectory_id for ref in nested_refs] == ["nested"]


@pytest.mark.parametrize("invalid", ["parent", "call", "child", "extra", "symlink"])
def test_prime_rejects_invalid_spawn_evidence(tmp_path: Path, invalid: str) -> None:
    root = _session(tmp_path, "root")
    child = tmp_path / "child"
    child.mkdir()
    _session(child, "child", root, 1)
    data = {"parent_session_id": "root", "parent_tool_call_id": "same-call-id-per-session", "rlm_child_id": "child"}
    if invalid == "parent":
        data["parent_session_id"] = "different-parent"
    elif invalid == "call":
        data["parent_tool_call_id"] = "absent-call"
    elif invalid == "child":
        data["rlm_child_id"] = "different-child"
    elif invalid == "extra":
        data["unknown"] = "field"
    path = child / "aec-spawn.json"
    if invalid == "symlink":
        path.symlink_to(root)
    else:
        path.write_text(json.dumps(data))
    with pytest.raises(PrimeSessionEvidenceError):
        prime_session_trajectory(tmp_path)
