# ABOUTME: Unit tests for the five-category fact detectors + matchers.
# ABOUTME: Each test names the leak pattern from Idea B's hallucination waves.

from aec_bench.adapters.lambda_rlm.grounding import extract_facts, match_fact_in_text

# ─── extract_facts: built-in categories ───────────────────────────────────────


def test_extract_url_facts_includes_linkedin():
    facts = extract_facts("See https://linkedin.com/in/x and http://example.com/page.")
    urls = [f.fact for f in facts if f.category == "url"]
    assert "https://linkedin.com/in/x" in urls
    assert any("example.com" in u for u in urls)


def test_extract_document_ref_facts():
    text = "per NZS 3604 and ISO 9001:2015 and EST11221 and AS/NZS 4773"
    facts = extract_facts(text)
    refs = [f.fact for f in facts if f.category == "document_ref"]
    assert any("NZS" in r and "3604" in r for r in refs)
    assert any("ISO" in r and "9001" in r for r in refs)
    assert any("EST11221" in r for r in refs)


def test_extract_number_with_unit_facts():
    text = "output 200m³/h at 1.5MW peak; site is 50m × 30m"
    facts = extract_facts(text)
    nums = [f.fact for f in facts if f.category == "number_with_unit"]
    # Tolerant of optional whitespace between number and unit
    assert any("200" in n and "m³" in n for n in nums)
    assert any("1.5" in n and "MW" in n for n in nums)


def test_extract_iso_dates():
    facts = extract_facts("Phase 1 by 2026-06-30; review on 2026-07-15.")
    dates = [f.fact for f in facts if f.category == "date"]
    assert "2026-06-30" in dates
    assert "2026-07-15" in dates


def test_extract_long_dates():
    facts = extract_facts("Due 30 June 2026 with kickoff on 1 July 2026.")
    dates = [f.fact for f in facts if f.category == "date"]
    assert any("June" in d for d in dates)
    assert any("July" in d for d in dates)


def test_extract_proper_noun_phrases():
    facts = extract_facts("Mark Abbott met Phil Smith at North Plant Plant yesterday.")
    pn = [f.fact for f in facts if f.category == "proper_noun_phrase"]
    assert "Mark Abbott" in pn
    assert "Phil Smith" in pn
    assert "North Plant Plant" in pn


def test_extract_proper_noun_filters_stopword_starts():
    facts = extract_facts("The Project covers Phase 2 of the works.")
    pn = [f.fact for f in facts if f.category == "proper_noun_phrase"]
    # 'The Project' starts with stopword 'The' and 'Project Covers' starts with stopword 'Project'
    # 'Phase 2' is filtered by stopword 'Phase'
    assert "The Project" not in pn


# ─── extract_facts: custom patterns ───────────────────────────────────────────


def test_extract_facts_supports_custom_pattern():
    import re

    custom = {"project_codes": re.compile(r"\b(?:EST|WWL|HCP)\d{5,6}\b")}
    facts = extract_facts("EST112345 vs unknown ABC9999.", custom_patterns=custom)
    refs = [f.fact for f in facts if f.category == "document_ref"]
    assert "EST112345" in refs


# ─── match_fact_in_text: category-specific rules ──────────────────────────────


def test_match_url_normalises_trailing_slash():
    assert match_fact_in_text(
        "https://linkedin.com/in/x",
        "url",
        "...see https://linkedin.com/in/x/ for details...",
    )


def test_match_url_normalises_query_params():
    assert match_fact_in_text(
        "https://linkedin.com/in/x",
        "url",
        "...visit https://linkedin.com/in/x?utm_source=email...",
    )


def test_match_document_ref_case_insensitive_whitespace_collapsed():
    assert match_fact_in_text("ISO 9001", "document_ref", "per iso  9001 standard")


def test_match_number_with_unit_strips_whitespace():
    assert match_fact_in_text("200 m³/h", "number_with_unit", "output of 200m³/h")


def test_match_iso_date_canonicalisation():
    assert match_fact_in_text("2026-06-30", "date", "due by 30 June 2026")


def test_match_long_date_canonicalisation():
    assert match_fact_in_text("30 June 2026", "date", "due 2026-06-30")


def test_match_proper_noun_phrase_within_window():
    # Both tokens within 50 chars in same text → match
    assert match_fact_in_text(
        "Mark Abbott",
        "proper_noun_phrase",
        "the meeting was led by Mark and his colleague Abbott yesterday",
    )


def test_match_proper_noun_phrase_tokens_too_far_apart_no_match():
    far_apart = "Mark went home. " + ("x " * 100) + "Abbott left later."
    assert not match_fact_in_text("Mark Abbott", "proper_noun_phrase", far_apart)


def test_match_no_match_returns_false():
    assert not match_fact_in_text("MISSING-CODE", "document_ref", "completely different text")
    assert not match_fact_in_text("https://nope.test/", "url", "no urls here")


# ─── run_grounding_check: end-to-end audit pass ───────────────────────────────


def _make_block_trace_dict(
    block_index: int,
    start: int,
    end: int,
    provenance: tuple[str, ...],
) -> dict:
    return {
        "block_index": block_index,
        "block_type": "generated",
        "text": "",
        "start_offset": start,
        "end_offset": end,
        "ref": None,
        "prompt": None,
        "sources": list(provenance),
        "resolved_slots": {},
        "provenance": list(provenance),
        "slot_provenance": {},
        "declared_provenance": list(provenance),
        "fetched_provenance": [],
    }


def test_run_grounding_check_flags_url_not_in_provenance():
    """Keystone shape: a LinkedIn URL not in any accessed slice gets flagged."""
    from aec_bench.adapters.lambda_rlm.grounding import run_grounding_check
    from aec_bench.adapters.lambda_rlm.sandbox import DocumentSandbox

    sandbox = DocumentSandbox.from_documents(
        {"brief.md": "## Scope\nExampleCo will deliver options assessment."},
        extractor_overrides={},
    )
    section_text = "ExampleCo will deliver, see https://linkedin.com/in/richard-smith for context."
    block_traces = [
        _make_block_trace_dict(
            block_index=0,
            start=0,
            end=len(section_text),
            provenance=("brief.md#scope",),
        ),
    ]
    result = run_grounding_check(
        section_id="scope_of_work",
        section_text=section_text,
        block_traces=block_traces,
        sandbox=sandbox,
    )
    assert result.section_id == "scope_of_work"
    linkedin_flags = [f for f in result.flagged if "linkedin.com" in f.fact]
    assert len(linkedin_flags) == 1
    assert linkedin_flags[0].category == "url"
    assert linkedin_flags[0].matched_anchors == ()
    assert linkedin_flags[0].block_provenance == ("brief.md#scope",)


def test_run_grounding_check_grounds_fact_present_in_slice():
    """A fact that DOES appear in an accessed slice is grounded, not flagged."""
    from aec_bench.adapters.lambda_rlm.grounding import run_grounding_check
    from aec_bench.adapters.lambda_rlm.sandbox import DocumentSandbox

    sandbox = DocumentSandbox.from_documents(
        {"brief.md": "## Scope\nMark Abbott chairs the meeting."},
        extractor_overrides={},
    )
    section_text = "Mark Abbott will chair."
    block_traces = [
        _make_block_trace_dict(
            block_index=0,
            start=0,
            end=len(section_text),
            provenance=("brief.md#scope",),
        ),
    ]
    result = run_grounding_check(
        section_id="s",
        section_text=section_text,
        block_traces=block_traces,
        sandbox=sandbox,
    )
    # Mark Abbott should be grounded (appears in #scope slice)
    flagged_pn = [f for f in result.flagged if "Mark" in f.fact]
    assert flagged_pn == []  # not flagged
    assert result.facts_grounded >= 1


def test_run_grounding_check_skips_facts_outside_any_block():
    """Facts whose offsets don't fall inside any block are silently skipped."""
    from aec_bench.adapters.lambda_rlm.grounding import run_grounding_check
    from aec_bench.adapters.lambda_rlm.sandbox import DocumentSandbox

    sandbox = DocumentSandbox.from_documents(
        {"brief.md": "scope"},
        extractor_overrides={},
    )
    # Section text has a URL but block_traces[0] only covers the first 5 chars.
    section_text = "abcde https://linkedin.com/in/x"
    block_traces = [
        _make_block_trace_dict(
            block_index=0,
            start=0,
            end=5,
            provenance=("brief.md",),
        ),
    ]
    result = run_grounding_check(
        section_id="s",
        section_text=section_text,
        block_traces=block_traces,
        sandbox=sandbox,
    )
    # The URL isn't inside block 0 (which ends at offset 5) → skipped, not flagged.
    assert all("linkedin" not in f.fact for f in result.flagged)


def test_run_grounding_check_handles_stale_anchor_silently():
    """If a provenance anchor isn't in the sandbox, no crash — just no match."""
    from aec_bench.adapters.lambda_rlm.grounding import run_grounding_check
    from aec_bench.adapters.lambda_rlm.sandbox import DocumentSandbox

    sandbox = DocumentSandbox.from_documents(
        {"brief.md": "## Real\nreal text"},
        extractor_overrides={},
    )
    section_text = "Some Mark Abbott reference."
    block_traces = [
        _make_block_trace_dict(
            block_index=0,
            start=0,
            end=len(section_text),
            provenance=("brief.md#nonexistent",),  # bad anchor
        ),
    ]
    # Should not raise; the fact is flagged because no slice text could be fetched.
    result = run_grounding_check(
        section_id="s",
        section_text=section_text,
        block_traces=block_traces,
        sandbox=sandbox,
    )
    # Mark Abbott couldn't be matched to a missing slice → flagged.
    pn_flags = [f for f in result.flagged if "Mark" in f.fact]
    assert len(pn_flags) == 1


def test_run_grounding_check_aggregates_facts_checked_and_grounded():
    """facts_checked = total located in some block; facts_grounded = those that matched."""
    from aec_bench.adapters.lambda_rlm.grounding import run_grounding_check
    from aec_bench.adapters.lambda_rlm.sandbox import DocumentSandbox

    sandbox = DocumentSandbox.from_documents(
        {"brief.md": "## Scope\nExampleCo will deliver per ISO 9001."},
        extractor_overrides={},
    )
    # Section has two facts: ISO 9001 (should ground) and an unrelated URL (should flag).
    section_text = "Per ISO 9001 see https://nope.test/page."
    block_traces = [
        _make_block_trace_dict(
            block_index=0,
            start=0,
            end=len(section_text),
            provenance=("brief.md#scope",),
        ),
    ]
    result = run_grounding_check(
        section_id="s",
        section_text=section_text,
        block_traces=block_traces,
        sandbox=sandbox,
    )
    assert result.facts_checked >= 2
    assert result.facts_grounded >= 1  # ISO 9001 grounded
    flagged_urls = [f for f in result.flagged if f.category == "url"]
    assert len(flagged_urls) == 1


# ─── False-positive fixes from live North Plant run 20260425-162255 ───────────────


def test_proper_noun_regex_does_not_match_all_caps_headings():
    """ALL CAPS headings (e.g. 'ADDRESS FOR NOTICES') must NOT match the
    proper-noun regex. Previously these would match because [a-zA-Z] allows
    uppercase tokens; now restricted to title-case [A-Z][a-z]+."""
    facts = extract_facts("ADDRESS FOR NOTICES\n\nExample Dairy Limited")
    pn = [f.fact for f in facts if f.category == "proper_noun_phrase"]
    # 'ADDRESS FOR NOTICES' must not appear; 'Example Dairy Limited' may appear
    # (legitimate title-case proper-noun phrase).
    assert not any("ADDRESS" in f for f in pn)
    assert not any("NOTICES" in f for f in pn)


def test_proper_noun_regex_does_not_span_newlines():
    """A title-case word followed by a heading break and another title-case
    word must NOT collapse into a single phrase."""
    facts = extract_facts("Mark\n\nExample Dairy Limited")
    pn = [f.fact for f in facts if f.category == "proper_noun_phrase"]
    # 'Mark Example Dairy' should not appear as a phrase
    assert not any(p == "Mark Example Dairy" or "Mark\n" in p for p in pn)


def test_run_grounding_check_skips_blocks_with_empty_provenance():
    """Blocks with no declared sources (verbatim, scratchpad-only fills) are
    skipped — they don't count toward facts_checked or get flagged."""
    from aec_bench.adapters.lambda_rlm.grounding import run_grounding_check
    from aec_bench.adapters.lambda_rlm.sandbox import DocumentSandbox

    sandbox = DocumentSandbox.from_documents(
        {"brief.md": "## Scope\nbody"},
        extractor_overrides={},
    )
    section_text = "Mark Abbott meets Phil Smith on 2026-06-30."
    block_traces = [
        # Block has empty provenance — auditing it would just produce noise.
        {
            "block_index": 0,
            "block_type": "verbatim",
            "text": section_text,
            "start_offset": 0,
            "end_offset": len(section_text),
            "ref": None,
            "prompt": None,
            "sources": [],
            "resolved_slots": {},
            "provenance": [],
            "slot_provenance": {},
            "declared_provenance": [],
            "fetched_provenance": [],
        },
    ]
    result = run_grounding_check(
        section_id="s",
        section_text=section_text,
        block_traces=block_traces,
        sandbox=sandbox,
    )
    # Nothing audited because no block had declared provenance.
    assert result.facts_checked == 0
    assert result.facts_grounded == 0
    assert result.flagged == ()


def test_proper_noun_stopwords_filter_signature_block_table_labels():
    """Signature-block and term-section flags from North Plant run 20260425-163325:
    'Name Mark Abbott', 'Position Project Manager', 'This Statement' all started
    with stopwords that table-header rendering produced. Test confirms they no
    longer match as proper-noun phrases.

    Note on accepted limitation: when a stopword-prefixed phrase is greedy-matched
    by the regex (e.g. 'Name Mark Abbott'), the inner 'Mark Abbott' is NOT
    separately recovered — Python's regex engine doesn't backtrack into matched
    spans. Recovering inner names would require NER, which is out of scope
    for the v1 deterministic-regex detector. The pragmatic consequence: when
    a name is wrapped by a stopword, both the wrapped phrase AND the inner
    name go un-flagged. This is preferable to false positives.
    """
    text = "Name Mark Abbott | Position Project Manager\nThis Statement of Work covers"
    facts = extract_facts(text)
    pn = [f.fact for f in facts if f.category == "proper_noun_phrase"]
    # The stopword-prefixed phrases must be filtered.
    assert "Name Mark Abbott" not in pn
    assert "Position Project Manager" not in pn
    assert "This Statement" not in pn


def test_proper_noun_captures_name_when_not_stopword_prefixed():
    """A name that appears outside a stopword wrapper is still captured."""
    facts = extract_facts("The meeting was led by Mark Abbott yesterday afternoon.")
    pn = [f.fact for f in facts if f.category == "proper_noun_phrase"]
    assert "Mark Abbott" in pn


# ─── Back-brief integration (v1.1, North Plant run 20260425-171114) ───────────────
#
# Every flagged fact in the 20260425-171114 run had `references/*:<topic>` in
# its provenance — a back-brief topic reference. Without back-brief threading,
# `_slice_texts` silently drops these refs (parse_anchor_ref raises on '*'),
# so the audit pool can never see legitimate back-brief content. These tests
# pin the v1.1 behaviour: back-brief acts as a slice source that mirrors the
# compose_bridge._format_sandbox_sources resolution order.


def test_back_brief_topic_grounds_fact_present_in_topic_text():
    """Provenance `references/*:<topic>` + back_brief[<topic>] containing the
    fact → fact is grounded, not flagged. Mirrors the live-run pattern where
    'North Plant Rennet Casein' (back-brief content) was being marked as
    ungrounded purely because the auditor couldn't see back-brief text."""
    from aec_bench.adapters.lambda_rlm.grounding import run_grounding_check
    from aec_bench.adapters.lambda_rlm.sandbox import DocumentSandbox

    sandbox = DocumentSandbox.from_documents(
        {"brief.md": "## Scope\nUnrelated content."},
        extractor_overrides={},
    )
    section_text = "The works cover North Plant Rennet Casein production."
    block_traces = [
        _make_block_trace_dict(
            block_index=0,
            start=0,
            end=len(section_text),
            provenance=("references/*:services",),
        ),
    ]
    back_brief = {
        "services": "Scope covers North Plant Rennet Casein air heater upgrade.",
    }
    result = run_grounding_check(
        section_id="description_of_services",
        section_text=section_text,
        block_traces=block_traces,
        sandbox=sandbox,
        back_brief=back_brief,
    )
    pn_flags = [f for f in result.flagged if "North Plant" in f.fact]
    assert pn_flags == []
    assert result.facts_grounded >= 1


def test_back_brief_missing_topic_still_flags_fact():
    """If provenance is `references/*:<topic>` but back_brief has no entry for
    that topic, the fact has no slice source and stays flagged. Confirms the
    audit doesn't silently exonerate facts whose claimed source is empty."""
    from aec_bench.adapters.lambda_rlm.grounding import run_grounding_check
    from aec_bench.adapters.lambda_rlm.sandbox import DocumentSandbox

    sandbox = DocumentSandbox.from_documents(
        {"brief.md": "## Scope\nbody"},
        extractor_overrides={},
    )
    section_text = "The works cover North Plant Rennet Casein production."
    block_traces = [
        _make_block_trace_dict(
            block_index=0,
            start=0,
            end=len(section_text),
            provenance=("references/*:equipment",),
        ),
    ]
    back_brief = {"services": "wrong topic, no North Plant mention here"}
    result = run_grounding_check(
        section_id="equipment_by_fonterra",
        section_text=section_text,
        block_traces=block_traces,
        sandbox=sandbox,
        back_brief=back_brief,
    )
    pn_flags = [f for f in result.flagged if "North Plant" in f.fact]
    assert len(pn_flags) == 1


def test_back_brief_omitted_preserves_legacy_skip_behaviour():
    """When back_brief is not passed, `references/*:<topic>` refs continue to
    parse-fail and get silently dropped (legacy v1 behaviour). Facts then have
    no slice source and are flagged — confirms we haven't broken the existing
    contract for callers that don't know about back-brief."""
    from aec_bench.adapters.lambda_rlm.grounding import run_grounding_check
    from aec_bench.adapters.lambda_rlm.sandbox import DocumentSandbox

    sandbox = DocumentSandbox.from_documents(
        {"brief.md": "## Scope\nbody"},
        extractor_overrides={},
    )
    section_text = "The works cover North Plant Rennet Casein production."
    block_traces = [
        _make_block_trace_dict(
            block_index=0,
            start=0,
            end=len(section_text),
            provenance=("references/*:services",),
        ),
    ]
    result = run_grounding_check(
        section_id="s",
        section_text=section_text,
        block_traces=block_traces,
        sandbox=sandbox,
        # back_brief omitted
    )
    pn_flags = [f for f in result.flagged if "North Plant" in f.fact]
    assert len(pn_flags) == 1


def test_back_brief_mixed_with_sandbox_anchor_provenance():
    """A block with mixed provenance — one normal anchor + one back-brief topic
    — grounds facts found in either source. The auditor must consult both."""
    from aec_bench.adapters.lambda_rlm.grounding import run_grounding_check
    from aec_bench.adapters.lambda_rlm.sandbox import DocumentSandbox

    sandbox = DocumentSandbox.from_documents(
        {"brief.md": "## Scope\nMark Abbott chairs the project."},
        extractor_overrides={},
    )
    section_text = "Mark Abbott will deliver North Plant Rennet Casein scope."
    block_traces = [
        _make_block_trace_dict(
            block_index=0,
            start=0,
            end=len(section_text),
            provenance=("brief.md#scope", "references/*:services"),
        ),
    ]
    back_brief = {"services": "North Plant Rennet Casein upgrade is the focus."}
    result = run_grounding_check(
        section_id="s",
        section_text=section_text,
        block_traces=block_traces,
        sandbox=sandbox,
        back_brief=back_brief,
    )
    # Both 'Mark Abbott' (sandbox) and 'North Plant Rennet Casein' (back-brief)
    # should ground; nothing flagged.
    assert result.flagged == ()
    assert result.facts_grounded >= 2
