# ABOUTME: Tests for the tool_loop adapter's pydantic-ai → TrajectoryWriter emitter.
# ABOUTME: Verifies emitted entries round-trip through the behavioral trace parser.

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
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


class TestWorkspaceOutputFallback:
    def test_recovers_non_empty_output_file_as_completed_response(self, tmp_path: Path) -> None:
        from aec_bench.adapters.tool_loop_local import (
            completion_from_workspace_output,
        )

        (tmp_path / "output.md").write_text('{"answer": 42}\n', encoding="utf-8")

        response = completion_from_workspace_output(str(tmp_path))

        assert response is not None
        assert response.done is True
        assert response.output_text == '{"answer": 42}\n'
        assert response.error_message is None

    def test_ignores_missing_output_file(self, tmp_path: Path) -> None:
        from aec_bench.adapters.tool_loop_local import (
            completion_from_workspace_output,
        )

        assert completion_from_workspace_output(str(tmp_path)) is None

    def test_next_turn_recovers_workspace_output_after_agent_exception(self, tmp_path: Path) -> None:
        from aec_bench.adapters.tool_loop import ToolLoopRequest
        from aec_bench.adapters.tool_loop_local import PydanticAiToolLoopClient

        (tmp_path / "output.md").write_text('{"ok": true}\n', encoding="utf-8")
        client = PydanticAiToolLoopClient.__new__(PydanticAiToolLoopClient)
        client._workspace = str(tmp_path)

        def raise_after_writing(_request: ToolLoopRequest) -> None:
            raise RuntimeError("schema failure")

        client._run_agent = raise_after_writing

        response = client.next_turn(ToolLoopRequest(model="test-model", instruction="solve it"))

        assert response.done is True
        assert response.output_text == '{"ok": true}\n'
        assert response.error_message is None


class TestPydanticAiNativeTools:
    def test_registers_host_controlled_tool_with_native_agent(self, monkeypatch) -> None:
        from aec_bench.adapters.tool_loop_local import PydanticAiToolLoopClient

        registered: list[str] = []

        class FakeAgent:
            def __init__(self, *_args: Any, **_kwargs: Any) -> None:
                pass

            def tool_plain(self, func=None, /, *, name=None, **_kwargs):
                def register(callback):
                    registered.append(name or callback.__name__)
                    return callback

                return register(func) if func is not None else register

        def submit_checkpoint(checkpoint_id: str) -> str:
            return checkpoint_id

        monkeypatch.setattr("pydantic_ai.Agent", FakeAgent)
        monkeypatch.setattr(
            "aec_bench.adapters.rlm.providers.resolve_pydantic_provider",
            lambda _model: "test",
        )
        monkeypatch.setattr(
            "aec_bench.adapters.rlm.providers._build_pydantic_model",
            lambda _model, _provider: object(),
        )
        monkeypatch.setattr(
            "aec_bench.adapters.rlm.providers._build_model_settings",
            lambda _provider, cache: {},
        )

        PydanticAiToolLoopClient(
            "test-model",
            workspace="/tmp/workspace",
            native_tools=[submit_checkpoint],
        )

        assert registered == ["bash", "submit_checkpoint"]

    def test_pydantic_ai_client_can_disable_bash_for_confined_native_tools(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from aec_bench.adapters.tool_loop_local import PydanticAiToolLoopClient

        registered: list[str] = []

        class FakeAgent:
            def __init__(self, *_args, **_kwargs) -> None:
                pass

            def tool_plain(self, tool):
                registered.append(tool.__name__)
                return tool

        def read_workspace_file(path: str) -> str:
            return path

        monkeypatch.setattr("pydantic_ai.Agent", FakeAgent)
        monkeypatch.setattr(
            "aec_bench.adapters.rlm.providers.resolve_pydantic_provider",
            lambda _model: "test",
        )
        monkeypatch.setattr(
            "aec_bench.adapters.rlm.providers._build_pydantic_model",
            lambda _model, _provider: object(),
        )
        monkeypatch.setattr(
            "aec_bench.adapters.rlm.providers._build_model_settings",
            lambda _provider, cache: {},
        )

        PydanticAiToolLoopClient(
            "test-model",
            workspace="/tmp/workspace",
            native_tools=[read_workspace_file],
            enable_bash=False,
        )

        assert registered == ["read_workspace_file"]
