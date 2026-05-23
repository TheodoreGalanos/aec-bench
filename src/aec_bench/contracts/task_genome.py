# ABOUTME: Contract models for task genome sidecar manifests.
# ABOUTME: Describes decomposed task pressures with provenance and review metadata.

from typing import Any, Literal

from pydantic import Field, field_validator

from aec_bench.contracts.validators import (
    NonEmptyStr,
    StrictModel,
    ensure_optional_relative_path,
    ensure_relative_path,
)

Confidence = Literal["high", "medium", "low"]
TaskGenomeStatus = Literal["extracted", "needs_review"]


class ProvenanceRef(StrictModel):
    file: NonEmptyStr
    section: str | None = None
    signal: str | None = None

    @field_validator("file")
    @classmethod
    def validate_file(cls, value: str) -> str:
        return ensure_relative_path(value)


class DomainFrame(StrictModel):
    discipline: NonEmptyStr
    subdomain: NonEmptyStr
    role: str | None = None
    standards: list[str] = Field(default_factory=list)


class Scenario(StrictModel):
    summary: NonEmptyStr
    setting: str | None = None


class InputBundle(StrictModel):
    quantities: list[str] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)

    @field_validator("artifacts")
    @classmethod
    def validate_artifacts(cls, value: list[str]) -> list[str]:
        return [ensure_relative_path(item) for item in value]


class PressurePoint(StrictModel):
    id: NonEmptyStr
    type: NonEmptyStr
    description: NonEmptyStr
    provenance: list[ProvenanceRef] = Field(default_factory=list)
    confidence: Confidence = "medium"
    reviewed_by: NonEmptyStr = "deterministic_extractor"


class OutputContract(StrictModel):
    format: NonEmptyStr
    required_fields: list[str] = Field(default_factory=list)
    output_path: str | None = None


class VerifierContract(StrictModel):
    mode: NonEmptyStr
    script: str | None = None
    field_scores: dict[str, str] = Field(default_factory=dict)
    validation_rules: dict[str, int] = Field(default_factory=dict)

    @field_validator("script")
    @classmethod
    def validate_script(cls, value: str | None) -> str | None:
        return ensure_optional_relative_path(value)


class ExtractionSummary(StrictModel):
    deterministic_fields: list[str] = Field(default_factory=list)
    reasoning_review_fields: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class TaskGenomeManifest(StrictModel):
    task_id: NonEmptyStr
    source_task_path: NonEmptyStr
    status: TaskGenomeStatus = "extracted"
    domain_frame: DomainFrame
    scenario: Scenario
    input_bundle: InputBundle
    reasoning_moves: list[str] = Field(default_factory=list)
    pressure_points: list[PressurePoint] = Field(default_factory=list)
    output_contract: OutputContract
    verifier_contract: VerifierContract
    difficulty_controls: dict[str, Any] = Field(default_factory=dict)
    trajectory_affordances: dict[str, Any] = Field(default_factory=dict)
    extraction: ExtractionSummary

    @field_validator("source_task_path")
    @classmethod
    def validate_source_task_path(cls, value: str) -> str:
        return ensure_relative_path(value)


class TaskGenomeEvidencePacket(StrictModel):
    task_id: NonEmptyStr
    source_task_path: NonEmptyStr
    deterministic_manifest: TaskGenomeManifest
    task_toml: dict[str, Any] = Field(default_factory=dict)
    instruction_sections: dict[str, str] = Field(default_factory=dict)
    verifier_files: dict[str, str] = Field(default_factory=dict)
    artifact_paths: list[str] = Field(default_factory=list)

    @field_validator("source_task_path")
    @classmethod
    def validate_source_task_path(cls, value: str) -> str:
        return ensure_relative_path(value)

    @field_validator("verifier_files")
    @classmethod
    def validate_verifier_file_paths(cls, value: dict[str, str]) -> dict[str, str]:
        return {ensure_relative_path(path): content for path, content in value.items()}

    @field_validator("artifact_paths")
    @classmethod
    def validate_artifact_paths(cls, value: list[str]) -> list[str]:
        return [ensure_relative_path(item) for item in value]
