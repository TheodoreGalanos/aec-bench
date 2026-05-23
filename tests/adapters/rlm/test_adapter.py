# ABOUTME: Integration tests for the RlmAdapter — full REPL loop with replay client.
# ABOUTME: Validates that the adapter integrates engine, metadata, guardrails, and error tracking.

from __future__ import annotations

from pathlib import Path

from aec_bench.adapters.base import AdapterRequest
from aec_bench.adapters.rlm.adapter import RlmAdapter
from aec_bench.adapters.rlm.client import ReplayRlmClient, RlmCompletionResponse, ToolCall
from aec_bench.adapters.rlm.config import ExecutionConfig, GuardrailConfig
from aec_bench.contracts.agent_output import AgentOutputStatus


def _make_adapter(responses: list[RlmCompletionResponse], **kwargs) -> RlmAdapter:
    client = ReplayRlmClient(responses=responses)
    return RlmAdapter(
        adapter_name="rlm-test",
        model_name="test-model",
        client=client,
        guardrails=GuardrailConfig(
            token_budget=100_000,
            max_iterations=kwargs.get("max_iterations", 50),
        ),
    )


def test_adapter_executes_code_and_returns_final_answer() -> None:
    adapter = _make_adapter(
        [
            RlmCompletionResponse(
                output_text='```repl\nresult = {"voltage_drop_v": 8.4}\n```',
                input_tokens=500,
                output_tokens=100,
            ),
            RlmCompletionResponse(
                output_text='FINAL\n```json\n{"voltage_drop_v": 8.4}\n```',
                input_tokens=400,
                output_tokens=80,
                done=True,
            ),
        ]
    )
    result = adapter.execute(AdapterRequest(instruction="Calculate the voltage drop."))
    assert result.agent_output.status == AgentOutputStatus.COMPLETED
    assert result.adapter_name == "rlm-test"
    assert result.usage_input_tokens == 900
    assert result.usage_output_tokens == 180


def test_adapter_stops_at_iteration_cap() -> None:
    adapter = _make_adapter(
        [
            RlmCompletionResponse(
                output_text="```repl\nx = 1\n```",
                input_tokens=100,
                output_tokens=50,
            ),
            RlmCompletionResponse(
                output_text="```repl\ny = 2\n```",
                input_tokens=100,
                output_tokens=50,
            ),
            RlmCompletionResponse(
                output_text="FINAL\n42",
                input_tokens=100,
                output_tokens=50,
                done=True,
            ),
        ],
        max_iterations=2,
    )
    result = adapter.execute(AdapterRequest(instruction="Do something."))
    assert result.agent_output.status == AgentOutputStatus.PARTIAL


def test_adapter_handles_repl_error_and_continues() -> None:
    adapter = _make_adapter(
        [
            RlmCompletionResponse(
                output_text="```repl\n1/0\n```",
                input_tokens=100,
                output_tokens=50,
            ),
            RlmCompletionResponse(
                output_text="```repl\nresult = 42\n```",
                input_tokens=100,
                output_tokens=50,
            ),
            RlmCompletionResponse(
                output_text="FINAL\n42",
                input_tokens=100,
                output_tokens=50,
                done=True,
            ),
        ]
    )
    result = adapter.execute(AdapterRequest(instruction="Calculate something."))
    assert result.agent_output.status == AgentOutputStatus.COMPLETED
    assert len(result.transcript) >= 3


def test_adapter_records_transcript() -> None:
    adapter = _make_adapter(
        [
            RlmCompletionResponse(
                output_text="```repl\nx = 1\n```",
                input_tokens=100,
                output_tokens=50,
            ),
            RlmCompletionResponse(
                output_text="FINAL\n1",
                input_tokens=100,
                output_tokens=50,
                done=True,
            ),
        ]
    )
    result = adapter.execute(AdapterRequest(instruction="Test."))
    assert len(result.transcript) >= 2


def test_adapter_name_and_model() -> None:
    adapter = _make_adapter([])
    assert adapter.adapter_name() == "rlm-test"
    assert adapter.resolved_model() == "test-model"


def test_adapter_injects_subcalls_into_repl() -> None:
    """Agent can call extract() from REPL code."""
    from aec_bench.adapters.rlm.config import SubcallConfig

    sub_client = ReplayRlmClient(
        responses=[
            RlmCompletionResponse(
                output_text='```json\n{"speed": 45}\n```',
                input_tokens=50,
                output_tokens=20,
            ),
        ]
    )
    main_client = ReplayRlmClient(
        responses=[
            RlmCompletionResponse(
                output_text=('```repl\ndata = extract(text="wind speed is 45", fields=["speed"])\n```'),
                input_tokens=200,
                output_tokens=80,
            ),
            RlmCompletionResponse(
                output_text="FINAL\n45",
                input_tokens=100,
                output_tokens=20,
                done=True,
            ),
        ]
    )
    adapter = RlmAdapter(
        adapter_name="rlm-test",
        model_name="main-model",
        client=main_client,
        subcall_client=sub_client,
        subcall_model="sub-model",
        subcall_configs={"extract": SubcallConfig(name="extract", enabled=True)},
    )
    result = adapter.execute(AdapterRequest(instruction="Find wind speed."))
    assert result.agent_output.status == AgentOutputStatus.COMPLETED


def test_adapter_injects_template_into_repl() -> None:
    """Agent can interact with report template from REPL code."""
    from aec_bench.adapters.rlm.template import ReportTemplate
    from aec_bench.contracts.repl import DependencyTreeSchema, OutputField, TreeSection

    schema = DependencyTreeSchema(
        sections=[
            TreeSection(
                id="intro",
                title="Introduction",
                fields={
                    "summary": OutputField(
                        name="summary",
                        dtype="str",
                        description="Summary",
                    )
                },
                depends_on=[],
            ),
        ]
    )
    template = ReportTemplate(schema)

    main_client = ReplayRlmClient(
        responses=[
            RlmCompletionResponse(
                output_text=('```repl\nresult = report.fill_section("intro", {"summary": "Hello"})\n```'),
                input_tokens=200,
                output_tokens=80,
            ),
            RlmCompletionResponse(
                output_text="FINAL\nDone",
                input_tokens=100,
                output_tokens=20,
                done=True,
            ),
        ]
    )
    adapter = RlmAdapter(
        adapter_name="rlm-test",
        model_name="main-model",
        client=main_client,
        template=template,
    )
    result = adapter.execute(AdapterRequest(instruction="Fill the template."))
    assert result.agent_output.status == AgentOutputStatus.COMPLETED
    assert template.get_status().completed_sections == 1


# ---- FINAL_VAR mechanism ----


def test_adapter_final_var_triggers_completion() -> None:
    """Calling FINAL_VAR in REPL should trigger completion."""
    adapter = _make_adapter(
        [
            RlmCompletionResponse(
                output_text='```repl\nresult = FINAL_VAR({"answer": 42})\nprint(result)\n```',
                input_tokens=500,
                output_tokens=100,
            ),
        ]
    )
    result = adapter.execute(AdapterRequest(instruction="Compute something."))
    assert result.agent_output.status == AgentOutputStatus.COMPLETED


# ---- Scratchpad integration ----


def test_adapter_scratchpad_note_recall(tmp_path: Path) -> None:
    """NOTE/RECALL should work in REPL when scratchpad is configured."""
    adapter = RlmAdapter(
        adapter_name="rlm-test",
        model_name="test-model",
        client=ReplayRlmClient(
            responses=[
                RlmCompletionResponse(
                    output_text=('```repl\nNOTE("speed", 45)\nresult = RECALL("speed")\nprint(result)\n```'),
                    input_tokens=300,
                    output_tokens=80,
                ),
                RlmCompletionResponse(
                    output_text="FINAL\n45",
                    input_tokens=200,
                    output_tokens=30,
                    done=True,
                ),
            ]
        ),
        scratchpad_path=str(tmp_path / ".scratchpad.json"),
    )
    result = adapter.execute(AdapterRequest(instruction="Test scratchpad."))
    assert result.agent_output.status == AgentOutputStatus.COMPLETED


# ---- Compaction ----


def test_adapter_compaction_resets_conversation() -> None:
    """When input tokens exceed threshold, adapter should compact and continue."""
    compaction_client = ReplayRlmClient(
        responses=[
            RlmCompletionResponse(
                output_text="Agent extracted wind speed data and computed results.",
                input_tokens=200,
                output_tokens=50,
            ),
        ]
    )
    main_client = ReplayRlmClient(
        responses=[
            # Turn 1: normal — low tokens
            RlmCompletionResponse(
                output_text="```repl\nx = 42\n```",
                input_tokens=500,
                output_tokens=100,
            ),
            # Turn 2: HIGH tokens — triggers compaction (>85% of 10k limit)
            RlmCompletionResponse(
                output_text="```repl\ny = 99\n```",
                input_tokens=9000,
                output_tokens=200,
            ),
            # Turn 3: after compaction, finish
            RlmCompletionResponse(
                output_text="FINAL\n42",
                input_tokens=500,
                output_tokens=50,
                done=True,
            ),
        ]
    )
    adapter = RlmAdapter(
        adapter_name="rlm-test",
        model_name="test-model",
        client=main_client,
        compaction_client=compaction_client,
        execution=ExecutionConfig(
            context_limit=10_000,
            compaction_threshold_pct=0.85,
            hard_ceiling_pct=0.95,
        ),
    )
    result = adapter.execute(AdapterRequest(instruction="Compute."))
    assert result.agent_output.status == AgentOutputStatus.COMPLETED
    # Should have used more tokens due to compaction overhead
    assert result.usage_input_tokens > 500


# ---- Hard ceiling ----


def test_adapter_hard_ceiling_forces_partial() -> None:
    """When per-call context exceeds hard ceiling, adapter should stop.

    Set compaction threshold very high (0.99) so the hard ceiling (0.95)
    check fires first.
    """
    adapter = RlmAdapter(
        adapter_name="rlm-test",
        model_name="test-model",
        client=ReplayRlmClient(
            responses=[
                RlmCompletionResponse(
                    output_text="```repl\nx = 1\n```",
                    input_tokens=9600,  # >95% of 10k
                    output_tokens=100,
                ),
            ]
        ),
        execution=ExecutionConfig(
            context_limit=10_000,
            compaction_threshold_pct=0.99,
            hard_ceiling_pct=0.95,
        ),
    )
    result = adapter.execute(AdapterRequest(instruction="Compute."))
    assert result.agent_output.status == AgentOutputStatus.PARTIAL


# ---- Protected vars survive agent code ----


def test_adapter_protects_scaffolding_from_overwrite() -> None:
    """Agent code that overwrites FINAL_VAR should be restored."""
    adapter = _make_adapter(
        [
            RlmCompletionResponse(
                output_text='```repl\nFINAL_VAR = "oops"\n```',
                input_tokens=300,
                output_tokens=80,
            ),
            # FINAL_VAR should still work after restoration
            RlmCompletionResponse(
                output_text='```repl\nresult = FINAL_VAR({"answer": 1})\nprint(result)\n```',
                input_tokens=300,
                output_tokens=80,
            ),
        ]
    )
    result = adapter.execute(AdapterRequest(instruction="Test."))
    assert result.agent_output.status == AgentOutputStatus.COMPLETED


# ---- Dynamic HELP ----


def test_help_only_lists_enabled_subcalls() -> None:
    """HELP() should only list sub-calls that are actually enabled."""
    from aec_bench.adapters.rlm.adapter import _make_help

    help_fn = _make_help(enabled_subcalls={"extract", "summarise"})
    output = help_fn()
    assert "extract(" in output
    assert "summarise(" in output
    assert "calculate(" not in output
    assert "verify(" not in output
    assert "retrieve(" not in output


def test_help_with_no_subcalls() -> None:
    """HELP() with no sub-calls should still list core commands."""
    from aec_bench.adapters.rlm.adapter import _make_help

    help_fn = _make_help(enabled_subcalls=set())
    output = help_fn()
    assert "NOTE(" in output
    assert "RECALL(" in output
    assert "FINAL_VAR(" in output
    assert "SUB-CALLS" not in output


def test_help_with_all_subcalls() -> None:
    """HELP() with all sub-calls should list all of them."""
    from aec_bench.adapters.rlm.adapter import _make_help

    all_subs = {"extract", "summarise", "calculate", "retrieve", "verify", "reason"}
    help_fn = _make_help(enabled_subcalls=all_subs)
    output = help_fn()
    assert "extract(" in output
    assert "reason(" in output


# ---- Prohibited constraints ----


def test_prohibited_constraints_appear_in_system_prompt() -> None:
    """Prohibited constraints should render as MUST NOT rules in system prompt."""
    from aec_bench.adapters.rlm.adapter import _build_system_prompt

    prompt = _build_system_prompt(
        prohibited=["Skip the codes search sub-call", "Write output from memory"],
    )
    assert "You MUST NOT:" in prompt
    assert "Skip the codes search sub-call" in prompt
    assert "Write output from memory" in prompt


# ---- First-block-only execution (tool_use stop behaviour) ----


def test_adapter_executes_first_block_only_when_multiple() -> None:
    """When model generates multiple ```repl blocks, only the first executes.

    The adapter truncates the response and lets the model re-plan after
    seeing the result — like tool_use stop behaviour.
    """
    adapter = _make_adapter(
        [
            # Turn 1: model generates 3 blocks, only first executes
            RlmCompletionResponse(
                output_text=(
                    "Let me set up the data.\n\n"
                    "```repl\nx = 10\nprint(x)\n```\n\n"
                    "Now compute.\n\n"
                    "```repl\ny = x * 2\n```\n\n"
                    "And store the result.\n\n"
                    "```repl\nresult = x + y\nprint(result)\n```"
                ),
                input_tokens=500,
                output_tokens=200,
            ),
            # Turn 2: model sees x=10 output, continues properly
            RlmCompletionResponse(
                output_text="```repl\ny = x * 2\nprint(y)\n```",
                input_tokens=600,
                output_tokens=50,
            ),
            # Turn 3: finish
            RlmCompletionResponse(
                output_text="FINAL\n20",
                input_tokens=400,
                output_tokens=50,
                done=True,
            ),
        ]
    )
    result = adapter.execute(AdapterRequest(instruction="Compute."))
    assert result.agent_output.status == AgentOutputStatus.COMPLETED
    # First tool result should be from x=10 only (first block)
    tool_entries = [e for e in result.transcript if e.role.value == "tool"]
    assert len(tool_entries) >= 1
    assert "10" in tool_entries[0].content


def test_adapter_multi_block_final_var_not_reached() -> None:
    """FINAL_VAR in a later block is NOT executed — model must re-plan.

    Previously FINAL_VAR (last block) was the only block that ran,
    causing immediate exit with no real work done.
    """
    adapter = _make_adapter(
        [
            # Turn 1: model dumps everything including FINAL_VAR in block 3.
            # Only block 1 (data assignment) executes; FINAL_VAR is discarded.
            RlmCompletionResponse(
                output_text=(
                    "Let me do all the work.\n\n"
                    "```repl\ndata = {'voltage': 230}\n```\n\n"
                    "Store it.\n\n"
                    "```repl\nresult = data['voltage'] * 2\n```\n\n"
                    "Done.\n\n"
                    '```repl\nFINAL_VAR({"answer": result})\n```'
                ),
                input_tokens=500,
                output_tokens=200,
            ),
            # Turn 2: model re-plans, does the multiply
            RlmCompletionResponse(
                output_text="```repl\nresult = data['voltage'] * 2\nprint(result)\n```",
                input_tokens=600,
                output_tokens=50,
            ),
            # Turn 3: model finishes properly
            RlmCompletionResponse(
                output_text='```repl\nFINAL_VAR({"answer": result})\n```',
                input_tokens=400,
                output_tokens=50,
            ),
        ]
    )
    result = adapter.execute(AdapterRequest(instruction="Compute voltage."))
    assert result.agent_output.status == AgentOutputStatus.COMPLETED


# ---- Early return interception ----


def test_adapter_intercepts_early_return_on_first_iteration() -> None:
    """If agent tries to FINAL on iteration 0, force a verification step."""
    adapter = _make_adapter(
        [
            # Iteration 0: agent immediately says FINAL — should be intercepted
            RlmCompletionResponse(
                output_text="FINAL\nThe answer is 42",
                input_tokens=500,
                output_tokens=100,
                done=True,
            ),
            # Iteration 1: agent verifies and re-submits — should be accepted
            RlmCompletionResponse(
                output_text="FINAL\nThe verified answer is 42",
                input_tokens=400,
                output_tokens=80,
                done=True,
            ),
        ]
    )
    result = adapter.execute(AdapterRequest(instruction="Calculate something."))
    assert result.agent_output.status == AgentOutputStatus.COMPLETED
    # Should have consumed both responses (intercepted first, accepted second)
    assert result.usage_input_tokens == 900
    assert result.usage_output_tokens == 180


# ---- System prompt identity ----


def test_system_prompt_contains_rlm_identity() -> None:
    """System prompt should frame the REPL as extended cognition, not a tool."""
    from aec_bench.adapters.rlm.adapter import _build_system_prompt

    prompt = _build_system_prompt()
    assert "extended cognition" in prompt.lower() or "how you think" in prompt.lower()
    assert "NO knowledge" in prompt or "no knowledge" in prompt
    assert "hallucination" in prompt.lower()
    assert "read" in prompt.lower() and "extract" in prompt.lower()


def test_system_prompt_no_repl_block_instructions() -> None:
    """Tool_use handles code blocks structurally — no ```repl instructions needed."""
    from aec_bench.adapters.rlm.adapter import _build_system_prompt

    prompt = _build_system_prompt()
    assert "```repl" not in prompt


# ---- Tool-use path ----


def test_adapter_tool_use_completes_with_tool_calls() -> None:
    """Adapter should handle tool_call responses, execute code, and loop."""
    adapter = _make_adapter(
        [
            RlmCompletionResponse(
                output_text="Let me check.",
                input_tokens=500,
                output_tokens=100,
                tool_call=ToolCall(name="repl", code="x = 42\nprint(x)", call_id="c1"),
            ),
            RlmCompletionResponse(
                output_text="Done.",
                input_tokens=600,
                output_tokens=80,
                tool_call=ToolCall(name="repl", code='FINAL_VAR({"answer": 42})', call_id="c2"),
            ),
        ]
    )
    result = adapter.execute(AdapterRequest(instruction="Calculate."))
    assert result.agent_output.status == AgentOutputStatus.COMPLETED
    assert result.usage_input_tokens == 1100
    assert result.usage_output_tokens == 180


def test_adapter_tool_use_stops_when_model_done() -> None:
    """When model responds without a tool_call (done=True), adapter completes.

    The first done=True on iteration 1 is intercepted by early-return
    interception (no code executed yet). The second response is accepted.
    """
    adapter = _make_adapter(
        [
            RlmCompletionResponse(
                output_text="The answer is 42.",
                input_tokens=500,
                output_tokens=100,
                done=True,
            ),
            RlmCompletionResponse(
                output_text="Verified: the answer is 42.",
                input_tokens=400,
                output_tokens=80,
                done=True,
            ),
        ]
    )
    result = adapter.execute(AdapterRequest(instruction="Compute."))
    assert result.agent_output.status == AgentOutputStatus.COMPLETED


def test_adapter_tool_use_guardrails_stop_loop() -> None:
    """Guardrails should stop the tool-use loop."""
    adapter = _make_adapter(
        [
            RlmCompletionResponse(
                output_text="",
                input_tokens=100,
                output_tokens=50,
                tool_call=ToolCall(name="repl", code="x = 1", call_id="c1"),
            ),
            RlmCompletionResponse(
                output_text="",
                input_tokens=100,
                output_tokens=50,
                tool_call=ToolCall(name="repl", code="y = 2", call_id="c2"),
            ),
            RlmCompletionResponse(
                output_text="",
                input_tokens=100,
                output_tokens=50,
                tool_call=ToolCall(name="repl", code="z = 3", call_id="c3"),
            ),
        ],
        max_iterations=2,
    )
    result = adapter.execute(AdapterRequest(instruction="Do it."))
    assert result.agent_output.status == AgentOutputStatus.PARTIAL
