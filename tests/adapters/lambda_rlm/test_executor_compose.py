# ABOUTME: Tests the executor's compose-mode dispatch through the bridge.
# ABOUTME: Compose sections skip extraction/review and route directly to the renderer.

import json

from aec_bench.adapters.lambda_rlm.config import LambdaRlmConfig
from aec_bench.adapters.lambda_rlm.executor import PlanExecutor
from aec_bench.adapters.lambda_rlm.state import (
    CompositionOp,
    ExecutionPlan,
    SectionPlan,
)
from aec_bench.adapters.rlm.client import ReplayRlmClient, RlmCompletionResponse
from aec_bench.adapters.rlm.template import ReportTemplate
from aec_bench.contracts.repl import DependencyTreeSchema, OutputField, TreeSection
from aec_bench.contracts.report_template import FillBlock, VerbatimBlock


def _compose_template() -> ReportTemplate:
    schema = DependencyTreeSchema(
        sections=(
            TreeSection(
                id="the_site",
                title="The Site",
                fields={"text": OutputField(name="text", dtype="str", description="")},
                depends_on=(),
                generation_mode="compose",
                blocks=(
                    VerbatimBlock(ref="the_site.condition.preamble"),
                    FillBlock(
                        ref="the_site.access.access_route",
                        sources=("brief:site_information",),
                    ),
                ),
            ),
        ),
    )
    return ReportTemplate(schema)


def _empty_section_plan(section_id: str) -> SectionPlan:
    """Compose sections do their own work — no leaf extraction."""
    return SectionPlan(
        section_id=section_id,
        generation_mode="compose",
        sources=[],
        leaf_ops=[],
        reduce_ops=[],
        composition_op=CompositionOp.MERGE_EXTRACTIONS,
        estimated_leaf_calls=0,
        estimated_reduce_calls=0,
    )


def test_executor_renders_compose_section_via_bridge():
    """A compose section should produce assembled text without going through
    the standard extract → generate prompt pipeline."""
    client = ReplayRlmClient(
        responses=[
            RlmCompletionResponse(
                output_text=json.dumps({"access_point": "Pass Office Gate 3"}),
                input_tokens=120,
                output_tokens=15,
            ),
        ],
    )
    boilerplate = {
        "the_site": {
            "condition": {"preamble": "The Site remains operational throughout."},
            "access": {
                "access_route": "The Contractor shall access via the {{access_point}}.",
            },
        },
    }
    plan = ExecutionPlan(
        section_order=["the_site"],
        section_plans={"the_site": _empty_section_plan("the_site")},
        skipped_sections=[],
    )

    executor = PlanExecutor(
        client=client,
        model="test-model",
        template=_compose_template(),
        source_docs={"brief:site_information": "Access via Pass Office Gate 3."},
        config=LambdaRlmConfig(),
        boilerplate_fragments=boilerplate,
    )

    state = executor.execute(plan)

    assert state.sections["the_site"] == (
        "The Site remains operational throughout.\n\nThe Contractor shall access via the Pass Office Gate 3."
    )
    # One LLM call — the slot resolver. No extract / review / generate prompts.
    assert state.llm_calls == 1
    assert state.tokens_used == 135  # 120 in + 15 out


def test_assembler_renders_consistent_numbered_headings():
    """The assembler owns the section numbering — every section gets `# {N}. {title}`
    where N is its 1-indexed position. LLM-supplied headings on transform/guided
    content are stripped before the assembler prepends its own."""
    from unittest.mock import MagicMock

    from aec_bench.adapters.lambda_rlm.adapter import LambdaRlmAdapter
    from aec_bench.adapters.lambda_rlm.config import LambdaRlmConfig
    from aec_bench.adapters.rlm.template import ReportTemplate
    from aec_bench.contracts.repl import (
        DependencyTreeSchema,
        OutputField,
        TreeSection,
    )

    schema = DependencyTreeSchema(
        sections=(
            TreeSection(
                id="intro",
                title="Introduction",
                fields={"text": OutputField(name="text", dtype="str", description="")},
                generation_mode="transform",
            ),
            TreeSection(
                id="scope",
                title="Scope of Works",
                fields={"text": OutputField(name="text", dtype="str", description="")},
                generation_mode="guided",
            ),
            TreeSection(
                id="grs",
                title="General Requirements",
                fields={"content": OutputField(name="content", dtype="str", description="")},
                generation_mode="compose",
                blocks=(),
            ),
        ),
    )
    adapter = LambdaRlmAdapter(
        adapter_name="lambda-rlm",
        model_name="m",
        client=MagicMock(),
        template=ReportTemplate(schema),
        source_docs={},
        config=LambdaRlmConfig(),
        workspace="/tmp",
    )

    rendered = adapter._assemble_output(
        {
            # LLM hallucinated number "5" — assembler must overwrite to "1"
            "intro": {"content": "# 5. Introduction\n\n## 1.1 Purpose\n\nProject brief."},
            # LLM omitted number — assembler must add proper one
            "scope": {"content": "# Scope of Works\n\nThe Contractor shall..."},
            # Compose section: no LLM heading at all
            "grs": {"content": "## General\n\nThe Contractor shall ensure..."},
        },
    )
    expected = (
        "# 1. Introduction\n\n## 1.1 Purpose\n\nProject brief.\n\n"
        "# 2. Scope of Works\n\nThe Contractor shall...\n\n"
        "# 3. General Requirements\n\n## General\n\nThe Contractor shall ensure..."
    )
    assert rendered == expected


def test_assembler_leaves_content_alone_when_no_leading_heading():
    """Content that doesn't start with a `#` line should be appended cleanly."""
    from unittest.mock import MagicMock

    from aec_bench.adapters.lambda_rlm.adapter import LambdaRlmAdapter
    from aec_bench.adapters.lambda_rlm.config import LambdaRlmConfig
    from aec_bench.adapters.rlm.template import ReportTemplate
    from aec_bench.contracts.repl import (
        DependencyTreeSchema,
        OutputField,
        TreeSection,
    )

    schema = DependencyTreeSchema(
        sections=(
            TreeSection(
                id="x",
                title="Section X",
                fields={"text": OutputField(name="text", dtype="str", description="")},
                generation_mode="transform",
            ),
        ),
    )
    adapter = LambdaRlmAdapter(
        adapter_name="lambda-rlm",
        model_name="m",
        client=MagicMock(),
        template=ReportTemplate(schema),
        source_docs={},
        config=LambdaRlmConfig(),
        workspace="/tmp",
    )
    rendered = adapter._assemble_output({"x": {"content": "Plain prose with no heading."}})
    assert rendered == "# 1. Section X\n\nPlain prose with no heading."


def test_compose_section_output_gets_section_title_heading():
    """Compose sections don't have an LLM that adds '# Title' on its own,
    so the assembler must prepend the section title."""
    from unittest.mock import MagicMock

    from aec_bench.adapters.lambda_rlm.adapter import LambdaRlmAdapter
    from aec_bench.adapters.lambda_rlm.config import LambdaRlmConfig

    template = _compose_template()  # one compose section "the_site"
    adapter = LambdaRlmAdapter(
        adapter_name="lambda-rlm",
        model_name="m",
        client=MagicMock(),
        template=template,
        source_docs={},
        config=LambdaRlmConfig(),
        workspace="/tmp",
    )

    rendered = adapter._assemble_output(
        {"the_site": {"content": "## 8.1 Site Condition\n\nSite remains operational."}},
    )
    # Compose sections must carry their parent title with the canonical position
    # number; the boilerplate body would otherwise dangle directly under the
    # previous section's content.
    assert rendered.startswith("# 1. The Site\n\n## 8.1 Site Condition")


def test_compose_section_passes_sandbox_through_to_resolver_and_generator(tmp_path):
    """Executor's _compose_section threads self._sandbox into render_compose_section."""
    from aec_bench.adapters.lambda_rlm.config import LambdaRlmConfig, SandboxConfig
    from aec_bench.adapters.lambda_rlm.sandbox import DocumentSandbox

    # Build a sandbox with brief.md that has a #scope anchor
    sandbox = DocumentSandbox.from_documents(
        {"brief.md": "# Title\n\n## Scope\nAccess via Pass Office Gate 3."},
        extractor_overrides={},
    )

    # Capture the prompt sent to the LLM for the fill block
    captured_prompts: list[str] = []

    class _CapturingClient:
        def generate(self, *, model, messages, system_prompt):
            captured_prompts.append(messages[0].content)
            return RlmCompletionResponse(
                output_text=json.dumps({"access_point": "Pass Office Gate 3"}),
                input_tokens=100,
                output_tokens=10,
            )

    # Template uses brief.md#scope as the anchored source reference
    schema = DependencyTreeSchema(
        sections=(
            TreeSection(
                id="the_site",
                title="The Site",
                fields={"text": OutputField(name="text", dtype="str", description="")},
                depends_on=(),
                generation_mode="compose",
                blocks=(
                    FillBlock(
                        ref="the_site.access.access_route",
                        sources=("brief.md#scope",),
                    ),
                ),
            ),
        ),
    )
    template = ReportTemplate(schema)

    boilerplate = {
        "the_site": {
            "access": {
                "access_route": "The Contractor shall access via the {{access_point}}.",
            },
        },
    }
    plan = ExecutionPlan(
        section_order=["the_site"],
        section_plans={"the_site": _empty_section_plan("the_site")},
        skipped_sections=[],
    )
    config = LambdaRlmConfig(sandbox=SandboxConfig(enabled=True, tool_use=False))

    executor = PlanExecutor(
        client=_CapturingClient(),
        model="test-model",
        template=template,
        source_docs={},
        config=config,
        boilerplate_fragments=boilerplate,
        sandbox=sandbox,
    )

    executor.execute(plan)

    # The prompt must cite the anchor — proving the sandbox slice path ran
    assert len(captured_prompts) == 1
    assert "Source: brief.md (anchor: #scope)" in captured_prompts[0]


def test_compose_section_emits_provenance_in_composition_trace(tmp_path):
    """The composition_traces dict gains provenance, slot_provenance,
    declared_provenance, and fetched_provenance for generated-block entries."""
    from aec_bench.adapters.lambda_rlm.config import LambdaRlmConfig, SandboxConfig
    from aec_bench.adapters.lambda_rlm.sandbox import DocumentSandbox

    sandbox = DocumentSandbox.from_documents(
        {"brief.md": "# Title\n\n## Scope\nAccess via Pass Office Gate 3."},
        extractor_overrides={},
    )

    class _StubClient:
        def generate(self, *, model, messages, system_prompt):
            return RlmCompletionResponse(
                output_text=json.dumps({"access_point": "Pass Office Gate 3"}),
                input_tokens=50,
                output_tokens=8,
            )

    schema = DependencyTreeSchema(
        sections=(
            TreeSection(
                id="the_site",
                title="The Site",
                fields={"text": OutputField(name="text", dtype="str", description="")},
                depends_on=(),
                generation_mode="compose",
                blocks=(
                    FillBlock(
                        ref="the_site.access.access_route",
                        sources=("brief.md#scope",),
                    ),
                ),
            ),
        ),
    )
    template = ReportTemplate(schema)

    boilerplate = {
        "the_site": {
            "access": {
                "access_route": "The Contractor shall access via the {{access_point}}.",
            },
        },
    }
    plan = ExecutionPlan(
        section_order=["the_site"],
        section_plans={"the_site": _empty_section_plan("the_site")},
        skipped_sections=[],
    )
    config = LambdaRlmConfig(sandbox=SandboxConfig(enabled=True, tool_use=False))

    executor = PlanExecutor(
        client=_StubClient(),
        model="test-model",
        template=template,
        source_docs={},
        config=config,
        boilerplate_fragments=boilerplate,
        sandbox=sandbox,
    )

    state = executor.execute(plan)

    trace_entries = state.composition_traces["the_site"]
    assert len(trace_entries) == 1  # one fill block

    entry = trace_entries[0]
    # All four provenance fields must be present and be JSON-friendly types
    assert "provenance" in entry
    assert "slot_provenance" in entry
    assert "declared_provenance" in entry
    assert "fetched_provenance" in entry
    # They must be lists or dicts (not tuples — tuples are not JSON-serialisable)
    assert isinstance(entry["provenance"], list)
    assert isinstance(entry["slot_provenance"], dict)
    assert isinstance(entry["declared_provenance"], list)
    assert isinstance(entry["fetched_provenance"], list)


def test_executor_skips_compose_sections_when_no_boilerplate_supplied():
    """If a template declares compose blocks but the executor wasn't given
    fragments, the section should fail loudly rather than silently produce
    empty content or fall through to LLM generation."""
    plan = ExecutionPlan(
        section_order=["the_site"],
        section_plans={"the_site": _empty_section_plan("the_site")},
        skipped_sections=[],
    )
    executor = PlanExecutor(
        client=ReplayRlmClient([]),
        model="test-model",
        template=_compose_template(),
        source_docs={},
        config=LambdaRlmConfig(),
        # boilerplate_fragments omitted → defaults to {}
    )

    import pytest

    with pytest.raises(LookupError, match="the_site"):
        executor.execute(plan)
