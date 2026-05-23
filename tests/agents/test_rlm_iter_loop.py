# ABOUTME: Integration tests for the async iter() RLM loop using structural analysis.
# ABOUTME: Validates compaction triggers, output priority, and scaffolding presence.

import ast

from aec_bench.agents.rlm_script import build_rlm_script


def test_script_compiles_and_has_main() -> None:
    """The generated script should define async main() and call asyncio.run()."""
    script = build_rlm_script()
    tree = ast.parse(script)
    function_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)]
    assert "main" in function_names


def test_main_is_async() -> None:
    """main() must be an async function."""
    script = build_rlm_script()
    tree = ast.parse(script)
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "main":
            return
    raise AssertionError("main() is not async")


def test_script_output_priority_chain_order() -> None:
    """Output chain should check direct write before template_submit before final_var before fallback."""
    script = build_rlm_script()
    dw_pos = script.index("direct_write")
    ts_pos = script.index("template_submit")
    fv_pos = script.index('"final_var"')
    fb_pos = script.index('"fallback"')
    assert dw_pos < ts_pos < fv_pos < fb_pos, (
        f"Output priority order wrong: direct_write@{dw_pos}, "
        f"template_submit@{ts_pos}, final_var@{fv_pos}, fallback@{fb_pos}"
    )


def test_script_compaction_threshold_derived_from_config() -> None:
    """Compaction threshold should be computed from config values."""
    script = build_rlm_script()
    assert "compaction_threshold_pct" in script
    assert "_compaction_threshold = int(" in script
    assert "_hard_ceiling = int(" in script


def test_script_imports_asyncio_and_end() -> None:
    """Script must import asyncio and End from pydantic_graph."""
    script = build_rlm_script()
    assert "import asyncio" in script
    assert "from pydantic_graph import End" in script


def test_script_has_compaction_restart_logic() -> None:
    """After compaction, the loop should restart with new history."""
    script = build_rlm_script()
    # The compaction block should set compacted flag and break
    assert "_compacted = True" in script
    assert "break" in script  # breaks out of iter() to restart
    # And the while loop should continue
    assert "while not done:" in script


def test_script_tracks_subcall_tokens() -> None:
    """Sub-call token accumulation should use a module-level counter."""
    script = build_rlm_script()
    assert "_subcall_token_total" in script


def test_script_writes_agent_result_with_new_fields() -> None:
    """agent_result.json should include output_source and compaction_count."""
    script = build_rlm_script()
    assert '"output_source"' in script
    assert '"compaction_count"' in script


def test_script_no_run_sync_for_main_agent() -> None:
    """The main agent should not use run_sync — only sub-calls may."""
    script = build_rlm_script()
    # run_sync should only appear in sub-call functions (llm_query, extract, summarise, compact)
    # and NOT in the main run section
    assert "rlm_agent.run_sync" not in script
    # But sub-calls still use run_sync
    assert "run_sync" in script  # sub-calls use it
