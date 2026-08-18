# ABOUTME: Defines content-addressed four-cell study plans for harness and program treatments.
# ABOUTME: Enforces shared factors, one common ABI, and seeded Williams-square execution order.

from __future__ import annotations

import hashlib
import json
import random
from enum import StrEnum
from typing import Any, Literal

from pydantic import PositiveInt, field_validator, model_validator

from aec_bench.contracts.execution_program import ExecutionProgramRef
from aec_bench.contracts.harness_instance import HarnessInstanceRef
from aec_bench.contracts.harness_kernel import KernelRef
from aec_bench.contracts.validators import NonEmptyStr, StrictModel


class HarnessProgramCell(StrEnum):
    """The four independently crossed harness and program treatment cells."""

    H0_P0 = "h0_p0"
    HX_P0 = "hx_p0"
    H0_PX = "h0_px"
    HX_PX = "hx_px"


_CELL_ORDER = {
    HarnessProgramCell.H0_P0: 0,
    HarnessProgramCell.HX_P0: 1,
    HarnessProgramCell.H0_PX: 2,
    HarnessProgramCell.HX_PX: 3,
}
_WILLIAMS_ROWS = (
    (0, 1, 3, 2),
    (1, 2, 0, 3),
    (2, 3, 1, 0),
    (3, 0, 2, 1),
)


class HarnessProgramCandidateReference(StrictModel):
    """Content identity for one kernel-policy-task-set-harness-program binding."""

    reference_sha256: NonEmptyStr
    cell: HarnessProgramCell
    kernel_ref: KernelRef
    kernel_abi_sha256: NonEmptyStr
    policy_sha256: NonEmptyStr
    task_set_id: NonEmptyStr
    task_set_sha256: NonEmptyStr
    harness_ref: HarnessInstanceRef
    harness_abi_sha256: NonEmptyStr
    program_ref: ExecutionProgramRef
    program_abi_sha256: NonEmptyStr
    resource_sha256: NonEmptyStr

    @field_validator(
        "reference_sha256",
        "kernel_abi_sha256",
        "policy_sha256",
        "task_set_sha256",
        "harness_abi_sha256",
        "program_abi_sha256",
        "resource_sha256",
    )
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        return _validate_sha256(value)

    @model_validator(mode="after")
    def validate_identity(self) -> HarnessProgramCandidateReference:
        if not (self.kernel_abi_sha256 == self.harness_abi_sha256 == self.program_abi_sha256):
            raise ValueError("candidate kernel, harness, and program must use one common ABI")
        expected = _canonical_sha256(self.model_dump(mode="json", exclude={"reference_sha256"}))
        if self.reference_sha256 != expected:
            raise ValueError("reference_sha256 must bind the canonical candidate reference")
        return self

    @classmethod
    def create(
        cls,
        *,
        cell: HarnessProgramCell | str,
        kernel_ref: KernelRef,
        kernel_abi_sha256: str,
        policy_sha256: str,
        task_set_id: str,
        task_set_sha256: str,
        harness_ref: HarnessInstanceRef,
        harness_abi_sha256: str,
        program_ref: ExecutionProgramRef,
        program_abi_sha256: str,
        resource_sha256: str,
    ) -> HarnessProgramCandidateReference:
        resolved_cell = HarnessProgramCell(cell)
        payload = {
            "cell": resolved_cell.value,
            "kernel_ref": kernel_ref.model_dump(mode="json"),
            "kernel_abi_sha256": kernel_abi_sha256,
            "policy_sha256": policy_sha256,
            "task_set_id": task_set_id,
            "task_set_sha256": task_set_sha256,
            "harness_ref": harness_ref.model_dump(mode="json"),
            "harness_abi_sha256": harness_abi_sha256,
            "program_ref": program_ref.model_dump(mode="json"),
            "program_abi_sha256": program_abi_sha256,
            "resource_sha256": resource_sha256,
        }
        return cls(
            reference_sha256=_canonical_sha256(payload),
            cell=resolved_cell,
            kernel_ref=kernel_ref,
            kernel_abi_sha256=kernel_abi_sha256,
            policy_sha256=policy_sha256,
            task_set_id=task_set_id,
            task_set_sha256=task_set_sha256,
            harness_ref=harness_ref,
            harness_abi_sha256=harness_abi_sha256,
            program_ref=program_ref,
            program_abi_sha256=program_abi_sha256,
            resource_sha256=resource_sha256,
        )


class HarnessProgramCandidateSet(StrictModel):
    """The four cross-compatible candidate references for one task set."""

    task_set_id: NonEmptyStr
    candidates: tuple[HarnessProgramCandidateReference, ...]

    @field_validator("candidates")
    @classmethod
    def canonicalize_candidates(
        cls,
        value: tuple[HarnessProgramCandidateReference, ...],
    ) -> tuple[HarnessProgramCandidateReference, ...]:
        return tuple(sorted(value, key=lambda candidate: _CELL_ORDER[candidate.cell]))

    @model_validator(mode="after")
    def validate_harness_program_integrity(self) -> HarnessProgramCandidateSet:
        cells = [candidate.cell for candidate in self.candidates]
        if len(cells) != len(HarnessProgramCell) or set(cells) != set(HarnessProgramCell):
            raise ValueError("candidate set requires exactly one candidate for each harness-program cell")
        if any(candidate.task_set_id != self.task_set_id for candidate in self.candidates):
            raise ValueError("harness-program candidates must share one task-set identity")
        _validate_shared_candidate_identities(self.candidates)
        _validate_harness_program_cell_factors({candidate.cell: candidate for candidate in self.candidates})
        return self


def _validate_shared_candidate_identities(
    candidates: tuple[HarnessProgramCandidateReference, ...],
) -> None:
    for field_name, label in (
        ("kernel_ref", "kernel"),
        ("kernel_abi_sha256", "kernel ABI"),
        ("policy_sha256", "policy"),
        ("task_set_sha256", "task set"),
        ("resource_sha256", "resource envelope"),
    ):
        if len({getattr(candidate, field_name) for candidate in candidates}) != 1:
            raise ValueError(f"harness-program candidates must share one {label}")


def _validate_harness_program_cell_factors(
    by_cell: dict[HarnessProgramCell, HarnessProgramCandidateReference],
) -> None:
    h0_p0 = by_cell[HarnessProgramCell.H0_P0]
    hx_p0 = by_cell[HarnessProgramCell.HX_P0]
    h0_px = by_cell[HarnessProgramCell.H0_PX]
    hx_px = by_cell[HarnessProgramCell.HX_PX]
    if h0_p0.harness_ref != h0_px.harness_ref:
        raise ValueError("h0_p0 and h0_px must share the fixed harness")
    if hx_p0.harness_ref != hx_px.harness_ref:
        raise ValueError("hx_p0 and hx_px must share the learned harness")
    if h0_p0.harness_ref == hx_p0.harness_ref:
        raise ValueError("learned harness must differ from the fixed harness")
    if h0_p0.program_ref != hx_p0.program_ref:
        raise ValueError("h0_p0 and hx_p0 must share the fixed program")
    if h0_px.program_ref != hx_px.program_ref:
        raise ValueError("h0_px and hx_px must share the learned program")
    if h0_p0.program_ref == h0_px.program_ref:
        raise ValueError("learned program must differ from the fixed program")


class HarnessProgramStudyDesign(StrictModel):
    """Preregistered execution design for the complete blocked harness-program."""

    interpretation: Literal["randomized_blocked_factorial"] = "randomized_blocked_factorial"
    execution_order: Literal["seeded_williams_square_v1"] = "seeded_williams_square_v1"
    counterbalanced: Literal[True] = True
    fresh_runtime_per_cell: Literal[True] = True
    cluster_unit: Literal["task_set"] = "task_set"


class HarnessProgramStudyManifest(StrictModel):
    """Inputs needed to expand a deterministic harness-program study plan."""

    schema_version: Literal["1"] = "1"
    experiment_id: NonEmptyStr
    randomization_seed: int
    repetitions: PositiveInt
    candidate_sets: tuple[HarnessProgramCandidateSet, ...]
    study_design: HarnessProgramStudyDesign = HarnessProgramStudyDesign()

    @field_validator("candidate_sets")
    @classmethod
    def canonicalize_candidate_sets(
        cls,
        value: tuple[HarnessProgramCandidateSet, ...],
    ) -> tuple[HarnessProgramCandidateSet, ...]:
        if not value:
            raise ValueError("harness-program study requires at least one candidate set")
        ordered = tuple(sorted(value, key=lambda candidate_set: candidate_set.task_set_id))
        task_set_ids = [candidate_set.task_set_id for candidate_set in ordered]
        if len(task_set_ids) != len(set(task_set_ids)):
            raise ValueError("harness-program candidate-set task-set ids must be unique")
        return ordered

    @model_validator(mode="after")
    def validate_shared_study_factors(self) -> HarnessProgramStudyManifest:
        references = [candidate_set.candidates[0] for candidate_set in self.candidate_sets]
        for field_name, label in (
            ("kernel_ref", "kernel"),
            ("kernel_abi_sha256", "kernel ABI"),
            ("policy_sha256", "policy"),
            ("resource_sha256", "resource envelope"),
        ):
            if len({getattr(reference, field_name) for reference in references}) != 1:
                raise ValueError(f"harness-program study task sets must share one {label}")
        return self


class HarnessProgramTrial(StrictModel):
    """One ordered treatment execution within a paired task-set block."""

    trial_id: NonEmptyStr
    experiment_id: NonEmptyStr
    block_id: NonEmptyStr
    sequence_index: PositiveInt
    task_set_id: NonEmptyStr
    task_set_sha256: NonEmptyStr
    repetition: PositiveInt
    order_index: PositiveInt
    cell: HarnessProgramCell
    candidate: HarnessProgramCandidateReference

    @field_validator("task_set_sha256")
    @classmethod
    def validate_task_set_hash(cls, value: str) -> str:
        return _validate_sha256(value)

    @model_validator(mode="after")
    def validate_trial_identity(self) -> HarnessProgramTrial:
        if self.order_index > len(HarnessProgramCell):
            raise ValueError("harness-program trial order_index must be between 1 and 4")
        if self.candidate.cell is not self.cell:
            raise ValueError("harness-program trial cell must match its candidate")
        if self.candidate.task_set_id != self.task_set_id or self.candidate.task_set_sha256 != self.task_set_sha256:
            raise ValueError("harness-program trial task set must match its candidate")
        expected = _trial_id(
            experiment_id=self.experiment_id,
            block_id=self.block_id,
            sequence_index=self.sequence_index,
            task_set_sha256=self.task_set_sha256,
            repetition=self.repetition,
            order_index=self.order_index,
            cell=self.cell,
            candidate_sha256=self.candidate.reference_sha256,
        )
        if self.trial_id != expected:
            raise ValueError("trial_id must bind the canonical harness-program trial")
        return self


class HarnessProgramBlock(StrictModel):
    """One complete four-cell block for one task set and repetition."""

    block_id: NonEmptyStr
    experiment_id: NonEmptyStr
    sequence_index: PositiveInt
    task_set_id: NonEmptyStr
    task_set_sha256: NonEmptyStr
    repetition: PositiveInt
    trials: tuple[HarnessProgramTrial, ...]

    @field_validator("task_set_sha256")
    @classmethod
    def validate_task_set_hash(cls, value: str) -> str:
        return _validate_sha256(value)

    @model_validator(mode="after")
    def validate_complete_block(self) -> HarnessProgramBlock:
        expected_block_id = _block_id(
            experiment_id=self.experiment_id,
            sequence_index=self.sequence_index,
            task_set_sha256=self.task_set_sha256,
            repetition=self.repetition,
        )
        if self.block_id != expected_block_id:
            raise ValueError("block_id must bind the canonical harness-program block")
        if len(self.trials) != len(HarnessProgramCell):
            raise ValueError("block trials must contain exactly four cells")
        if [trial.order_index for trial in self.trials] != [1, 2, 3, 4]:
            raise ValueError("block trials must use canonical execution order")
        if {trial.cell for trial in self.trials} != set(HarnessProgramCell):
            raise ValueError("block trials must contain every harness-program cell")
        if any(
            trial.block_id != self.block_id
            or trial.experiment_id != self.experiment_id
            or trial.sequence_index != self.sequence_index
            or trial.task_set_id != self.task_set_id
            or trial.task_set_sha256 != self.task_set_sha256
            or trial.repetition != self.repetition
            for trial in self.trials
        ):
            raise ValueError("block trials must match their parent block")
        HarnessProgramCandidateSet(
            task_set_id=self.task_set_id, candidates=tuple(trial.candidate for trial in self.trials)
        )
        return self


class HarnessProgramPlan(StrictModel):
    """Content-bound expansion of a complete blocked harness-program study."""

    schema_version: Literal["1"] = "1"
    plan_sha256: NonEmptyStr
    manifest_sha256: NonEmptyStr
    experiment_id: NonEmptyStr
    randomization_seed: int
    repetitions: PositiveInt
    study_design: HarnessProgramStudyDesign
    trial_count: PositiveInt
    blocks: tuple[HarnessProgramBlock, ...]
    trials: tuple[HarnessProgramTrial, ...]

    @field_validator("plan_sha256", "manifest_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return _validate_sha256(value)

    @model_validator(mode="after")
    def validate_plan(self) -> HarnessProgramPlan:
        expected_hash = _canonical_sha256(self.model_dump(mode="json", exclude={"plan_sha256"}))
        if self.plan_sha256 != expected_hash:
            raise ValueError("plan_sha256 must bind the canonical harness-program plan")
        if self.trial_count != len(self.trials):
            raise ValueError("trial_count must equal the number of harness-program trials")
        if [block.sequence_index for block in self.blocks] != list(range(1, len(self.blocks) + 1)):
            raise ValueError("harness-program blocks must use contiguous canonical sequence indexes")
        flattened = tuple(trial for block in self.blocks for trial in block.trials)
        if self.trials != flattened:
            raise ValueError("plan trials must equal the ordered block trials")
        if len({trial.trial_id for trial in self.trials}) != len(self.trials):
            raise ValueError("harness-program trial ids must be unique")
        if any(trial.experiment_id != self.experiment_id for trial in self.trials):
            raise ValueError("harness-program trials must match the plan experiment")
        return self


def build_harness_program_plan(manifest: HarnessProgramStudyManifest) -> HarnessProgramPlan:
    """Expand candidate sets into deterministic, position-balanced four-cell blocks."""

    manifest = HarnessProgramStudyManifest.model_validate(manifest.model_dump(mode="json"))
    manifest_sha256 = _canonical_sha256(manifest.model_dump(mode="json"))
    randomizer = random.Random(manifest.randomization_seed)
    labels = list(HarnessProgramCell)
    randomizer.shuffle(labels)
    row_offset = randomizer.randrange(len(_WILLIAMS_ROWS))
    blocks: list[HarnessProgramBlock] = []

    for candidate_set in manifest.candidate_sets:
        by_cell = {candidate.cell: candidate for candidate in candidate_set.candidates}
        task_set_sha256 = candidate_set.candidates[0].task_set_sha256
        for repetition in range(1, manifest.repetitions + 1):
            sequence_index = len(blocks) + 1
            row = _WILLIAMS_ROWS[(sequence_index - 1 + row_offset) % len(_WILLIAMS_ROWS)]
            ordered_cells = tuple(labels[index] for index in row)
            block_id = _block_id(
                experiment_id=manifest.experiment_id,
                sequence_index=sequence_index,
                task_set_sha256=task_set_sha256,
                repetition=repetition,
            )
            trials = tuple(
                _build_trial(
                    experiment_id=manifest.experiment_id,
                    block_id=block_id,
                    sequence_index=sequence_index,
                    task_set_id=candidate_set.task_set_id,
                    task_set_sha256=task_set_sha256,
                    repetition=repetition,
                    order_index=order_index,
                    cell=cell,
                    candidate=by_cell[cell],
                )
                for order_index, cell in enumerate(ordered_cells, start=1)
            )
            blocks.append(
                HarnessProgramBlock(
                    block_id=block_id,
                    experiment_id=manifest.experiment_id,
                    sequence_index=sequence_index,
                    task_set_id=candidate_set.task_set_id,
                    task_set_sha256=task_set_sha256,
                    repetition=repetition,
                    trials=trials,
                )
            )

    flattened = tuple(trial for block in blocks for trial in block.trials)
    payload: dict[str, Any] = {
        "schema_version": "1",
        "manifest_sha256": manifest_sha256,
        "experiment_id": manifest.experiment_id,
        "randomization_seed": manifest.randomization_seed,
        "repetitions": manifest.repetitions,
        "study_design": manifest.study_design.model_dump(mode="json"),
        "trial_count": len(flattened),
        "blocks": [block.model_dump(mode="json") for block in blocks],
        "trials": [trial.model_dump(mode="json") for trial in flattened],
    }
    return HarnessProgramPlan(plan_sha256=_canonical_sha256(payload), **payload)


def _build_trial(
    *,
    experiment_id: str,
    block_id: str,
    sequence_index: int,
    task_set_id: str,
    task_set_sha256: str,
    repetition: int,
    order_index: int,
    cell: HarnessProgramCell,
    candidate: HarnessProgramCandidateReference,
) -> HarnessProgramTrial:
    return HarnessProgramTrial(
        trial_id=_trial_id(
            experiment_id=experiment_id,
            block_id=block_id,
            sequence_index=sequence_index,
            task_set_sha256=task_set_sha256,
            repetition=repetition,
            order_index=order_index,
            cell=cell,
            candidate_sha256=candidate.reference_sha256,
        ),
        experiment_id=experiment_id,
        block_id=block_id,
        sequence_index=sequence_index,
        task_set_id=task_set_id,
        task_set_sha256=task_set_sha256,
        repetition=repetition,
        order_index=order_index,
        cell=cell,
        candidate=candidate,
    )


def _block_id(*, experiment_id: str, sequence_index: int, task_set_sha256: str, repetition: int) -> str:
    return f"block-{
        _canonical_sha256(
            {
                'experiment_id': experiment_id,
                'sequence_index': sequence_index,
                'task_set_sha256': task_set_sha256,
                'repetition': repetition,
            }
        )
    }"


def _trial_id(
    *,
    experiment_id: str,
    block_id: str,
    sequence_index: int,
    task_set_sha256: str,
    repetition: int,
    order_index: int,
    cell: HarnessProgramCell,
    candidate_sha256: str,
) -> str:
    return f"trial-{
        _canonical_sha256(
            {
                'experiment_id': experiment_id,
                'block_id': block_id,
                'sequence_index': sequence_index,
                'task_set_sha256': task_set_sha256,
                'repetition': repetition,
                'order_index': order_index,
                'cell': cell.value,
                'candidate_sha256': candidate_sha256,
            }
        )
    }"


def _validate_sha256(value: str) -> str:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError("sha256 must contain 64 lowercase hexadecimal characters")
    return value


def _canonical_sha256(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
