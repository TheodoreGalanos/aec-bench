# ABOUTME: Unit tests for synthesis tool-loop tool implementations.
# ABOUTME: Each tool is a pure function over SynthesisInput — no LLM calls, easy to cover.

from __future__ import annotations

import pytest

from aec_bench.contracts.synthesis import (
    SynthesisCandidate,
    SynthesisCriteria,
    SynthesisInput,
)
from aec_bench.synthesis.tools import (
    get_candidate,
    get_criteria_bundle,
    get_source,
    search_across_candidates,
    search_source,
)


def _input(
    *,
    candidates: tuple[tuple[str, str], ...] = (),
    references: dict[str, str] | None = None,
    writing_rules: tuple[str, ...] = (),
    rubric_criteria: tuple[tuple[str, str], ...] = (),
    expert_personas: tuple[str, ...] = (),
) -> SynthesisInput:
    return SynthesisInput(
        candidates=tuple(SynthesisCandidate(candidate_id=cid, content=content) for cid, content in candidates),
        criteria=SynthesisCriteria(
            section_title="Methodology",
            writing_rules=writing_rules,
            rubric_criteria=rubric_criteria,
            expert_personas=expert_personas,
            summary="outline the approach",
        ),
        references=references or {},
    )


class TestGetCandidate:
    def test_returns_all_candidates_when_i_is_none(self) -> None:
        inp = _input(
            candidates=(
                ("cand-0", "first draft"),
                ("cand-1", "second draft"),
            )
        )
        result = get_candidate(inp, i=None)
        assert len(result) == 2
        assert result[0] == {"candidate_id": "cand-0", "content": "first draft"}
        assert result[1] == {"candidate_id": "cand-1", "content": "second draft"}

    def test_returns_single_candidate_by_index(self) -> None:
        inp = _input(
            candidates=(
                ("cand-0", "a"),
                ("cand-1", "b"),
                ("cand-2", "c"),
            )
        )
        result = get_candidate(inp, i=1)
        assert len(result) == 1
        assert result[0]["candidate_id"] == "cand-1"
        assert result[0]["content"] == "b"

    def test_out_of_range_raises(self) -> None:
        inp = _input(candidates=(("cand-0", "x"),))
        with pytest.raises(IndexError):
            get_candidate(inp, i=5)

    def test_empty_candidates_returns_empty_list(self) -> None:
        inp = _input(candidates=())
        assert get_candidate(inp, i=None) == []


class TestGetSource:
    def test_returns_extracted_content(self) -> None:
        inp = _input(references={"project_brief:site": "Site is on Highway 1."})
        assert get_source(inp, "project_brief:site") == "Site is on Highway 1."

    def test_missing_source_raises(self) -> None:
        inp = _input(references={"a": "x"})
        with pytest.raises(KeyError):
            get_source(inp, "not_there")


class TestSearchSource:
    def test_scoped_to_single_source(self) -> None:
        inp = _input(
            references={
                "source_a": "The substation is 500kVA rated for 22kV operation.",
                "source_b": "Unrelated content about drainage pits.",
            }
        )
        hits = search_source(inp, source_label="source_a", query="substation")
        assert len(hits) >= 1
        assert all(h["source_label"] == "source_a" for h in hits)
        assert "substation" in hits[0]["snippet"].lower()

    def test_across_all_sources_when_label_none(self) -> None:
        inp = _input(
            references={
                "source_a": "Electrical specification for the kiosk.",
                "source_b": "Kiosk installation plans.",
            }
        )
        hits = search_source(inp, source_label=None, query="kiosk")
        labels = {h["source_label"] for h in hits}
        assert labels == {"source_a", "source_b"}

    def test_no_matches_returns_empty_list(self) -> None:
        inp = _input(references={"a": "hello world"})
        assert search_source(inp, source_label=None, query="nonexistent_token") == []

    def test_k_caps_result_count(self) -> None:
        # Eight one-line matches, k=3 caps result.
        text = "\n".join(f"match line {i} kiosk" for i in range(8))
        inp = _input(references={"s": text})
        hits = search_source(inp, source_label="s", query="kiosk", k=3)
        assert len(hits) == 3


class TestSearchAcrossCandidates:
    def test_returns_hits_with_candidate_id(self) -> None:
        inp = _input(
            candidates=(
                ("cand-0", "The Contractor shall install the kiosk substation per spec."),
                ("cand-1", "No relevant content here."),
                ("cand-2", "Install a new substation with earthing system."),
            )
        )
        hits = search_across_candidates(inp, query="substation")
        ids = {h["candidate_id"] for h in hits}
        assert ids == {"cand-0", "cand-2"}
        for h in hits:
            assert "score" in h
            assert "snippet" in h

    def test_empty_query_returns_empty(self) -> None:
        inp = _input(candidates=(("cand-0", "anything"),))
        assert search_across_candidates(inp, query="") == []

    def test_ordered_by_score_descending(self) -> None:
        inp = _input(
            candidates=(
                ("cand-0", "kiosk substation kiosk substation kiosk substation"),  # 3 matches
                ("cand-1", "kiosk substation"),  # 1 match
                ("cand-2", "kiosk substation kiosk substation"),  # 2 matches
            )
        )
        hits = search_across_candidates(inp, query="substation")
        scores = [h["score"] for h in hits]
        assert scores == sorted(scores, reverse=True)

    def test_k_caps_result_count(self) -> None:
        inp = _input(candidates=tuple((f"cand-{i}", "kiosk substation") for i in range(8)))
        hits = search_across_candidates(inp, query="substation", k=3)
        assert len(hits) == 3


class TestGetCriteriaBundle:
    def test_shape(self) -> None:
        inp = _input(
            writing_rules=("rule A", "rule B"),
            rubric_criteria=(("essential", "criterion X"), ("optional", "criterion Y")),
            expert_personas=("Senior engineer",),
        )
        bundle = get_criteria_bundle(inp)
        assert bundle["section_title"] == "Methodology"
        assert bundle["summary"] == "outline the approach"
        assert bundle["writing_rules"] == ["rule A", "rule B"]
        assert bundle["rubric_criteria"] == [
            {"category": "essential", "text": "criterion X"},
            {"category": "optional", "text": "criterion Y"},
        ]
        assert bundle["expert_personas"] == ["Senior engineer"]
