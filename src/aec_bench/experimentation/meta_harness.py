# ABOUTME: Provides runtime-neutral functional composition for harness candidate studies.
# ABOUTME: Keeps candidate execution and assessment policy in caller-supplied functions.

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

from aec_bench.contracts.trial_record import TrialRecord


@dataclass(frozen=True)
class HarnessCandidate[CandidateT]:
    candidate_id: str
    value: CandidateT

    def __post_init__(self) -> None:
        if not self.candidate_id.strip():
            raise ValueError("candidate_id must not be blank")


@dataclass(frozen=True)
class HarnessCandidateTrials[CandidateT]:
    candidate: HarnessCandidate[CandidateT]
    records: tuple[TrialRecord, ...]

    def __post_init__(self) -> None:
        if not self.records:
            raise ValueError("candidate evaluation must return at least one TrialRecord")
        if any(not isinstance(record, TrialRecord) for record in self.records):
            raise TypeError("candidate evaluation must return only TrialRecord values")
        trial_ids = [record.trial_id for record in self.records]
        if len(trial_ids) != len(set(trial_ids)):
            raise ValueError("candidate evaluation returned a duplicate trial_id")


@dataclass(frozen=True)
class HarnessStudyResult[CandidateT, AssessmentT]:
    baseline: HarnessCandidateTrials[CandidateT]
    candidates: tuple[HarnessCandidateTrials[CandidateT], ...]
    assessment: AssessmentT


@dataclass(frozen=True)
class MetaHarnessRound[CandidateT, AssessmentT]:
    round_index: int
    study: HarnessStudyResult[CandidateT, AssessmentT]
    selected: HarnessCandidateTrials[CandidateT]


type MetaHarnessStopReason = Literal["stop_condition", "max_rounds"]


@dataclass(frozen=True)
class MetaHarnessResult[CandidateT, AssessmentT]:
    initial: HarnessCandidateTrials[CandidateT]
    rounds: tuple[MetaHarnessRound[CandidateT, AssessmentT], ...]
    selected: HarnessCandidateTrials[CandidateT]
    stop_reason: MetaHarnessStopReason


type CandidateEvaluator[CandidateT] = Callable[[HarnessCandidate[CandidateT]], Sequence[TrialRecord]]
type CandidateAssessor[CandidateT, AssessmentT] = Callable[
    [HarnessCandidateTrials[CandidateT], tuple[HarnessCandidateTrials[CandidateT], ...]],
    AssessmentT,
]
type CandidateSelector[CandidateT, AssessmentT] = Callable[
    [
        HarnessCandidateTrials[CandidateT],
        tuple[HarnessCandidateTrials[CandidateT], ...],
        AssessmentT,
    ],
    HarnessCandidate[CandidateT],
]
type CandidateRefiner[CandidateT, AssessmentT] = Callable[
    [HarnessCandidate[CandidateT], AssessmentT],
    HarnessCandidate[CandidateT],
]
type CandidateProposer[CandidateT, AssessmentT] = Callable[
    [HarnessCandidate[CandidateT], AssessmentT | None],
    Sequence[HarnessCandidate[CandidateT]],
]
type MetaHarnessStop[CandidateT, AssessmentT] = Callable[[MetaHarnessRound[CandidateT, AssessmentT]], bool]


def evaluate_harness_candidate[CandidateT](
    candidate: HarnessCandidate[CandidateT],
    *,
    evaluate: CandidateEvaluator[CandidateT],
) -> HarnessCandidateTrials[CandidateT]:
    """Evaluate one candidate and retain every returned trial as assessment evidence."""

    records = tuple(evaluate(candidate))
    return HarnessCandidateTrials(candidate=candidate, records=records)


def run_harness_study[CandidateT, AssessmentT](
    *,
    baseline: HarnessCandidate[CandidateT],
    candidates: Sequence[HarnessCandidate[CandidateT]],
    evaluate: CandidateEvaluator[CandidateT],
    assess: CandidateAssessor[CandidateT, AssessmentT],
) -> HarnessStudyResult[CandidateT, AssessmentT]:
    """Evaluate one baseline and a non-empty candidate set, then assess the evidence."""

    proposed = tuple(candidates)
    _validate_proposed_candidates(baseline=baseline, candidates=proposed, used_candidate_ids=set())
    baseline_trials = evaluate_harness_candidate(baseline, evaluate=evaluate)
    candidate_trials = tuple(evaluate_harness_candidate(candidate, evaluate=evaluate) for candidate in proposed)
    assessment = assess(baseline_trials, candidate_trials)
    return HarnessStudyResult(
        baseline=baseline_trials,
        candidates=candidate_trials,
        assessment=assessment,
    )


def run_meta_harness[CandidateT, AssessmentT](
    *,
    initial: HarnessCandidate[CandidateT],
    propose: CandidateProposer[CandidateT, AssessmentT],
    evaluate: CandidateEvaluator[CandidateT],
    assess: CandidateAssessor[CandidateT, AssessmentT],
    select: CandidateSelector[CandidateT, AssessmentT],
    refine: CandidateRefiner[CandidateT, AssessmentT],
    stop: MetaHarnessStop[CandidateT, AssessmentT],
    max_rounds: int,
) -> MetaHarnessResult[CandidateT, AssessmentT]:
    """Run a bounded propose, evaluate, assess, select, and refine process."""

    if max_rounds <= 0:
        raise ValueError("max_rounds must be positive")

    initial_trials = evaluate_harness_candidate(initial, evaluate=evaluate)
    current_trials = initial_trials
    previous_assessment: AssessmentT | None = None
    used_candidate_ids = {initial.candidate_id}
    rounds: list[MetaHarnessRound[CandidateT, AssessmentT]] = []

    for round_index in range(1, max_rounds + 1):
        candidates = tuple(propose(current_trials.candidate, previous_assessment))
        _validate_proposed_candidates(
            baseline=current_trials.candidate,
            candidates=candidates,
            used_candidate_ids=used_candidate_ids,
        )
        candidate_trials = tuple(evaluate_harness_candidate(candidate, evaluate=evaluate) for candidate in candidates)
        used_candidate_ids.update(candidate.candidate_id for candidate in candidates)
        assessment = assess(current_trials, candidate_trials)
        study = HarnessStudyResult(
            baseline=current_trials,
            candidates=candidate_trials,
            assessment=assessment,
        )
        selected_candidate = select(current_trials, candidate_trials, assessment)
        selected_trials = _resolve_selected_trials(
            selected_candidate=selected_candidate,
            current=current_trials,
            candidates=candidate_trials,
        )
        round_result = MetaHarnessRound(
            round_index=round_index,
            study=study,
            selected=selected_trials,
        )
        rounds.append(round_result)

        if stop(round_result):
            return MetaHarnessResult(
                initial=initial_trials,
                rounds=tuple(rounds),
                selected=selected_trials,
                stop_reason="stop_condition",
            )
        if round_index == max_rounds:
            return MetaHarnessResult(
                initial=initial_trials,
                rounds=tuple(rounds),
                selected=selected_trials,
                stop_reason="max_rounds",
            )

        refined = refine(selected_trials.candidate, assessment)
        if not isinstance(refined, HarnessCandidate):
            raise TypeError("refine must return a HarnessCandidate")
        if refined.candidate_id in used_candidate_ids:
            raise ValueError("refined candidate must have a new candidate_id")
        used_candidate_ids.add(refined.candidate_id)
        current_trials = evaluate_harness_candidate(refined, evaluate=evaluate)
        previous_assessment = assessment

    raise AssertionError("positive max_rounds must return from the bounded loop")


def _validate_proposed_candidates[CandidateT](
    *,
    baseline: HarnessCandidate[CandidateT],
    candidates: tuple[HarnessCandidate[CandidateT], ...],
    used_candidate_ids: set[str],
) -> None:
    if not candidates:
        raise ValueError("harness study requires at least one candidate")
    if any(not isinstance(candidate, HarnessCandidate) for candidate in candidates):
        raise TypeError("propose must return only HarnessCandidate values")
    candidate_ids = [baseline.candidate_id, *(candidate.candidate_id for candidate in candidates)]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("candidate_id values must be unique in one study")
    reused = set(candidate_ids[1:]) & used_candidate_ids
    if reused:
        raise ValueError("proposed candidate_id values must be unique in one meta-harness run")


def _resolve_selected_trials[CandidateT](
    *,
    selected_candidate: HarnessCandidate[CandidateT],
    current: HarnessCandidateTrials[CandidateT],
    candidates: tuple[HarnessCandidateTrials[CandidateT], ...],
) -> HarnessCandidateTrials[CandidateT]:
    if not isinstance(selected_candidate, HarnessCandidate):
        raise TypeError("select must return a HarnessCandidate")
    evaluated = (current, *candidates)
    try:
        return next(item for item in evaluated if item.candidate.candidate_id == selected_candidate.candidate_id)
    except StopIteration as error:
        raise ValueError("selected candidate must be evaluated in the current round") from error


__all__ = (
    "CandidateAssessor",
    "CandidateEvaluator",
    "CandidateProposer",
    "CandidateRefiner",
    "CandidateSelector",
    "HarnessCandidate",
    "HarnessCandidateTrials",
    "HarnessStudyResult",
    "MetaHarnessResult",
    "MetaHarnessRound",
    "MetaHarnessStop",
    "MetaHarnessStopReason",
    "evaluate_harness_candidate",
    "run_harness_study",
    "run_meta_harness",
)
