# ABOUTME: Pydantic contract for structured agent trajectory entries.
# ABOUTME: Validates JSONL entries produced by the container-side TrajectoryWriter.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, NonNegativeInt, PositiveInt, field_validator, model_validator

from aec_bench.contracts.execution_program import ExecutionProgramRef
from aec_bench.contracts.harness_instance import HarnessInstanceRef
from aec_bench.contracts.harness_kernel import KernelRef
from aec_bench.contracts.validators import NonEmptyStr, StrictModel


class MetaHarnessTrajectoryContext(StrictModel):
    kernel_ref: KernelRef
    harness_ref: HarnessInstanceRef
    program_ref: ExecutionProgramRef
    plan_run_id: NonEmptyStr
    program_node_id: NonEmptyStr
    binding_ids: tuple[NonEmptyStr, ...] = ()
    repair_iteration: NonNegativeInt | None = None
    execution_seed: int | None = None
    execution_seed_semantics: Literal["paired_repetition_label_only"] = "paired_repetition_label_only"
    attempt: PositiveInt = 1
    motif_ids: tuple[NonEmptyStr, ...] = ()
    proposal_session_id: NonEmptyStr | None = None
    proposal_invocation_id: NonEmptyStr | None = None

    @field_validator("binding_ids", "motif_ids")
    @classmethod
    def validate_sorted_unique_lineage(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if tuple(sorted(set(value))) != value:
            raise ValueError("meta-harness lineage ids must be sorted and unique")
        return value

    @model_validator(mode="after")
    def validate_proposal_invocation_lineage(self) -> MetaHarnessTrajectoryContext:
        if (self.proposal_session_id is None) != (self.proposal_invocation_id is None):
            raise ValueError("proposal session and invocation lineage must be provided together")
        return self


class TrajectoryReasoning(StrictModel):
    """Thinking text exposed by a provider, which can be a summary of hidden reasoning."""

    content: str
    provider_name: str | None = None
    part_id: str | None = None
    has_signature: bool = False


class TrajectoryUsage(StrictModel):
    """Per-response token counts; missing counts have no numeric value."""

    input_tokens: NonNegativeInt | None = None
    output_tokens: NonNegativeInt | None = None
    cache_read_tokens: NonNegativeInt | None = None
    cache_write_tokens: NonNegativeInt | None = None
    details: dict[str, NonNegativeInt] = Field(default_factory=dict)


class TrajectoryModelResponse(StrictModel):
    """One observed model response and usage normalised by its producing SDK."""

    source: NonEmptyStr
    model_name: str | None = None
    provider_name: str | None = None
    response_id: str | None = None
    usage: TrajectoryUsage | None = None


class TrajectoryEntry(StrictModel):
    """A single structured entry from an agent trajectory JSONL file."""

    step: NonNegativeInt
    role: str
    content: str | None = None
    reasoning: TrajectoryReasoning | None = None
    model_response: TrajectoryModelResponse | None = None
    subagent: TrajectorySubagentEntry | None = None
    tool_name: str | None = None
    tool_call_id: str | None = None
    command: str | None = None
    arguments: dict[str, Any] | None = None
    stdout: str | None = None
    stderr: str | None = None
    exit_code: int | None = None
    duration_ms: int | None = None
    media: list[str] | None = None
    metadata: dict[str, Any] | None = None  # RLM step metadata (structured)
    meta_harness: MetaHarnessTrajectoryContext | None = None
    call_type: str | None = None  # warmup, main, or subagent
    output_summary: str | None = None  # truncated preview of stdout
    timestamp: str | None = None

    @model_validator(mode="after")
    def validate_response_payloads(self) -> TrajectoryEntry:
        for role, payload in (
            ("reasoning", self.reasoning),
            ("model_response", self.model_response),
            ("subagent", self.subagent),
        ):
            if (self.role == role) != (payload is not None):
                raise ValueError(f"{role} payload is required only for role={role!r}")
        return self


class TrajectorySubagentEntry(StrictModel):
    """One child record, attributed to an explicit parent tool call."""

    trajectory_id: NonEmptyStr
    parent_tool_call_id: NonEmptyStr | None = None
    agent_name: NonEmptyStr
    model_name: NonEmptyStr | None = None
    entry: TrajectoryEntry


def read_trajectory(path: Path) -> list[TrajectoryEntry]:
    """Read current trajectory JSONL entries, or return an empty list when absent."""
    if not path.exists():
        return []

    entries: list[TrajectoryEntry] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        data = json.loads(line)
        entries.append(TrajectoryEntry.model_validate(data))

    return entries
