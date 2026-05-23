# ABOUTME: Tests for the PydanticAI-based RLM REPL runner script builder.
# ABOUTME: Validates syntax, structure, and key RLM components of the container script.

import ast

from aec_bench.agents.rlm_script import build_rlm_script


def test_build_returns_nonempty_string() -> None:
    script = build_rlm_script()
    assert isinstance(script, str)
    assert len(script) > 100


def test_script_is_valid_python() -> None:
    script = build_rlm_script()
    ast.parse(script)


def test_script_uses_pydantic_ai() -> None:
    script = build_rlm_script()
    assert "from pydantic_ai import Agent" in script
    assert "rlm_agent.iter(" in script
    assert "UsageLimits" in script


def test_script_contains_repl_tool() -> None:
    script = build_rlm_script()
    assert "repl_tool" in script
    assert "tool_plain" in script
    assert "exec(" in script


def test_script_contains_final_var_mechanism() -> None:
    script = build_rlm_script()
    assert "FINAL_VAR" in script
    assert "final_value" in script
    assert "final_called" in script


def test_script_contains_context_as_variable() -> None:
    script = build_rlm_script()
    assert 'repl.inject("context"' in script
    assert "context` variable" in script


def test_script_contains_llm_query() -> None:
    script = build_rlm_script()
    assert "llm_query" in script
    assert "SHOW_VARS" in script


def test_script_writes_output_files() -> None:
    script = build_rlm_script()
    assert "agent_result.json" in script
    assert "output.md" in script
    assert "symbolic_state.json" in script


def test_script_reads_rlm_config() -> None:
    script = build_rlm_script()
    assert "rlm.toml" in script


def test_script_uses_trajectory_writer() -> None:
    script = build_rlm_script()
    assert "TrajectoryWriter" in script


def test_script_supports_bedrock() -> None:
    script = build_rlm_script()
    assert "BedrockConverseModel" in script
    assert "BedrockProvider" in script


def test_script_supports_azure() -> None:
    script = build_rlm_script()
    assert "AzureProvider" in script


def test_script_uses_async_iter() -> None:
    """Script should use Agent.iter() instead of run_sync() for the main loop."""
    script = build_rlm_script()
    assert "async def main()" in script
    assert "asyncio.run(main())" in script
    assert "rlm_agent.iter(" in script


def test_script_has_compaction_logic() -> None:
    script = build_rlm_script()
    assert "compaction_threshold" in script
    assert "compaction_count" in script
    assert "_hard_ceiling" in script


def test_script_has_stderr_logging() -> None:
    script = build_rlm_script()
    assert "file=sys.stderr" in script
    assert "[Turn" in script


def test_script_has_subcall_token_aggregation() -> None:
    script = build_rlm_script()
    assert "_subcall_token_total" in script


def test_script_has_output_priority_chain() -> None:
    script = build_rlm_script()
    assert "_output_source" in script
    assert "direct_write" in script
    assert "template_submit" in script
    assert '"final_var"' in script
    assert '"fallback"' in script


def test_script_has_progressive_scaffolding() -> None:
    script = build_rlm_script()
    assert "_build_footer" in script
    assert "_compacted" in script


def test_script_no_longer_uses_history_processors() -> None:
    """History processors are replaced by compaction."""
    script = build_rlm_script()
    assert "history_processors" not in script
    assert "_sliding_window_processor" not in script
    assert "_metadata_only_processor" not in script


def test_script_writes_structured_metadata() -> None:
    """step_metadata should go through TrajectoryWriter metadata param, not embedded in stdout."""
    script = build_rlm_script()
    assert "metadata=step_meta" in script
    # Old text-embedded approach should be gone
    assert "--- step_metadata ---" not in script
