# ABOUTME: Defines the generic content-addressed specification and runner for one paired repair attempt.
# ABOUTME: Reuses RepairRuntime and shared adaptive diagnosis rules without requiring a full adaptive cycle.

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Never, Self

from pydantic import field_validator, model_validator

from aec_bench.contracts.harness_instance import TaskSourceBindingConfig
from aec_bench.contracts.harness_kernel import FrozenStrictModel, validate_sha256
from aec_bench.contracts.legacy_content_address import LegacyContentAddressedModel
from aec_bench.contracts.run_bundle import TaskSnapshotRef
from aec_bench.contracts.trial_record import ArtifactReference
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.evolution.repair_lifecycle import (
    RepairCandidate,
    RepairLoopRequest,
    RepairLoopResult,
    RepairLoopStatus,
)
from aec_bench.experimentation.qualification.adaptive_diagnosis import (
    AdaptiveDiagnosisConfiguration,
    diagnosis_function_for_configuration,
    validate_adaptive_diagnosis_feasibility,
)
from aec_bench.experimentation.qualification.repair_runtime import (
    RepairAttemptPlan,
    RepairEvidenceUsePolicy,
    RepairRuntime,
    RepairRuntimeExecution,
    RepairTerminalRecord,
    RepairVerifierPolicy,
)
from aec_bench.harness.compilation.task_snapshot import resolve_task_snapshots
from aec_bench.harness.harbor_dispatch import HarborCommandExecutor
from aec_bench.harness.harbor_workflow import SynchronousHarborWorkflow
from aec_bench.harness.kernel_catalogue import KernelRuntimeRegistry


class RepairRunSpec(LegacyContentAddressedModel):
    """Immutable inputs needed to execute exactly one evidence-gated paired repair."""

    schema_version: Literal["aecbench.repair-run-spec.v3"] = "aecbench.repair-run-spec.v3"
    request: RepairLoopRequest
    parent: RepairCandidate
    evidence_use_policy: RepairEvidenceUsePolicy
    verifier_policy: RepairVerifierPolicy
    diagnosis_rule: AdaptiveDiagnosisConfiguration
    policy_id: NonEmptyStr
    harness_generator_sha256: str
    program_generator_sha256: str
    task_snapshots: tuple[TaskSnapshotRef, ...]

    @field_validator("harness_generator_sha256", "program_generator_sha256")
    @classmethod
    def validate_generator_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_parent(self) -> Self:
        if self.evidence_use_policy != RepairEvidenceUsePolicy.exploratory_matched_repair():
            raise ValueError("standalone repair spec requires the exploratory matched-repair evidence-use policy")
        if self.parent.candidate_id != self.request.parent_candidate_id:
            raise ValueError("repair parent does not match its request")
        source_bindings = tuple(
            binding.configuration
            for binding in self.parent.harness_request.recipe.bindings
            if isinstance(binding.configuration, TaskSourceBindingConfig)
        )
        if len(source_bindings) != 1:
            raise ValueError("repair parent must contain exactly one task-source binding")
        task_refs = tuple(snapshot.task_id for snapshot in self.task_snapshots)
        if task_refs != self.request.pairing.task_ids or task_refs != source_bindings[0].task_refs:
            raise ValueError("repair task snapshots must exactly match request and parent task refs")
        validate_adaptive_diagnosis_feasibility(
            self.diagnosis_rule,
            candidate=self.parent,
            pairing=self.request.pairing,
        )
        return self


class RepairAttemptClaimError(RuntimeError):
    """Fail-closed attempt-identity error that never authorises an automatic resume."""


class RepairAttemptClaim(LegacyContentAddressedModel):
    """Exclusive declaration that one exact repair spec owns an attempt identity."""

    schema_version: Literal["aecbench.repair-attempt-claim.v1"] = "aecbench.repair-attempt-claim.v1"
    claim_key: str
    loop_id: NonEmptyStr
    attempt_id: NonEmptyStr
    parent_candidate_id: NonEmptyStr
    child_candidate_id: NonEmptyStr
    repair_run_spec_content_sha256: str
    repair_run_spec: ArtifactReference

    @field_validator("claim_key", "repair_run_spec_content_sha256")
    @classmethod
    def validate_claim_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_claim_identity(self) -> Self:
        if self.claim_key != _repair_attempt_claim_key(loop_id=self.loop_id, attempt_id=self.attempt_id):
            raise ValueError("repair attempt claim key does not match its loop and attempt identity")
        if self.repair_run_spec.kind != "repair-run-spec":
            raise ValueError("repair attempt claim must reference one repair-run-spec artifact")
        return self


class RepairAttemptCompletion(LegacyContentAddressedModel):
    """Immutable success receipt joining an exclusive attempt claim to its terminal artifact."""

    schema_version: Literal["aecbench.repair-attempt-completion.v2"] = "aecbench.repair-attempt-completion.v2"
    claim_key: str
    claim_content_sha256: str
    loop_id: NonEmptyStr
    attempt_id: NonEmptyStr
    repair_run_spec: ArtifactReference
    attempt_plan: ArtifactReference
    terminal_status: RepairLoopStatus
    evidence_use_policy: RepairEvidenceUsePolicy
    terminal: ArtifactReference

    @field_validator("claim_key", "claim_content_sha256")
    @classmethod
    def validate_completion_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_completion_identity(self) -> Self:
        if self.claim_key != _repair_attempt_claim_key(loop_id=self.loop_id, attempt_id=self.attempt_id):
            raise ValueError("repair attempt completion key does not match its loop and attempt identity")
        if self.repair_run_spec.kind != "repair-run-spec":
            raise ValueError("repair attempt completion must reference one repair-run-spec artifact")
        if self.attempt_plan.kind != "repair-attempt-plan":
            raise ValueError("repair attempt completion must reference one repair-attempt-plan artifact")
        if self.terminal.kind != "repair-terminal":
            raise ValueError("repair attempt completion must reference one repair-terminal artifact")
        return self


@dataclass(frozen=True)
class _RepairAttemptLease:
    claim: RepairAttemptClaim
    claim_path: Path
    completion_path: Path


def prepare_repair_run_spec(
    *,
    request: RepairLoopRequest,
    parent: RepairCandidate,
    verifier_policy: RepairVerifierPolicy,
    evidence_use_policy: RepairEvidenceUsePolicy,
    diagnosis_rule: AdaptiveDiagnosisConfiguration,
    policy_id: str,
    harness_generator_sha256: str,
    program_generator_sha256: str,
    tasks_root: Path,
    registry: KernelRuntimeRegistry,
) -> RepairRunSpec:
    """Resolve the exact fixed-K task/task-review bytes and return a preregistered repair spec."""

    if parent.harness_request.kernel_ref != registry.manifest.ref:
        raise ValueError("repair parent does not target the current fixed kernel")
    snapshots = resolve_task_snapshots(
        task_refs=request.pairing.task_ids,
        tasks_root=Path(tasks_root),
    )
    return RepairRunSpec(
        request=request,
        parent=parent,
        evidence_use_policy=evidence_use_policy,
        verifier_policy=verifier_policy,
        diagnosis_rule=diagnosis_rule,
        policy_id=policy_id,
        harness_generator_sha256=harness_generator_sha256,
        program_generator_sha256=program_generator_sha256,
        task_snapshots=snapshots,
    )


def run_repair(
    *,
    spec: RepairRunSpec,
    registry: KernelRuntimeRegistry,
    workflow: SynchronousHarborWorkflow,
    artifacts_root: Path,
    executor: HarborCommandExecutor | None = None,
) -> RepairRuntimeExecution:
    """Execute one strict repair spec through the installed compiler, Harbor, verifier, and repair loop."""

    source = RepairRunSpec.model_validate(spec.model_dump(mode="python"))
    if source.parent.harness_request.kernel_ref != registry.manifest.ref:
        raise ValueError("configured repair parent does not target the installed fixed kernel")
    current_snapshots = resolve_task_snapshots(
        task_refs=source.request.pairing.task_ids,
        tasks_root=workflow.tasks_root,
    )
    if current_snapshots != source.task_snapshots:
        raise ValueError("repair spec task/task-review snapshots drifted before execution")
    artifacts_path = Path(artifacts_root)
    spec_artifact = _store_spec(source, artifacts_root=artifacts_path)
    attempt_lease = _claim_repair_attempt(
        spec=source,
        spec_artifact=spec_artifact,
        artifacts_root=artifacts_path,
    )
    runtime = RepairRuntime(
        request=source.request,
        parent=source.parent,
        registry=registry,
        workflow=workflow,
        artifacts_root=artifacts_path,
        policy_id=source.policy_id,
        harness_generator_sha256=source.harness_generator_sha256,
        program_generator_sha256=source.program_generator_sha256,
        verifier_policy=source.verifier_policy,
        evidence_use_policy=source.evidence_use_policy,
        diagnosis=diagnosis_function_for_configuration(source.diagnosis_rule),
        repair_run_spec=spec_artifact,
        preregistered_task_snapshots=source.task_snapshots,
        executor=executor,
    )
    execution = runtime.execute()
    _complete_repair_attempt(attempt_lease, execution=execution)
    return execution


def _store_spec(spec: RepairRunSpec, *, artifacts_root: Path) -> ArtifactReference:
    encoded = _model_bytes(spec)
    sha256 = hashlib.sha256(encoded).hexdigest()
    path = artifacts_root / "repair-specs" / sha256 / "repair-run-spec.json"
    _ensure_directory(path.parent)
    try:
        _write_exclusive(path, encoded)
    except FileExistsError as exists_error:
        try:
            existing = path.read_bytes()
        except OSError as error:
            raise ValueError("content-addressed repair spec path is unreadable") from error
        if existing != encoded:
            raise ValueError("content-addressed repair spec path contains different bytes") from exists_error
    return ArtifactReference(
        kind="repair-run-spec",
        path=str(path),
        sha256=sha256,
        media_type="application/json",
    )


def _claim_repair_attempt(
    *,
    spec: RepairRunSpec,
    spec_artifact: ArtifactReference,
    artifacts_root: Path,
) -> _RepairAttemptLease:
    """Acquire one cross-process attempt claim with exclusive file creation."""

    claim_key = _repair_attempt_claim_key(
        loop_id=spec.request.loop_id,
        attempt_id=spec.request.attempt_id,
    )
    claim_root = Path(artifacts_root) / "repair-attempt-claims" / claim_key
    _ensure_directory(claim_root)
    claim_path = claim_root / "claim.json"
    completion_path = claim_root / "completion.json"
    claim = RepairAttemptClaim(
        claim_key=claim_key,
        loop_id=spec.request.loop_id,
        attempt_id=spec.request.attempt_id,
        parent_candidate_id=spec.request.parent_candidate_id,
        child_candidate_id=spec.request.child_candidate_id,
        repair_run_spec_content_sha256=spec.content_sha256,
        repair_run_spec=spec_artifact,
    )
    if _path_exists(completion_path) and not _path_exists(claim_path):
        raise RepairAttemptClaimError(
            "repair attempt has an orphan completion receipt without its claim; refusing execution"
        )
    try:
        _write_exclusive(claim_path, _model_bytes(claim))
    except FileExistsError:
        _reject_existing_attempt_claim(
            expected=claim,
            claim_path=claim_path,
            completion_path=completion_path,
        )
    if _path_exists(completion_path):
        raise RepairAttemptClaimError(
            "repair attempt completion appeared while acquiring its claim; refusing execution"
        )
    return _RepairAttemptLease(
        claim=claim,
        claim_path=claim_path,
        completion_path=completion_path,
    )


def _complete_repair_attempt(
    lease: _RepairAttemptLease,
    *,
    execution: RepairRuntimeExecution,
) -> RepairAttemptCompletion:
    """Persist a terminal receipt only while the exact acquired claim remains clean."""

    _require_canonical_model(
        lease.claim_path,
        RepairAttemptClaim,
        label="repair attempt claim",
        expected=lease.claim,
    )
    _validate_claimed_spec(lease.claim)
    _require_stored_artifact_path(
        execution.attempt_plan.path,
        execution.attempt_plan.reference,
        label="repair attempt plan",
    )
    _validate_attempt_plan_for_claim(
        execution.attempt_plan.reference,
        claim=lease.claim,
    )
    _require_stored_artifact_path(
        execution.terminal.path,
        execution.terminal.reference,
        label="repair terminal",
    )
    terminal = _validate_terminal_for_claim(
        execution.terminal.reference,
        claim=lease.claim,
        attempt_plan=execution.attempt_plan.reference,
        expected_result=execution.result,
    )
    completion = RepairAttemptCompletion(
        claim_key=lease.claim.claim_key,
        claim_content_sha256=lease.claim.content_sha256,
        loop_id=lease.claim.loop_id,
        attempt_id=lease.claim.attempt_id,
        repair_run_spec=lease.claim.repair_run_spec,
        attempt_plan=execution.attempt_plan.reference,
        terminal_status=terminal.result.status,
        evidence_use_policy=terminal.evidence_use_policy,
        terminal=execution.terminal.reference,
    )
    try:
        _write_exclusive(lease.completion_path, _model_bytes(completion))
    except FileExistsError as error:
        raise RepairAttemptClaimError(
            "repair attempt completion receipt already exists; refusing to overwrite it"
        ) from error
    return completion


def _reject_existing_attempt_claim(
    *,
    expected: RepairAttemptClaim,
    claim_path: Path,
    completion_path: Path,
) -> Never:
    existing = _require_canonical_model(
        claim_path,
        RepairAttemptClaim,
        label="repair attempt claim",
    )
    if existing != expected:
        raise RepairAttemptClaimError("repair attempt identity is already claimed by a different exact RepairRunSpec")
    _validate_claimed_spec(existing)
    if not _path_exists(completion_path):
        raise RepairAttemptClaimError(
            "repair attempt claim is incomplete or active; refusing concurrent execution or unsafe auto-resume"
        )
    completion = _require_canonical_model(
        completion_path,
        RepairAttemptCompletion,
        label="repair attempt completion receipt",
    )
    if (
        completion.claim_key != existing.claim_key
        or completion.claim_content_sha256 != existing.content_sha256
        or completion.loop_id != existing.loop_id
        or completion.attempt_id != existing.attempt_id
        or completion.repair_run_spec != existing.repair_run_spec
    ):
        raise RepairAttemptClaimError(
            "repair attempt completion receipt does not match its exact claim; refusing execution"
        )
    plan = _validate_attempt_plan_for_claim(completion.attempt_plan, claim=existing)
    terminal = _validate_terminal_for_claim(
        completion.terminal,
        claim=existing,
        attempt_plan=completion.attempt_plan,
    )
    if completion.terminal_status is not terminal.result.status:
        raise RepairAttemptClaimError(
            "repair attempt completion status does not match its terminal; refusing execution"
        )
    if completion.evidence_use_policy != plan.evidence_use_policy:
        raise RepairAttemptClaimError(
            "repair attempt completion evidence-use policy does not match its exact spec; refusing execution"
        )
    raise RepairAttemptClaimError("repair attempt already completed; refusing duplicate execution")


def _validate_claimed_spec(claim: RepairAttemptClaim) -> RepairRunSpec:
    _verify_artifact_reference(claim.repair_run_spec, label="claimed repair run spec")
    spec = _require_canonical_model(
        Path(claim.repair_run_spec.path),
        RepairRunSpec,
        label="claimed repair run spec",
    )
    if spec.content_sha256 != claim.repair_run_spec_content_sha256:
        raise RepairAttemptClaimError(
            "claimed repair run spec content identity does not match its claim; refusing execution"
        )
    if (
        spec.request.loop_id != claim.loop_id
        or spec.request.attempt_id != claim.attempt_id
        or spec.request.parent_candidate_id != claim.parent_candidate_id
        or spec.request.child_candidate_id != claim.child_candidate_id
    ):
        raise RepairAttemptClaimError(
            "claimed repair run spec request identity does not match its claim; refusing execution"
        )
    return spec


def _validate_attempt_plan_for_claim(
    reference: ArtifactReference,
    *,
    claim: RepairAttemptClaim,
) -> RepairAttemptPlan:
    if reference.kind != "repair-attempt-plan":
        raise RepairAttemptClaimError("repair attempt plan artifact has the wrong kind")
    _verify_artifact_reference(reference, label="repair attempt plan")
    plan = _require_canonical_model(
        Path(reference.path),
        RepairAttemptPlan,
        label="repair attempt plan",
    )
    spec = _validate_claimed_spec(claim)
    if (
        plan.request != spec.request
        or plan.parent != spec.parent
        or plan.evidence_use_policy != spec.evidence_use_policy
        or plan.repair_run_spec != claim.repair_run_spec
    ):
        raise RepairAttemptClaimError("repair attempt plan does not match its claimed spec; refusing execution")
    return plan


def _validate_terminal_for_claim(
    reference: ArtifactReference,
    *,
    claim: RepairAttemptClaim,
    attempt_plan: ArtifactReference,
    expected_result: RepairLoopResult | None = None,
) -> RepairTerminalRecord:
    if reference.kind != "repair-terminal":
        raise RepairAttemptClaimError("repair terminal artifact has the wrong kind")
    _verify_artifact_reference(reference, label="repair terminal")
    terminal = _require_canonical_model(
        Path(reference.path),
        RepairTerminalRecord,
        label="repair terminal",
    )
    if expected_result is not None and terminal.result != expected_result:
        raise RepairAttemptClaimError("repair terminal result does not match the completed runtime execution")
    if (
        terminal.result.loop_id != claim.loop_id
        or terminal.result.attempt_id != claim.attempt_id
        or terminal.result.parent_candidate_id != claim.parent_candidate_id
        or terminal.result.child_candidate_id not in {None, claim.child_candidate_id}
    ):
        raise RepairAttemptClaimError("repair terminal result identity does not match its claim; refusing completion")
    if terminal.repair_run_spec != claim.repair_run_spec:
        raise RepairAttemptClaimError(
            "repair terminal does not reference its claimed repair run spec; refusing completion"
        )
    spec = _validate_claimed_spec(claim)
    if terminal.evidence_use_policy != spec.evidence_use_policy:
        raise RepairAttemptClaimError(
            "repair terminal evidence-use policy does not match its claimed spec; refusing completion"
        )
    if terminal.attempt_plan_sha256 != attempt_plan.sha256:
        raise RepairAttemptClaimError("repair terminal does not reference its exact attempt plan; refusing completion")
    return terminal


def _require_stored_artifact_path(
    path: Path,
    reference: ArtifactReference,
    *,
    label: str,
) -> None:
    if str(path) != reference.path:
        raise RepairAttemptClaimError(f"{label} path differs from its artifact reference")


def _repair_attempt_claim_key(*, loop_id: str, attempt_id: str) -> str:
    encoded = json.dumps(
        {
            "attempt_id": attempt_id,
            "loop_id": loop_id,
            "schema_version": "aecbench.repair-attempt-identity.v1",
        },
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _model_bytes(model: FrozenStrictModel) -> bytes:
    return (json.dumps(model.model_dump(mode="json"), indent=2, sort_keys=True) + "\n").encode("utf-8")


def _write_exclusive(path: Path, encoded: bytes) -> None:
    """Create one immutable file atomically; leave partial bytes fail-closed after interruption."""

    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        remaining = memoryview(encoded)
        while remaining:
            written = os.write(descriptor, remaining)
            if written <= 0:
                raise OSError("exclusive repair-attempt write made no progress")
            remaining = remaining[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    _fsync_directory(path.parent)


def _ensure_directory(path: Path) -> None:
    """Create each missing directory and durably publish its parent entry."""

    missing: list[Path] = []
    candidate = path
    while not candidate.exists():
        missing.append(candidate)
        if candidate.parent == candidate:
            break
        candidate = candidate.parent
    for directory in reversed(missing):
        try:
            directory.mkdir()
        except FileExistsError:
            if not directory.is_dir():
                raise
        _fsync_directory(directory.parent)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _require_canonical_model[ModelT: FrozenStrictModel](
    path: Path,
    model_type: type[ModelT],
    *,
    label: str,
    expected: ModelT | None = None,
) -> ModelT:
    try:
        encoded = path.read_bytes()
        model = model_type.model_validate_json(encoded)
    except (OSError, ValueError) as error:
        raise RepairAttemptClaimError(f"{label} is corrupt or unreadable; refusing execution") from error
    if encoded != _model_bytes(model):
        raise RepairAttemptClaimError(f"{label} is corrupt or non-canonical; refusing execution")
    if expected is not None and model != expected:
        raise RepairAttemptClaimError(f"{label} changed after acquisition; refusing completion")
    return model


def _verify_artifact_reference(reference: ArtifactReference, *, label: str) -> None:
    path = Path(reference.path)
    try:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        raise RepairAttemptClaimError(f"{label} artifact is missing or unreadable") from error
    if digest != reference.sha256:
        raise RepairAttemptClaimError(f"{label} artifact hash mismatch")


def _path_exists(path: Path) -> bool:
    return os.path.lexists(path)
