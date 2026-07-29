# ABOUTME: Defines the generic extension boundary for importing execution-specific Harbor evidence.
# ABOUTME: Keeps the core TrialRecord importer independent from proposal and future execution policies.

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from aec_bench.contracts.trial_record import (
    ArtifactReference,
    WorldExecutionRecord,
    WorldTrialProvenance,
)
from aec_bench.harness.harbor_contract import HarborTrialResult


class HarborImportError(Exception):
    """Reject missing, malformed, or causally inconsistent Harbor evidence."""


class ImportEvidenceIntent(StrEnum):
    """Host-owned reason for loading execution-specific evidence."""

    TRIAL_RECORD = "trial_record"
    CANDIDATE_FAILURE = "candidate_failure"


@dataclass(frozen=True)
class ImportEvidenceContext:
    """Canonical Harbor and task paths supplied to one evidence extension."""

    trial_dir: Path
    repo_root: Path
    task_instance_dir: Path
    harbor_result: HarborTrialResult


class ImportedExecutionEvidence(Protocol):
    """Evidence projection consumed by the generic TrialRecord importer."""

    @property
    def execution_kind(self) -> str:
        """Return the allowlisted execution kind that produced this evidence."""

    @property
    def adapter_name(self) -> str:
        """Return the adapter identity recorded on the TrialRecord."""

    @property
    def artifacts(self) -> tuple[ArtifactReference, ...]:
        """Return exact verified artifacts to attach to the TrialRecord."""

    def sanitize_agent_configuration(
        self,
        configuration: dict[str, Any],
    ) -> dict[str, Any]:
        """Return a portable, evidence-bound agent configuration."""

    @property
    def world_execution(self) -> WorldExecutionRecord | None:
        """Return the optional stewardship execution projection."""

    @property
    def world_provenance(self) -> WorldTrialProvenance | None:
        """Return the optional stewardship provenance projection."""


class ImportEvidenceExtension(Protocol):
    """Loads fail-closed evidence for one allowlisted execution kind."""

    @property
    def execution_kind(self) -> str:
        """Return the exact execution kind handled by this extension."""

    def load(
        self,
        *,
        context: ImportEvidenceContext,
        intent: ImportEvidenceIntent,
    ) -> ImportedExecutionEvidence:
        """Validate and return evidence for the requested import intent."""


__all__ = (
    "HarborImportError",
    "ImportEvidenceContext",
    "ImportEvidenceExtension",
    "ImportEvidenceIntent",
    "ImportedExecutionEvidence",
)
