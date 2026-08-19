# ABOUTME: Defines and persists RunPlan study, invocation, authority, and execution evidence.
# ABOUTME: Keeps canonical Harbor receipt bytes and replay validation outside runtime orchestration.

from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal, Self

from pydantic import (
    NonNegativeInt,
    PositiveInt,
    field_validator,
    model_validator,
)

from aec_bench.contracts.authority import (
    AuthorityAction,
    AuthorityDecision,
    AuthorityEvent,
    AuthorityPrincipal,
    AuthorityPrincipalKind,
    BasisKind,
    TaintLabel,
)
from aec_bench.contracts.evaluation_refs import EvaluationRegimeRef
from aec_bench.contracts.harness_kernel import (
    FrozenStrictModel,
    validate_sha256,
)
from aec_bench.contracts.legacy_content_address import LegacyContentAddressedModel
from aec_bench.contracts.run_bundle import RunPlan
from aec_bench.contracts.trial_record import ArtifactReference
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.experimentation.governance.authority_ledger import (
    AuthorityLedger,
    StoredAuthorityEvent,
    StoredBasis,
)
from aec_bench.harness.budget import HarnessBudgetObservation
from aec_bench.harness.declared_stage import (
    StoredStageExecutionReceipt,
)
from aec_bench.harness.program_execution import (
    OperationExecutionContext,
    ProgramExecutionResult,
)
from aec_bench.ledger.durability import fsync_directory, mkdir_durable
from aec_bench.ledger.reader import read_trial_record


class MetaHarnessStudyContext(FrozenStrictModel):
    """Invocation-specific study lineage kept separate from candidate RunPlan identity."""

    run_id: NonEmptyStr
    policy_id: NonEmptyStr
    harness_generator_sha256: str
    program_generator_sha256: str
    split: Literal["discovery", "repair_gate", "calibration", "holdout"]
    parent_bundle_id: NonEmptyStr | None = None
    harness_program_cell: Literal["h0_p0", "hx_p0", "h0_px", "hx_px"] | None = None
    paired_block_id: NonEmptyStr | None = None
    harness_program_plan: ArtifactReference | None = None
    execution_seed: int | None = None
    repair_attempt_id: NonEmptyStr | None = None
    repair_iteration: NonNegativeInt | None = None
    repair_decision: ArtifactReference | None = None
    motif_ids: tuple[NonEmptyStr, ...] = ()
    evaluation_regime_ref: EvaluationRegimeRef | None = None

    @field_validator("harness_generator_sha256", "program_generator_sha256")
    @classmethod
    def validate_generator_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("motif_ids")
    @classmethod
    def validate_motif_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if tuple(sorted(set(value))) != value:
            raise ValueError("motif ids must be sorted and unique")
        return value

    @model_validator(mode="after")
    def validate_study_fields(self) -> Self:
        harness_program_fields = (
            self.harness_program_cell,
            self.paired_block_id,
            self.harness_program_plan,
        )
        if any(value is not None for value in harness_program_fields) and not all(
            value is not None for value in harness_program_fields
        ):
            raise ValueError("harness-program cell, paired block, and plan must be provided together")
        repair = (
            self.repair_attempt_id,
            self.repair_iteration,
            self.repair_decision,
        )
        if any(value is not None for value in repair) and not all(value is not None for value in repair):
            raise ValueError("repair attempt, iteration, and decision must be provided together")
        if self.split == "holdout" and any(value is not None for value in repair):
            raise ValueError("holdout execution cannot carry repair provenance")
        return self


class HarborJobFileDigest(FrozenStrictModel):
    """Content digest for one regular file beneath a completed Harbor job directory."""

    relative_path: NonEmptyStr
    sha256: str
    size_bytes: NonNegativeInt

    @field_validator("relative_path")
    @classmethod
    def validate_relative_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
            raise ValueError("Harbor job file digest requires a normalized relative path")
        return value

    @field_validator("sha256")
    @classmethod
    def validate_file_sha256(cls, value: str) -> str:
        return validate_sha256(value)


class HarborInvocationReceipt(LegacyContentAddressedModel):
    """Durable byte-level receipt for one completed external Harbor invocation."""

    schema_version: Literal["aecbench.harbor-invocation-receipt.v1"] = "aecbench.harbor-invocation-receipt.v1"
    bundle_id: NonEmptyStr
    run_id: NonEmptyStr
    program_node_id: NonEmptyStr
    attempt: PositiveInt
    fanout_index: NonNegativeInt | None = None
    experiment_id: NonEmptyStr
    harbor_config: ArtifactReference
    job_dir: NonEmptyStr
    job_files: tuple[HarborJobFileDigest, ...]
    imported_trial_records: tuple[ArtifactReference, ...]

    @model_validator(mode="after")
    def validate_file_inventories(self) -> Self:
        job_paths = tuple(item.relative_path for item in self.job_files)
        if job_paths != tuple(sorted(set(job_paths))):
            raise ValueError("Harbor job file digests must be sorted and unique")
        trial_paths = tuple(item.path for item in self.imported_trial_records)
        if len(trial_paths) != len(set(trial_paths)):
            raise ValueError("Harbor invocation TrialRecord references must be unique")
        if self.harbor_config.kind != "harbor-config":
            raise ValueError("Harbor invocation receipt requires a Harbor config artifact")
        if any(item.kind != "trial-record" for item in self.imported_trial_records):
            raise ValueError("Harbor invocation receipt accepts only TrialRecord artifacts")
        return self


@dataclass(frozen=True)
class HarborInvocationReceiptArtifact:
    """Physical content-addressed receipt plus its parsed immutable contract."""

    path: Path
    reference: ArtifactReference
    receipt: HarborInvocationReceipt


@dataclass(frozen=True)
class HarborInvocationGovernance:
    """Host-stored trial and receipt origins plus scoped scored-import authority."""

    trial_bases: tuple[StoredBasis, ...]
    receipt_basis: StoredBasis
    authority_event: StoredAuthorityEvent


@dataclass(frozen=True)
class HarborInvocationEvidence:
    """One completed Harbor operation invocation produced by a px node attempt."""

    program_node_id: str
    attempt: int
    fanout_index: int | None
    experiment_id: str
    job_dir: Path
    imported_trial_paths: tuple[Path, ...]
    receipt: HarborInvocationReceiptArtifact
    governance: HarborInvocationGovernance | None = None


@dataclass(frozen=True)
class StageExecutionEvidence:
    """One isolated unscored stage dispatch and its content-addressed receipt."""

    program_node_id: str
    attempt: int
    task_id: str
    stage_id: str
    job_dir: Path
    receipt: StoredStageExecutionReceipt


@dataclass(frozen=True)
class RunBundleExecution:
    """Terminal px evidence plus every materialized Harbor invocation."""

    program: ProgramExecutionResult
    stage_executions: tuple[StageExecutionEvidence, ...]
    harbor_invocations: tuple[HarborInvocationEvidence, ...]
    budget: HarnessBudgetObservation


def load_harbor_invocation_receipt(path: Path) -> HarborInvocationReceipt:
    """Load one receipt from only its content-addressed path and reverify every bound byte."""

    receipt_path = Path(path).resolve()
    if not receipt_path.is_file():
        raise ValueError("Harbor invocation receipt is missing")
    encoded = receipt_path.read_bytes()
    physical_sha256 = hashlib.sha256(encoded).hexdigest()
    if receipt_path.parent.name != physical_sha256:
        raise ValueError("Harbor invocation receipt path does not match its physical content hash")
    receipt = HarborInvocationReceipt.model_validate_json(encoded)
    _verify_physical_artifact(receipt.harbor_config, label="Harbor config")
    for reference in receipt.imported_trial_records:
        _verify_physical_artifact(reference, label="imported TrialRecord")
    observed_job_files = _job_file_digests(Path(receipt.job_dir))
    if observed_job_files != receipt.job_files:
        raise ValueError("Harbor job file inventory or hashes changed after receipt publication")
    return receipt


def persist_harbor_invocation_receipt(
    *,
    artifacts_root: Path,
    bundle: RunPlan,
    study: MetaHarnessStudyContext,
    context: OperationExecutionContext,
    experiment_id: str,
    harbor_config_path: Path,
    job_dir: Path,
    imported_trial_paths: tuple[Path, ...],
) -> HarborInvocationReceiptArtifact:
    """Persist the current receipt with canonical serialization."""

    receipt = HarborInvocationReceipt(
        bundle_id=bundle.run_manifest.run_id,
        run_id=study.run_id,
        program_node_id=context.node_id,
        attempt=context.attempt_index,
        fanout_index=context.fanout_index,
        experiment_id=experiment_id,
        harbor_config=_physical_artifact_reference(
            harbor_config_path,
            kind="harbor-config",
            media_type="application/yaml",
        ),
        job_dir=str(Path(job_dir).resolve()),
        job_files=_job_file_digests(job_dir),
        imported_trial_records=tuple(
            _physical_artifact_reference(
                path,
                kind="trial-record",
                media_type="application/json",
            )
            for path in imported_trial_paths
        ),
    )
    encoded = (
        json.dumps(
            receipt.model_dump(mode="json"),
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    physical_sha256 = hashlib.sha256(encoded).hexdigest()
    receipt_path = (
        Path(artifacts_root)
        / _safe_segment(bundle.run_manifest.run_id)
        / "runs"
        / _safe_segment(study.run_id)
        / "receipts"
        / physical_sha256
        / "harbor-invocation-receipt.json"
    ).resolve()
    _write_content_addressed_atomic(receipt_path, encoded)
    reference = ArtifactReference(
        kind="harbor-invocation-receipt",
        path=str(receipt_path),
        sha256=physical_sha256,
        media_type="application/json",
    )
    loaded = load_harbor_invocation_receipt(receipt_path)
    if loaded != receipt:
        raise ValueError("persisted Harbor invocation receipt differs from completed invocation")
    return HarborInvocationReceiptArtifact(
        path=receipt_path,
        reference=reference,
        receipt=receipt,
    )


def record_scored_import_authority(
    *,
    ledger: AuthorityLedger,
    bundle: RunPlan,
    study: MetaHarnessStudyContext,
    receipt: HarborInvocationReceiptArtifact,
    imported_trial_paths: tuple[Path, ...],
) -> HarborInvocationGovernance:
    """Copy completed import evidence before granting scoped import authority."""

    host_runtime = AuthorityPrincipal(
        principal_id="host.runtime",
        kind=AuthorityPrincipalKind.HOST_RUNTIME,
    )
    trial_bases: list[StoredBasis] = []
    for index, trial_path in enumerate(imported_trial_paths):
        encoded = Path(trial_path).read_bytes()
        record = read_trial_record(Path(trial_path))
        trial_bases.append(
            ledger.observe_basis(
                kind=BasisKind.EVIDENCE,
                artifact_id=(f"trial-record.{receipt.receipt.content_sha256}.{index}"),
                content=encoded,
                producer=AuthorityPrincipal(
                    principal_id=f"model.{record.agent.model}",
                    kind=AuthorityPrincipalKind.MODEL,
                ),
                producer_process_id=f"harbor.{record.trial_id}",
                observed_by=host_runtime,
                channel="harbor-import",
                operation_id="scored-evidence-import",
                invocation_id=receipt.receipt.content_sha256,
                operation_taint=(
                    TaintLabel.MODEL_REPORTED,
                    TaintLabel.RUNTIME_OBSERVED,
                ),
            )
        )
    receipt_basis = ledger.observe_basis(
        kind=BasisKind.EVIDENCE,
        artifact_id=(f"harbor-invocation-receipt.{receipt.receipt.content_sha256}"),
        content=receipt.path.read_bytes(),
        producer=host_runtime,
        producer_process_id="aecbench.run-bundle-runtime",
        observed_by=host_runtime,
        channel="harbor-import",
        operation_id="scored-import-receipt",
        invocation_id=receipt.receipt.content_sha256,
        parent_origin_sha256s=tuple(item.origin.content_sha256 for item in trial_bases),
        operation_taint=(TaintLabel.RUNTIME_OBSERVED,),
    )
    event = AuthorityEvent(
        event_id=f"authority.scored-import.{receipt.receipt.content_sha256}",
        principal=host_runtime,
        action=AuthorityAction.SCORED_EVIDENCE_IMPORT,
        decision=AuthorityDecision.GRANTED,
        subject_id=f"harbor-invocation.{receipt.receipt.content_sha256}",
        subject_sha256=receipt.reference.sha256,
        basis=(
            *(item.reference for item in trial_bases),
            receipt_basis.reference,
        ),
        kernel_ref=bundle.harness.kernel_ref,
        reasons=("exact imported trials and invocation receipt persisted",),
        revalidation_triggers=(
            "basis_replay_due",
            ("evaluation_regime_change" if study.evaluation_regime_ref is not None else "legacy_evidence_boundary"),
        ),
    )
    authority_event = ledger.issue_authority_event(event)
    return HarborInvocationGovernance(
        trial_bases=tuple(trial_bases),
        receipt_basis=receipt_basis,
        authority_event=authority_event,
    )


def _job_file_digests(
    job_dir: Path,
) -> tuple[HarborJobFileDigest, ...]:
    root = Path(job_dir).resolve()
    if not root.is_dir():
        raise ValueError("completed Harbor invocation job directory is missing")
    return tuple(
        HarborJobFileDigest(
            relative_path=path.relative_to(root).as_posix(),
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            size_bytes=path.stat().st_size,
        )
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    )


def _physical_artifact_reference(
    path: Path,
    *,
    kind: str,
    media_type: str,
) -> ArtifactReference:
    resolved = Path(path).resolve()
    if not resolved.is_file():
        raise ValueError(f"{kind} artifact is missing")
    return ArtifactReference(
        kind=kind,
        path=str(resolved),
        sha256=hashlib.sha256(resolved.read_bytes()).hexdigest(),
        media_type=media_type,
    )


def _verify_physical_artifact(
    reference: ArtifactReference,
    *,
    label: str,
) -> None:
    path = Path(reference.path)
    if not path.is_file():
        raise ValueError(f"{label} artifact is missing")
    if hashlib.sha256(path.read_bytes()).hexdigest() != reference.sha256:
        raise ValueError(f"{label} artifact hash changed after receipt publication")


def _write_content_addressed_atomic(path: Path, encoded: bytes) -> None:
    mkdir_durable(path.parent)
    if path.exists():
        if path.read_bytes() != encoded:
            raise ValueError("content-addressed Harbor invocation receipt contains different bytes")
        return
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.read_bytes() != encoded:
                raise ValueError("content-addressed Harbor invocation receipt contains different bytes") from None
        fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _safe_segment(value: str) -> str:
    safe = "".join(character if character.isalnum() or character in "-." else "-" for character in value)
    if not safe or safe in {".", ".."}:
        raise ValueError("runtime identifier cannot be represented as a safe path segment")
    return safe


__all__ = (
    "HarborInvocationEvidence",
    "HarborInvocationGovernance",
    "HarborInvocationReceipt",
    "HarborInvocationReceiptArtifact",
    "HarborJobFileDigest",
    "MetaHarnessStudyContext",
    "RunBundleExecution",
    "StageExecutionEvidence",
    "load_harbor_invocation_receipt",
    "persist_harbor_invocation_receipt",
    "record_scored_import_authority",
)
