# ABOUTME: Tests that SourceFidelityParams + InformationMinimalityParams flow into prompts.
# ABOUTME: Backwards-compat verified: omitting kwargs produces identical output to pre-change.

from aec_bench.adapters.lambda_rlm.config import LambdaRlmConfig
from aec_bench.adapters.lambda_rlm.executor import PlanExecutor
from aec_bench.adapters.lambda_rlm.prompts import (
    build_extraction_prompt,
    build_generation_prompt,
    build_review_prompt,
)
from aec_bench.adapters.rlm.client import ReplayRlmClient
from aec_bench.adapters.rlm.template import ReportTemplate
from aec_bench.contracts.constitution import (
    InformationMinimalityParams,
    SourceFidelityParams,
)
from aec_bench.contracts.repl import DependencyTreeSchema, OutputField, TreeSection


def _minimal_template() -> ReportTemplate:
    """Single-section template — used only to satisfy PlanExecutor construction."""
    return ReportTemplate(
        DependencyTreeSchema(
            sections=(
                TreeSection(
                    id="intro",
                    title="Intro",
                    fields={"body": OutputField(name="body", dtype="str", description="")},
                    depends_on=(),
                    generation_mode="transform",
                    writing_guidance=(),
                    input_mapping=(),
                ),
            )
        )
    )


def test_extraction_prompt_default_enforces_tracing_clause():
    """Without source_fidelity kwarg, the explicit-statement clause is present."""
    prompt = build_extraction_prompt(
        section_title="Scope",
        generation_mode="prose",
        writing_guidance=["be crisp"],
        source_label="brief.md",
        chunk_text="alpha\nbravo",
        dependency_context={},
    )
    assert "explicitly stated" in prompt


def test_extraction_prompt_tracing_disabled_drops_clause():
    params = SourceFidelityParams(
        require_source_tracing=False,
        tbd_placeholder="[TBD]",
        gap_framing="tbd",
    )
    prompt = build_extraction_prompt(
        section_title="Scope",
        generation_mode="prose",
        writing_guidance=["be crisp"],
        source_label="brief.md",
        chunk_text="alpha",
        dependency_context={},
        source_fidelity=params,
    )
    assert "explicitly stated" not in prompt


def test_extraction_prompt_preview_length_caps_dependency_context():
    info_min = InformationMinimalityParams(
        default_threshold=2000,
        search_threshold=10_000,
        preview_length=50,
        truncation_strategy="metadata",
    )
    long_content = "A" * 600
    prompt = build_extraction_prompt(
        section_title="Scope",
        generation_mode="prose",
        writing_guidance=["crisp"],
        source_label="brief.md",
        chunk_text="alpha",
        dependency_context={"intro": long_content},
        information_minimality=info_min,
    )
    assert "A" * 50 in prompt
    assert "A" * 51 not in prompt


def test_extraction_prompt_default_preview_length_is_500():
    """Without information_minimality kwarg, dependency_context truncates at 500."""
    long_content = "B" * 600
    prompt = build_extraction_prompt(
        section_title="Scope",
        generation_mode="prose",
        writing_guidance=["crisp"],
        source_label="brief.md",
        chunk_text="alpha",
        dependency_context={"intro": long_content},
    )
    assert "B" * 500 in prompt
    assert "B" * 501 not in prompt


def test_generation_prompt_default_uses_tbd_placeholder():
    """Without source_fidelity kwarg, the default [TBD] anti-fabrication language is present."""
    prompt = build_generation_prompt(
        section_title="Scope",
        writing_guidance=["crisp"],
        extracted_data={"fact": "v"},
        dependency_sections={},
    )
    assert "[TBD]" in prompt


def test_generation_prompt_gap_framing_tbd_uses_custom_placeholder():
    params = SourceFidelityParams(
        require_source_tracing=True,
        tbd_placeholder="[NEEDS CONFIRMATION]",
        gap_framing="tbd",
    )
    prompt = build_generation_prompt(
        section_title="Scope",
        writing_guidance=["crisp"],
        extracted_data={"fact": "v"},
        dependency_sections={},
        source_fidelity=params,
    )
    assert "[NEEDS CONFIRMATION]" in prompt


def test_generation_prompt_gap_framing_exclude_adds_exclude_clause():
    params = SourceFidelityParams(
        require_source_tracing=True,
        tbd_placeholder="[TBD]",
        gap_framing="exclude",
    )
    prompt = build_generation_prompt(
        section_title="Scope",
        writing_guidance=["crisp"],
        extracted_data={"fact": "v"},
        dependency_sections={},
        source_fidelity=params,
    )
    assert "excluded or reframed" in prompt


def test_generation_prompt_gap_framing_omit_adds_omit_clause():
    params = SourceFidelityParams(
        require_source_tracing=True,
        tbd_placeholder="[TBD]",
        gap_framing="omit",
    )
    prompt = build_generation_prompt(
        section_title="Scope",
        writing_guidance=["crisp"],
        extracted_data={"fact": "v"},
        dependency_sections={},
        source_fidelity=params,
    )
    assert "Missing data must be omitted" in prompt


def test_review_prompt_emits_gap_framing_policy_check():
    params = SourceFidelityParams(
        require_source_tracing=True,
        tbd_placeholder="[TBD]",
        gap_framing="exclude",
    )
    prompt = build_review_prompt(
        section_title="Scope",
        writing_guidance=["crisp"],
        input_sources=["brief.md"],
        extracted_data={"a": 1},
        dependency_summaries={},
        source_fidelity=params,
    )
    assert "5. GAP FRAMING" in prompt
    assert "'exclude'" in prompt


def test_review_prompt_without_source_fidelity_omits_gap_framing_check():
    prompt = build_review_prompt(
        section_title="Scope",
        writing_guidance=["crisp"],
        input_sources=["brief.md"],
        extracted_data={"a": 1},
        dependency_summaries={},
    )
    assert "5. GAP FRAMING" not in prompt
    assert "Gap framing policy" not in prompt


def test_executor_accepts_constitution_params():
    """PlanExecutor should accept source_fidelity and information_minimality kwargs."""
    executor = PlanExecutor(
        client=ReplayRlmClient([]),
        model="test-model",
        template=_minimal_template(),
        source_docs={},
        config=LambdaRlmConfig(),
        trajectory_callback=None,
        source_fidelity=SourceFidelityParams(
            require_source_tracing=True,
            tbd_placeholder="[TBD]",
            gap_framing="exclude",
        ),
        information_minimality=InformationMinimalityParams(
            default_threshold=2000,
            search_threshold=10_000,
            preview_length=300,
            truncation_strategy="metadata",
        ),
    )
    assert executor._source_fidelity is not None
    assert executor._information_minimality is not None
    assert executor._source_fidelity.gap_framing == "exclude"
    assert executor._information_minimality.preview_length == 300


def test_executor_defaults_constitution_params_to_none():
    """Without kwargs, PlanExecutor's constitution params default to None (back-compat)."""
    executor = PlanExecutor(
        client=ReplayRlmClient([]),
        model="test-model",
        template=_minimal_template(),
        source_docs={},
        config=LambdaRlmConfig(),
        trajectory_callback=None,
    )
    assert executor._source_fidelity is None
    assert executor._information_minimality is None
