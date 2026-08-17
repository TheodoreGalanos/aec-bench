# ABOUTME: Defines the persisted DeepSeek trial manifest and secret-redaction audit.
# ABOUTME: Keeps the receipt readable while hashing only retained evidence artifacts.

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from aec_bench.contracts.harness_kernel import validate_sha256
from aec_bench.contracts.validators import LenientModel, NonEmptyStr, StrictModel


class DeepSeekEvidenceArtifact(LenientModel):
    role: NonEmptyStr
    path: NonEmptyStr
    sha256: str
    size_bytes: int = Field(ge=0)

    @field_validator("path")
    @classmethod
    def validate_relative_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("evidence artifact path must stay relative to the trial evidence root")
        return value

    @field_validator("sha256")
    @classmethod
    def validate_artifact_sha256(cls, value: str) -> str:
        return validate_sha256(value)


class DeepSeekEvidenceReference(LenientModel):
    path: NonEmptyStr
    sha256: str

    @field_validator("path")
    @classmethod
    def validate_relative_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("evidence reference path must stay relative to the trial evidence root")
        return value

    @field_validator("sha256")
    @classmethod
    def validate_reference_sha256(cls, value: str) -> str:
        return validate_sha256(value)


class DeepSeekPluginIdentity(LenientModel):
    plugin_id: NonEmptyStr
    version: NonEmptyStr
    role: Literal["output_commit", "native_tools"]
    artifact_path: NonEmptyStr
    artifact_sha256: str
    package_lock_path: NonEmptyStr
    package_lock_sha256: str

    @field_validator("artifact_path", "package_lock_path")
    @classmethod
    def validate_artifact_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("plugin artifact path must stay relative to the trial evidence root")
        return value

    @field_validator("artifact_sha256", "package_lock_sha256")
    @classmethod
    def validate_plugin_sha256(cls, value: str) -> str:
        return validate_sha256(value)


class DeepSeekAdapterIdentity(LenientModel):
    kind: Literal["deepseek_harness"] = "deepseek_harness"
    aec_bench_version: NonEmptyStr
    aec_bench_revision: NonEmptyStr | None = None
    aec_bench_revision_reason: NonEmptyStr | None = None
    python_sdk_version: NonEmptyStr
    runtime_distribution_version: NonEmptyStr
    runtime_reported_version: str | None = None

    @model_validator(mode="after")
    def validate_revision(self) -> Self:
        if (self.aec_bench_revision is None) == (self.aec_bench_revision_reason is None):
            raise ValueError("AEC identity requires either a source revision or an unavailable reason")
        return self


class DeepSeekCompositionIdentity(LenientModel):
    sandbox_mode: Literal["workspace-write"] = "workspace-write"
    sandbox_enforcement: Literal["partial"] = "partial"
    subagents_enabled: Literal[False] = False
    workflows_enabled: Literal[False] = False
    code_mode_enabled: Literal[False] = False
    output_commit_mode: Literal["disabled", "required"]
    native_tools: tuple[NonEmptyStr, ...] = ()

    @field_validator("native_tools")
    @classmethod
    def validate_native_tools(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("native tool names must be unique")
        return value


class DeepSeekModelIdentity(LenientModel):
    provider: Literal["azure", "deepseek"]
    harness_route: Literal["azure", "deepseek-official"]
    requested: NonEmptyStr
    resolved: NonEmptyStr


class DeepSeekExecutionIdentity(LenientModel):
    status: Literal["completed", "failed"]
    root_session_id: str | None = None
    child_session_ids: tuple[str, ...] = ()
    workspace: NonEmptyStr
    started_at: datetime
    finished_at: datetime
    finish_reason: str | None = None
    aec_model_turns_used: int = Field(ge=0)
    deepseek_root_turns: int = Field(ge=0)
    tool_calls_started: int = Field(ge=0)
    tool_calls_completed: int = Field(ge=0)
    timeout_sec: int = Field(ge=1)
    max_tokens: int | None = Field(default=None, ge=1)
    process_group_retired: bool

    @model_validator(mode="after")
    def validate_execution(self) -> Self:
        if self.finished_at < self.started_at:
            raise ValueError("finished_at cannot precede started_at")
        if self.status == "completed" and not self.root_session_id:
            raise ValueError("completed DeepSeek evidence requires a root session")
        return self


class DeepSeekAttestationLevel(LenientModel):
    status: Literal["complete", "partial", "unavailable"]
    artifacts: tuple[DeepSeekEvidenceReference, ...] = ()
    reason: NonEmptyStr | None = None

    @model_validator(mode="after")
    def validate_status(self) -> Self:
        if self.status == "complete" and (not self.artifacts or self.reason is not None):
            raise ValueError("complete attestation requires artifacts and cannot have an unavailable reason")
        if self.status == "partial" and not self.artifacts and self.reason is None:
            raise ValueError("partial attestation requires an artifact or a reason")
        if self.status == "unavailable" and (self.artifacts or self.reason is None):
            raise ValueError("unavailable attestation requires a reason and cannot reference artifacts")
        return self


class DeepSeekCompositionAttestation(LenientModel):
    declared: DeepSeekAttestationLevel
    resolved_runtime: DeepSeekAttestationLevel
    model_visible: DeepSeekAttestationLevel


class DeepSeekQualificationIdentity(LenientModel):
    matrix_id: NonEmptyStr
    matrix: DeepSeekEvidenceReference
    provider_route: Literal["azure", "deepseek-official"]
    status: Literal["partial", "qualified", "unqualified"]
    live_qualified: bool
    qualified_features: tuple[NonEmptyStr, ...] = ()

    @model_validator(mode="after")
    def validate_qualification(self) -> Self:
        if self.live_qualified != (self.status == "qualified"):
            raise ValueError("live_qualified must agree with qualified status")
        return self


class DeepSeekActorToolEvidence(LenientModel):
    task_world_id: NonEmptyStr
    actor_catalogue_sha256: str
    public_native_tool_surface_sha256: str
    presentation_mode: Literal["deepseek-native"]
    actor_authority_scope: Literal["segment-snapshot"]
    mapping: DeepSeekEvidenceReference
    actor_authority: DeepSeekEvidenceReference
    correlation: DeepSeekEvidenceReference

    @field_validator("actor_catalogue_sha256", "public_native_tool_surface_sha256")
    @classmethod
    def validate_identity_sha256(cls, value: str) -> str:
        return validate_sha256(value)


class DeepSeekEvidenceManifest(LenientModel):
    schema_id: Literal["aec-bench/deepseek-evidence/2"] = Field(
        alias="schema",
        serialization_alias="schema",
    )
    trial_id: NonEmptyStr
    generated_at: datetime
    adapter: DeepSeekAdapterIdentity
    composition: DeepSeekCompositionIdentity
    attestation: DeepSeekCompositionAttestation
    qualification: DeepSeekQualificationIdentity
    model: DeepSeekModelIdentity
    execution: DeepSeekExecutionIdentity
    plugins: tuple[DeepSeekPluginIdentity, ...] = ()
    actor_native_tools: DeepSeekActorToolEvidence | None = None
    redaction_audit_path: NonEmptyStr
    artifacts: tuple[DeepSeekEvidenceArtifact, ...]

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        artifact_paths = [artifact.path for artifact in self.artifacts]
        if len(set(artifact_paths)) != len(artifact_paths):
            raise ValueError("evidence manifest artifact paths must be unique")
        artifact_roles_by_path = {artifact.path: artifact.role for artifact in self.artifacts}
        if artifact_roles_by_path.get(self.redaction_audit_path) != "redaction_audit":
            raise ValueError("redaction audit path must reference the redaction_audit artifact")
        for plugin in self.plugins:
            if artifact_roles_by_path.get(plugin.artifact_path) != "optional_plugin":
                raise ValueError("plugin artifact path must reference an optional_plugin artifact")
            if artifact_roles_by_path.get(plugin.package_lock_path) != "plugin_package_lock":
                raise ValueError("plugin package lock must reference the plugin_package_lock artifact")
            artifact_by_path = {artifact.path: artifact for artifact in self.artifacts}
            if artifact_by_path[plugin.artifact_path].sha256 != plugin.artifact_sha256:
                raise ValueError("plugin build hash must match its evidence artifact")
            if artifact_by_path[plugin.package_lock_path].sha256 != plugin.package_lock_sha256:
                raise ValueError("plugin package lock hash must match its evidence artifact")
        output_commit_plugins = [plugin for plugin in self.plugins if plugin.role == "output_commit"]
        tool_plugins = [plugin for plugin in self.plugins if plugin.role == "native_tools"]
        if self.composition.output_commit_mode == "required" and len(output_commit_plugins) != 1:
            raise ValueError("required output commitment must retain one plugin artifact")
        if self.composition.output_commit_mode == "disabled" and output_commit_plugins:
            raise ValueError("commit-disabled evidence cannot list an output commit plugin")
        expected_tool_plugins = 1 if self.composition.native_tools else 0
        if len(tool_plugins) != expected_tool_plugins:
            raise ValueError("native tool evidence must match its plugin artifact")
        references = [
            *self.attestation.declared.artifacts,
            *self.attestation.resolved_runtime.artifacts,
            *self.attestation.model_visible.artifacts,
            self.qualification.matrix,
        ]
        if self.actor_native_tools is not None:
            references.extend(
                (
                    self.actor_native_tools.mapping,
                    self.actor_native_tools.actor_authority,
                    self.actor_native_tools.correlation,
                )
            )
        artifact_by_path = {artifact.path: artifact for artifact in self.artifacts}
        for reference in references:
            artifact = artifact_by_path.get(reference.path)
            if artifact is None or artifact.sha256 != reference.sha256:
                raise ValueError(f"evidence reference does not match a retained artifact: {reference.path}")
        declared_roles = {artifact_roles_by_path[reference.path] for reference in self.attestation.declared.artifacts}
        if not {"composition_identity", "cordis_input", "system_prompt"}.issubset(declared_roles):
            raise ValueError("declared attestation must reference composition, Cordis, and system prompt evidence")
        if self.actor_native_tools is not None and not self.composition.native_tools:
            raise ValueError("actor native evidence requires a native tool composition")
        return self


class DeepSeekRedactedFile(StrictModel):
    path: NonEmptyStr
    redaction_kinds: tuple[NonEmptyStr, ...]
    replacement_count: int = Field(ge=1)


class DeepSeekRedactionAudit(StrictModel):
    schema_version: Literal["aecbench.deepseek-redaction-audit.v1"] = "aecbench.deepseek-redaction-audit.v1"
    replacement_count: int = Field(ge=0)
    files: tuple[DeepSeekRedactedFile, ...] = ()

    @model_validator(mode="after")
    def validate_replacement_count(self) -> Self:
        if self.replacement_count != sum(record.replacement_count for record in self.files):
            raise ValueError("redaction audit replacement count must equal its file records")
        return self


def verify_deepseek_evidence_manifest(path: Path) -> DeepSeekEvidenceManifest:
    """Validate one receipt and every retained artifact against its recorded bytes."""
    if path.is_symlink() or not path.is_file():
        raise ValueError("DeepSeek evidence manifest must be a regular file")
    manifest = DeepSeekEvidenceManifest.model_validate_json(path.read_text(encoding="utf-8"))
    evidence_root = path.parent.resolve()
    for artifact in manifest.artifacts:
        artifact_path = evidence_root / artifact.path
        if artifact_path.is_symlink() or not artifact_path.is_file():
            raise ValueError(f"DeepSeek evidence artifact is not a regular file: {artifact.path}")
        if not artifact_path.resolve().is_relative_to(evidence_root):
            raise ValueError(f"DeepSeek evidence artifact leaves the trial root: {artifact.path}")
        content = artifact_path.read_bytes()
        if len(content) != artifact.size_bytes or hashlib.sha256(content).hexdigest() != artifact.sha256:
            raise ValueError(f"DeepSeek evidence artifact does not match its receipt: {artifact.path}")
    return manifest
