# ABOUTME: Tests LLM-driven behavioral trace loading, classification, and scoring.
# ABOUTME: Covers Harbor imports and canonical transcript artifact adaptation.

import json
import re
import tempfile
from pathlib import Path

import pytest

from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.trial_record import OutputRecord
from aec_bench.evaluation.behavioral import (
    BehavioralClassificationError,
    BehavioralTraceError,
    BondType,
    ClassifiedTrace,
    LLMTurnClassifier,
    TurnClassification,
    build_ideal_pattern,
    build_transition_matrix,
    load_behavioral_trace,
    score_trace_structural,
)
from aec_bench.harness.harbor_import import import_harbor_trial
from tests.support.trial_record_factories import make_trial_record

REPO_ROOT = Path(__file__).resolve().parents[2]
HARBOR_TRIAL_DIR = REPO_ROOT / "jobs" / "2026-03-04__17-57-43" / "brisbane-8rm__BHVuXg2"

_skip_no_job_data = pytest.mark.skipif(
    not HARBOR_TRIAL_DIR.exists(),
    reason="requires archived Harbor job data in jobs/",
)


class StubBehavioralLLMClient:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def complete(
        self,
        prompt: str,
        *,
        temperature: float = 0.0,
        max_tokens: int = 4000,
    ) -> str:
        del temperature
        del max_tokens
        self.prompts.append(prompt)
        indices_match = re.search(r"Classify turns:\s*([\d,\s]+)$", prompt, re.MULTILINE)
        assert indices_match is not None
        indices = [int(raw.strip()) for raw in indices_match.group(1).split(",")]

        classifications: list[dict[str, object]] = []
        for index in indices:
            block_match = re.search(rf"--- Turn {index} .*?(?=--- Turn|\Z)", prompt, re.DOTALL)
            block = block_match.group(0).lower() if block_match is not None else ""
            if "verify" in block or "check" in block:
                bond_type = "verification"
            elif "perhaps" in block or "consider" in block:
                bond_type = "exploration"
            else:
                bond_type = "execution"
            classifications.append(
                {
                    "turn_index": index,
                    "bond_type": bond_type,
                    "confidence": 0.9,
                    "rationale": f"classified as {bond_type}",
                }
            )
        return json.dumps({"classifications": classifications})


class MalformedBehavioralLLMClient:
    def complete(
        self,
        prompt: str,
        *,
        temperature: float = 0.0,
        max_tokens: int = 4000,
    ) -> str:
        del prompt
        del temperature
        del max_tokens
        return "not-json"


class PartialBehavioralLLMClient:
    def complete(
        self,
        prompt: str,
        *,
        temperature: float = 0.0,
        max_tokens: int = 4000,
    ) -> str:
        del temperature
        del max_tokens
        indices_match = re.search(r"Classify turns:\s*([\d,\s]+)$", prompt, re.MULTILINE)
        assert indices_match is not None
        first_index = int(indices_match.group(1).split(",")[0].strip())
        return json.dumps(
            {
                "classifications": [
                    {
                        "turn_index": first_index,
                        "bond_type": "execution",
                        "confidence": 0.9,
                        "rationale": "partial response",
                    }
                ]
            }
        )


@_skip_no_job_data
def test_load_behavioral_trace_from_real_harbor_record() -> None:
    record = import_harbor_trial(trial_dir=HARBOR_TRIAL_DIR, repo_root=REPO_ROOT)

    trace = load_behavioral_trace(record)

    assert trace.trace_id == record.trial_id
    assert trace.model_name == record.agent.model
    assert trace.metadata["reward"] == record.evaluation.reward
    assistant_turns = [turn for turn in trace.turns if turn.role == "assistant"]
    assert assistant_turns
    assert any(turn.tool_calls for turn in assistant_turns)


def test_load_behavioral_trace_from_canonical_transcript_artifact(tmp_path: Path) -> None:
    conversation_path = tmp_path / "conversation.jsonl"
    conversation_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "role": "system",
                        "content": "Use tools carefully.",
                        "event": "message",
                    }
                ),
                json.dumps(
                    {
                        "role": "user",
                        "content": "Review the drawing.",
                        "event": "message",
                    }
                ),
                json.dumps(
                    {
                        "role": "assistant",
                        "content": "Calling bash.",
                        "event": "tool_call",
                        "tool_name": "bash",
                        "tool_call_id": "call-1",
                    }
                ),
                json.dumps(
                    {
                        "role": "tool",
                        "content": "found output.jsonl",
                        "event": "tool_result",
                        "tool_name": "bash",
                        "tool_call_id": "call-1",
                    }
                ),
                json.dumps(
                    {
                        "role": "assistant",
                        "content": "Verify the result.",
                        "event": "message",
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    record = make_trial_record(
        outputs=OutputRecord(
            agent_output=AgentOutput(
                status=AgentOutputStatus.COMPLETED,
                output_path="/workspace/output.jsonl",
                output_format="jsonl",
            ),
            raw_output_path="/workspace/output.jsonl",
            conversation_path=conversation_path.as_posix(),
            agent_result={"turns_used": 2, "max_turns": 6},
        )
    )

    trace = load_behavioral_trace(record)

    assert [turn.role for turn in trace.turns] == ["system", "user", "assistant", "assistant"]
    assert trace.turns[2].tool_calls[0].tool_name == "bash"
    assert trace.turns[2].tool_results[0].output == "found output.jsonl"
    assert trace.metadata["turns_used"] == 2


def test_load_behavioral_trace_requires_conversation_artifact() -> None:
    record = make_trial_record(outputs=OutputRecord(conversation_path=None, agent_result={}))

    with pytest.raises(BehavioralTraceError, match="conversation artifact"):
        load_behavioral_trace(record)


def test_load_behavioral_trace_from_trajectory(tmp_path: Path) -> None:
    trajectory_path = tmp_path / "trajectory.jsonl"
    trajectory_path.write_text(
        '{"version": 1, "format": "aec-bench-trajectory"}\n'
        '{"step": 0, "role": "user", "content": "Calculate voltage drop"}\n'
        '{"step": 1, "role": "assistant", "content": "I will calculate using AS3008."}\n'
        '{"step": 1, "role": "tool_call", "tool_name": "bash", "command": "python3 calc.py"}\n'
        '{"step": 1, "role": "tool_result", "tool_name": "bash",'
        ' "stdout": "result: 3.2", "exit_code": 0}\n'
        '{"step": 2, "role": "assistant", "content": "Writing output."}\n',
        encoding="utf-8",
    )

    record = make_trial_record(
        outputs=OutputRecord(
            agent_output=AgentOutput(
                status=AgentOutputStatus.COMPLETED,
                output_path="/workspace/output.md",
                output_format="md",
            ),
            conversation_path=None,
            trajectory_path=str(trajectory_path),
        )
    )

    trace = load_behavioral_trace(record)

    user_turns = [t for t in trace.turns if t.role == "user"]
    assert len(user_turns) == 1
    assert user_turns[0].content == "Calculate voltage drop"

    assistant_turns = [t for t in trace.turns if t.role == "assistant"]
    assert len(assistant_turns) == 2

    # First assistant turn has tool calls and tool results
    assert len(assistant_turns[0].tool_calls) == 1
    assert assistant_turns[0].tool_calls[0].tool_name == "bash"
    assert len(assistant_turns[0].tool_results) == 1
    assert assistant_turns[0].tool_results[0].output == "result: 3.2"
    assert assistant_turns[0].tool_results[0].is_error is False

    # Second assistant turn has no tool calls
    assert len(assistant_turns[1].tool_calls) == 0
    assert assistant_turns[1].content == "Writing output."


def test_load_behavioral_trace_trajectory_fallback(tmp_path: Path) -> None:
    """When trajectory_path points to a nonexistent file, falls back to conversation.jsonl."""
    record = make_trial_record(
        outputs=OutputRecord(
            agent_output=AgentOutput(
                status=AgentOutputStatus.COMPLETED,
                output_path="/workspace/output.md",
                output_format="md",
            ),
            conversation_path=None,
            trajectory_path=str(tmp_path / "nonexistent.jsonl"),
        )
    )

    # conversation_path is also None, so should raise BehavioralTraceError
    with pytest.raises(BehavioralTraceError):
        load_behavioral_trace(record)


def test_llm_turn_classifier_batches_assistant_turns() -> None:
    client = StubBehavioralLLMClient()
    classifier = LLMTurnClassifier(client=client, batch_size=2)
    trace = load_behavioral_trace(
        make_trial_record(
            outputs=OutputRecord(
                agent_output=AgentOutput(
                    status=AgentOutputStatus.COMPLETED,
                    output_path="/workspace/output.jsonl",
                    output_format="jsonl",
                ),
                raw_output_path="/workspace/output.jsonl",
                conversation_path=_write_trace_fixture(
                    [
                        {"role": "user", "content": "Solve the task.", "event": "message"},
                        {
                            "role": "assistant",
                            "content": "Running the calculation now.",
                            "event": "message",
                        },
                        {
                            "role": "assistant",
                            "content": "Verify the answer against the schedule.",
                            "event": "message",
                        },
                        {
                            "role": "assistant",
                            "content": "Perhaps compare an alternate interpretation.",
                            "event": "message",
                        },
                    ]
                ),
                agent_result={},
            )
        )
    )

    classified = classifier.classify_trace(trace)

    assert [item.bond_type for item in classified.classifications] == [
        BondType.EXECUTION,
        BondType.VERIFICATION,
        BondType.EXPLORATION,
    ]
    assert len(client.prompts) == 2


def test_llm_turn_classifier_rejects_malformed_llm_output() -> None:
    classifier = LLMTurnClassifier(client=MalformedBehavioralLLMClient())
    trace = load_behavioral_trace(
        make_trial_record(
            outputs=OutputRecord(
                agent_output=AgentOutput(
                    status=AgentOutputStatus.COMPLETED,
                    output_path="/workspace/output.jsonl",
                    output_format="jsonl",
                ),
                raw_output_path="/workspace/output.jsonl",
                conversation_path=_write_trace_fixture(
                    [
                        {"role": "user", "content": "Solve the task.", "event": "message"},
                        {
                            "role": "assistant",
                            "content": "Running the calculation now.",
                            "event": "message",
                        },
                    ]
                ),
                agent_result={},
            )
        )
    )

    with pytest.raises(BehavioralClassificationError, match="Failed to parse LLM response"):
        classifier.classify_trace(trace)


def test_llm_turn_classifier_rejects_partial_llm_output() -> None:
    classifier = LLMTurnClassifier(client=PartialBehavioralLLMClient(), batch_size=2)
    trace = load_behavioral_trace(
        make_trial_record(
            outputs=OutputRecord(
                agent_output=AgentOutput(
                    status=AgentOutputStatus.COMPLETED,
                    output_path="/workspace/output.jsonl",
                    output_format="jsonl",
                ),
                raw_output_path="/workspace/output.jsonl",
                conversation_path=_write_trace_fixture(
                    [
                        {"role": "user", "content": "Solve the task.", "event": "message"},
                        {
                            "role": "assistant",
                            "content": "Running the calculation now.",
                            "event": "message",
                        },
                        {
                            "role": "assistant",
                            "content": "Verify the answer.",
                            "event": "message",
                        },
                    ]
                ),
                agent_result={},
            )
        )
    )

    with pytest.raises(BehavioralClassificationError, match="LLM did not classify this turn"):
        classifier.classify_trace(trace)


def test_transition_matrix_and_structural_score_follow_successful_patterns() -> None:
    classified_a = ClassifiedTrace(
        trace_id="trial-a",
        model_name="claude",
        classifications=(
            TurnClassification(turn_index=1, bond_type=BondType.EXECUTION, confidence=0.9),
            TurnClassification(turn_index=2, bond_type=BondType.VERIFICATION, confidence=0.9),
            TurnClassification(turn_index=3, bond_type=BondType.EXECUTION, confidence=0.9),
        ),
        metadata={"reward": 1.0},
    )
    classified_b = ClassifiedTrace(
        trace_id="trial-b",
        model_name="claude",
        classifications=(
            TurnClassification(turn_index=1, bond_type=BondType.EXECUTION, confidence=0.8),
            TurnClassification(turn_index=2, bond_type=BondType.VERIFICATION, confidence=0.8),
            TurnClassification(turn_index=3, bond_type=BondType.EXECUTION, confidence=0.8),
        ),
        metadata={"reward": 1.0},
    )
    classified_c = ClassifiedTrace(
        trace_id="trial-c",
        model_name="claude",
        classifications=(
            TurnClassification(turn_index=1, bond_type=BondType.EXPLORATION, confidence=0.7),
            TurnClassification(turn_index=2, bond_type=BondType.EXECUTION, confidence=0.7),
        ),
        metadata={"reward": 0.0},
    )

    ideal = build_ideal_pattern([classified_a, classified_b, classified_c], reward_key="reward")
    trace_matrix = build_transition_matrix(classified_a)
    score = score_trace_structural(
        classified_a,
        ideal_matrix=ideal,
        ideal_sequence=[BondType.EXECUTION, BondType.VERIFICATION, BondType.EXECUTION],
        reward=1.0,
    )

    assert trace_matrix.labels == tuple(bond.value for bond in BondType)
    assert ideal.sample_count == 6
    assert score.trace_id == "trial-a"
    assert score.cosine_similarity == pytest.approx(1.0)
    assert score.edit_distance == 0
    assert score.normalized_edit_distance == pytest.approx(0.0)


def _write_trace_fixture(entries: list[dict[str, object]]) -> str:
    fixture_dir = Path(tempfile.mkdtemp(prefix="behavioral-trace-"))
    conversation_path = fixture_dir / "conversation.jsonl"
    conversation_path.write_text(
        "\n".join(json.dumps(entry) for entry in entries),
        encoding="utf-8",
    )
    return conversation_path.as_posix()
