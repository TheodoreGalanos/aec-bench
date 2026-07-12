# ABOUTME: Defines private target commitments and one-shot audit publication contracts.
# ABOUTME: Binds sealed provider semantics while exposing only aggregate holdout evidence publicly.

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal, TypeVar

from pydantic import Field, FiniteFloat, NonNegativeInt, field_validator, model_validator

from aec_bench.contracts.trial_record import ArtifactReference, TrialRecord
from aec_bench.contracts.validators import NonEmptyStr, StrictModel
from aec_bench.ledger.durability import fsync_directory, mkdir_durable
from aec_bench.meta_harness.evidence_lifecycle import evidence_lifecycle_package_identity
from aec_bench.meta_harness.evidence_lifecycle_ablation_plan import (
    LifecycleAblationManifest,
    build_lifecycle_ablation_plan,
)
from aec_bench.meta_harness.evidence_lifecycle_calibration import (
    LifecycleCalibrationFreeze,
)
from aec_bench.meta_harness.evidence_lifecycle_transfer import (
    LifecycleTransferEvaluationSpec,
    build_sealed_lifecycle_transfer_evaluation,
)
from aec_bench.task_world_templates.lifecycles import (
    SealedLifecycleMount,
    sealed_lifecycle_provider_protocol_identity,
)

__all__ = [
    "LifecycleHoldoutAuditAlreadyClaimedError",
    "LifecycleHoldoutAuditClaim",
    "LifecycleHoldoutAuditOutcomeCounts",
    "LifecycleHoldoutAuditReceipt",
    "LifecycleHoldoutProviderIdentity",
    "LifecycleHoldoutPrivateLayout",
    "LifecycleHoldoutTargetCommitment",
    "LifecycleHoldoutTargetFreeze",
    "build_lifecycle_holdout_audit_receipt",
    "claim_lifecycle_holdout_audit",
    "lifecycle_holdout_private_layout",
    "validate_lifecycle_holdout_target_mount",
    "validate_lifecycle_holdout_target_freeze",
    "write_lifecycle_holdout_audit_receipt",
    "write_lifecycle_holdout_target_commitment",
    "write_lifecycle_holdout_target_freeze",
]

_BoundedReward = Annotated[FiniteFloat, Field(ge=0.0, le=1.0)]
_TARGET_COMMITMENT_DOMAIN = b"aec-bench.sealed-lifecycle-target.v1\x00"
_ModelT = TypeVar("_ModelT", bound=StrictModel)


class LifecycleHoldoutAuditAlreadyClaimedError(ValueError):
    """Report that the private authority already consumed its one execution slot."""


@dataclass(frozen=True)
class LifecycleHoldoutPrivateLayout:
    """Derive every private audit path from the root frozen before public results."""

    root: Path
    calibration_freeze_path: Path
    target_freeze_path: Path
    claim_path: Path
    execution_root: Path
    run_start_path: Path
    run_dir: Path
    ledger_root: Path


class LifecycleHoldoutProviderIdentity(StrictModel):
    """Bind opaque implementation identities without exposing provider source or names."""

    schema_version: Literal["1"] = "1"
    provider_contract_sha256: NonEmptyStr
    resolver_contract_sha256: NonEmptyStr
    verifier_contract_sha256: NonEmptyStr

    @field_validator(
        "provider_contract_sha256",
        "resolver_contract_sha256",
        "verifier_contract_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return ArtifactReference.validate_sha256(value)


class LifecycleHoldoutTargetFreeze(StrictModel):
    """Privately freeze one already-selected target before public results are observed."""

    schema_version: Literal["1"] = "1"
    target_freeze_sha256: NonEmptyStr
    public_target_commitment_sha256: NonEmptyStr
    public_experiment_id: NonEmptyStr
    public_manifest_sha256: NonEmptyStr
    public_plan_sha256: NonEmptyStr
    public_selection_policy_sha256: NonEmptyStr
    private_audit_root: NonEmptyStr
    holdout_repetitions: Literal[1]
    lifecycle_id: NonEmptyStr
    world_id: NonEmptyStr
    lifecycle_spec_sha256: NonEmptyStr
    package_sha256: NonEmptyStr
    package_tree_sha256: NonEmptyStr
    provider_protocol_sha256: NonEmptyStr
    provider_identity: LifecycleHoldoutProviderIdentity
    commitment_salt: NonEmptyStr

    @field_validator(
        "target_freeze_sha256",
        "public_target_commitment_sha256",
        "public_manifest_sha256",
        "public_plan_sha256",
        "public_selection_policy_sha256",
        "lifecycle_spec_sha256",
        "package_sha256",
        "package_tree_sha256",
        "provider_protocol_sha256",
        "commitment_salt",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return ArtifactReference.validate_sha256(value)

    @field_validator("private_audit_root")
    @classmethod
    def validate_private_audit_root(cls, value: str) -> str:
        path = Path(value)
        if not path.is_absolute() or path.resolve(strict=False) != path:
            raise ValueError("private audit root must be a canonical absolute path")
        return value

    @model_validator(mode="after")
    def validate_commitments(self) -> LifecycleHoldoutTargetFreeze:
        payload = self.model_dump(
            mode="json",
            exclude={"target_freeze_sha256", "public_target_commitment_sha256"},
        )
        expected_freeze = _canonical_sha256(payload)
        if self.target_freeze_sha256 != expected_freeze:
            raise ValueError("target freeze hash does not bind its canonical private payload")
        expected_public = _target_commitment_sha256(
            commitment_salt=self.commitment_salt,
            target_freeze_sha256=expected_freeze,
        )
        if self.public_target_commitment_sha256 != expected_public:
            raise ValueError("public target commitment does not bind the private target freeze")
        return self


class LifecycleHoldoutTargetCommitment(StrictModel):
    """Publish an opaque pre-campaign commitment without revealing target identity."""

    schema_version: Literal["1"] = "1"
    publication_sha256: NonEmptyStr
    target_commitment_sha256: NonEmptyStr
    public_experiment_id: NonEmptyStr
    public_manifest_sha256: NonEmptyStr
    public_plan_sha256: NonEmptyStr
    target_selected_before_public_results: Literal[True] = True

    @field_validator(
        "publication_sha256",
        "target_commitment_sha256",
        "public_manifest_sha256",
        "public_plan_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return ArtifactReference.validate_sha256(value)

    @model_validator(mode="after")
    def validate_publication_hash(self) -> LifecycleHoldoutTargetCommitment:
        expected = _canonical_sha256(self.model_dump(mode="json", exclude={"publication_sha256"}))
        if self.publication_sha256 != expected:
            raise ValueError("target commitment publication hash does not bind its payload")
        return self


class LifecycleHoldoutAuditClaim(StrictModel):
    """Privately and exclusively consume one preregistered holdout execution slot."""

    schema_version: Literal["1"] = "1"
    claim_sha256: NonEmptyStr
    calibration_freeze_sha256: NonEmptyStr
    target_freeze_sha256: NonEmptyStr
    holdout_repetition: Literal[1]
    status: Literal["claimed"] = "claimed"

    @field_validator("claim_sha256", "calibration_freeze_sha256", "target_freeze_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return ArtifactReference.validate_sha256(value)

    @model_validator(mode="after")
    def validate_claim_hash(self) -> LifecycleHoldoutAuditClaim:
        expected = _canonical_sha256(self.model_dump(mode="json", exclude={"claim_sha256"}))
        if self.claim_sha256 != expected:
            raise ValueError("audit claim hash does not bind its payload")
        return self


class LifecycleHoldoutAuditOutcomeCounts(StrictModel):
    """Expose only closed aggregate outcome categories."""

    evaluated_pass: NonNegativeInt
    evaluated_fail: NonNegativeInt
    not_evaluable: NonNegativeInt


class LifecycleHoldoutAuditReceipt(StrictModel):
    """Publish a strict aggregate without copying any private record fields."""

    schema_version: Literal["1"] = "1"
    publication_sha256: NonEmptyStr
    calibration_freeze_sha256: NonEmptyStr
    target_commitment_sha256: NonEmptyStr
    interpretation: Literal["descriptive_holdout_generalization"]
    causal_effects_supported: Literal[False] = False
    cross_run_learning_supported: Literal[False] = False
    target_record_count: NonNegativeInt
    eligible_target_count: NonNegativeInt
    mean_target_reward: _BoundedReward | None
    outcome_counts: LifecycleHoldoutAuditOutcomeCounts

    @field_validator("publication_sha256", "calibration_freeze_sha256", "target_commitment_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return ArtifactReference.validate_sha256(value)

    @model_validator(mode="after")
    def validate_aggregate(self) -> LifecycleHoldoutAuditReceipt:
        counts = self.outcome_counts
        total = counts.evaluated_pass + counts.evaluated_fail + counts.not_evaluable
        eligible = counts.evaluated_pass + counts.evaluated_fail
        if total != self.target_record_count or eligible != self.eligible_target_count:
            raise ValueError("holdout outcome counts do not match the published aggregate")
        if self.eligible_target_count == 0 and self.mean_target_reward is not None:
            raise ValueError("holdout mean reward requires an eligible target")
        if self.eligible_target_count > 0 and self.mean_target_reward is None:
            raise ValueError("eligible holdout targets require a mean reward")
        expected = _canonical_sha256(self.model_dump(mode="json", exclude={"publication_sha256"}))
        if self.publication_sha256 != expected:
            raise ValueError("holdout receipt publication hash does not bind its payload")
        return self


def write_lifecycle_holdout_target_freeze(
    *,
    calibration_manifest: LifecycleAblationManifest,
    mount: SealedLifecycleMount,
    commitment_salt: str,
    output_path: Path,
) -> Path:
    """Write one private target freeze against the preregistered public plan."""
    destination = Path(output_path)
    private_audit_root = _private_audit_root_for_target_path(destination)
    target = _build_target_freeze(
        calibration_manifest=calibration_manifest,
        mount=mount,
        commitment_salt=commitment_salt,
        private_audit_root=private_audit_root,
    )
    return _write_private_idempotent_model(destination, target)


def lifecycle_holdout_private_layout(
    target: LifecycleHoldoutTargetFreeze,
) -> LifecycleHoldoutPrivateLayout:
    """Return the only local private layout authorized by one target freeze."""
    root = Path(target.private_audit_root)
    authority = root / "authority"
    execution = root / "execution"
    return LifecycleHoldoutPrivateLayout(
        root=root,
        calibration_freeze_path=authority / "calibration-freeze.json",
        target_freeze_path=authority / "target-freeze.json",
        claim_path=authority / "claim.json",
        execution_root=execution,
        run_start_path=execution / "run-start.json",
        run_dir=execution / "run",
        ledger_root=root / "ledger",
    )


def validate_lifecycle_holdout_target_freeze(
    *,
    calibration_manifest: LifecycleAblationManifest,
    target_freeze_path: Path,
    mount: SealedLifecycleMount,
) -> LifecycleHoldoutTargetFreeze:
    """Rebuild the target commitment and reject package, plan, or provider drift."""
    target_path = Path(target_freeze_path)
    target = _read_model_once(target_path, LifecycleHoldoutTargetFreeze)
    _validate_target_freeze_location(target_path, target)
    expected = _build_target_freeze(
        calibration_manifest=calibration_manifest,
        mount=mount,
        commitment_salt=target.commitment_salt,
        private_audit_root=Path(target.private_audit_root),
    )
    if target != expected:
        raise ValueError("sealed target freeze does not match the active provider")
    return target


def validate_lifecycle_holdout_target_mount(
    *,
    target_freeze_path: Path,
    mount: SealedLifecycleMount,
    require_authority_location: bool = True,
) -> LifecycleHoldoutTargetFreeze:
    """Validate one private target freeze against an explicitly supplied mount."""
    target_path = Path(target_freeze_path)
    target = _read_model_once(target_path, LifecycleHoldoutTargetFreeze)
    if require_authority_location:
        _validate_target_freeze_location(target_path, target)
    _validate_target_against_mount(target, mount)
    return target


def write_lifecycle_holdout_target_commitment(
    *,
    target_freeze_path: Path,
    output_path: Path,
) -> Path:
    """Publish only the opaque commitment and public campaign identities."""
    target = _read_model_once(Path(target_freeze_path), LifecycleHoldoutTargetFreeze)
    payload = {
        "schema_version": "1",
        "target_commitment_sha256": target.public_target_commitment_sha256,
        "public_experiment_id": target.public_experiment_id,
        "public_manifest_sha256": target.public_manifest_sha256,
        "public_plan_sha256": target.public_plan_sha256,
        "target_selected_before_public_results": True,
    }
    commitment = LifecycleHoldoutTargetCommitment.model_validate(
        {**payload, "publication_sha256": _canonical_sha256(payload)}
    )
    return _write_idempotent_model(Path(output_path), commitment)


def claim_lifecycle_holdout_audit(
    *,
    calibration_freeze_path: Path,
    target_freeze_path: Path,
    mount: SealedLifecycleMount,
    output_path: Path,
) -> LifecycleHoldoutAuditClaim:
    """Validate both freezes and exclusively publish the pre-execution claim."""
    target_path = Path(target_freeze_path)
    target = _read_model_once(target_path, LifecycleHoldoutTargetFreeze)
    _validate_target_freeze_location(target_path, target)
    layout = lifecycle_holdout_private_layout(target)
    if Path(calibration_freeze_path) != layout.calibration_freeze_path or Path(output_path) != layout.claim_path:
        raise ValueError("sealed holdout paths do not match the target-bound private audit layout")
    calibration = _read_model_once(layout.calibration_freeze_path, LifecycleCalibrationFreeze)
    _validate_target_against_mount(target, mount)
    if (
        calibration.experiment_id != target.public_experiment_id
        or calibration.manifest_sha256 != target.public_manifest_sha256
        or calibration.plan_sha256 != target.public_plan_sha256
        or calibration.selection_policy.holdout_repetitions != target.holdout_repetitions
    ):
        raise ValueError("calibration freeze does not match the precommitted target campaign")
    payload = {
        "schema_version": "1",
        "calibration_freeze_sha256": calibration.freeze_sha256,
        "target_freeze_sha256": target.target_freeze_sha256,
        "holdout_repetition": 1,
        "status": "claimed",
    }
    claim = LifecycleHoldoutAuditClaim.model_validate({**payload, "claim_sha256": _canonical_sha256(payload)})
    _write_private_exclusive_model(Path(output_path), claim)
    return claim


def build_lifecycle_holdout_audit_receipt(
    *,
    calibration_freeze: LifecycleCalibrationFreeze,
    target_freeze_path: Path,
    evaluation_spec: LifecycleTransferEvaluationSpec,
    target_mount: SealedLifecycleMount,
) -> LifecycleHoldoutAuditReceipt:
    """Run the sealed evaluator and derive its exact public aggregate."""
    calibration = LifecycleCalibrationFreeze.model_validate(calibration_freeze.model_dump(mode="json"))
    target = _read_model_once(Path(target_freeze_path), LifecycleHoldoutTargetFreeze)
    if (
        calibration.experiment_id != target.public_experiment_id
        or calibration.manifest_sha256 != target.public_manifest_sha256
        or calibration.plan_sha256 != target.public_plan_sha256
    ):
        raise ValueError("private holdout summary target does not match the calibration campaign")
    private_summary = build_sealed_lifecycle_transfer_evaluation(
        evaluation_spec,
        target_mount=target_mount,
    )
    evaluated_reference = evaluation_spec.holdout_target_records[0]
    evaluated_record = TrialRecord.model_validate_json(Path(evaluated_reference.ledger_path).read_bytes())
    provenance = evaluated_record.lifecycle_provenance
    target_reference = provenance.sealed_target_freeze if provenance is not None else None
    target_freeze_sha256 = hashlib.sha256(Path(target_freeze_path).read_bytes()).hexdigest()
    if target_reference is None or target_reference.sha256 != target_freeze_sha256:
        raise ValueError("receipt target freeze does not match the evaluated private record")
    expected_condition = calibration.selected_condition
    selected = private_summary.selected_condition
    if (
        selected.model != expected_condition.resolved_model
        or selected.adapter != expected_condition.resolved_adapter
        or selected.runtime_dependency_sha256 != expected_condition.runtime_dependency_sha256
        or selected.execution_mode != expected_condition.execution_mode
        or selected.memory_visibility_policy != expected_condition.memory_visibility_policy
        or selected.max_turns_per_session != expected_condition.max_turns_per_session
    ):
        raise ValueError("private holdout summary does not use the frozen public condition")
    if private_summary.target_record_count != target.holdout_repetitions:
        raise ValueError("private holdout summary does not contain the preregistered target count")

    evaluated_pass = 0
    evaluated_fail = 0
    not_evaluable = 0
    for result in private_summary.target_results:
        if result.status == "not_evaluable":
            not_evaluable += 1
        elif result.verifier_reward == 1.0:
            evaluated_pass += 1
        elif result.verifier_reward is not None:
            evaluated_fail += 1
        else:
            raise ValueError("eligible private holdout result is missing verifier reward")
    payload = {
        "schema_version": "1",
        "calibration_freeze_sha256": calibration.freeze_sha256,
        "target_commitment_sha256": target.public_target_commitment_sha256,
        "interpretation": "descriptive_holdout_generalization",
        "causal_effects_supported": False,
        "cross_run_learning_supported": False,
        "target_record_count": private_summary.target_record_count,
        "eligible_target_count": private_summary.eligible_target_count,
        "mean_target_reward": private_summary.mean_target_reward,
        "outcome_counts": {
            "evaluated_pass": evaluated_pass,
            "evaluated_fail": evaluated_fail,
            "not_evaluable": not_evaluable,
        },
    }
    return LifecycleHoldoutAuditReceipt.model_validate({**payload, "publication_sha256": _canonical_sha256(payload)})


def write_lifecycle_holdout_audit_receipt(
    receipt: LifecycleHoldoutAuditReceipt,
    output_path: Path,
) -> Path:
    """Publish one byte-identical aggregate receipt without replacement."""
    validated = LifecycleHoldoutAuditReceipt.model_validate(receipt.model_dump(mode="json"))
    return _write_idempotent_model(Path(output_path), validated)


def _build_target_freeze(
    *,
    calibration_manifest: LifecycleAblationManifest,
    mount: SealedLifecycleMount,
    commitment_salt: str,
    private_audit_root: Path,
) -> LifecycleHoldoutTargetFreeze:
    manifest = LifecycleAblationManifest.model_validate(calibration_manifest.model_dump(mode="json"))
    policy = manifest.selection_policy
    if policy is None:
        raise ValueError("sealed target freeze requires a preregistered public selection policy")
    if policy.holdout_repetitions != 1:
        raise ValueError("sealed target freeze currently requires exactly one holdout repetition")
    ArtifactReference.validate_sha256(commitment_salt)
    plan = build_lifecycle_ablation_plan(manifest)
    provider_identity, package_identity = _mounted_private_identity(mount)
    selection_policy_sha256 = _canonical_sha256(policy.model_dump(mode="json"))
    payload = {
        "schema_version": "1",
        "public_experiment_id": manifest.experiment_id,
        "public_manifest_sha256": plan.manifest_sha256,
        "public_plan_sha256": plan.plan_sha256,
        "public_selection_policy_sha256": selection_policy_sha256,
        "private_audit_root": str(private_audit_root),
        "holdout_repetitions": 1,
        "lifecycle_id": package_identity["lifecycle_id"],
        "world_id": package_identity["world_id"],
        "lifecycle_spec_sha256": package_identity["spec_sha256"],
        "package_sha256": mount.package_sha256,
        "package_tree_sha256": mount.package_tree_sha256,
        "provider_protocol_sha256": sealed_lifecycle_provider_protocol_identity()["sha256"],
        "provider_identity": provider_identity.model_dump(mode="json"),
        "commitment_salt": commitment_salt,
    }
    target_freeze_sha256 = _canonical_sha256(payload)
    public_target_commitment_sha256 = _target_commitment_sha256(
        commitment_salt=commitment_salt,
        target_freeze_sha256=target_freeze_sha256,
    )
    return LifecycleHoldoutTargetFreeze.model_validate(
        {
            **payload,
            "target_freeze_sha256": target_freeze_sha256,
            "public_target_commitment_sha256": public_target_commitment_sha256,
        }
    )


def _validate_target_against_mount(
    target: LifecycleHoldoutTargetFreeze,
    mount: SealedLifecycleMount,
) -> None:
    provider_identity, package_identity = _mounted_private_identity(mount)
    current = {
        "lifecycle_id": package_identity["lifecycle_id"],
        "world_id": package_identity["world_id"],
        "lifecycle_spec_sha256": package_identity["spec_sha256"],
        "package_sha256": mount.package_sha256,
        "package_tree_sha256": mount.package_tree_sha256,
        "provider_protocol_sha256": sealed_lifecycle_provider_protocol_identity()["sha256"],
        "provider_identity": provider_identity,
    }
    expected = {
        "lifecycle_id": target.lifecycle_id,
        "world_id": target.world_id,
        "lifecycle_spec_sha256": target.lifecycle_spec_sha256,
        "package_sha256": target.package_sha256,
        "package_tree_sha256": target.package_tree_sha256,
        "provider_protocol_sha256": target.provider_protocol_sha256,
        "provider_identity": target.provider_identity,
    }
    if current != expected:
        raise ValueError("sealed target freeze does not match the active provider")


def _mounted_private_identity(
    mount: SealedLifecycleMount,
) -> tuple[LifecycleHoldoutProviderIdentity, dict[str, str]]:
    method = getattr(mount.provider, "audit_contract_identity", None)
    if not callable(method):
        raise ValueError("sealed audit provider does not declare opaque contract identities")
    try:
        with mount.activate():
            raw_identity = method(mount.package_dir)
            package_identity = evidence_lifecycle_package_identity(mount.package_dir)
        identity = LifecycleHoldoutProviderIdentity.model_validate(raw_identity)
    except Exception:
        raise ValueError("sealed audit provider contract identity is invalid") from None
    if package_identity["package_sha256"] != mount.package_sha256:
        raise ValueError("sealed target freeze does not match the active provider")
    return identity, package_identity


def _read_model_once(path: Path, model_type: type[_ModelT]) -> _ModelT:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise ValueError("write-once artifact path is not a regular file")
    return model_type.model_validate_json(candidate.read_bytes())


def _private_audit_root_for_target_path(path: Path) -> Path:
    destination = Path(path)
    if (
        not destination.is_absolute()
        or destination.resolve(strict=False) != destination
        or destination.name != "target-freeze.json"
        or destination.parent.name != "authority"
    ):
        raise ValueError("target freeze must use the canonical private audit authority path")
    root = destination.parent.parent
    _prepare_private_parent(root)
    return root


def _validate_target_freeze_location(
    path: Path,
    target: LifecycleHoldoutTargetFreeze,
) -> None:
    layout = lifecycle_holdout_private_layout(target)
    if Path(path) != layout.target_freeze_path:
        raise ValueError("target freeze does not match the target-bound private audit layout")
    _prepare_private_parent(layout.root)


def _write_idempotent_model(path: Path, value: StrictModel) -> Path:
    content = _model_bytes(value)
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file() or path.read_bytes() != content:
            raise ValueError("write-once artifact already exists with different content")
        return path
    _publish_exclusive(path, content)
    return path


def _write_private_idempotent_model(path: Path, value: StrictModel) -> Path:
    _prepare_private_parent(path.parent)
    return _write_idempotent_model(path, value)


def _write_private_exclusive_model(path: Path, value: StrictModel) -> Path:
    _prepare_private_parent(path.parent)
    if path.exists() or path.is_symlink():
        raise LifecycleHoldoutAuditAlreadyClaimedError("sealed holdout audit already claimed")
    try:
        _publish_exclusive(path, _model_bytes(value))
    except FileExistsError as exc:
        raise LifecycleHoldoutAuditAlreadyClaimedError("sealed holdout audit already claimed") from exc
    return path


def _prepare_private_parent(parent: Path) -> None:
    candidate = Path(parent)
    if not candidate.is_absolute():
        raise ValueError("private holdout root must be absolute")
    missing: list[Path] = []
    current = candidate
    while not current.exists() and not current.is_symlink():
        missing.append(current)
        current = current.parent
    if current.is_symlink() or not current.is_dir():
        raise ValueError("private holdout root must be a canonical directory")
    for directory in reversed(missing):
        try:
            directory.mkdir(mode=0o700)
        except FileExistsError:
            pass
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError("private holdout root must be a canonical directory")
        os.chmod(directory, 0o700)
        fsync_directory(directory.parent)
    if candidate.is_symlink() or not candidate.is_dir() or candidate.resolve() != candidate:
        raise ValueError("private holdout root must be a canonical directory")
    if stat.S_IMODE(candidate.stat().st_mode) & 0o077:
        raise ValueError("private holdout root must be owner-only")


def _publish_exclusive(path: Path, content: bytes) -> None:
    destination = Path(path)
    if destination.is_symlink():
        raise ValueError("write-once artifact destination must not be a symlink")
    mkdir_durable(destination.parent)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, destination)
        fsync_directory(destination.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _model_bytes(value: StrictModel) -> bytes:
    return (json.dumps(value.model_dump(mode="json"), indent=2, sort_keys=True) + "\n").encode("utf-8")


def _target_commitment_sha256(*, commitment_salt: str, target_freeze_sha256: str) -> str:
    return hashlib.sha256(
        _TARGET_COMMITMENT_DOMAIN + bytes.fromhex(commitment_salt) + bytes.fromhex(target_freeze_sha256)
    ).hexdigest()


def _canonical_sha256(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
