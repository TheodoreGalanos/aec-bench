# ABOUTME: Tests deterministic four-cell planning for fixed and learned harness-program treatments.
# ABOUTME: Covers content identity, shared-factor integrity, common ABI checks, and counterbalancing.

from __future__ import annotations

from collections import Counter, defaultdict

import pytest
from pydantic import ValidationError

from aec_bench.experimentation.qualification.harness_program_study.plan import (
    HarnessProgramCandidateReference,
    HarnessProgramCandidateSet,
    HarnessProgramCell,
    HarnessProgramPlan,
    HarnessProgramStudyManifest,
    build_harness_program_plan,
)


def _sha(label: str) -> str:
    import hashlib

    return hashlib.sha256(label.encode()).hexdigest()


def test_candidate_reference_is_content_addressed_and_requires_one_common_abi() -> None:
    candidate = _candidate(HarnessProgramCell.H0_P0)

    assert (
        candidate.reference_sha256
        == HarnessProgramCandidateReference.create(
            cell=HarnessProgramCell.H0_P0,
            kernel_sha256=_sha("kernel"),
            kernel_abi_sha256=_sha("abi"),
            policy_sha256=_sha("policy"),
            task_set_id="task-set.alpha",
            task_set_sha256=_sha("task-set.alpha"),
            harness_sha256=_sha("h0"),
            harness_abi_sha256=_sha("abi"),
            program_sha256=_sha("p0"),
            program_abi_sha256=_sha("abi"),
            resource_sha256=_sha("resource"),
        ).reference_sha256
    )

    with pytest.raises(ValidationError, match="common ABI"):
        HarnessProgramCandidateReference.create(
            cell=HarnessProgramCell.H0_P0,
            kernel_sha256=_sha("kernel"),
            kernel_abi_sha256=_sha("abi"),
            policy_sha256=_sha("policy"),
            task_set_id="task-set.alpha",
            task_set_sha256=_sha("task-set.alpha"),
            harness_sha256=_sha("h0"),
            harness_abi_sha256=_sha("harness-abi"),
            program_sha256=_sha("p0"),
            program_abi_sha256=_sha("program-abi"),
            resource_sha256=_sha("resource"),
        )

    tampered = candidate.model_dump(mode="json") | {"harness_sha256": _sha("tampered")}
    with pytest.raises(ValidationError, match="reference_sha256"):
        HarnessProgramCandidateReference.model_validate(tampered)


@pytest.mark.parametrize(
    ("cell", "field", "replacement", "message"),
    [
        (HarnessProgramCell.H0_PX, "harness_sha256", _sha("wrong-harness"), "fixed harness"),
        (HarnessProgramCell.HX_P0, "program_sha256", _sha("wrong-program"), "fixed program"),
        (HarnessProgramCell.HX_PX, "kernel_sha256", _sha("wrong-kernel"), "kernel"),
        (HarnessProgramCell.HX_PX, "policy_sha256", _sha("wrong-policy"), "policy"),
        (HarnessProgramCell.HX_PX, "task_set_sha256", _sha("wrong-task-set"), "task set"),
        (HarnessProgramCell.HX_PX, "resource_sha256", _sha("wrong-resource"), "resource"),
    ],
)
def test_candidate_set_rejects_broken_shared_factor_integrity(
    cell: HarnessProgramCell,
    field: str,
    replacement: str,
    message: str,
) -> None:
    candidates = list(_candidate_set("task-set.alpha").candidates)
    index = next(index for index, candidate in enumerate(candidates) if candidate.cell is cell)
    payload = candidates[index].model_dump(mode="json") | {field: replacement}
    payload.pop("reference_sha256")
    candidates[index] = HarnessProgramCandidateReference.create(**payload)

    with pytest.raises(ValidationError, match=message):
        HarnessProgramCandidateSet(task_set_id="task-set.alpha", candidates=tuple(candidates))


def test_candidate_set_requires_exactly_four_distinct_treatment_cells() -> None:
    candidates = list(_candidate_set("task-set.alpha").candidates)
    candidates[-1] = candidates[0]

    with pytest.raises(ValidationError, match="exactly one candidate for each harness-program cell"):
        HarnessProgramCandidateSet(task_set_id="task-set.alpha", candidates=tuple(candidates))


def test_candidate_set_requires_nontrivial_harness_and_program_treatments() -> None:
    candidates = list(_candidate_set("task-set.alpha").candidates)
    for index, candidate in enumerate(candidates):
        if candidate.cell in {HarnessProgramCell.HX_P0, HarnessProgramCell.HX_PX}:
            payload = candidate.model_dump(mode="json")
            payload["harness_sha256"] = _sha("h0")
            payload.pop("reference_sha256")
            candidates[index] = HarnessProgramCandidateReference.create(**payload)

    with pytest.raises(ValidationError, match="learned harness must differ"):
        HarnessProgramCandidateSet(task_set_id="task-set.alpha", candidates=tuple(candidates))


def test_candidate_set_requires_nontrivial_program_treatment() -> None:
    candidates = list(_candidate_set("task-set.alpha").candidates)
    for index, candidate in enumerate(candidates):
        if candidate.cell in {HarnessProgramCell.H0_PX, HarnessProgramCell.HX_PX}:
            payload = candidate.model_dump(mode="json")
            payload["program_sha256"] = _sha("p0")
            payload.pop("reference_sha256")
            candidates[index] = HarnessProgramCandidateReference.create(**payload)

    with pytest.raises(ValidationError, match="learned program must differ"):
        HarnessProgramCandidateSet(task_set_id="task-set.alpha", candidates=tuple(candidates))


def test_manifest_requires_one_policy_across_task_sets() -> None:
    with pytest.raises(ValidationError, match="share one policy"):
        HarnessProgramStudyManifest(
            experiment_id="harness-program.demo",
            randomization_seed=1,
            repetitions=1,
            candidate_sets=(
                _candidate_set("task-set.alpha"),
                _candidate_set("task-set.beta", policy_label="other-policy"),
            ),
        )


def test_plan_expands_four_cells_per_block_with_seeded_williams_counterbalancing() -> None:
    manifest = HarnessProgramStudyManifest(
        experiment_id="harness-program.demo",
        randomization_seed=73,
        repetitions=2,
        candidate_sets=(
            _candidate_set("task-set.alpha"),
            _candidate_set("task-set.beta"),
        ),
    )

    plan = build_harness_program_plan(manifest)

    assert plan.trial_count == 16
    assert len(plan.blocks) == 4
    assert len({trial.trial_id for trial in plan.trials}) == 16
    for block in plan.blocks:
        assert {trial.cell for trial in block.trials} == set(HarnessProgramCell)
        assert [trial.order_index for trial in block.trials] == [1, 2, 3, 4]

    positions: dict[HarnessProgramCell, Counter[int]] = defaultdict(Counter)
    ordered_blocks = sorted(plan.blocks, key=lambda block: block.sequence_index)
    for block in ordered_blocks:
        for trial in block.trials:
            positions[trial.cell][trial.order_index] += 1
    assert all(counter == Counter({1: 1, 2: 1, 3: 1, 4: 1}) for counter in positions.values())


def test_plan_is_deterministic_and_seed_changes_only_execution_order() -> None:
    candidate_sets = (_candidate_set("task-set.beta"), _candidate_set("task-set.alpha"))
    first = build_harness_program_plan(
        HarnessProgramStudyManifest(
            experiment_id="harness-program.demo",
            randomization_seed=11,
            repetitions=2,
            candidate_sets=candidate_sets,
        )
    )
    repeated = build_harness_program_plan(
        HarnessProgramStudyManifest(
            experiment_id="harness-program.demo",
            randomization_seed=11,
            repetitions=2,
            candidate_sets=tuple(reversed(candidate_sets)),
        )
    )
    reseeded = build_harness_program_plan(
        HarnessProgramStudyManifest(
            experiment_id="harness-program.demo",
            randomization_seed=12,
            repetitions=2,
            candidate_sets=candidate_sets,
        )
    )

    assert first == repeated
    assert first.plan_sha256 == repeated.plan_sha256
    assert first.plan_sha256 != reseeded.plan_sha256
    assert _trial_membership(first) == _trial_membership(reseeded)
    assert _execution_orders(first) != _execution_orders(reseeded)


def test_plan_hash_rejects_tampered_trial_content() -> None:
    plan = build_harness_program_plan(
        HarnessProgramStudyManifest(
            experiment_id="harness-program.demo",
            randomization_seed=1,
            repetitions=1,
            candidate_sets=(_candidate_set("task-set.alpha"),),
        )
    )
    payload = plan.model_dump(mode="json")
    payload["trials"][0]["order_index"] = 4

    with pytest.raises(ValidationError, match="plan_sha256|block trials|trial_id"):
        type(plan).model_validate(payload)


def _candidate_set(task_set_id: str, *, policy_label: str = "policy") -> HarnessProgramCandidateSet:
    return HarnessProgramCandidateSet(
        task_set_id=task_set_id,
        candidates=tuple(
            _candidate(cell, task_set_id=task_set_id, policy_label=policy_label) for cell in HarnessProgramCell
        ),
    )


def _candidate(
    cell: HarnessProgramCell,
    *,
    task_set_id: str = "task-set.alpha",
    policy_label: str = "policy",
) -> HarnessProgramCandidateReference:
    learned_harness = cell in {HarnessProgramCell.HX_P0, HarnessProgramCell.HX_PX}
    learned_program = cell in {HarnessProgramCell.H0_PX, HarnessProgramCell.HX_PX}
    return HarnessProgramCandidateReference.create(
        cell=cell,
        kernel_sha256=_sha("kernel"),
        kernel_abi_sha256=_sha("abi"),
        policy_sha256=_sha(policy_label),
        task_set_id=task_set_id,
        task_set_sha256=_sha(task_set_id),
        harness_sha256=_sha("hx" if learned_harness else "h0"),
        harness_abi_sha256=_sha("abi"),
        program_sha256=_sha("px" if learned_program else "p0"),
        program_abi_sha256=_sha("abi"),
        resource_sha256=_sha("resource"),
    )


def _trial_membership(plan: HarnessProgramPlan) -> set[tuple[str, int, HarnessProgramCell, str]]:
    return {
        (trial.task_set_id, trial.repetition, trial.cell, trial.candidate.reference_sha256) for trial in plan.trials
    }


def _execution_orders(plan: HarnessProgramPlan) -> list[tuple[HarnessProgramCell, ...]]:
    return [
        tuple(trial.cell for trial in block.trials)
        for block in sorted(plan.blocks, key=lambda item: item.sequence_index)
    ]
