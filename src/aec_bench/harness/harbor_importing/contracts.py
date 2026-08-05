# ABOUTME: Defines current Harbor import context and the two supported evidence intents.
# ABOUTME: Keeps execution-kind dispatch concrete at the serialized import boundary.

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

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


def execution_kind_from_context(context: ImportEvidenceContext) -> str | None:
    """Return the current execution kind declared by one Harbor agent."""

    configuration = context.harbor_result.config.agent.kwargs
    declared = configuration.get("execution_kind")
    if isinstance(declared, str) and declared:
        return declared
    adapter = configuration.get("adapter")
    return adapter if isinstance(adapter, str) and adapter else None
