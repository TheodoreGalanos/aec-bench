# ABOUTME: Tests for script builder functions — verifies each script contains expected content.
# ABOUTME: String assertions only, no execution. Scripts are validated by their structure.

from aec_bench.agents.scripts import (
    build_anthropic_tool_loop_script,
    build_openai_tool_loop_script,
    build_pydantic_ai_script,
)


def test_anthropic_script_returns_string() -> None:
    script = build_anthropic_tool_loop_script()
    assert isinstance(script, str)
    assert len(script) > 100


def test_anthropic_script_uses_messages_api() -> None:
    script = build_anthropic_tool_loop_script()
    assert "x-api-key" in script
    assert "tool_use" in script
    assert "api.anthropic.com" in script


def test_anthropic_script_includes_trajectory_writer() -> None:
    script = build_anthropic_tool_loop_script()
    assert "from trajectory_writer import TrajectoryWriter" in script
    assert "traj = TrajectoryWriter()" in script
    assert "traj.system(" in script
    assert "traj.user(" in script
    assert "traj.new_step()" in script
    assert "traj.thinking(" in script
    assert "traj.tool_call(" in script
    assert "traj.tool_result(" in script
    assert "traj.close()" in script


def test_openai_script_returns_string() -> None:
    script = build_openai_tool_loop_script()
    assert isinstance(script, str)
    assert len(script) > 100


def test_openai_script_uses_chat_completions() -> None:
    script = build_openai_tool_loop_script()
    assert "tool_calls" in script or "function" in script
    assert "chat/completions" in script


def test_openai_script_includes_trajectory_writer() -> None:
    script = build_openai_tool_loop_script()
    assert "from trajectory_writer import TrajectoryWriter" in script
    assert "traj = TrajectoryWriter()" in script
    assert "traj.close()" in script


def test_pydantic_ai_script_returns_string() -> None:
    script = build_pydantic_ai_script()
    assert isinstance(script, str)
    assert len(script) > 100


def test_pydantic_ai_script_uses_pydantic_ai() -> None:
    script = build_pydantic_ai_script()
    assert "pydantic_ai" in script
    assert "BinaryContent" in script
    assert "UsageLimits" in script


def test_pydantic_ai_script_includes_trajectory_writer() -> None:
    script = build_pydantic_ai_script()
    assert "from trajectory_writer import TrajectoryWriter" in script
    assert "traj = TrajectoryWriter()" in script
    assert "traj.close()" in script


def test_pydantic_ai_script_excludes_trajectory_from_artifacts() -> None:
    script = build_pydantic_ai_script()
    assert '"trajectory.jsonl"' in script


def test_pydantic_ai_script_has_mime_registry() -> None:
    script = build_pydantic_ai_script()
    assert "_IMAGE_MIME" in script
    assert "image/jpeg" in script
    assert "application/pdf" in script


def test_anthropic_script_not_pydantic() -> None:
    """Anthropic script uses raw HTTP, not pydantic-ai."""
    script = build_anthropic_tool_loop_script()
    assert "pydantic_ai" not in script


def test_openai_script_not_pydantic() -> None:
    """OpenAI script uses raw HTTP, not pydantic-ai."""
    script = build_openai_tool_loop_script()
    assert "pydantic_ai" not in script
