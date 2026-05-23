# ABOUTME: KEYSTONE test for Idea B v1 acceptance.
# ABOUTME: Proves sandbox grounding flags the F8 LinkedIn-URL leak that
# ABOUTME: motivated the sixth hallucination prompt-tightening wave.

"""KEYSTONE TEST for Idea B v1 acceptance.

The 20260425 North Plant run produced output containing
'LinkedIn: www.linkedin.com/in/glenbodger' — a URL the agent fabricated from
background web research, not from any provenance source. This test reproduces
the leak shape and confirms grounding_report.json would flag the URL.

If this test ever fails, sandbox grounding is no longer catching the class of
leak that prompt rules from the F8 batch were trying to forbid by name.
"""

from aec_bench.adapters.lambda_rlm.grounding import run_grounding_check
from aec_bench.adapters.lambda_rlm.sandbox import DocumentSandbox


def _make_block_trace(start: int, end: int, provenance: tuple[str, ...]) -> dict:
    """Mirror the JSON-friendly shape executor._compose_section produces."""
    return {
        "block_index": 0,
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


def test_keystone_linkedin_url_flagged_when_not_in_provenance():
    """Idea B v1 acceptance: a fabricated LinkedIn URL is flagged.

    Section text is a realistic snippet from the 20260425 North Plant run. The
    declared provenance points to a brief whose Scope section does NOT contain
    any LinkedIn URL. The grounding check must flag the URL as ungrounded.
    """
    # Build a sandbox whose accessed slice does NOT contain the LinkedIn URL.
    sandbox = DocumentSandbox.from_documents(
        {
            "brief.md": (
                "## Scope\n"
                "ExampleCo will provide an options assessment for the North Plant "
                "casein air heater. Glen Bodger leads delivery as Technical "
                "Director, Process Systems."
            ),
        },
        extractor_overrides={},
    )

    # The actual leak shape: section text mentions Glen Bodger AND a LinkedIn
    # URL. Glen Bodger should ground (he's in the brief slice). The URL should
    # NOT ground (it's nowhere in any accessed slice).
    # Note: URL detector requires https?:// prefix; real-world leaks include it.
    section_text = (
        "Glen Bodger is the Technical Director, Process Systems at ExampleCo. "
        "LinkedIn: https://www.linkedin.com/in/glenbodger"
    )

    block_traces = [
        _make_block_trace(
            start=0,
            end=len(section_text),
            provenance=("brief.md#scope",),
        ),
    ]

    result = run_grounding_check(
        section_id="key_personnel",
        section_text=section_text,
        block_traces=block_traces,
        sandbox=sandbox,
    )

    # The keystone assertion: at least one flagged URL containing 'linkedin.com'.
    linkedin_flags = [f for f in result.flagged if f.category == "url" and "linkedin.com" in f.fact]
    assert linkedin_flags, (
        f"KEYSTONE FAILURE: LinkedIn URL was not flagged. Idea B's structural "
        f"fix is no longer catching the F8 leak class. Flagged: {result.flagged!r}"
    )
    assert linkedin_flags[0].block_provenance == ("brief.md#scope",)
    # No actual anchor contained the URL — matched_anchors stays empty.
    assert linkedin_flags[0].matched_anchors == ()


def test_keystone_grounded_facts_not_flagged():
    """Sanity: facts that DO appear in provenance slices are grounded."""
    sandbox = DocumentSandbox.from_documents(
        {"brief.md": "## Scope\nGlen Bodger leads delivery."},
        extractor_overrides={},
    )
    section_text = "Glen Bodger leads delivery."
    block_traces = [
        _make_block_trace(
            start=0,
            end=len(section_text),
            provenance=("brief.md#scope",),
        ),
    ]
    result = run_grounding_check(
        section_id="key_personnel",
        section_text=section_text,
        block_traces=block_traces,
        sandbox=sandbox,
    )
    pn_flags = [f for f in result.flagged if "Glen" in f.fact]
    assert pn_flags == [], "Glen Bodger should ground from #scope slice"
    assert result.facts_grounded >= 1
