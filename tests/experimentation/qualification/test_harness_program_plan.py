# ABOUTME: Tests deterministic four-cell planning for fixed and learned harness-program treatments.
# ABOUTME: Covers content identity, shared-factor integrity, common ABI checks, and counterbalancing.

from __future__ import annotations

from collections import Counter, defaultdict

import pytest
from pydantic import ValidationError

from aec_bench.contracts.execution_program import ExecutionProgramRef
from aec_bench.contracts.harness_instance import HarnessInstanceRef
from aec_bench.contracts.harness_kernel import KernelRef
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
            kernel_ref=KernelRef(kernel_id="kernel", version="1"),
            kernel_abi_sha256=_sha("abi"),
            policy_sha256=_sha("policy"),
            task_set_id="task-set.alpha",
            task_set_sha256=_sha("task-set.alpha"),
            harness_ref=HarnessInstanceRef(instance_id="h0"),
            harness_abi_sha256=_sha("abi"),
            program_ref=ExecutionProgramRef(program_id="p0", version="1"),
            program_abi_sha256=_sha("abi"),
            resource_sha256=_sha("resource"),
        ).reference_sha256
    )

    with pytest.raises(ValidationError, match="common ABI"):
        HarnessProgramCandidateReference.create(
            cell=HarnessProgramCell.H0_P0,
            kernel_ref=KernelRef(kernel_id="kernel", version="1"),
            kernel_abi_sha256=_sha("abi"),
            policy_sha256=_sha("policy"),
            task_set_id="task-set.alpha",
            task_set_sha256=_sha("task-set.alpha"),
            harness_ref=HarnessInstanceRef(instance_id="h0"),
            harness_abi_sha256=_sha("harness-abi"),
            program_ref=ExecutionProgramRef(program_id="p0", version="1"),
            program_abi_sha256=_sha("program-abi"),
            resource_sha256=_sha("resource"),
        )

    tampered = candidate.model_dump(mode="json") | {"harness_ref": {"instance_id": "tampered"}}
    with pytest.raises(ValidationError, match="reference_sha256"):
        HarnessProgramCandidateReference.model_validate(tampered)


@pytest.mark.parametrize(
    ("cell", "field", "replacement", "message"),
    [
        (HarnessProgramCell.H0_PX, "harness_ref", HarnessInstanceRef(instance_id="wrong-harness"), "fixed harness"),
        (
            HarnessProgramCell.HX_P0,
            "program_ref",
            ExecutionProgramRef(program_id="wrong-program", version="1"),
            "fixed program",
        ),
        (HarnessProgramCell.HX_PX, "kernel_ref", KernelRef(kernel_id="wrong-kernel", version="1"), "kernel"),
        (HarnessProgramCell.HX_PX, "policy_sha256", _sha("wrong-policy"), "policy"),
        (HarnessProgramCell.HX_PX, "task_set_sha256", _sha("wrong-task-set"), "task set"),
        (HarnessProgramCell.HX_PX, "resource_sha256", _sha("wrong-resource"), "resource"),
    ],
)
def test_candidate_set_rejects_broken_shared_factor_integrity(
    cell: HarnessProgramCell,
    field: str,
    replacement: object,
    message: str,
) -> None:
    candidates = list(_candidate_set("task-set.alpha").candidates)
    index = next(index for index, candidate in enumerate(candidates) if candidate.cell is cell)
    candidates[index] = _replace_candidate_field(candidates[index], field=field, replacement=replacement)

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
            candidates[index] = _replace_candidate_field(
                candidate,
                field="harness_ref",
                replacement=HarnessInstanceRef(instance_id="h0"),
            )

    with pytest.raises(ValidationError, match="learned harness must differ"):
        HarnessProgramCandidateSet(task_set_id="task-set.alpha", candidates=tuple(candidates))


def test_candidate_set_requires_nontrivial_program_treatment() -> None:
    candidates = list(_candidate_set("task-set.alpha").candidates)
    for index, candidate in enumerate(candidates):
        if candidate.cell in {HarnessProgramCell.H0_PX, HarnessProgramCell.HX_PX}:
            candidates[index] = _replace_candidate_field(
                candidate,
                field="program_ref",
                replacement=ExecutionProgramRef(program_id="p0", version="1"),
            )

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
        kernel_ref=KernelRef(kernel_id="kernel", version="1"),
        kernel_abi_sha256=_sha("abi"),
        policy_sha256=_sha(policy_label),
        task_set_id=task_set_id,
        task_set_sha256=_sha(task_set_id),
        harness_ref=HarnessInstanceRef(instance_id="hx" if learned_harness else "h0"),
        harness_abi_sha256=_sha("abi"),
        program_ref=ExecutionProgramRef(program_id="px" if learned_program else "p0", version="1"),
        program_abi_sha256=_sha("abi"),
        resource_sha256=_sha("resource"),
    )


def _replace_candidate_field(
    candidate: HarnessProgramCandidateReference,
    *,
    field: str,
    replacement: object,
) -> HarnessProgramCandidateReference:
    values: dict[str, object] = {
        "cell": candidate.cell,
        "kernel_ref": candidate.kernel_ref,
        "kernel_abi_sha256": candidate.kernel_abi_sha256,
        "policy_sha256": candidate.policy_sha256,
        "task_set_id": candidate.task_set_id,
        "task_set_sha256": candidate.task_set_sha256,
        "harness_ref": candidate.harness_ref,
        "harness_abi_sha256": candidate.harness_abi_sha256,
        "program_ref": candidate.program_ref,
        "program_abi_sha256": candidate.program_abi_sha256,
        "resource_sha256": candidate.resource_sha256,
    }
    values[field] = replacement
    return HarnessProgramCandidateReference.create(**values)  # type: ignore[arg-type]


def _trial_membership(plan: HarnessProgramPlan) -> set[tuple[str, int, HarnessProgramCell, str]]:
    return {
        (trial.task_set_id, trial.repetition, trial.cell, trial.candidate.reference_sha256) for trial in plan.trials
    }


def _execution_orders(plan: HarnessProgramPlan) -> list[tuple[HarnessProgramCell, ...]]:
    return [
        tuple(trial.cell for trial in block.trials)
        for block in sorted(plan.blocks, key=lambda item: item.sequence_index)
    ]
