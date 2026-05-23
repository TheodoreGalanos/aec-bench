# ABOUTME: Tests patch proposer — LLM call parsing, escalation to REVIEW when unfixable.
# ABOUTME: Uses a stub RlmClient returning canned JSON to isolate parsing from the live model.

import json

from aec_bench.adapters.rlm.client import RlmCompletionResponse, RlmMessage
from aec_bench.contracts.remediation import PatchStatus
from aec_bench.remediation.proposer import propose_patch, propose_patch_annotated


class _StubClient:
    def __init__(self, response_json: dict) -> None:
        self._response = response_json
        self.calls: list[tuple[str, list[RlmMessage], str | None]] = []

    def generate(self, *, model, messages, system_prompt):
        self.calls.append((model, messages, system_prompt))
        return RlmCompletionResponse(
            output_text=json.dumps(self._response),
            input_tokens=100,
            output_tokens=50,
            cache_read_tokens=0,
            cache_write_tokens=0,
        )


def test_propose_patch_parses_apply_response():
    stub = _StubClient(
        {
            "status": "apply",
            "locator_phrase": "shall not permit any person",
            "replacement": "shall not permit unauthorised personnel",
            "occurrence": 1,
            "rationale": "Name the Site Access Coordinator",
            "confidence": "high",
        }
    )
    proposal = propose_patch(
        section_id="contractor_obligations",
        section_excerpt="The Contractor shall not permit any person to access the Site.",
        criterion="clear responsible party",
        evidence="Obligation lacks named party",
        client=stub,
        model="test-model",
    )
    assert proposal.status == PatchStatus.APPLY
    assert proposal.patch.locator_phrase == "shall not permit any person"
    assert proposal.patch.replacement.startswith("shall not permit unauthorised")
    assert proposal.confidence == "high"


def test_propose_patch_parses_review_escalation():
    stub = _StubClient(
        {
            "status": "review",
            "rationale": "DCAC process details not present in any source — requires client input.",
            "confidence": "low",
        }
    )
    proposal = propose_patch(
        section_id="contractor_obligations",
        section_excerpt="DCAC [TBD].",
        criterion="DCAC process steps",
        evidence="No DCAC process captured",
        client=stub,
        model="test-model",
    )
    assert proposal.status == PatchStatus.REVIEW
    assert proposal.patch.replacement == ""


def test_propose_patch_includes_section_and_criterion_in_prompt():
    stub = _StubClient(
        {
            "status": "apply",
            "locator_phrase": "x",
            "replacement": "y",
            "occurrence": 1,
            "rationale": "r",
            "confidence": "medium",
        }
    )
    propose_patch(
        section_id="scope_of_works",
        section_excerpt="Sample.",
        criterion="unambiguous pricing",
        evidence="vague allow-for language",
        client=stub,
        model="test-model",
    )
    assert len(stub.calls) == 1
    _, messages, _ = stub.calls[0]
    combined_prompt = messages[0].content
    assert "scope_of_works" in combined_prompt
    assert "unambiguous pricing" in combined_prompt
    assert "vague allow-for language" in combined_prompt
    assert "Sample." in combined_prompt


def test_propose_patch_defaults_to_review_on_malformed_json():
    stub = _StubClient({"not_a_valid_response": True})
    proposal = propose_patch(
        section_id="x",
        section_excerpt="y",
        criterion="z",
        evidence="w",
        client=stub,
        model="test-model",
    )
    assert proposal.status == PatchStatus.REVIEW
    assert "parse" in proposal.rationale.lower() or "malformed" in proposal.rationale.lower()


def test_propose_patch_collapses_apply_without_locator_to_review():
    """If LLM says 'apply' but doesn't provide locator+replacement, demote to REVIEW."""
    stub = _StubClient(
        {
            "status": "apply",
            "locator_phrase": "",
            "replacement": "something",
            "occurrence": 1,
            "rationale": "r",
            "confidence": "medium",
        }
    )
    proposal = propose_patch(
        section_id="x",
        section_excerpt="y",
        criterion="z",
        evidence="w",
        client=stub,
        model="test-model",
    )
    assert proposal.status == PatchStatus.REVIEW


def test_propose_patch_normalises_unknown_confidence():
    """Confidence not in high/medium/low → defaults to 'medium'."""
    stub = _StubClient(
        {
            "status": "apply",
            "locator_phrase": "a",
            "replacement": "b",
            "occurrence": 1,
            "rationale": "r",
            "confidence": "very-high",
        }
    )
    proposal = propose_patch(
        section_id="x",
        section_excerpt="y",
        criterion="z",
        evidence="w",
        client=stub,
        model="test-model",
    )
    assert proposal.confidence == "medium"


def test_propose_annotated_parses_apply_response():
    stub = _StubClient(
        {
            "status": "apply",
            "replacement": "allow up to 40 hours of investigation works",
            "rationale": "Added scope ceiling",
            "confidence": "high",
        }
    )
    proposal = propose_patch_annotated(
        section_id="contractor_obligations",
        annotated_section=(
            "The Contractor shall <<<REVIEW>>>allow for investigation works<<<END_REVIEW>>> as part of the lump sum."
        ),
        span_to_replace="allow for investigation works",
        criterion="unambiguous pricing",
        evidence="Open-ended 'allow for' language",
        client=stub,
        model="test-model",
    )
    assert proposal.status == PatchStatus.APPLY
    assert "40 hours" in proposal.patch.replacement
    # Proposal's locator_phrase carries span_to_replace for applier compatibility
    assert proposal.patch.locator_phrase == "allow for investigation works"


def test_propose_annotated_escalates_to_review_when_unfixable():
    stub = _StubClient(
        {
            "status": "review",
            "rationale": "Scope ceiling requires client input",
            "confidence": "low",
        }
    )
    proposal = propose_patch_annotated(
        section_id="contractor_obligations",
        annotated_section="Something <<<REVIEW>>>needs fixing<<<END_REVIEW>>>.",
        span_to_replace="needs fixing",
        criterion="c",
        evidence="e",
        client=stub,
        model="test-model",
    )
    assert proposal.status == PatchStatus.REVIEW


def test_propose_annotated_includes_markers_in_prompt():
    stub = _StubClient(
        {
            "status": "apply",
            "replacement": "y",
            "rationale": "r",
            "confidence": "medium",
        }
    )
    propose_patch_annotated(
        section_id="x",
        annotated_section="before <<<REVIEW>>>target<<<END_REVIEW>>> after",
        span_to_replace="target",
        criterion="c",
        evidence="e",
        client=stub,
        model="test-model",
    )
    _, messages, _ = stub.calls[0]
    assert "<<<REVIEW>>>" in messages[0].content
    assert "<<<END_REVIEW>>>" in messages[0].content
    assert "target" in messages[0].content


def test_propose_annotated_malformed_response_returns_review():
    stub = _StubClient({"garbage": True})
    proposal = propose_patch_annotated(
        section_id="x",
        annotated_section="s",
        span_to_replace="t",
        criterion="c",
        evidence="e",
        client=stub,
        model="test-model",
    )
    assert proposal.status == PatchStatus.REVIEW


def test_propose_annotated_apply_with_empty_replacement_collapses_to_review():
    stub = _StubClient(
        {
            "status": "apply",
            "replacement": "",
            "rationale": "nothing to suggest",
            "confidence": "low",
        }
    )
    proposal = propose_patch_annotated(
        section_id="x",
        annotated_section="s <<<REVIEW>>>span<<<END_REVIEW>>>",
        span_to_replace="span",
        criterion="c",
        evidence="e",
        client=stub,
        model="test-model",
    )
    assert proposal.status == PatchStatus.REVIEW
