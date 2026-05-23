# ABOUTME: Tests for lambda-rlm prompt template construction.
# ABOUTME: Validates extraction, review, generation, and reduce prompts contain required elements.

from aec_bench.adapters.lambda_rlm.prompts import (
    build_extraction_prompt,
    build_generation_prompt,
    build_reduce_prompt,
    build_review_prompt,
    build_structure_retry_guidance,
)
from aec_bench.adapters.lambda_rlm.structure_validator import FieldGap
from aec_bench.contracts.repl import OutputField


def test_extraction_prompt_contains_section_context():
    prompt = build_extraction_prompt(
        section_title="Methodology",
        generation_mode="guided",
        writing_guidance=["Paragraphs only", "Cite specific measurements"],
        source_label="brief:Scope of Works",
        chunk_text="The project scope includes road widening...",
        dependency_context={"background": "The project is on Princes Highway."},
    )
    assert "Methodology" in prompt
    assert "guided" in prompt
    assert "Paragraphs only" in prompt
    assert "Cite specific measurements" in prompt
    assert "brief:Scope of Works" in prompt
    assert "road widening" in prompt
    assert "Princes Highway" in prompt
    assert "JSON" in prompt


def test_extraction_prompt_without_dependencies():
    prompt = build_extraction_prompt(
        section_title="Background",
        generation_mode="transform",
        writing_guidance=["Carry language ~95% verbatim"],
        source_label="brief:Description",
        chunk_text="Project background text.",
        dependency_context={},
    )
    assert "Background" in prompt
    assert "Previously written" not in prompt


def test_extraction_prompt_requests_confidence() -> None:
    prompt = build_extraction_prompt(
        section_title="Background",
        generation_mode="transform",
        writing_guidance=["Carry language ~95% verbatim"],
        source_label="brief:Description",
        chunk_text="Project background text.",
        dependency_context={},
    )
    assert "__confidence__" in prompt
    assert "1.0 = all facts directly stated in the source" in prompt
    assert "0.0 = no relevant facts found" in prompt


def test_review_prompt_structure():
    prompt = build_review_prompt(
        section_title="Methodology",
        writing_guidance=["Paragraphs only", "Cite feasibility measurements"],
        input_sources=["brief:Scope", "feasibility:criteria"],
        extracted_data={"location": "Princes Highway", "speed": "80 km/h"},
        dependency_summaries={"design": "CHR treatment selected."},
    )
    assert "Methodology" in prompt
    assert "COMPLETENESS" in prompt
    assert "FAITHFULNESS" in prompt
    assert "RULE COMPLIANCE" in prompt
    assert "COHERENCE" in prompt
    assert "Princes Highway" in prompt
    assert "CHR treatment" in prompt
    assert "JSON" in prompt


def test_generation_prompt_includes_extracted_data():
    prompt = build_generation_prompt(
        section_title="Background",
        writing_guidance=["Carry language ~95% verbatim", "Include road designation"],
        extracted_data={
            "location": "Princes Highway",
            "objective": "Safety improvement",
        },
        dependency_sections={},
    )
    assert "Background" in prompt
    assert "Princes Highway" in prompt
    assert "Safety improvement" in prompt
    assert "Carry language" in prompt


def test_generation_prompt_includes_dependency_sections():
    prompt = build_generation_prompt(
        section_title="Design",
        writing_guidance=["Commit to preferred option"],
        extracted_data={"options": "CHR, BAR, MASH TL3"},
        dependency_sections={"background": "The project is on Princes Highway near Kogarah."},
    )
    assert "Design" in prompt
    assert "Kogarah" in prompt
    assert "CHR, BAR, MASH TL3" in prompt


def test_reduce_prompt_contains_inputs():
    prompt = build_reduce_prompt(
        section_title="Methodology",
        source_label="feasibility:full",
        extraction_results=[
            {"options": "CHR treatment"},
            {"geometry": "radius 150m"},
        ],
    )
    assert "Methodology" in prompt
    assert "CHR treatment" in prompt
    assert "radius 150m" in prompt
    assert "feasibility:full" in prompt


def test_build_generation_prompt_omits_block_when_no_required_fields() -> None:
    prompt = build_generation_prompt(
        section_title="X",
        writing_guidance=[],
        extracted_data={},
        dependency_sections={},
    )
    assert "MUST populate" not in prompt
    assert "Missing any required field" not in prompt


def test_build_generation_prompt_includes_required_fields_block() -> None:
    fields = (
        OutputField(name="number", dtype="str", description="ref", required=True),
        OutputField(name="title", dtype="str", description="title", required=True),
    )
    prompt = build_generation_prompt(
        section_title="Drawing Register",
        writing_guidance=["rule"],
        extracted_data={},
        dependency_sections={},
        required_fields=fields,
    )
    assert "MUST populate" in prompt
    assert "number [str]" in prompt and "ref" in prompt
    assert "title [str]" in prompt
    assert "Missing any required field will trigger regeneration" in prompt


def test_build_generation_prompt_filters_non_required_fields() -> None:
    fields = (
        OutputField(name="discipline", dtype="str", description="", required=False),
        OutputField(name="number", dtype="str", description="ref", required=True),
    )
    prompt = build_generation_prompt(
        section_title="X",
        writing_guidance=[],
        extracted_data={},
        dependency_sections={},
        required_fields=fields,
    )
    assert "discipline [str]" not in prompt
    assert "number [str]" in prompt


def test_build_structure_retry_guidance_lists_gaps() -> None:
    missing = (
        FieldGap(
            field_name="revision",
            dtype="str",
            kind="missing",
            locator="no rev letter",
        ),
    )
    malformed = (
        FieldGap(
            field_name="number",
            dtype="str",
            kind="malformed",
            locator="prose only",
        ),
    )
    text = build_structure_retry_guidance(missing=missing, malformed=malformed)
    assert "missing or malformed" in text.lower()
    assert "revision [str]: no rev letter" in text
    assert "number [str]: prose only" in text
    assert "Regenerate the section" in text
