# ABOUTME: Prompt templates for the lambda-rlm adapter phases.
# ABOUTME: Builds structured prompts for extraction, review, generation, and reduce operations.

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from aec_bench.contracts.constitution import (
    InformationMinimalityParams,
    SourceFidelityParams,
)
from aec_bench.contracts.repl import OutputField


def build_extraction_prompt(
    *,
    section_title: str,
    generation_mode: str,
    writing_guidance: list[str],
    source_label: str,
    chunk_text: str,
    dependency_context: dict[str, str],
    source_fidelity: SourceFidelityParams | None = None,
    information_minimality: InformationMinimalityParams | None = None,
    source_priority: int | None = None,
) -> str:
    """Build a leaf extraction prompt for a source chunk."""
    guidance_lines = "\n".join(f"- {rule}" for rule in writing_guidance)
    preview_length = information_minimality.preview_length if information_minimality is not None else 500
    require_tracing = source_fidelity.require_source_tracing if source_fidelity is not None else True

    parts = [
        "You are extracting information from a document section.",
        "",
        f"Target section: {section_title}",
        f"Generation mode: {generation_mode}",
        "",
        "Writing guidance:",
        guidance_lines,
    ]

    if dependency_context:
        parts.append("")
        parts.append("Previously written sections for context:")
        for sec_id, content in dependency_context.items():
            parts.append(f"### {sec_id}")
            parts.append(content[:preview_length])

    parts.extend(
        [
            "",
            f"Source: {source_label}",
            "---",
            chunk_text,
            "---",
            "",
            "Return a JSON object with keys you consider relevant for writing this section.",
            ("Each key should be a descriptive snake_case name. Each value should be the extracted fact or text."),
            ("Extract specific values (names, numbers, dates, abbreviations) rather than vague summaries."),
            ("Also include a top-level key named __confidence__ with a float between 0.0 and 1.0."),
            (
                "Use this scale: 1.0 = all facts directly stated in the source; "
                "0.0 = no relevant facts found. Use your judgment for values in between."
            ),
        ]
    )

    if require_tracing:
        parts.append(
            "IMPORTANT: Extract only what is explicitly stated in the source text. "
            "Do not expand acronyms unless the source text provides the expansion. "
            "Do not infer or fabricate values that are not present in the text."
        )

    if source_priority is not None:
        parts.append("")
        parts.append(
            f"This source has priority {source_priority} "
            "(lower number = higher authority). Extract facts carefully; "
            "higher-authority sources take precedence over lower-authority "
            "ones when they disagree."
        )

    return "\n".join(parts)


def build_review_prompt(
    *,
    section_title: str,
    writing_guidance: list[str],
    input_sources: list[str],
    extracted_data: dict[str, Any],
    dependency_summaries: dict[str, str],
    source_fidelity: SourceFidelityParams | None = None,
    source_priority: Mapping[str, int] | None = None,
) -> str:
    """Build a contract review prompt checking extraction alignment."""
    guidance_lines = "\n".join(f"- {rule}" for rule in writing_guidance)
    sources_lines = "\n".join(f"- {s}" for s in input_sources)

    parts = [
        "You are reviewing extracted data before it is used to write a report section.",
        "",
        f"Section: {section_title}",
        "",
        "Writing guidance rules:",
        guidance_lines,
        "",
        "Required input sources:",
        sources_lines,
        "",
        "Extracted data:",
        json.dumps(extracted_data, indent=2, default=str),
    ]

    if dependency_summaries:
        parts.append("")
        parts.append("Dependency sections already written:")
        for sec_id, summary in dependency_summaries.items():
            parts.append(f"### {sec_id}")
            parts.append(summary[:300])

    parts.extend(
        [
            "",
            "Check the following:",
            ("1. COMPLETENESS — Does the extracted data cover all fields listed in the section definition?"),
            ("2. FAITHFULNESS — Are extracted values specific (names, numbers, dates) rather than vague summaries?"),
            ("3. RULE COMPLIANCE — Will the writing guidance rules be satisfiable from this data?"),
            (
                "   Flag each rule as: COVERED (data supports it), GAP (data missing), "
                "or RISK (data present but ambiguous)."
            ),
            ("4. COHERENCE — Does the extracted data align with what dependency sections established?"),
        ]
    )

    if source_fidelity is not None:
        parts.append(
            f"5. GAP FRAMING — Flag any gap so the generator can honour the "
            f"'{source_fidelity.gap_framing}' policy (exclude | tbd | omit)."
        )

    if source_priority and len(set(source_priority.values())) > 1:
        max_tier = max(source_priority.values())
        lower_authority = [s for s, t in source_priority.items() if t == max_tier]
        parts.append("")
        parts.append(
            f"Note: {', '.join(lower_authority)} are lower-authority sources "
            f"(priority {max_tier}). Do NOT flag as gaps any facts that are missing "
            "from lower-authority sources but present in higher-authority ones."
        )

    parts.extend(
        [
            "",
            "Return a JSON object:",
            "{",
            '  "status": "pass" | "needs_reextract" | "needs_supplement",',
            '  "gaps": ["list of specific gaps"],',
            '  "risks": ["list of specific risks"],',
            '  "reextract_sources": ["source labels that need another pass, if any"],',
            '  "supplement_guidance": "what additional extraction is needed, if any"',
            "}",
        ]
    )

    return "\n".join(parts)


def _summarise_data_availability(extracted_data: dict[str, Any]) -> str:
    """Build a plain-language summary of which sources have data and which are empty."""
    if not extracted_data:
        return "WARNING: No data was extracted for this section. All content must use [TBD] placeholders."

    available: list[str] = []
    empty: list[str] = []
    for key, value in extracted_data.items():
        if value is None or value == {} or value == [] or value == "":
            empty.append(key)
        elif isinstance(value, dict) and all(v is None or v == "" or v == {} or v == [] for v in value.values()):
            empty.append(key)
        else:
            available.append(key)

    lines = []
    if available:
        lines.append(f"Data available from: {', '.join(available)}")
    if empty:
        lines.append(
            f"NO DATA available from: {', '.join(empty)} — use [TBD] for any details "
            f"that would come from these sources. Do NOT fabricate values to fill these gaps."
        )
    return "\n".join(lines)


def build_generation_prompt(
    *,
    section_title: str,
    writing_guidance: list[str],
    extracted_data: dict[str, Any],
    dependency_sections: dict[str, str],
    review_gaps: list[str] | None = None,
    review_risks: list[str] | None = None,
    source_fidelity: SourceFidelityParams | None = None,
    source_priority: Mapping[str, int] | None = None,
    required_fields: Sequence[OutputField] | None = None,
) -> str:
    """Build a section generation prompt from extracted data."""
    guidance_lines = "\n".join(f"- {rule}" for rule in writing_guidance)
    availability = _summarise_data_availability(extracted_data)

    parts = [
        f'You are writing the "{section_title}" section of a report.',
        "",
        "Writing guidance:",
        guidance_lines,
        "",
        "Data availability:",
        availability,
        "",
        "Extracted data:",
        json.dumps(extracted_data, indent=2, default=str),
    ]

    if dependency_sections:
        parts.append("")
        parts.append("Previously written sections for context:")
        for sec_id, content in dependency_sections.items():
            parts.append(f"### {sec_id}")
            parts.append(content)

    if source_priority and len(set(source_priority.values())) > 1:
        sorted_sources = sorted(source_priority.items(), key=lambda kv: kv[1])
        parts.append("")
        parts.append("Source precedence (ordered by authority):")
        for src, tier in sorted_sources:
            parts.append(f"- Tier {tier}: {src}")
        parts.append(
            "When sources disagree on a specific fact, use the value from "
            "the higher-authority source (lower tier number)."
        )

    # Review insights — risks passed as corrections, gaps as exclusions
    if review_risks:
        parts.append("")
        parts.append("Review corrections (fix these using extracted data):")
        for risk in review_risks:
            parts.append(f"  - {risk}")

    if review_gaps:
        parts.append("")
        parts.append(
            "The following topics LACK source data — omit them or write [TBD]. "
            "Do NOT attempt to fill these from your own knowledge:"
        )
        for gap in review_gaps:
            parts.append(f"  - {gap}")

    if required_fields:
        enforced = [f for f in required_fields if f.required]
        if enforced:
            parts.append("")
            parts.append("This section MUST populate the following fields:")
            for f in enforced:
                parts.append(f"- {f.name} [{f.dtype}] — {f.description}")
            parts.append("Missing any required field will trigger regeneration.")

    parts.extend(
        [
            "",
            "Write the section content. Follow the writing guidance rules exactly.",
            "",
            "CRITICAL — Use ONLY the extracted data provided above:",
            "- Do NOT add document names, standards, or references from your own knowledge.",
            (
                "- Do NOT invent acronym expansions. If an acronym is not expanded "
                "in the extracted data, use the acronym only."
            ),
            (
                "- Do NOT fabricate contact names, email addresses, project "
                "references, bulletin numbers, or procedure references."
            ),
            ("- If a source had NO DATA (listed above), write [TBD] for any detail that would come from that source."),
            (
                "- Do NOT satisfy writing guidance rules by inventing plausible-"
                "sounding values. A [TBD] is always better than a fabrication."
            ),
            ("- Every fact, name, number, and reference in your output must be traceable to the extracted data above."),
        ]
    )

    if source_fidelity is not None:
        if source_fidelity.gap_framing == "exclude":
            parts.append(
                "- Missing data must cause the sentence to be excluded or reframed "
                "around what is present. Never fabricate values."
            )
        elif source_fidelity.gap_framing == "omit":
            parts.append("- Missing data must be omitted. Never fabricate values.")

    prompt = "\n".join(parts)

    if source_fidelity is not None and source_fidelity.tbd_placeholder != "[TBD]":
        prompt = prompt.replace("[TBD]", source_fidelity.tbd_placeholder)

    return prompt


def build_reduce_prompt(
    *,
    section_title: str,
    source_label: str,
    extraction_results: list[dict[str, Any]],
) -> str:
    """Build a reduce prompt that merges chunked extraction results."""
    parts = [
        "You are merging extraction results from multiple chunks of the same source document.",
        "",
        f"Target section: {section_title}",
        f"Source: {source_label}",
        "",
        "The following extractions were produced from different chunks of this source.",
        "Merge them into a single JSON object, combining complementary facts and deduplicating.",
        "",
    ]

    for i, result in enumerate(extraction_results):
        parts.append(f"Chunk {i + 1}:")
        parts.append(json.dumps(result, indent=2, default=str))
        parts.append("")

    parts.extend(
        [
            "Return a single merged JSON object with all relevant extracted data.",
            "Prefer specific values over vague ones. Deduplicate where chunks overlap.",
        ]
    )

    return "\n".join(parts)


def build_structure_retry_guidance(
    *,
    missing: Sequence[Any],
    malformed: Sequence[Any],
) -> str:
    """Build the retry addendum that lists gaps from a previous attempt.

    Caller passes the missing/malformed FieldGap tuples from the
    StructureValidationResult; this helper formats them as a single
    block to be appended to the regeneration prompt.
    """
    lines = [
        "Your previous attempt was missing or malformed for these required fields:",
    ]
    for gap in missing:
        locator = gap.locator or "not detectable in the section content"
        lines.append(f"- {gap.field_name} [{gap.dtype}]: {locator}")
    for gap in malformed:
        locator = gap.locator or "value present but in an unrecognisable format"
        lines.append(f"- {gap.field_name} [{gap.dtype}]: {locator}")
    lines.append("Regenerate the section, populating every required field correctly.")
    return "\n".join(lines)
