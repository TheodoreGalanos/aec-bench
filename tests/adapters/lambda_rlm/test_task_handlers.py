# ABOUTME: Tests the lambda-rlm block-task handler registry — Idea C v1.
# ABOUTME: Two registries (slot/prose); two handlers initially (extract_fact, synthesise_narrative).

import pytest

from aec_bench.contracts.report_template import BlockTask


def test_slot_handler_registry_has_extract_fact():
    from aec_bench.adapters.lambda_rlm.task_handlers import SLOT_TASK_HANDLERS

    assert BlockTask.EXTRACT_FACT in SLOT_TASK_HANDLERS
    handler = SLOT_TASK_HANDLERS[BlockTask.EXTRACT_FACT]
    assert handler.task == BlockTask.EXTRACT_FACT
    assert handler.cost_class == "cheap"


def test_prose_handler_registry_has_synthesise_narrative():
    from aec_bench.adapters.lambda_rlm.task_handlers import PROSE_TASK_HANDLERS

    assert BlockTask.SYNTHESISE_NARRATIVE in PROSE_TASK_HANDLERS
    handler = PROSE_TASK_HANDLERS[BlockTask.SYNTHESISE_NARRATIVE]
    assert handler.task == BlockTask.SYNTHESISE_NARRATIVE
    assert handler.cost_class == "strong"


def test_summarise_context_handler_registered():
    from aec_bench.adapters.lambda_rlm.task_handlers import PROSE_TASK_HANDLERS

    assert BlockTask.SUMMARISE_CONTEXT in PROSE_TASK_HANDLERS
    handler = PROSE_TASK_HANDLERS[BlockTask.SUMMARISE_CONTEXT]
    assert handler.task == BlockTask.SUMMARISE_CONTEXT
    assert handler.cost_class == "medium"


def test_classify_and_restate_not_yet_registered():
    """CLASSIFY_APPLICABILITY and RESTATE_CLAUSE are spec'd but not built yet.

    Adding either is a one-handler addition without touching the resolver,
    generator, or composer — the dispatch surface is now stable.
    """
    from aec_bench.adapters.lambda_rlm.task_handlers import (
        PROSE_TASK_HANDLERS,
        SLOT_TASK_HANDLERS,
    )

    assert BlockTask.RESTATE_CLAUSE not in PROSE_TASK_HANDLERS
    assert BlockTask.CLASSIFY_APPLICABILITY not in SLOT_TASK_HANDLERS


def test_get_slot_handler_returns_registered():
    from aec_bench.adapters.lambda_rlm.task_handlers import get_slot_handler

    handler = get_slot_handler(BlockTask.EXTRACT_FACT)
    assert handler.task == BlockTask.EXTRACT_FACT


def test_get_slot_handler_rejects_prose_task():
    from aec_bench.adapters.lambda_rlm.task_handlers import get_slot_handler

    with pytest.raises(KeyError, match="no slot handler"):
        get_slot_handler(BlockTask.SYNTHESISE_NARRATIVE)


def test_get_prose_handler_returns_registered():
    from aec_bench.adapters.lambda_rlm.task_handlers import get_prose_handler

    handler = get_prose_handler(BlockTask.SYNTHESISE_NARRATIVE)
    assert handler.task == BlockTask.SYNTHESISE_NARRATIVE


def test_get_prose_handler_rejects_unimplemented_task():
    from aec_bench.adapters.lambda_rlm.task_handlers import get_prose_handler

    with pytest.raises(KeyError, match="no prose handler"):
        get_prose_handler(BlockTask.RESTATE_CLAUSE)


def test_extract_fact_prompt_includes_fragment_slot_list_and_sources():
    from aec_bench.adapters.lambda_rlm.task_handlers import (
        SLOT_TASK_HANDLERS,
        SlotPromptContext,
    )
    from aec_bench.contracts.report_template import BoilerplateFragment

    handler = SLOT_TASK_HANDLERS[BlockTask.EXTRACT_FACT]
    ctx = SlotPromptContext(
        fragment=BoilerplateFragment(
            text="Project: {{project_name}}.",
            slots=("project_name",),
        ),
        remaining_slots=("project_name",),
        sources_block="### Source: brief.md\nProject is North Plant.",
    )
    prompt = handler.build_prompt(ctx)

    assert "Project: {{project_name}}." in prompt
    assert "project_name" in prompt
    assert "Source: brief.md" in prompt
    assert "JSON object" in prompt


def test_extract_fact_parse_tolerates_prose_around_json():
    from aec_bench.adapters.lambda_rlm.task_handlers import SLOT_TASK_HANDLERS

    handler = SLOT_TASK_HANDLERS[BlockTask.EXTRACT_FACT]
    parsed = handler.parse('Sure thing: {"project_name": "North Plant"}')
    assert parsed == {"project_name": "North Plant"}


def test_extract_fact_parse_returns_empty_on_garbage():
    from aec_bench.adapters.lambda_rlm.task_handlers import SLOT_TASK_HANDLERS

    handler = SLOT_TASK_HANDLERS[BlockTask.EXTRACT_FACT]
    assert handler.parse("no json here") == {}


def test_synthesise_narrative_prompt_includes_user_prompt_and_sources():
    from aec_bench.adapters.lambda_rlm.task_handlers import (
        PROSE_TASK_HANDLERS,
        ProsePromptContext,
    )

    handler = PROSE_TASK_HANDLERS[BlockTask.SYNTHESISE_NARRATIVE]
    ctx = ProsePromptContext(
        user_prompt="Write the access constraints.",
        sources_block="### Source: brief.md\nSite has restricted access.",
        known_facts=None,
        scope_evolution=None,
    )
    prompt = handler.build_prompt(ctx)

    assert "Write the access constraints." in prompt
    assert "Source: brief.md" in prompt
    # Today's behaviour: instruction to write directly with no preamble.
    assert "no preamble" in prompt


def test_synthesise_narrative_prompt_includes_known_facts_when_present():
    from aec_bench.adapters.lambda_rlm.task_handlers import (
        PROSE_TASK_HANDLERS,
        ProsePromptContext,
    )

    handler = PROSE_TASK_HANDLERS[BlockTask.SYNTHESISE_NARRATIVE]
    ctx = ProsePromptContext(
        user_prompt="Write something.",
        sources_block="### Source: brief.md\nFoo.",
        known_facts="- project_name: North Plant",
        scope_evolution=None,
    )
    prompt = handler.build_prompt(ctx)
    assert "Known facts" in prompt
    assert "project_name: North Plant" in prompt


def test_synthesise_narrative_prompt_includes_scope_evolution_when_present():
    from aec_bench.adapters.lambda_rlm.task_handlers import (
        PROSE_TASK_HANDLERS,
        ProsePromptContext,
    )

    handler = PROSE_TASK_HANDLERS[BlockTask.SYNTHESISE_NARRATIVE]
    ctx = ProsePromptContext(
        user_prompt="Write something.",
        sources_block="### Source: brief.md\nFoo.",
        known_facts=None,
        scope_evolution="Client expanded scope mid-thread.",
    )
    prompt = handler.build_prompt(ctx)
    assert "Scope summary" in prompt
    assert "Client expanded scope mid-thread." in prompt


def test_synthesise_narrative_parse_is_identity():
    from aec_bench.adapters.lambda_rlm.task_handlers import PROSE_TASK_HANDLERS

    handler = PROSE_TASK_HANDLERS[BlockTask.SYNTHESISE_NARRATIVE]
    assert handler.parse("hello world") == "hello world"


# ─── summarise_context ─────────────────────────────────────────────────────


def test_summarise_context_prompt_frames_task_as_summary():
    from aec_bench.adapters.lambda_rlm.task_handlers import (
        PROSE_TASK_HANDLERS,
        ProsePromptContext,
    )

    handler = PROSE_TASK_HANDLERS[BlockTask.SUMMARISE_CONTEXT]
    ctx = ProsePromptContext(
        user_prompt="List concrete deliverables from the email thread.",
        sources_block=("### Source: email_thread\nSarah requested an Options Assessment Report and a workshop."),
        known_facts=None,
        scope_evolution=None,
    )
    prompt = handler.build_prompt(ctx)

    # The summarise framing makes the task explicit.
    assert "summarise" in prompt.lower()
    # The user's specific instruction is preserved verbatim.
    assert "List concrete deliverables from the email thread." in prompt
    # Sources flow through.
    assert "Source: email_thread" in prompt


def test_summarise_context_prompt_demands_evidence_grounding():
    """Closing rule must explicitly require source-evidenced items only."""
    from aec_bench.adapters.lambda_rlm.task_handlers import (
        PROSE_TASK_HANDLERS,
        ProsePromptContext,
    )

    handler = PROSE_TASK_HANDLERS[BlockTask.SUMMARISE_CONTEXT]
    ctx = ProsePromptContext(
        user_prompt="x",
        sources_block="### Source: y\nz",
        known_facts=None,
        scope_evolution=None,
    )
    prompt = handler.build_prompt(ctx)
    # Anti-fabrication clause is the whole point of summarise vs synthesise.
    assert "evidenced" in prompt.lower() or "no fabrication" in prompt.lower()


def test_summarise_context_includes_known_facts_and_scope_evolution_when_present():
    from aec_bench.adapters.lambda_rlm.task_handlers import (
        PROSE_TASK_HANDLERS,
        ProsePromptContext,
    )

    handler = PROSE_TASK_HANDLERS[BlockTask.SUMMARISE_CONTEXT]
    ctx = ProsePromptContext(
        user_prompt="List deliverables.",
        sources_block="### Source: thread\n...",
        known_facts="- project_name: North Plant",
        scope_evolution="Client narrowed scope from full study to options-only.",
    )
    prompt = handler.build_prompt(ctx)
    assert "project_name: North Plant" in prompt
    assert "Client narrowed scope" in prompt


def test_summarise_context_parse_is_identity():
    from aec_bench.adapters.lambda_rlm.task_handlers import PROSE_TASK_HANDLERS

    handler = PROSE_TASK_HANDLERS[BlockTask.SUMMARISE_CONTEXT]
    assert handler.parse("a faithful summary") == "a faithful summary"
