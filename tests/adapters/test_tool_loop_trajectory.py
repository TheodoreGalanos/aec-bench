# ABOUTME: Tests for the tool_loop adapter's pydantic-ai → TrajectoryWriter emitter.
# ABOUTME: Verifies emitted entries round-trip through the behavioral trace parser.

from __future__ import annotations

from pathlib import Path

from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from aec_bench.evaluation.behavioral import _parse_trajectory_to_turns
from aec_bench.trajectory.writer import TrajectoryWriter


def _build_messages() -> list[ModelRequest | ModelResponse]:
    """Construct a realistic pydantic-ai message sequence for one trial.

    Sequence: system/user → assistant calls bash → tool returns → assistant text.
    """
    return [
        ModelRequest(
            parts=[
                SystemPromptPart(content="You are an expert engineer."),
                UserPromptPart(content="Size a cable for 60 A over 20 m."),
            ]
        ),
        ModelResponse(
            parts=[
                TextPart(content="I'll check the cable tables first."),
                ToolCallPart(
                    tool_name="bash",
                    args={"command": "cat cable_tables.csv | head"},
                    tool_call_id="call-1",
                ),
            ]
        ),
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="bash",
                    content="25mm2 Cu: 0.9 mV/A/m",
                    tool_call_id="call-1",
                )
            ]
        ),
        ModelResponse(
            parts=[
                TextPart(content="Final answer: 25mm² copper."),
            ]
        ),
    ]


class TestEmitPydanticAiMessagesToTrajectory:
    def test_round_trip_produces_assistant_turns(self, tmp_path: Path) -> None:
        from aec_bench.adapters.tool_loop_local import (
            emit_pydantic_ai_messages_to_trajectory,
        )

        traj_path = tmp_path / "trajectory.jsonl"
        writer = TrajectoryWriter(path=str(traj_path))
        try:
            emit_pydantic_ai_messages_to_trajectory(_build_messages(), writer)
        finally:
            writer.close()

        turns = _parse_trajectory_to_turns(traj_path)
        assistant_turns = [t for t in turns if t.role == "assistant"]
        assert len(assistant_turns) == 2
        assert "I'll check" in assistant_turns[0].content

    def test_emits_tool_calls_with_arguments(self, tmp_path: Path) -> None:
        from aec_bench.adapters.tool_loop_local import (
            emit_pydantic_ai_messages_to_trajectory,
        )

        traj_path = tmp_path / "trajectory.jsonl"
        writer = TrajectoryWriter(path=str(traj_path))
        try:
            emit_pydantic_ai_messages_to_trajectory(_build_messages(), writer)
        finally:
            writer.close()

        turns = _parse_trajectory_to_turns(traj_path)
        first_assistant = next(t for t in turns if t.role == "assistant")
        tool_names = [tc.tool_name for tc in first_assistant.tool_calls]
        assert "bash" in tool_names

    def test_emits_tool_results_into_same_step(self, tmp_path: Path) -> None:
        from aec_bench.adapters.tool_loop_local import (
            emit_pydantic_ai_messages_to_trajectory,
        )

        traj_path = tmp_path / "trajectory.jsonl"
        writer = TrajectoryWriter(path=str(traj_path))
        try:
            emit_pydantic_ai_messages_to_trajectory(_build_messages(), writer)
        finally:
            writer.close()

        turns = _parse_trajectory_to_turns(traj_path)
        first_assistant = next(t for t in turns if t.role == "assistant")
        outputs = [tr.output for tr in first_assistant.tool_results]
        assert any("0.9 mV/A/m" in output for output in outputs)

    def test_emits_system_and_user_at_step_zero(self, tmp_path: Path) -> None:
        from aec_bench.adapters.tool_loop_local import (
            emit_pydantic_ai_messages_to_trajectory,
        )

        traj_path = tmp_path / "trajectory.jsonl"
        writer = TrajectoryWriter(path=str(traj_path))
        try:
            emit_pydantic_ai_messages_to_trajectory(_build_messages(), writer)
        finally:
            writer.close()

        turns = _parse_trajectory_to_turns(traj_path)
        roles = [t.role for t in turns]
        assert roles[0] == "system"
        assert roles[1] == "user"
