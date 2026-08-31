# ABOUTME: Defines effect-free values used by local artifact task attempts.
# ABOUTME: Owns attempts, selection candidates, decisions, and persisted attempt evidence.

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from aec_bench.adapters.base import AdapterRequest, AdapterResult
from aec_bench.contracts.agent_output import AgentOutputStatus
from aec_bench.contracts.trial_extensions import ArtifactReference
from aec_bench.contracts.validators import StrictModel


@dataclass(frozen=True)
class SelectorCandidate:
    index: int
    attempt_id: str
    status: AgentOutputStatus
    primary_output: bytes | None
    output_reference: ArtifactReference | None

    @property
    def eligible(self) -> bool:
        return self.status is AgentOutputStatus.COMPLETED and bool(self.primary_output)


@dataclass(frozen=True)
class SelectorDecision:
    selected_index: int | None
    reason: str
    configuration: Mapping[str, object]
    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


class CandidateAttemptEvidence(StrictModel):
    index: int
    attempt_id: str
    status: AgentOutputStatus
    elapsed_seconds: float
    eligible: bool
    selector_visible_output: ArtifactReference | None = None


class SelectorEvidence(StrictModel):
    kind: Literal["self"] = "self"
    configuration: dict[str, object]
    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    selected_index: int | None = None


class AttemptSelectionEvidence(StrictModel):
    candidates: tuple[CandidateAttemptEvidence, ...]
    selector: SelectorEvidence
    decision: Literal["selected", "failed"]
    reason: str
    selected_index: int | None = None


@dataclass(frozen=True)
class TaskAttempt:
    attempt_id: str
    trial_id: str
    parent_attempt_id: str | None
    workspace: Path
    request: AdapterRequest
    result: AdapterResult
    elapsed_seconds: float
    selector_visible_output: bytes | None = None
    output_reference: ArtifactReference | None = None

    @property
    def status(self) -> AgentOutputStatus:
        return self.result.agent_output.status


@dataclass(frozen=True)
class AttemptSelection:
    attempt: TaskAttempt | None
    decision: str
    reason: str
    evidence: AttemptSelectionEvidence | None = None

    @classmethod
    def selected(
        cls,
        attempt: TaskAttempt,
        *,
        reason: str,
        evidence: AttemptSelectionEvidence | None = None,
    ) -> AttemptSelection:
        return cls(attempt=attempt, decision="selected", reason=reason, evidence=evidence)

    @classmethod
    def failed(
        cls,
        *,
        reason: str,
        evidence: AttemptSelectionEvidence | None = None,
    ) -> AttemptSelection:
        return cls(attempt=None, decision="failed", reason=reason, evidence=evidence)


__all__ = (
    "AttemptSelection",
    "AttemptSelectionEvidence",
    "CandidateAttemptEvidence",
    "SelectorCandidate",
    "SelectorDecision",
    "SelectorEvidence",
    "TaskAttempt",
)
