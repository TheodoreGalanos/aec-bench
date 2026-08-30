# ABOUTME: Defines current run manifests and trial records with separate execution, evaluation, and evidence status.
# ABOUTME: Keeps shared run identity and optional forensic artifacts outside each persisted trial record.

from __future__ import annotations

import hashlib
from datetime import datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Annotated, Any, Literal, Self

from pydantic import Field, NonNegativeFloat, NonNegativeInt, PositiveInt, PrivateAttr, field_validator, model_validator

from aec_bench.contracts.agent_output import AgentOutput
from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.authority_evidence import AuthorityEvidenceKind, AuthorityEvidenceRef
from aec_bench.contracts.dataset import DatasetRef, dataset_reference_key
from aec_bench.contracts.evaluation_refs import EvaluationRegimeRef
from aec_bench.contracts.evaluation_result import EvaluationResult
from aec_bench.contracts.identity import EntityIdentity
from aec_bench.contracts.task_definition import Visibility
from aec_bench.contracts.task_snapshot import TaskSnapshotRef
from aec_bench.contracts.trial_extensions import (
    AdaptationProvenance,
    ArtifactReference,
    DerivationStepRecord,
    LifecycleExecutionRecord,
    LifecycleSessionRecord,
    LifecycleTrialProvenance,
    MetaHarnessTrialProvenance,
    ProposalSessionTrialProvenance,
    VerifierExecutionReceipt,
)
from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr, StrictModel

type TrialTaskKind = Literal["artifact", "lifecycle", "world"]


class ExecutionStatus(StrEnum):
    PLANNED = "planned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INVALID = "invalid"


class EvaluationStatus(StrEnum):
    NOT_REQUESTED = "not_requested"
    PENDING = "pending"
    COMPLETED = "completed"
    INVALID = "invalid"
    FAILED = "failed"


class EvidenceStatus(StrEnum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    VERIFIED = "verified"
    INCOMPLETE = "incomplete"
    INVALID = "invalid"


class GitSourceRef(FrozenStrictModel):
    kind: Literal["git"] = "git"
    revision: NonEmptyStr

    @field_validator("revision")
    @classmethod
    def validate_revision(cls, value: str) -> str:
        if len(value) != 40 or any(character not in "0123456789abcdef" for character in value):
            raise ValueError("Git source revision must be a full lowercase 40-character commit")
        return value


class SnapshotSourceRef(FrozenStrictModel):
    kind: Literal["snapshot"] = "snapshot"
    artifact: ArtifactRef
    base_revision: NonEmptyStr | None = None

    @field_validator("base_revision")
    @classmethod
    def validate_base_revision(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return GitSourceRef.validate_revision(value)


class UnresolvedSourceRef(FrozenStrictModel):
    kind: Literal["unresolved"] = "unresolved"
    reason: NonEmptyStr


type SourceRef = Annotated[GitSourceRef | SnapshotSourceRef | UnresolvedSourceRef, Field(discriminator="kind")]


class AgentConfiguration(FrozenStrictModel):
    adapter: NonEmptyStr
    model: NonEmptyStr
    adapter_revision: NonEmptyStr | None = None
    configuration: dict[str, Any] = Field(default_factory=dict)


AgentReference = AgentConfiguration


class ExecutionEnvironmentRef(FrozenStrictModel):
    runtime_image: NonEmptyStr
    compute_backend: NonEmptyStr
    tool_versions: dict[str, str] | None = None


EnvironmentSnapshot = ExecutionEnvironmentRef


class ProviderRoute(FrozenStrictModel):
    provider: NonEmptyStr
    route: NonEmptyStr


class AuthorityExpectation(FrozenStrictModel):
    authority_kind: AuthorityEvidenceKind
    protocol: NonEmptyStr
    required: bool = True


class QualificationRequirement(FrozenStrictModel):
    matrix_id: NonEmptyStr
    provider_route: NonEmptyStr
    feature: NonEmptyStr
    evidence_level: Literal["keyless", "live"]


class RunManifest(FrozenStrictModel):
    schema_version: Literal[2] = 2
    run_id: NonEmptyStr
    experiment_id: NonEmptyStr
    dataset: DatasetRef | None = None
    source: SourceRef
    agent: AgentConfiguration
    execution_environment: ExecutionEnvironmentRef
    provider_route: ProviderRoute
    expected_authorities: tuple[AuthorityExpectation, ...] = ()
    evaluation_regime: EvaluationRegimeRef | None = None
    qualification: QualificationRequirement | None = None

    @field_validator("expected_authorities")
    @classmethod
    def validate_expected_authorities(
        cls,
        value: tuple[AuthorityExpectation, ...],
    ) -> tuple[AuthorityExpectation, ...]:
        keys = [(item.authority_kind, item.protocol) for item in value]
        if len(keys) != len(set(keys)):
            raise ValueError("expected authority identities must be unique")
        return value

    @model_validator(mode="after")
    def validate_qualification(self) -> Self:
        if self.qualification is None:
            return self
        if self.qualification.provider_route != self.provider_route.route:
            raise ValueError("qualification provider route must match the run provider route")
        if not any(
            item.required and item.authority_kind is AuthorityEvidenceKind.PROVIDER
            for item in self.expected_authorities
        ):
            raise ValueError("qualification runs require provider evidence")
        return self


class TaskReference(FrozenStrictModel):
    task_id: NonEmptyStr
    task_revision: NonEmptyStr
    visibility: Visibility | None = None


class FileReference(FrozenStrictModel):
    artifact: ArtifactRef
    source: NonEmptyStr | None = None

    @property
    def path(self) -> str:
        return self.artifact.artifact_id

    @property
    def hash(self) -> str:
        return self.artifact.sha256


class TrialInput(FrozenStrictModel):
    instruction: NonEmptyStr
    task_revision: NonEmptyStr
    task_kind: TrialTaskKind = "artifact"
    visibility: Visibility | None = None
    system_prompt: str | None = None
    input_files: tuple[FileReference, ...] | None = None


InputRecord = TrialInput


class PlannedTrialBinding(FrozenStrictModel):
    """Optional exact binding from one result to its canonical planned trial."""

    schema_version: Literal[1] = 1
    run_identity: EntityIdentity
    trial_identity: EntityIdentity
    task_release: TaskSnapshotRef
    agent_condition_identity: EntityIdentity
    ordinal: PositiveInt
    repetition: PositiveInt
    execution_family: TrialTaskKind
    evaluation_profile: EvaluationRegimeRef | None = None
    expected_authorities: tuple[AuthorityExpectation, ...] = ()

    @field_validator("expected_authorities")
    @classmethod
    def validate_expected_authorities(
        cls,
        value: tuple[AuthorityExpectation, ...],
    ) -> tuple[AuthorityExpectation, ...]:
        keys = [(item.authority_kind, item.protocol) for item in value]
        if len(keys) != len(set(keys)):
            raise ValueError("planned trial authority identities must be unique")
        return value


class TrialArtifactRef(FrozenStrictModel):
    role: NonEmptyStr
    artifact: ArtifactRef
    logical_path: NonEmptyStr | None = None

    @field_validator("logical_path")
    @classmethod
    def validate_logical_path(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if "\\" in value:
            raise ValueError("artifact logical_path must use forward slashes")
        if "\0" in value:
            raise ValueError("artifact logical_path must not contain a null byte")
        path = PurePosixPath(value)
        if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
            raise ValueError("artifact logical_path must be a portable relative path")
        return value

    @property
    def kind(self) -> str:
        return self.role

    @property
    def path(self) -> str:
        return self.logical_path or self.artifact.artifact_id

    @property
    def sha256(self) -> str:
        return self.artifact.sha256

    @property
    def media_type(self) -> str:
        return self.artifact.media_type


class TrialOutput(StrictModel):
    agent_output: AgentOutput | None = None
    raw_output: ArtifactRef | None = None
    conversation: ArtifactRef | None = None
    trajectory: ArtifactRef | None = None
    agent_result: dict[str, Any] | None = None
    artifacts: tuple[TrialArtifactRef, ...] = ()
    terminated: bool = False
    truncated: bool = False
    final_reason: NonEmptyStr | None = None
    raw_output_path: str | None = Field(default=None, exclude=True)
    conversation_path: str | None = Field(default=None, exclude=True)
    trajectory_path: str | None = Field(default=None, exclude=True)

    _artifact_root: Path | None = PrivateAttr(default=None)

    @model_validator(mode="after")
    def validate_terminal_state(self) -> Self:
        if self.terminated and self.truncated:
            raise ValueError("output cannot be both terminated and truncated")
        declared = tuple(item for item in (self.raw_output, self.conversation, self.trajectory) if item is not None)
        retained = {item.artifact for item in self.artifacts}
        if any(item not in retained for item in declared):
            raise ValueError("named output artifacts must be included in artifacts")
        return self

    def bind_artifact_root(self, root: Path) -> Self:
        self._artifact_root = root
        self.raw_output_path = self._path(self.raw_output) or self.raw_output_path
        self.conversation_path = self._path(self.conversation) or self.conversation_path
        self.trajectory_path = self._path(self.trajectory) or self.trajectory_path
        return self

    def bind_runtime_paths(
        self,
        *,
        raw_output_path: str | None,
        conversation_path: str | None,
        trajectory_path: str | None,
    ) -> Self:
        self.raw_output_path = raw_output_path
        self.conversation_path = conversation_path
        self.trajectory_path = trajectory_path
        return self

    def artifact_path(self, role: str) -> str | None:
        """Resolve one retained output artifact by its semantic role."""

        match = next((item for item in self.artifacts if item.role == role), None)
        if match is None:
            return None
        if self._artifact_root is None:
            return match.artifact.artifact_id
        return str(self._artifact_root / match.artifact.artifact_id)

    def _path(self, artifact: ArtifactRef | None) -> str | None:
        if artifact is None:
            return None
        if self._artifact_root is None:
            return artifact.artifact_id
        return str(self._artifact_root / artifact.artifact_id)


OutputRecord = TrialOutput


class TimingRecord(FrozenStrictModel):
    total_seconds: NonNegativeFloat
    agent_seconds: NonNegativeFloat | None = None
    setup_seconds: NonNegativeFloat | None = None
    verification_seconds: NonNegativeFloat | None = None


class CostRecord(FrozenStrictModel):
    model_calls: NonNegativeInt | None = None
    tokens_in: NonNegativeInt | None = None
    tokens_out: NonNegativeInt | None = None
    cache_read_tokens: NonNegativeInt | None = None
    cache_write_tokens: NonNegativeInt | None = None
    estimated_cost_usd: NonNegativeFloat | None = None
    advisor_calls: NonNegativeInt | None = None
    advisor_input_tokens: NonNegativeInt | None = None
    advisor_output_tokens: NonNegativeInt | None = None


class TrialExtensionRef(FrozenStrictModel):
    extension_kind: NonEmptyStr
    artifact: ArtifactRef


class TrialRecord(StrictModel):
    schema_version: Literal[2] = 2
    trial_id: NonEmptyStr
    run_id: NonEmptyStr
    task_id: NonEmptyStr
    planned_trial_binding: PlannedTrialBinding | None = None
    attempt: PositiveInt = 1
    execution_status: ExecutionStatus
    evaluation_status: EvaluationStatus
    evidence_status: EvidenceStatus
    started_at: datetime
    completed_at: datetime | None = None
    input: TrialInput
    output: TrialOutput | None = None
    evaluation: EvaluationResult | None = None
    timing: TimingRecord
    cost: CostRecord | None = None
    authority_evidence: tuple[AuthorityEvidenceRef, ...] = ()
    provider_evidence: ArtifactRef | None = None
    extension_refs: tuple[TrialExtensionRef, ...] = ()

    _run_manifest: RunManifest | None = PrivateAttr(default=None)
    _extension_values: dict[str, Any] = PrivateAttr(default_factory=dict)
    _pending_artifacts: dict[str, tuple[Path, str, str | None]] = PrivateAttr(default_factory=dict)
    _pending_artifact_hashes: dict[str, str] = PrivateAttr(default_factory=dict)

    @field_validator("started_at", "completed_at")
    @classmethod
    def validate_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("trial timestamps must include a timezone")
        return value

    @field_validator("authority_evidence")
    @classmethod
    def validate_authority_evidence(
        cls,
        value: tuple[AuthorityEvidenceRef, ...],
    ) -> tuple[AuthorityEvidenceRef, ...]:
        if any(item.authority_kind is AuthorityEvidenceKind.PROVIDER for item in value):
            raise ValueError("provider evidence must use provider_evidence")
        keys = [(item.authority_kind, item.protocol) for item in value]
        if len(keys) != len(set(keys)):
            raise ValueError("authority evidence identities must be unique")
        return value

    @field_validator("extension_refs")
    @classmethod
    def validate_extension_refs(cls, value: tuple[TrialExtensionRef, ...]) -> tuple[TrialExtensionRef, ...]:
        kinds = [item.extension_kind for item in value]
        if len(kinds) != len(set(kinds)):
            raise ValueError("trial extension kinds must be unique")
        return value

    @model_validator(mode="after")
    def validate_statuses(self) -> Self:
        binding = self.planned_trial_binding
        if binding is not None:
            if str(binding.trial_identity.id) != self.trial_id:
                raise ValueError("planned trial binding trial identity does not match trial_id")
            if str(binding.run_identity.id) != self.run_id:
                raise ValueError("planned trial binding run identity does not match run_id")
            if binding.task_release.task_id != self.task_id:
                raise ValueError("planned trial binding task release does not match task_id")
            if binding.execution_family != self.input.task_kind:
                raise ValueError("planned trial binding execution family does not match task kind")
        terminal = self.execution_status in {
            ExecutionStatus.COMPLETED,
            ExecutionStatus.FAILED,
            ExecutionStatus.CANCELLED,
            ExecutionStatus.INVALID,
        }
        if terminal != (self.completed_at is not None):
            raise ValueError("terminal execution status and completed_at must be present together")
        if self.execution_status is ExecutionStatus.COMPLETED and self.output is None:
            raise ValueError("completed execution requires an output")
        if self.evaluation_status is EvaluationStatus.COMPLETED and self.evaluation is None:
            raise ValueError("completed evaluation requires an evaluation result")
        if self.evaluation_status in {EvaluationStatus.NOT_REQUESTED, EvaluationStatus.PENDING} and self.evaluation:
            raise ValueError("not-requested or pending evaluation cannot include a result")
        output_artifacts = set() if self.output is None else {item.artifact for item in self.output.artifacts}
        authority_artifacts = {item.artifact for item in self.authority_evidence}
        if output_artifacts & authority_artifacts:
            raise ValueError("authority evidence must be referenced only through authority_evidence")
        if self.provider_evidence is not None and self.provider_evidence in output_artifacts:
            raise ValueError("provider evidence must be referenced only through provider_evidence")
        elapsed = None if self.completed_at is None else (self.completed_at - self.started_at).total_seconds()
        if elapsed is not None and abs(elapsed - self.timing.total_seconds) > 0.001:
            raise ValueError("timing.total_seconds must match the trial timestamps")
        return self

    def bind_run_manifest(self, manifest: RunManifest) -> Self:
        if manifest.run_id != self.run_id:
            raise ValueError("trial run_id does not match the run manifest")
        self._run_manifest = manifest
        self._validate_evidence_against_manifest()
        binding = self.planned_trial_binding
        if binding is not None:
            if binding.expected_authorities != manifest.expected_authorities:
                raise ValueError("planned trial binding authority policy does not match the run manifest")
            if binding.evaluation_profile != manifest.evaluation_regime:
                raise ValueError("planned trial binding evaluation profile does not match the run manifest")
        return self

    def bind_artifact_root(self, root: Path) -> Self:
        if self.output is not None:
            self.output.bind_artifact_root(root)
        return self

    def attach_extension(self, extension_kind: str, value: Any) -> Self:
        if not extension_kind.strip():
            raise ValueError("extension_kind must not be blank")
        if extension_kind in self._extension_values:
            raise ValueError(f"trial extension already attached: {extension_kind}")
        self._extension_values[extension_kind] = value
        return self

    def attach_artifact(
        self,
        role: str,
        path: Path,
        *,
        media_type: str,
        logical_path: str | None = None,
        expected_sha256: str | None = None,
    ) -> Self:
        if not role.strip():
            raise ValueError("artifact role must not be blank")
        selected_path = Path(path)
        selected_sha256 = hashlib.sha256(selected_path.read_bytes()).hexdigest()
        if expected_sha256 is not None:
            ArtifactReference.validate_sha256(expected_sha256)
            if selected_sha256 != expected_sha256:
                raise ValueError(f"trial artifact does not match its expected SHA-256: {role}")
        selected_expected_sha256 = expected_sha256 or selected_sha256
        if role in self._pending_artifacts:
            existing_path, existing_media_type, existing_logical_path = self._pending_artifacts[role]
            if (
                existing_media_type == media_type
                and existing_logical_path == logical_path
                and existing_path.is_file()
                and selected_path.is_file()
                and existing_path.read_bytes() == selected_path.read_bytes()
                and self._pending_artifact_hashes[role] == selected_expected_sha256
            ):
                return self
            raise ValueError(f"trial artifact role already attached: {role}")
        self._pending_artifacts[role] = (selected_path, media_type, logical_path)
        self._pending_artifact_hashes[role] = selected_expected_sha256
        if self.output is not None:
            if role == "raw_output":
                self.output.raw_output_path = str(selected_path)
            elif role == "conversation":
                self.output.conversation_path = str(selected_path)
            elif role == "trajectory":
                self.output.trajectory_path = str(selected_path)
        return self

    def _validate_evidence_against_manifest(self) -> None:
        actual: set[tuple[AuthorityEvidenceKind, str]] = {
            (item.authority_kind, item.protocol) for item in self.authority_evidence
        }
        required: set[tuple[AuthorityEvidenceKind, str]] = {
            (item.authority_kind, item.protocol)
            for item in self.run_manifest.expected_authorities
            if item.required and item.authority_kind is not AuthorityEvidenceKind.PROVIDER
        }
        provider_required = any(
            item.required and item.authority_kind is AuthorityEvidenceKind.PROVIDER
            for item in self.run_manifest.expected_authorities
        )
        if self.evidence_status is EvidenceStatus.NOT_REQUIRED and (required or provider_required):
            raise ValueError("evidence cannot be not_required when the run manifest requires evidence")
        missing = required - actual
        if self.evidence_status is EvidenceStatus.VERIFIED and missing:
            raise ValueError("verified evidence is missing required authority references")
        if self.evidence_status is EvidenceStatus.VERIFIED and provider_required and self.provider_evidence is None:
            raise ValueError("verified evidence is missing required provider evidence")

    @property
    def run_manifest(self) -> RunManifest:
        if self._run_manifest is None:
            raise RuntimeError("TrialRecord is not bound to its RunManifest")
        return self._run_manifest

    @property
    def experiment_id(self) -> str:
        return self.run_manifest.experiment_id

    @property
    def dataset_id(self) -> str | None:
        dataset = self.run_manifest.dataset
        return None if dataset is None else dataset_reference_key(dataset)

    @property
    def timestamp(self) -> datetime:
        return self.started_at

    @property
    def task(self) -> TaskReference:
        return TaskReference(
            task_id=self.task_id,
            task_revision=self.input.task_revision,
            visibility=self.input.visibility,
        )

    @property
    def agent(self) -> AgentConfiguration:
        return self.run_manifest.agent

    @property
    def environment(self) -> ExecutionEnvironmentRef:
        return self.run_manifest.execution_environment

    @property
    def inputs(self) -> TrialInput:
        return self.input

    @property
    def outputs(self) -> TrialOutput:
        if self.output is None:
            raise RuntimeError("TrialRecord has no execution output")
        return self.output

    @property
    def pending_extensions(self) -> dict[str, Any]:
        return dict(self._extension_values)

    @property
    def pending_artifacts(self) -> dict[str, tuple[Path, str, str | None]]:
        return dict(self._pending_artifacts)

    @property
    def pending_artifact_hashes(self) -> dict[str, str]:
        return dict(self._pending_artifact_hashes)

    @property
    def adaptation(self) -> AdaptationProvenance | None:
        return self._extension_value("adaptation", AdaptationProvenance)

    @property
    def lifecycle_execution(self) -> LifecycleExecutionRecord | None:
        return self._extension_value("lifecycle_execution", LifecycleExecutionRecord)

    @property
    def lifecycle_provenance(self) -> LifecycleTrialProvenance | None:
        return self._extension_value("lifecycle_provenance", LifecycleTrialProvenance)

    @property
    def meta_harness_provenance(self) -> MetaHarnessTrialProvenance | None:
        return self._extension_value("meta_harness_provenance", MetaHarnessTrialProvenance)

    @property
    def verifier_execution(self) -> VerifierExecutionReceipt | None:
        return self._extension_value("verifier_execution", VerifierExecutionReceipt)

    @property
    def episode_artifact(self) -> ArtifactRef | None:
        for item in self.authority_evidence:
            if item.authority_kind is AuthorityEvidenceKind.WORLD:
                return item.artifact
        for extension in self.extension_refs:
            if extension.extension_kind == "world_evidence":
                return extension.artifact
        return None

    def _extension_value(self, kind: str, model_type: type[Any]) -> Any | None:
        value = self._extension_values.get(kind)
        if value is None:
            return None
        if isinstance(value, model_type):
            return value
        return model_type.model_validate(value)


class PublicationPolicy(FrozenStrictModel):
    policy_id: NonEmptyStr
    require_evaluation: bool = True
    require_evidence: bool = True
    require_provider_evidence: bool = False
    require_reconstructive_source: bool = True
    require_dataset: bool = True


class PublicationEligibility(FrozenStrictModel):
    eligible: bool
    reasons: tuple[NonEmptyStr, ...] = ()


def derive_publication_eligibility(
    record: TrialRecord,
    manifest: RunManifest,
    policy: PublicationPolicy,
) -> PublicationEligibility:
    reasons: list[str] = []
    if record.execution_status is not ExecutionStatus.COMPLETED:
        reasons.append("execution_not_completed")
    if policy.require_evaluation and record.evaluation_status is not EvaluationStatus.COMPLETED:
        reasons.append("evaluation_not_completed")
    required_evidence = any(item.required for item in manifest.expected_authorities)
    if policy.require_evidence:
        accepted_evidence_statuses = (
            {EvidenceStatus.VERIFIED} if required_evidence else {EvidenceStatus.VERIFIED, EvidenceStatus.NOT_REQUIRED}
        )
        if record.evidence_status not in accepted_evidence_statuses:
            reasons.append("evidence_not_verified")
    if policy.require_provider_evidence and record.provider_evidence is None:
        reasons.append("provider_evidence_missing")
    if manifest.qualification is not None and record.evidence_status is not EvidenceStatus.VERIFIED:
        reasons.append("qualification_evidence_level_not_verified")
    if policy.require_reconstructive_source and isinstance(manifest.source, UnresolvedSourceRef):
        reasons.append("source_not_reconstructive")
    if policy.require_dataset and manifest.dataset is None:
        reasons.append("dataset_missing")
    if record.input.task_kind == "world":
        has_actor_evidence = any(
            item.authority_kind is AuthorityEvidenceKind.ACTOR_INVOCATION for item in record.authority_evidence
        )
        if not has_actor_evidence:
            reasons.append("actor_authority_not_closed")
    return PublicationEligibility(eligible=not reasons, reasons=tuple(reasons))


__all__ = (
    "AdaptationProvenance",
    "AgentConfiguration",
    "AgentReference",
    "ArtifactReference",
    "AuthorityExpectation",
    "CostRecord",
    "DerivationStepRecord",
    "EnvironmentSnapshot",
    "EvaluationRegimeRef",
    "EvaluationStatus",
    "EvidenceStatus",
    "ExecutionEnvironmentRef",
    "ExecutionStatus",
    "FileReference",
    "GitSourceRef",
    "InputRecord",
    "LifecycleExecutionRecord",
    "LifecycleSessionRecord",
    "LifecycleTrialProvenance",
    "MetaHarnessTrialProvenance",
    "OutputRecord",
    "PlannedTrialBinding",
    "ProviderRoute",
    "ProposalSessionTrialProvenance",
    "PublicationEligibility",
    "PublicationPolicy",
    "QualificationRequirement",
    "RunManifest",
    "SnapshotSourceRef",
    "SourceRef",
    "TaskReference",
    "TimingRecord",
    "TrialArtifactRef",
    "TrialExtensionRef",
    "TrialInput",
    "TrialOutput",
    "TrialRecord",
    "TrialTaskKind",
    "UnresolvedSourceRef",
    "derive_publication_eligibility",
)
