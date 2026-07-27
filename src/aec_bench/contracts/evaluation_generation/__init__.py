# ABOUTME: Exposes phase-neutral evaluation-generation contracts without eager sibling imports.
# ABOUTME: Resolves stable convenience exports lazily so cohesive contract modules remain independent.

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS_BY_MODULE: dict[str, tuple[str, ...]] = {
    "aec_bench.contracts.evaluation_generation.batch": (
        "CandidateAssignmentRef",
        "CandidateScheduleRef",
        "EvaluationBatchPlan",
        "TaskCandidatePlan",
    ),
    "aec_bench.contracts.evaluation_generation.cohort": (
        "EvaluationCohortBinding",
        "EvaluationCohortManifest",
        "EvaluationCohortPurpose",
        "EvaluationCohortRetirement",
        "EvaluationCohortTask",
        "EvaluationTaskIdentity",
    ),
    "aec_bench.contracts.evaluation_generation.lifecycle": (
        "CandidateBatchRejectionClosure",
        "EvaluationCriticRetirementRef",
        "EvaluationGenerationClosure",
        "EvaluationGenerationEvidenceRef",
        "EvaluationGenerationEvidenceRole",
        "EvaluationGenerationRetirementClosure",
        "GovernedBatchAssignmentEvidence",
        "GovernedBatchExecutionClosure",
        "GovernedBatchTerminalEvidence",
        "ProposalGenerationClosure",
    ),
    "aec_bench.contracts.evaluation_generation.preparation": (
        "PreparedEvaluationGeneration",
        "PreparedProposalTask",
    ),
    "aec_bench.contracts.evaluation_generation.spec": (
        "CandidateKindRequirement",
        "EvaluationExecutionProfileRef",
        "EvaluationGenerationBudget",
        "EvaluationGenerationSourceRef",
        "EvaluationGenerationSpec",
        "ProposalGenerationPolicy",
    ),
}

_EXPORT_MODULE_BY_NAME = {name: module_name for module_name, names in _EXPORTS_BY_MODULE.items() for name in names}
__all__ = tuple(_EXPORT_MODULE_BY_NAME)


def __getattr__(name: str) -> Any:
    """Load one public evaluation-generation contract on first access."""

    module_name = _EXPORT_MODULE_BY_NAME.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Return ordinary module names plus lazy evaluation-generation exports."""

    return sorted({*globals(), *__all__})
