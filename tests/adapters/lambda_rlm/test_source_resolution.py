# ABOUTME: Tests for lambda-RLM source label resolution and unresolved-source auditing.
# ABOUTME: Covers exact labels, colon-suffixed labels, special references, and misses.

from aec_bench.adapters.lambda_rlm.source_resolution import (
    SourceResolution,
    audit_section_sources,
    resolve_source_label,
)


def test_resolve_source_label_exact_match() -> None:
    docs = {"supplementary/03-hpaa-study": "HPAA text"}

    result = resolve_source_label("supplementary/03-hpaa-study", docs)

    assert result == SourceResolution(
        requested="supplementary/03-hpaa-study",
        resolved="supplementary/03-hpaa-study",
        content="HPAA text",
    )


def test_resolve_source_label_uses_doc_part_before_colon() -> None:
    docs = {"brief": "Brief text"}

    result = resolve_source_label("brief:Scope", docs)

    assert result.resolved == "brief"
    assert result.content == "Brief text"


def test_resolve_source_label_does_not_guess_semantic_directory_labels() -> None:
    docs = {"supplementary/03-hpaa-study": "HPAA text"}

    result = resolve_source_label("supplementary:HPAA Study and Concept Design Report", docs)

    assert result.resolved is None
    assert result.content == ""


def test_audit_section_sources_ignores_back_brief_wildcard_refs() -> None:
    sections = [
        {
            "id": "deliverables",
            "input_mapping": ["email_thread", "references/*:deliverables"],
        },
    ]
    docs = {"email_thread": "Thread text"}

    unresolved = audit_section_sources(sections, docs)

    assert unresolved == []


def test_audit_section_sources_reports_unresolved_regular_refs() -> None:
    sections = [
        {
            "id": "design",
            "input_mapping": ["brief:Scope", "feasibility:design_options"],
        },
    ]
    docs = {"brief": "Brief text"}

    unresolved = audit_section_sources(sections, docs)

    assert unresolved == [
        {"section_id": "design", "source": "feasibility:design_options"},
    ]
