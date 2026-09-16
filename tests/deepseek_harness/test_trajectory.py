# ABOUTME: Tests native DeepSeek notification projection into child trajectories.
# ABOUTME: Checks explicit ancestry, observed reasoning and usage, and missing-link handling.

import json
from pathlib import Path
from typing import Any

import pytest

from aec_bench.adapters.deepseek_harness.trajectory import deepseek_trajectory, write_deepseek_trajectory


def _event(session: str, kind: str, data: dict[str, Any]) -> dict[str, Any]:
    return {"method": "session.event", "params": {"sessionId": session, "event": {"type": kind, "data": data}}}


def _tree(*, linked: bool = True) -> list[dict[str, Any]]:
    records = [
        _event("root", "step/start", {"step": 1}),
        _event("root", "tool/call", {"name": "subagent", "callId": "spawn", "arguments": "{}"}),
        {"method": "subagent.started", "params": {"parentSessionId": "root", "childSessionId": "child"}},
        _event("child", "step/start", {"step": 1}),
        _event(
            "child",
            "assistant/message",
            {
                "message": {
                    "id": "answer",
                    "source": {"model": "deepseek", "provider": "deepseek-official"},
                    "content": [
                        {"type": "reasoning", "text": "Exposed reasoning"},
                        {"type": "text", "text": "Child answer"},
                    ],
                },
                "usage": {
                    "inputTokens": 6,
                    "outputTokens": 9,
                    "cacheReadTokens": 2,
                    "cacheWriteTokens": 1,
                    "reasoningTokens": 5,
                },
            },
        ),
        _event(
            "root",
            "tool/result",
            {
                "message": {
                    "content": [
                        {
                            "type": "tool-result",
                            "toolCallId": "spawn",
                            "content": [{"type": "text", "text": "Child answer"}],
                        }
                    ]
                }
            },
        ),
    ]
    if linked:
        records.insert(
            3, _event("root", "aec/subagent-spawn", {"child_session_id": "child", "parent_tool_call_id": "spawn"})
        )
    return records


def test_trajectory_preserves_response_and_explicit_atif_child_link() -> None:
    entries = deepseek_trajectory("root", _tree())
    child_entries = [entry.subagent.entry for entry in entries if entry.subagent]
    response = next(entry.model_response for entry in child_entries if entry.model_response)
    assert response.response_id is None
    assert next(entry.metadata for entry in child_entries if entry.model_response) == {"deepseek_message_id": "answer"}
    assert response.usage is not None
    assert response.usage.cache_write_tokens == 1
    assert response.usage.details == {"reasoningTokens": 5}
    assert next(entry.reasoning.content for entry in child_entries if entry.reasoning) == "Exposed reasoning"
    assert all(entry.timestamp is None for entry in entries)
    pytest.importorskip("harbor")
    from aec_bench.harness.atif import to_atif

    trace = to_atif(entries, agent_name="deepseek_harness", agent_version="test")
    assert trace.subagent_trajectories is not None
    child = trace.subagent_trajectories[0]
    observation = next(step.observation for step in trace.steps if step.observation)
    assert observation.results[0].source_call_id == "spawn"
    assert observation.results[0].subagent_trajectory_ref is not None
    assert observation.results[0].subagent_trajectory_ref[0].trajectory_id == child.trajectory_id
    assert child.trajectory_id == "child"


def test_unobserved_parent_call_is_not_inferred() -> None:
    entries = deepseek_trajectory("root", _tree(linked=False))
    assert all(entry.subagent.parent_tool_call_id is None for entry in entries if entry.subagent)


@pytest.mark.parametrize("invalid", ["call", "parent", "duplicate", "cycle"])
def test_invalid_lineage_is_rejected(invalid: str) -> None:
    records = _tree()
    if invalid == "call":
        records[3]["params"]["event"]["data"]["parent_tool_call_id"] = "absent"
    elif invalid == "parent":
        records[2]["params"]["parentSessionId"] = "absent"
    elif invalid == "duplicate":
        records.append(records[2])
    else:
        records = _tree(linked=False)
        records[2]["params"]["parentSessionId"] = "child"
    with pytest.raises(ValueError):
        deepseek_trajectory("root", records)


def test_failed_projection_keeps_existing_trace_and_raw_evidence(tmp_path: Path) -> None:
    source = _tree()
    source[3]["params"]["event"]["data"]["parent_tool_call_id"] = "absent"
    raw = json.dumps(source)
    destination = tmp_path / "trajectory.jsonl"
    destination.write_text("previous trace\n")
    write_deepseek_trajectory("root", source, destination)
    assert destination.read_text() == "previous trace\n"
    assert json.dumps(source) == raw


def test_absent_usage_does_not_become_zero_in_trajectory() -> None:
    records = _tree()
    del records[5]["params"]["event"]["data"]["usage"]
    entries = deepseek_trajectory("root", records)
    response = next(
        entry.subagent.entry.model_response
        for entry in entries
        if entry.subagent and entry.subagent.entry.model_response
    )
    assert response.usage is None
