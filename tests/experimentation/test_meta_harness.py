# ABOUTME: Tests the runtime-neutral functional meta-harness composition API.
# ABOUTME: Proves validation, evidence retention, bounded refinement, and import independence.

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pytest

from aec_bench.contracts.trial_record import EvaluationStatus, EvidenceStatus, ExecutionStatus, TrialRecord
from aec_bench.experimentation.meta_harness import (
    HarnessCandidate,
    HarnessCandidateTrials,
    evaluate_harness_candidate,
    run_harness_study,
    run_meta_harness,
)
from tests.support.trial_record_factories import make_trial_record


def _record(trial_id: str, **overrides: Any) -> TrialRecord:
    return make_trial_record(trial_id=trial_id, **overrides)


def test_harness_candidate_requires_a_non_blank_identity_and_is_frozen() -> None:
    with pytest.raises(ValueError, match="candidate_id must not be blank"):
        HarnessCandidate(candidate_id="  ", value={"temperature": 0.2})

    candidate = HarnessCandidate(candidate_id="candidate.baseline", value={"temperature": 0.2})

    with pytest.raises(FrozenInstanceError):
        candidate.candidate_id = "candidate.changed"  # type: ignore[misc]


@pytest.mark.asyncio
async def test_evaluate_harness_candidate_normalises_records_and_retains_failures() -> None:
    candidate = HarnessCandidate(candidate_id="candidate.baseline", value="baseline")
    failed = _record(
        "trial.failed",
        execution_status=ExecutionStatus.FAILED,
        evaluation=None,
        evaluation_status=EvaluationStatus.FAILED,
        evidence_status=EvidenceStatus.INCOMPLETE,
        output=None,
    )
    invalid = _record(
        "trial.invalid",
        execution_status=ExecutionStatus.INVALID,
        evaluation=None,
        evaluation_status=EvaluationStatus.INVALID,
        evidence_status=EvidenceStatus.INVALID,
        output=None,
    )

    result = await evaluate_harness_candidate(candidate, evaluate=lambda _candidate: [failed, invalid])

    assert result == HarnessCandidateTrials(candidate=candidate, records=(failed, invalid))


@pytest.mark.asyncio
async def test_evaluate_harness_candidate_awaits_async_evaluator() -> None:
    candidate = HarnessCandidate(candidate_id="candidate.async", value="async")
    record = _record("trial.async")

    async def evaluate(_candidate: HarnessCandidate[str]) -> list[TrialRecord]:
        return [record]

    result = await evaluate_harness_candidate(candidate, evaluate=evaluate)

    assert result.records == (record,)


@pytest.mark.parametrize(
    ("records", "message"),
    [
        ([], "at least one TrialRecord"),
        ([_record("trial.duplicate"), _record("trial.duplicate")], "duplicate trial_id"),
        ([object()], "TrialRecord values"),
    ],
)
@pytest.mark.asyncio
async def test_evaluate_harness_candidate_rejects_invalid_evaluator_output(
    records: list[object],
    message: str,
) -> None:
    candidate = HarnessCandidate(candidate_id="candidate.baseline", value="baseline")

    def invalid_evaluator(_candidate: HarnessCandidate[str]) -> list[TrialRecord]:
        return records  # type: ignore[return-value]

    with pytest.raises((TypeError, ValueError), match=message):
        await evaluate_harness_candidate(candidate, evaluate=invalid_evaluator)


@pytest.mark.asyncio
async def test_run_harness_study_evaluates_each_candidate_once_and_keeps_caller_assessment() -> None:
    baseline = HarnessCandidate(candidate_id="candidate.baseline", value=1)
    candidates = (
        HarnessCandidate(candidate_id="candidate.two", value=2),
        HarnessCandidate(candidate_id="candidate.three", value=3),
    )
    calls: list[str] = []
    assessment = {"preferred": "candidate.three", "reason": "caller-owned"}

    def evaluate(candidate: HarnessCandidate[int]) -> list[TrialRecord]:
        calls.append(candidate.candidate_id)
        return [_record(f"trial.{candidate.candidate_id}")]

    result = await run_harness_study(
        baseline=baseline,
        candidates=candidates,
        evaluate=evaluate,
        assess=lambda current, proposed: assessment,
    )

    assert calls == ["candidate.baseline", "candidate.two", "candidate.three"]
    assert result.baseline.candidate is baseline
    assert tuple(item.candidate for item in result.candidates) == candidates
    assert result.assessment is assessment


@pytest.mark.parametrize(
    ("candidate_ids", "message"),
    [
        ((), "at least one candidate"),
        (("candidate.same", "candidate.same"), "candidate_id values must be unique"),
        (("candidate.baseline",), "candidate_id values must be unique"),
    ],
)
@pytest.mark.asyncio
async def test_run_harness_study_rejects_invalid_candidate_sets(
    candidate_ids: tuple[str, ...],
    message: str,
) -> None:
    baseline = HarnessCandidate(candidate_id="candidate.baseline", value=0)
    candidates = tuple(
        HarnessCandidate(candidate_id=candidate_id, value=index) for index, candidate_id in enumerate(candidate_ids)
    )

    with pytest.raises(ValueError, match=message):
        await run_harness_study(
            baseline=baseline,
            candidates=candidates,
            evaluate=lambda candidate: [_record(f"trial.{candidate.candidate_id}")],
            assess=lambda current, proposed: None,
        )


@pytest.mark.asyncio
async def test_run_meta_harness_selects_only_evaluated_work_and_stops_early() -> None:
    initial = HarnessCandidate(candidate_id="candidate.initial", value=0)
    proposed = HarnessCandidate(candidate_id="candidate.proposed", value=1)

    result = await run_meta_harness(
        initial=initial,
        propose=lambda current, previous: (proposed,),
        evaluate=lambda candidate: [_record(f"trial.{candidate.candidate_id}")],
        assess=lambda current, candidates: {"selected": candidates[0].candidate.candidate_id},
        select=lambda current, candidates, assessment: candidates[0].candidate,
        refine=lambda selected, assessment: pytest.fail("early stop must not refine"),
        stop=lambda round_result: True,
        max_rounds=3,
    )

    assert result.initial.candidate is initial
    assert result.selected.candidate is proposed
    assert result.selected.records[0].trial_id == "trial.candidate.proposed"
    assert len(result.rounds) == 1
    assert result.stop_reason == "stop_condition"


@pytest.mark.asyncio
async def test_run_meta_harness_refines_with_new_identity_and_stops_at_maximum_rounds() -> None:
    initial = HarnessCandidate(candidate_id="candidate.0", value=0)
    evaluated: list[str] = []
    proposed_from: list[tuple[str, object]] = []

    def propose(
        current: HarnessCandidate[int],
        previous: dict[str, int] | None,
    ) -> tuple[HarnessCandidate[int], ...]:
        proposed_from.append((current.candidate_id, previous))
        return (HarnessCandidate(candidate_id=f"proposal.{current.value}", value=current.value + 10),)

    def evaluate(candidate: HarnessCandidate[int]) -> list[TrialRecord]:
        evaluated.append(candidate.candidate_id)
        return [_record(f"trial.{candidate.candidate_id}")]

    result = await run_meta_harness(
        initial=initial,
        propose=propose,
        evaluate=evaluate,
        assess=lambda current, candidates: {"round": current.candidate.value},
        select=lambda current, candidates, assessment: current.candidate,
        refine=lambda selected, assessment: HarnessCandidate(
            candidate_id=f"candidate.{selected.value + 1}",
            value=selected.value + 1,
        ),
        stop=lambda round_result: False,
        max_rounds=2,
    )

    assert evaluated == ["candidate.0", "proposal.0", "candidate.1", "proposal.1"]
    assert proposed_from == [("candidate.0", None), ("candidate.1", {"round": 0})]
    assert result.selected.candidate.candidate_id == "candidate.1"
    assert len(result.rounds) == 2
    assert result.stop_reason == "max_rounds"


@pytest.mark.asyncio
async def test_run_meta_harness_rejects_an_unevaluated_selection() -> None:
    with pytest.raises(ValueError, match="selected candidate must be evaluated in the current round"):
        await run_meta_harness(
            initial=HarnessCandidate(candidate_id="candidate.initial", value=0),
            propose=lambda current, previous: (HarnessCandidate(candidate_id="candidate.proposed", value=1),),
            evaluate=lambda candidate: [_record(f"trial.{candidate.candidate_id}")],
            assess=lambda current, candidates: None,
            select=lambda current, candidates, assessment: HarnessCandidate(candidate_id="candidate.unknown", value=2),
            refine=lambda selected, assessment: selected,
            stop=lambda round_result: True,
            max_rounds=1,
        )


@pytest.mark.parametrize(
    ("proposed", "message"),
    [
        ((), "at least one candidate"),
        (
            (
                HarnessCandidate(candidate_id="candidate.duplicate", value=1),
                HarnessCandidate(candidate_id="candidate.duplicate", value=2),
            ),
            "candidate_id values must be unique",
        ),
    ],
)
@pytest.mark.asyncio
async def test_run_meta_harness_rejects_invalid_proposals(
    proposed: tuple[HarnessCandidate[int], ...],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        await run_meta_harness(
            initial=HarnessCandidate(candidate_id="candidate.initial", value=0),
            propose=lambda current, previous: proposed,
            evaluate=lambda candidate: [_record(f"trial.{candidate.candidate_id}")],
            assess=lambda current, candidates: None,
            select=lambda current, candidates, assessment: current.candidate,
            refine=lambda selected, assessment: selected,
            stop=lambda round_result: True,
            max_rounds=1,
        )


@pytest.mark.asyncio
async def test_run_meta_harness_rejects_reused_refined_identity() -> None:
    with pytest.raises(ValueError, match="refined candidate must have a new candidate_id"):
        await run_meta_harness(
            initial=HarnessCandidate(candidate_id="candidate.initial", value=0),
            propose=lambda current, previous: (HarnessCandidate(candidate_id="candidate.proposed", value=1),),
            evaluate=lambda candidate: [_record(f"trial.{candidate.candidate_id}")],
            assess=lambda current, candidates: None,
            select=lambda current, candidates, assessment: current.candidate,
            refine=lambda selected, assessment: HarnessCandidate(candidate_id=selected.candidate_id, value=1),
            stop=lambda round_result: False,
            max_rounds=2,
        )


@pytest.mark.parametrize("max_rounds", [0, -1])
@pytest.mark.asyncio
async def test_run_meta_harness_requires_a_positive_round_bound(max_rounds: int) -> None:
    with pytest.raises(ValueError, match="max_rounds must be positive"):
        await run_meta_harness(
            initial=HarnessCandidate(candidate_id="candidate.initial", value=0),
            propose=lambda current, previous: (),
            evaluate=lambda candidate: [_record(f"trial.{candidate.candidate_id}")],
            assess=lambda current, candidates: None,
            select=lambda current, candidates, assessment: current.candidate,
            refine=lambda selected, assessment: selected,
            stop=lambda round_result: True,
            max_rounds=max_rounds,
        )


def test_meta_harness_core_has_no_runtime_specific_imports() -> None:
    module_path = Path("src/aec_bench/experimentation/meta_harness.py")
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imports = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    imports.update(
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module is not None
    )
    forbidden = (
        "aec_bench.adapters",
        "aec_bench.harness",
        "aec_bench.lifecycles",
        "aec_bench.worlds",
        "aec_bench.tasks",
    )

    assert not any(module.startswith(forbidden) for module in imports)
