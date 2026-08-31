# ABOUTME: Defines effect-free recipe and selector policies for artifact attempts.
# ABOUTME: Keeps candidate selection bounded and separate from filesystem effects.

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from aec_bench.contracts.run_plan import AttemptRecipe as CanonicalAttemptRecipe
from aec_bench.contracts.run_plan import BestOfAttemptRecipe, SingleAttemptRecipe
from aec_bench.harness.artifact.values import (
    AttemptSelection,
    AttemptSelectionEvidence,
    CandidateAttemptEvidence,
    SelectorCandidate,
    SelectorDecision,
    SelectorEvidence,
    TaskAttempt,
)


class AttemptRunner(Protocol):
    def __call__(
        self,
        *,
        attempt_id: str,
        parent: TaskAttempt | None = None,
        instruction: str | None = None,
    ) -> TaskAttempt: ...


class AttemptRecipe(Protocol):
    def __call__(self, run_once: AttemptRunner) -> AttemptSelection: ...


class AttemptSelector(Protocol):
    def __call__(self, candidates: Sequence[SelectorCandidate]) -> SelectorDecision: ...


def single_attempt() -> AttemptRecipe:
    def recipe(run_once: AttemptRunner) -> AttemptSelection:
        attempt = run_once(attempt_id="attempt-0")
        return AttemptSelection.selected(attempt, reason="single attempt")

    return recipe


def self_select() -> AttemptSelector:
    """Select the first eligible candidate with deterministic index tie-breaking."""

    def selector(candidates: Sequence[SelectorCandidate]) -> SelectorDecision:
        selected = next((candidate for candidate in candidates if candidate.eligible), None)
        selected_index = None if selected is None else selected.index
        return SelectorDecision(
            selected_index=selected_index,
            reason=("no candidate completed with a primary output" if selected is None else "first eligible candidate"),
            configuration={"policy": "first_eligible", "tie_break": "lowest_candidate_index"},
        )

    return selector


def best_of(*, k: int, selector: AttemptSelector) -> AttemptRecipe:
    if k < 1:
        raise ValueError("best-of candidate count must be positive")
    if k == 1:
        return single_attempt()

    def recipe(run_once: AttemptRunner) -> AttemptSelection:
        attempts = [run_once(attempt_id=f"attempt-{index}") for index in range(k)]
        candidates = tuple(_selector_candidate(index=index, attempt=attempt) for index, attempt in enumerate(attempts))
        decision = selector(candidates)
        selected_index = decision.selected_index
        if selected_index is not None and not 0 <= selected_index < len(attempts):
            raise ValueError("selector returned an out-of-range candidate index")
        selected: TaskAttempt | None = None if selected_index is None else attempts[selected_index]
        if selected is not None:
            assert selected_index is not None
            if not candidates[selected_index].eligible:
                raise ValueError("selector returned an ineligible candidate")
        evidence = AttemptSelectionEvidence(
            candidates=tuple(
                CandidateAttemptEvidence(
                    index=candidate.index,
                    attempt_id=candidate.attempt_id,
                    status=candidate.status,
                    elapsed_seconds=attempts[candidate.index].elapsed_seconds,
                    eligible=candidate.eligible,
                    selector_visible_output=candidate.output_reference,
                )
                for candidate in candidates
            ),
            selector=SelectorEvidence(
                configuration=dict(decision.configuration),
                model_calls=decision.model_calls,
                input_tokens=decision.input_tokens,
                output_tokens=decision.output_tokens,
                cache_read_tokens=decision.cache_read_tokens,
                cache_write_tokens=decision.cache_write_tokens,
                selected_index=selected_index,
            ),
            decision="failed" if selected is None else "selected",
            reason=decision.reason,
            selected_index=selected_index,
        )
        if selected is None:
            return AttemptSelection.failed(reason=decision.reason, evidence=evidence)
        return AttemptSelection.selected(selected, reason=decision.reason, evidence=evidence)

    return recipe


def build_attempt_recipe(spec: CanonicalAttemptRecipe) -> AttemptRecipe:
    if isinstance(spec, SingleAttemptRecipe):
        return single_attempt()
    if isinstance(spec, BestOfAttemptRecipe):
        return best_of(k=spec.candidates, selector=self_select())
    raise TypeError(f"unsupported attempt recipe specification: {type(spec).__name__}")


def _selector_candidate(*, index: int, attempt: TaskAttempt) -> SelectorCandidate:
    return SelectorCandidate(
        index=index,
        attempt_id=attempt.attempt_id,
        status=attempt.status,
        primary_output=attempt.selector_visible_output,
        output_reference=attempt.output_reference,
    )


__all__ = (
    "AttemptRecipe",
    "AttemptRunner",
    "AttemptSelector",
    "best_of",
    "build_attempt_recipe",
    "self_select",
    "single_attempt",
)
