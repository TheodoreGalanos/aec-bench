# ABOUTME: Unit tests for the GroundingReport boundary type.
# ABOUTME: Verifies aggregation methods + JSON round-trip.

from aec_bench.contracts.grounding_report import (
    FlaggedFact,
    GroundingReport,
    SectionGroundingResult,
)


def test_grounding_report_constructs_with_empty_sections():
    report = GroundingReport(sections=())
    assert report.sections == ()
    assert report.total_facts_checked() == 0
    assert report.total_facts_grounded() == 0


def test_section_grounding_result_carries_flagged_facts():
    flagged = FlaggedFact(
        fact="https://linkedin.com/in/x",
        category="url",
        block_index=2,
        block_provenance=("brief.md#scope",),
        matched_anchors=(),
    )
    section = SectionGroundingResult(
        section_id="scope_of_work",
        facts_checked=10,
        facts_grounded=9,
        flagged=(flagged,),
    )
    report = GroundingReport(sections=(section,))
    assert report.total_facts_checked() == 10
    assert report.total_facts_grounded() == 9
    assert len(report.sections[0].flagged) == 1
    assert report.sections[0].flagged[0].fact == "https://linkedin.com/in/x"


def test_grounding_report_serialisation_round_trip():
    flagged = FlaggedFact(
        fact="x",
        category="url",
        block_index=0,
        block_provenance=(),
        matched_anchors=(),
    )
    section = SectionGroundingResult(
        section_id="s",
        facts_checked=1,
        facts_grounded=0,
        flagged=(flagged,),
    )
    report = GroundingReport(sections=(section,))
    payload = report.to_dict()
    restored = GroundingReport.from_dict(payload)
    assert restored == report


def test_grounding_report_aggregates_across_multiple_sections():
    s1 = SectionGroundingResult(section_id="s1", facts_checked=5, facts_grounded=5, flagged=())
    s2 = SectionGroundingResult(section_id="s2", facts_checked=3, facts_grounded=2, flagged=())
    report = GroundingReport(sections=(s1, s2))
    assert report.total_facts_checked() == 8
    assert report.total_facts_grounded() == 7
