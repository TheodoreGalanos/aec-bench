# ABOUTME: Tests report-template composition contracts — fragments, blocks, resolver protocols.
# ABOUTME: Compose mode lets sections be assembled from verbatim/fill/generated blocks.

import dataclasses

import pytest

from aec_bench.contracts.report_template import (
    BlockGenerator,
    BoilerplateFragment,
    FillBlock,
    GeneratedBlock,
    SlotResolver,
    VerbatimBlock,
    parse_block,
)


def test_boilerplate_fragment_holds_text_and_slot_names():
    frag = BoilerplateFragment(
        text="The Contractor shall access the Site via the {{base_access_point}}.",
        slots=("base_access_point",),
    )
    assert "{{base_access_point}}" in frag.text
    assert frag.slots == ("base_access_point",)


def test_boilerplate_fragment_defaults_to_no_slots():
    frag = BoilerplateFragment(text="The Contractor shall comply.")
    assert frag.slots == ()


def test_boilerplate_fragment_is_frozen():
    frag = BoilerplateFragment(text="x")
    with pytest.raises(dataclasses.FrozenInstanceError):
        frag.text = "y"  # type: ignore[misc]


def test_verbatim_block_only_needs_a_ref():
    block = VerbatimBlock(ref="the_site.condition.preamble")
    assert block.type == "verbatim"
    assert block.ref == "the_site.condition.preamble"


def test_fill_block_carries_ref_and_sources():
    block = FillBlock(
        ref="the_site.access.access_route",
        sources=("project_brief:site_information",),
    )
    assert block.type == "fill"
    assert block.ref == "the_site.access.access_route"
    assert block.sources == ("project_brief:site_information",)


def test_fill_block_sources_default_to_empty():
    block = FillBlock(ref="x")
    assert block.sources == ()


def test_generated_block_carries_prompt_and_sources():
    block = GeneratedBlock(
        prompt="Write the project-specific access constraints, max 3 sentences.",
        sources=("project_brief:site_constraints",),
    )
    assert block.type == "generated"
    assert "access constraints" in block.prompt
    assert block.sources == ("project_brief:site_constraints",)


def test_blocks_are_frozen():
    for block in (
        VerbatimBlock(ref="x"),
        FillBlock(ref="x"),
        GeneratedBlock(prompt="p"),
    ):
        with pytest.raises(dataclasses.FrozenInstanceError):
            block.ref = "y"  # type: ignore[union-attr,misc,attr-defined]


def test_parse_block_dispatches_verbatim():
    block = parse_block({"type": "verbatim", "ref": "the_site.condition.preamble"})
    assert isinstance(block, VerbatimBlock)
    assert block.ref == "the_site.condition.preamble"


def test_parse_block_dispatches_fill():
    block = parse_block(
        {
            "type": "fill",
            "ref": "the_site.access.access_route",
            "sources": ["project_brief:site_information"],
        },
    )
    assert isinstance(block, FillBlock)
    assert block.sources == ("project_brief:site_information",)


def test_parse_block_dispatches_generated():
    block = parse_block(
        {
            "type": "generated",
            "prompt": "Write something.",
            "sources": ["project_brief:notes"],
        },
    )
    assert isinstance(block, GeneratedBlock)
    assert block.prompt == "Write something."


def test_parse_block_rejects_unknown_type():
    with pytest.raises(ValueError, match="unknown block type"):
        parse_block({"type": "magic", "ref": "x"})


def test_parse_block_rejects_missing_type():
    with pytest.raises(ValueError, match="missing 'type'"):
        parse_block({"ref": "x"})


def test_slot_resolver_protocol_is_runtime_checkable():
    class StubResolver:
        def resolve(self, fragment, sources):
            return {"base_access_point": "Pass Office"}

    assert isinstance(StubResolver(), SlotResolver)


def test_block_generator_protocol_is_runtime_checkable():
    class StubGenerator:
        def generate(self, prompt, sources):
            return "generated text"

    assert isinstance(StubGenerator(), BlockGenerator)


def test_protocol_rejects_missing_methods():
    class IncompleteResolver:
        pass

    assert not isinstance(IncompleteResolver(), SlotResolver)
    assert not isinstance(IncompleteResolver(), BlockGenerator)


# ─── TreeSection compose-mode integration ──────────────────────────────────────


def test_tree_section_blocks_field_defaults_to_none():
    """Existing non-compose sections must still parse without blocks."""
    from aec_bench.contracts.repl import TreeSection

    section = TreeSection(id="x", title="X", fields={})
    assert section.blocks is None


def test_tree_section_carries_compose_blocks():
    from aec_bench.contracts.repl import TreeSection

    blocks = (
        VerbatimBlock(ref="x.preamble"),
        FillBlock(ref="x.body", sources=("brief:notes",)),
    )
    section = TreeSection(
        id="x",
        title="X",
        fields={},
        generation_mode="compose",
        blocks=blocks,
    )
    assert section.blocks == blocks
    assert section.generation_mode == "compose"


# ─── BlockTrace provenance fields ──────────────────────────────────────────


def test_block_trace_provenance_default_empty():
    from aec_bench.contracts.report_template import BlockTrace

    trace = BlockTrace(
        block_index=0,
        block_type="generated",
        text="x",
        start_offset=0,
        end_offset=1,
    )
    assert trace.provenance == ()
    assert trace.slot_provenance == {}
    assert trace.declared_provenance == ()
    assert trace.fetched_provenance == ()


def test_block_trace_with_provenance_populated():
    from aec_bench.contracts.report_template import BlockTrace

    trace = BlockTrace(
        block_index=0,
        block_type="generated",
        text="x",
        start_offset=0,
        end_offset=1,
        provenance=("brief.md#scope", "thread.md@msg3"),
        declared_provenance=("brief.md#scope",),
        fetched_provenance=("thread.md@msg3",),
    )
    assert trace.provenance == ("brief.md#scope", "thread.md@msg3")
    assert trace.declared_provenance == ("brief.md#scope",)
    assert trace.fetched_provenance == ("thread.md@msg3",)


# ─── BlockTask taxonomy (Idea C) ───────────────────────────────────────────


def test_block_task_enum_has_five_values():
    from aec_bench.contracts.report_template import BlockTask

    assert {t.value for t in BlockTask} == {
        "extract_fact",
        "classify_applicability",
        "summarise_context",
        "restate_clause",
        "synthesise_narrative",
    }


def test_block_task_enum_members_are_string_valued():
    from aec_bench.contracts.report_template import BlockTask

    assert BlockTask.EXTRACT_FACT.value == "extract_fact"
    assert BlockTask.SYNTHESISE_NARRATIVE.value == "synthesise_narrative"


def test_generated_block_defaults_to_synthesise_narrative():
    from aec_bench.contracts.report_template import BlockTask

    block = GeneratedBlock(prompt="Write something.")
    assert block.task == BlockTask.SYNTHESISE_NARRATIVE


def test_fill_block_defaults_to_extract_fact():
    from aec_bench.contracts.report_template import BlockTask

    block = FillBlock(ref="x")
    assert block.task == BlockTask.EXTRACT_FACT


def test_generated_block_accepts_explicit_task():
    from aec_bench.contracts.report_template import BlockTask

    block = GeneratedBlock(
        prompt="Summarise the brief.",
        task=BlockTask.SUMMARISE_CONTEXT,
    )
    assert block.task == BlockTask.SUMMARISE_CONTEXT


def test_fill_block_accepts_explicit_task():
    from aec_bench.contracts.report_template import BlockTask

    block = FillBlock(ref="x", task=BlockTask.CLASSIFY_APPLICABILITY)
    assert block.task == BlockTask.CLASSIFY_APPLICABILITY


def test_parse_block_reads_task_field_on_generated():
    from aec_bench.contracts.report_template import BlockTask

    block = parse_block(
        {
            "type": "generated",
            "prompt": "Summarise.",
            "task": "summarise_context",
        },
    )
    assert isinstance(block, GeneratedBlock)
    assert block.task == BlockTask.SUMMARISE_CONTEXT


def test_parse_block_reads_task_field_on_fill():
    from aec_bench.contracts.report_template import BlockTask

    block = parse_block(
        {
            "type": "fill",
            "ref": "x",
            "task": "classify_applicability",
        },
    )
    assert isinstance(block, FillBlock)
    assert block.task == BlockTask.CLASSIFY_APPLICABILITY


def test_parse_block_defaults_task_when_absent():
    from aec_bench.contracts.report_template import BlockTask

    gen = parse_block({"type": "generated", "prompt": "x"})
    fill = parse_block({"type": "fill", "ref": "x"})
    assert isinstance(gen, GeneratedBlock)
    assert isinstance(fill, FillBlock)
    assert gen.task == BlockTask.SYNTHESISE_NARRATIVE
    assert fill.task == BlockTask.EXTRACT_FACT


def test_parse_block_rejects_unknown_task_with_allowed_list():
    with pytest.raises(ValueError, match="unknown task") as excinfo:
        parse_block({"type": "generated", "prompt": "x", "task": "telepathy"})
    msg = str(excinfo.value)
    # The error should enumerate the allowed values to help the author.
    assert "extract_fact" in msg
    assert "synthesise_narrative" in msg


def test_verbatim_block_does_not_accept_task():
    """Verbatim has no LLM step — task is only meaningful on fill/generated."""
    block = VerbatimBlock(ref="x")
    assert not hasattr(block, "task")


# ─── BlockTrace.task ───────────────────────────────────────────────────────


def test_block_trace_task_defaults_to_none():
    from aec_bench.contracts.report_template import BlockTrace

    trace = BlockTrace(
        block_index=0,
        block_type="generated",
        text="x",
        start_offset=0,
        end_offset=1,
    )
    assert trace.task is None


def test_block_trace_records_task():
    from aec_bench.contracts.report_template import BlockTask, BlockTrace

    trace = BlockTrace(
        block_index=0,
        block_type="generated",
        text="x",
        start_offset=0,
        end_offset=1,
        task=BlockTask.SUMMARISE_CONTEXT,
    )
    assert trace.task == BlockTask.SUMMARISE_CONTEXT


def test_block_trace_slot_provenance_for_fill_block():
    from aec_bench.contracts.report_template import BlockTrace

    trace = BlockTrace(
        block_index=0,
        block_type="fill",
        text="x",
        start_offset=0,
        end_offset=1,
        slot_provenance={
            "project_name": ("brief.md#header",),
            "site": ("thread.md@msg1",),
        },
    )
    assert trace.slot_provenance["project_name"] == ("brief.md#header",)
    assert trace.slot_provenance["site"] == ("thread.md@msg1",)
