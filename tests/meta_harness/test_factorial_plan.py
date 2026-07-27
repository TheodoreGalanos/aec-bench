# ABOUTME: Tests deterministic four-cell planning for fixed and learned harness-program factors.
# ABOUTME: Covers content identity, shared-factor integrity, common ABI checks, and counterbalancing.

from __future__ import annotations

from collections import Counter, defaultdict

import pytest
from pydantic import ValidationError

from aec_bench.meta_harness.factorial_plan import (
    FactorialCandidateReference,
    FactorialCandidateSet,
    FactorialCell,
    FactorialPlan,
    FactorialStudyManifest,
    build_factorial_plan,
)


def _sha(label: str) -> str:
    import hashlib

    return hashlib.sha256(label.encode()).hexdigest()


def test_candidate_reference_is_content_addressed_and_requires_one_common_abi() -> None:
    candidate = _candidate(FactorialCell.H0_P0)

    assert (
        candidate.reference_sha256
        == FactorialCandidateReference.create(
            cell=FactorialCell.H0_P0,
            kernel_sha256=_sha("kernel"),
            kernel_abi_sha256=_sha("abi"),
            policy_sha256=_sha("policy"),
            world_id="world.alpha",
            world_sha256=_sha("world.alpha"),
            harness_sha256=_sha("h0"),
            harness_abi_sha256=_sha("abi"),
            program_sha256=_sha("p0"),
            program_abi_sha256=_sha("abi"),
            resource_sha256=_sha("resource"),
        ).reference_sha256
    )

    with pytest.raises(ValidationError, match="common ABI"):
        FactorialCandidateReference.create(
            cell=FactorialCell.H0_P0,
            kernel_sha256=_sha("kernel"),
            kernel_abi_sha256=_sha("abi"),
            policy_sha256=_sha("policy"),
            world_id="world.alpha",
            world_sha256=_sha("world.alpha"),
            harness_sha256=_sha("h0"),
            harness_abi_sha256=_sha("harness-abi"),
            program_sha256=_sha("p0"),
            program_abi_sha256=_sha("program-abi"),
            resource_sha256=_sha("resource"),
        )

    tampered = candidate.model_dump(mode="json") | {"harness_sha256": _sha("tampered")}
    with pytest.raises(ValidationError, match="reference_sha256"):
        FactorialCandidateReference.model_validate(tampered)


@pytest.mark.parametrize(
    ("cell", "field", "replacement", "message"),
    [
        (FactorialCell.H0_PX, "harness_sha256", _sha("wrong-harness"), "fixed harness"),
        (FactorialCell.HX_P0, "program_sha256", _sha("wrong-program"), "fixed program"),
        (FactorialCell.HX_PX, "kernel_sha256", _sha("wrong-kernel"), "kernel"),
        (FactorialCell.HX_PX, "policy_sha256", _sha("wrong-policy"), "policy"),
        (FactorialCell.HX_PX, "world_sha256", _sha("wrong-world"), "world"),
        (FactorialCell.HX_PX, "resource_sha256", _sha("wrong-resource"), "resource"),
    ],
)
def test_candidate_set_rejects_broken_shared_factor_integrity(
    cell: FactorialCell,
    field: str,
    replacement: str,
    message: str,
) -> None:
    candidates = list(_candidate_set("world.alpha").candidates)
    index = next(index for index, candidate in enumerate(candidates) if candidate.cell is cell)
    payload = candidates[index].model_dump(mode="json") | {field: replacement}
    payload.pop("reference_sha256")
    candidates[index] = FactorialCandidateReference.create(**payload)

    with pytest.raises(ValidationError, match=message):
        FactorialCandidateSet(world_id="world.alpha", candidates=tuple(candidates))


def test_candidate_set_requires_exactly_four_distinct_treatment_cells() -> None:
    candidates = list(_candidate_set("world.alpha").candidates)
    candidates[-1] = candidates[0]

    with pytest.raises(ValidationError, match="exactly one candidate for each factorial cell"):
        FactorialCandidateSet(world_id="world.alpha", candidates=tuple(candidates))


def test_candidate_set_requires_nontrivial_harness_and_program_treatments() -> None:
    candidates = list(_candidate_set("world.alpha").candidates)
    for index, candidate in enumerate(candidates):
        if candidate.cell in {FactorialCell.HX_P0, FactorialCell.HX_PX}:
            payload = candidate.model_dump(mode="json")
            payload["harness_sha256"] = _sha("h0")
            payload.pop("reference_sha256")
            candidates[index] = FactorialCandidateReference.create(**payload)

    with pytest.raises(ValidationError, match="learned harness must differ"):
        FactorialCandidateSet(world_id="world.alpha", candidates=tuple(candidates))


def test_candidate_set_requires_nontrivial_program_treatment() -> None:
    candidates = list(_candidate_set("world.alpha").candidates)
    for index, candidate in enumerate(candidates):
        if candidate.cell in {FactorialCell.H0_PX, FactorialCell.HX_PX}:
            payload = candidate.model_dump(mode="json")
            payload["program_sha256"] = _sha("p0")
            payload.pop("reference_sha256")
            candidates[index] = FactorialCandidateReference.create(**payload)

    with pytest.raises(ValidationError, match="learned program must differ"):
        FactorialCandidateSet(world_id="world.alpha", candidates=tuple(candidates))


def test_manifest_requires_one_policy_across_task_worlds() -> None:
    with pytest.raises(ValidationError, match="share one policy"):
        FactorialStudyManifest(
            experiment_id="factorial.demo",
            randomization_seed=1,
            repetitions=1,
            candidate_sets=(
                _candidate_set("world.alpha"),
                _candidate_set("world.beta", policy_label="other-policy"),
            ),
        )


def test_plan_expands_four_cells_per_block_with_seeded_williams_counterbalancing() -> None:
    manifest = FactorialStudyManifest(
        experiment_id="factorial.demo",
        randomization_seed=73,
        repetitions=2,
        candidate_sets=(
            _candidate_set("world.alpha"),
            _candidate_set("world.beta"),
        ),
    )

    plan = build_factorial_plan(manifest)

    assert plan.trial_count == 16
    assert len(plan.blocks) == 4
    assert len({trial.trial_id for trial in plan.trials}) == 16
    for block in plan.blocks:
        assert {trial.cell for trial in block.trials} == set(FactorialCell)
        assert [trial.order_index for trial in block.trials] == [1, 2, 3, 4]

    positions: dict[FactorialCell, Counter[int]] = defaultdict(Counter)
    ordered_blocks = sorted(plan.blocks, key=lambda block: block.sequence_index)
    for block in ordered_blocks:
        for trial in block.trials:
            positions[trial.cell][trial.order_index] += 1
    assert all(counter == Counter({1: 1, 2: 1, 3: 1, 4: 1}) for counter in positions.values())


def test_plan_is_deterministic_and_seed_changes_only_execution_order() -> None:
    candidate_sets = (_candidate_set("world.beta"), _candidate_set("world.alpha"))
    first = build_factorial_plan(
        FactorialStudyManifest(
            experiment_id="factorial.demo",
            randomization_seed=11,
            repetitions=2,
            candidate_sets=candidate_sets,
        )
    )
    repeated = build_factorial_plan(
        FactorialStudyManifest(
            experiment_id="factorial.demo",
            randomization_seed=11,
            repetitions=2,
            candidate_sets=tuple(reversed(candidate_sets)),
        )
    )
    reseeded = build_factorial_plan(
        FactorialStudyManifest(
            experiment_id="factorial.demo",
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
    plan = build_factorial_plan(
        FactorialStudyManifest(
            experiment_id="factorial.demo",
            randomization_seed=1,
            repetitions=1,
            candidate_sets=(_candidate_set("world.alpha"),),
        )
    )
    payload = plan.model_dump(mode="json")
    payload["trials"][0]["order_index"] = 4

    with pytest.raises(ValidationError, match="plan_sha256|block trials|trial_id"):
        type(plan).model_validate(payload)


def _candidate_set(world_id: str, *, policy_label: str = "policy") -> FactorialCandidateSet:
    return FactorialCandidateSet(
        world_id=world_id,
        candidates=tuple(_candidate(cell, world_id=world_id, policy_label=policy_label) for cell in FactorialCell),
    )


def _candidate(
    cell: FactorialCell,
    *,
    world_id: str = "world.alpha",
    policy_label: str = "policy",
) -> FactorialCandidateReference:
    learned_harness = cell in {FactorialCell.HX_P0, FactorialCell.HX_PX}
    learned_program = cell in {FactorialCell.H0_PX, FactorialCell.HX_PX}
    return FactorialCandidateReference.create(
        cell=cell,
        kernel_sha256=_sha("kernel"),
        kernel_abi_sha256=_sha("abi"),
        policy_sha256=_sha(policy_label),
        world_id=world_id,
        world_sha256=_sha(world_id),
        harness_sha256=_sha("hx" if learned_harness else "h0"),
        harness_abi_sha256=_sha("abi"),
        program_sha256=_sha("px" if learned_program else "p0"),
        program_abi_sha256=_sha("abi"),
        resource_sha256=_sha("resource"),
    )


def _trial_membership(plan: FactorialPlan) -> set[tuple[str, int, FactorialCell, str]]:
    return {(trial.world_id, trial.repetition, trial.cell, trial.candidate.reference_sha256) for trial in plan.trials}


def _execution_orders(plan: FactorialPlan) -> list[tuple[FactorialCell, ...]]:
    return [
        tuple(trial.cell for trial in block.trials)
        for block in sorted(plan.blocks, key=lambda item: item.sequence_index)
    ]
