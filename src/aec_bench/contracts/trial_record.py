# ABOUTME: Contract models for append-only trial provenance in the aec-bench Python implementation.
# ABOUTME: Defines nested execution, input, output, timing, and completeness for replayable records.

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import (
    Field,
    NonNegativeFloat,
    NonNegativeInt,
    field_validator,
    model_validator,
)

from aec_bench.contracts.agent_output import AgentOutput
from aec_bench.contracts.evaluation_result import EvaluationResult
from aec_bench.contracts.validators import NonEmptyStr, StrictModel, ensure_non_empty_string


class Completeness(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"


class TaskReference(StrictModel):
    task_id: NonEmptyStr
    task_revision: NonEmptyStr


class AgentReference(StrictModel):
    adapter: NonEmptyStr
    model: NonEmptyStr
    adapter_revision: str | None = None
    configuration: dict[str, Any] = Field(default_factory=dict)


class EnvironmentSnapshot(StrictModel):
    runtime_image: NonEmptyStr
    compute_backend: NonEmptyStr
    tool_versions: dict[str, str] | None = None


class FileReference(StrictModel):
    path: NonEmptyStr
    hash: NonEmptyStr
    source: str | None = None


class InputRecord(StrictModel):
    instruction: NonEmptyStr
    system_prompt: str | None = None
    input_files: list[FileReference] | None = None


class OutputRecord(StrictModel):
    agent_output: AgentOutput | None = None
    raw_output_path: str | None = None
    conversation_path: str | None = None
    trajectory_path: str | None = None
    agent_result: dict[str, Any] | None = None


class TimingRecord(StrictModel):
    total_seconds: NonNegativeFloat
    agent_seconds: NonNegativeFloat | None = None
    setup_seconds: NonNegativeFloat | None = None
    verification_seconds: NonNegativeFloat | None = None


class CostRecord(StrictModel):
    tokens_in: NonNegativeInt | None = None
    tokens_out: NonNegativeInt | None = None
    cache_read_tokens: NonNegativeInt | None = None
    cache_write_tokens: NonNegativeInt | None = None
    estimated_cost_usd: NonNegativeFloat | None = None
    advisor_calls: NonNegativeInt | None = None
    advisor_input_tokens: NonNegativeInt | None = None
    advisor_output_tokens: NonNegativeInt | None = None


class DerivationStepRecord(StrictModel):
    axis: NonEmptyStr
    value: NonEmptyStr
    parent_value: NonEmptyStr

    @model_validator(mode="after")
    def validate_change(self) -> "DerivationStepRecord":
        if self.value == self.parent_value:
            msg = "derivation step must change the parent value"
            raise ValueError(msg)
        return self


class AdaptationProvenance(StrictModel):
    family_id: NonEmptyStr
    seed_task_id: NonEmptyStr
    variation_key: NonEmptyStr
    variation: dict[str, str]
    derivation_lineage: list[DerivationStepRecord] = Field(default_factory=list)

    @field_validator("variation")
    @classmethod
    def validate_variation(cls, value: dict[str, str]) -> dict[str, str]:
        if not value:
            msg = "variation must not be empty"
            raise ValueError(msg)
        for axis, axis_value in value.items():
            ensure_non_empty_string(axis)
            ensure_non_empty_string(axis_value)
        return value

    @model_validator(mode="after")
    def validate_lineage(self) -> "AdaptationProvenance":
        seen: set[str] = set()
        for step in self.derivation_lineage:
            if step.axis in seen:
                msg = "derivation_lineage axes must be unique"
                raise ValueError(msg)
            seen.add(step.axis)
            if step.axis not in self.variation:
                msg = "derivation_lineage axis must exist in variation"
                raise ValueError(msg)
            if self.variation[step.axis] != step.value:
                msg = "derivation_lineage value must match variation"
                raise ValueError(msg)
        return self


class TrialRecord(StrictModel):
    trial_id: NonEmptyStr
    experiment_id: NonEmptyStr
    dataset_id: str | None = None  # "name@version" or None for inline runs
    timestamp: datetime
    task: TaskReference
    agent: AgentReference
    environment: EnvironmentSnapshot
    inputs: InputRecord
    outputs: OutputRecord
    evaluation: EvaluationResult
    timing: TimingRecord
    cost: CostRecord | None = None
    adaptation: AdaptationProvenance | None = None
    completeness: Completeness

    @model_validator(mode="after")
    def validate_completeness(self) -> "TrialRecord":
        if self.completeness is Completeness.COMPLETE:
            missing = []
            if self.agent.adapter_revision is None:
                missing.append("agent.adapter_revision")
            if self.environment.tool_versions is None:
                missing.append("environment.tool_versions")
            if self.inputs.input_files is None:
                missing.append("inputs.input_files")
            if missing:
                msg = f"complete trial record missing provenance fields: {', '.join(missing)}"
                raise ValueError(msg)
        return self
