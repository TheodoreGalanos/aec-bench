# ABOUTME: Tests deterministic reduction of raw DeepSeek Harness notifications.
# ABOUTME: Pins model-step, transcript, usage, and idle semantics from the qualified SDK event trace.

import json
from pathlib import Path

from aec_bench.adapters.deepseek_harness.events import reduce_deepseek_notifications
from aec_bench.contracts.adapter_execution import TranscriptEvent, TranscriptRole


def _notifications() -> list[dict[str, object]]:
    fixture = Path(__file__).parent / "fixtures" / "text_turn_notifications.jsonl"
    return [json.loads(line) for line in fixture.read_text(encoding="utf-8").splitlines()]


def test_reducer_counts_root_model_steps_and_keeps_root_transcript() -> None:
    projection = reduce_deepseek_notifications("root-session", _notifications())

    assert projection.root_model_calls == 1
    assert projection.root_steps == 1
    assert projection.root_turns == 1
    assert projection.last_turn_end_reason == "completed"
    assert projection.idle_seen is True
    assert projection.final_response == "SDK snapshot OK"
    assert projection.usage_input_tokens == 1769
    assert projection.usage_output_tokens == 24
    assert projection.usage_cache_read_tokens == 0
    assert projection.maximum_input_tokens_in_one_call == 1769
    assert projection.maximum_output_tokens_in_one_call == 24
    assert len(projection.transcript) == 1
    assert projection.transcript[0].role is TranscriptRole.ASSISTANT
    assert projection.transcript[0].event is TranscriptEvent.MESSAGE
    assert projection.transcript[0].content == "SDK snapshot OK"


def test_reducer_diagnoses_unknown_events_without_failing() -> None:
    notifications = _notifications()
    notifications.insert(
        -1,
        {
            "method": "session.event",
            "params": {
                "sessionId": "root-session",
                "event": {"type": "future/event", "seq": 40, "time": 1785730505711, "data": {"value": 1}},
            },
        },
    )

    projection = reduce_deepseek_notifications("root-session", notifications)

    assert projection.unknown_event_types == ("future/event",)


def test_reducer_does_not_flatten_child_session_messages() -> None:
    notifications = _notifications()
    notifications.insert(
        -1,
        {
            "method": "session.event",
            "params": {
                "sessionId": "child-session",
                "event": {
                    "type": "assistant/message",
                    "seq": 1,
                    "time": 1785730505711,
                    "data": {
                        "turn": 1,
                        "step": 1,
                        "message": {"role": "assistant", "content": [{"type": "text", "text": "Child text"}]},
                    },
                },
            },
        },
    )

    projection = reduce_deepseek_notifications("root-session", notifications)

    assert [entry.content for entry in projection.transcript] == ["SDK snapshot OK"]
    assert projection.child_session_ids == ("child-session",)
