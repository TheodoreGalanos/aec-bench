# ABOUTME: Defines the generic Harbor import context and execution-evidence boundary.
# ABOUTME: Lets bounded contexts supply evidence without importing them into the harness.

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from aec_bench.contracts.authority_evidence import AuthorityEvidenceRef
from aec_bench.contracts.evaluation_result import EvaluationResult
from aec_bench.contracts.trial_record import ArtifactReference
from aec_bench.harness.harbor_contract import HarborTrialResult


class HarborImportError(Exception):
    """Reject missing, malformed, or causally inconsistent Harbor evidence."""


class ImportEvidenceIntent(StrEnum):
    """Host-owned reason for loading execution-specific evidence."""

    TRIAL_RECORD = "trial_record"
    CANDIDATE_FAILURE = "candidate_failure"


@dataclass(frozen=True)
class ImportEvidenceContext:
    """Canonical Harbor and task paths supplied to concrete evidence readers."""

    trial_dir: Path
    repo_root: Path
    task_instance_dir: Path
    harbor_result: HarborTrialResult


@dataclass(frozen=True)
class ImportedAuthorityEvidence:
    """One final authority reference and the retained bytes that it identifies."""

    reference: AuthorityEvidenceRef
    path: Path


class HarborImportEvidence(Protocol):
    """Portable evidence that one bounded execution adds to a Harbor import."""

    @property
    def adapter_name(self) -> str: ...

    @property
    def artifacts(self) -> tuple[ArtifactReference, ...]: ...

    @property
    def episode_artifact(self) -> ArtifactReference | None: ...

    @property
    def authority_evidence(self) -> tuple[ImportedAuthorityEvidence, ...]: ...

    def sanitize_agent_configuration(
        self,
        configuration: dict[str, Any],
    ) -> dict[str, Any]: ...

    def augment_evaluation(
        self,
        evaluation: EvaluationResult,
    ) -> EvaluationResult: ...


class HarborImportEvidenceLoader(Protocol):
    """Load optional bounded-context evidence for one Harbor import."""

    def __call__(
        self,
        *,
        context: ImportEvidenceContext,
        intent: ImportEvidenceIntent,
    ) -> HarborImportEvidence | None: ...


def execution_kind_from_context(context: ImportEvidenceContext) -> str | None:
    """Return the current execution kind declared by one Harbor agent."""

    configuration = context.harbor_result.config.agent.kwargs
    declared = configuration.get("execution_kind")
    if isinstance(declared, str) and declared:
        return declared
    adapter = configuration.get("adapter")
    return adapter if isinstance(adapter, str) and adapter else None
