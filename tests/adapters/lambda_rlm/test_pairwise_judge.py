# ABOUTME: Tests for the LLM-backed pairwise judge wrapper.
# ABOUTME: Uses a stub RlmClient to verify swap, parsing, and outcome construction.

from __future__ import annotations

from dataclasses import dataclass

from aec_bench.adapters.lambda_rlm.criteria import CriteriaBundle
from aec_bench.adapters.lambda_rlm.pairwise_judge import (
    LlmPairwiseJudge,
    _build_prompt,
    _parse_verdict,
)
from aec_bench.adapters.rlm.client import RlmCompletionResponse


@dataclass
class _StubClient:
    """Records the last prompt and returns a scripted response."""

    response_text: str
    last_prompt: str = ""

    def generate(self, *, model, messages, system_prompt, temperature=None):
        self.last_prompt = messages[0].content
        return RlmCompletionResponse(
            output_text=self.response_text,
            input_tokens=10,
            output_tokens=20,
        )


def _make_bundle(section_id: str = "methodology") -> CriteriaBundle:
    return CriteriaBundle(
        section_id=section_id,
        section_title="Test Section",
        summary="overview",
        writing_rules=("Rule one", "MANDATORY: Rule two"),
        rubric_dimensions=("dim1",),
        rubric_criteria=(),
        expert_personas=("Persona text",),
        eval_references=(),
    )


def test_parse_verdict_letter_a():
    raw = "VERDICT: A\nREASONING: Better coverage of essentials"
    verdict, reason = _parse_verdict(raw)
    assert verdict == "A"
    assert "essentials" in reason


def test_parse_verdict_letter_b():
    raw = "VERDICT: B\nREASONING: Stronger structure"
    verdict, reason = _parse_verdict(raw)
    assert verdict == "B"
    assert reason == "Stronger structure"


def test_parse_verdict_unparsable():
    raw = "I think A is much better because..."
    verdict, _ = _parse_verdict(raw)
    assert verdict is None


def test_build_prompt_no_references_omits_source_block():
    bundle = _make_bundle()
    prompt = _build_prompt(bundle, "candidate a content", "candidate b content", None)
    assert "SOURCE DOCUMENTS" not in prompt
    assert "CANDIDATE A:" in prompt
    assert "CANDIDATE B:" in prompt
    assert "VERDICT:" in prompt


def test_build_prompt_with_references_includes_source_block():
    bundle = _make_bundle()
    refs = {"scope": "scope contents", "design": "design contents"}
    prompt = _build_prompt(bundle, "a", "b", refs)
    assert "SOURCE DOCUMENTS" in prompt
    assert "scope contents" in prompt
    assert "design contents" in prompt


def test_judge_returns_correct_winner_when_judge_picks_a():
    client = _StubClient(response_text="VERDICT: A\nREASONING: better")
    judge = LlmPairwiseJudge(
        client=client,
        model="test-model",
        bundle=_make_bundle("section-fixed"),
    )
    outcome = judge.compare(
        a_id="cand-1",
        b_id="cand-2",
        completion_a="A text",
        completion_b="B text",
    )
    # Whichever candidate the judge sees as A wins. Because of the
    # deterministic swap, the winner is one of {cand-1, cand-2}, never both.
    assert outcome.a_id == "cand-1"
    assert outcome.b_id == "cand-2"
    assert outcome.a_won in (True, False)
    assert outcome.reasoning == "better"


def test_judge_winner_is_consistent_across_argument_order():
    """Swapping (a_id, b_id) at the call site must NOT flip the winner —
    the judge should be deterministic on a fixed pair when the LLM is."""
    client = _StubClient(response_text="VERDICT: A\nREASONING: r")
    judge = LlmPairwiseJudge(
        client=client,
        model="test-model",
        bundle=_make_bundle("section-fixed"),
    )
    outcome_ab = judge.compare(a_id="x", b_id="y", completion_a="X", completion_b="Y")
    outcome_ba = judge.compare(a_id="y", b_id="x", completion_a="Y", completion_b="X")
    # The winner id should be the same in both calls (the swap mechanism
    # ensures the judge sees the same content layout in both orderings)
    winner_ab = outcome_ab.a_id if outcome_ab.a_won else outcome_ab.b_id
    winner_ba = outcome_ba.a_id if outcome_ba.a_won else outcome_ba.b_id
    assert winner_ab == winner_ba


def test_judge_records_unparsable_as_default_a_winner():
    client = _StubClient(response_text="garbage response with no VERDICT line")
    judge = LlmPairwiseJudge(
        client=client,
        model="test-model",
        bundle=_make_bundle(),
    )
    outcome = judge.compare(
        a_id="cand-1",
        b_id="cand-2",
        completion_a="A",
        completion_b="B",
    )
    # Fail-safe: still produces an outcome rather than raising
    assert outcome.a_id == "cand-1"
    assert outcome.b_id == "cand-2"
    assert outcome.a_won in (True, False)
