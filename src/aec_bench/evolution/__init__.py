# ABOUTME: Evolution domain for aec-bench — automated agent improvement.
# ABOUTME: Provides workspace management, behavioral analysis, and evolution engine.

from importlib import import_module
from typing import Any

_EXPORTS: dict[str, tuple[str, str]] = {
    "CandidateChecks": ("aec_bench.evolution.evaluation", "CandidateChecks"),
    "CandidateProposal": ("aec_bench.evolution.core", "CandidateProposal"),
    "CandidateProposalRequest": ("aec_bench.evolution.core", "CandidateProposalRequest"),
    "ProposalStatus": ("aec_bench.evolution.core", "ProposalStatus"),
    "ReportWriter": ("aec_bench.evolution.application", "ReportWriter"),
    "build_avo": ("aec_bench.evolution.proposer", "build_avo"),
    "build_local_checks": ("aec_bench.evolution.backends.local", "build_local_checks"),
    "gate_candidate": ("aec_bench.evolution.core", "gate_candidate"),
    "next_evolution_state": ("aec_bench.evolution.core", "next_evolution_state"),
    "run_evolution": ("aec_bench.evolution.application", "run_evolution"),
    "run_evolution_from_config": ("aec_bench.evolution.application", "run_evolution_from_config"),
}

__all__ = (
    "CandidateChecks",
    "CandidateProposal",
    "CandidateProposalRequest",
    "ProposalStatus",
    "ReportWriter",
    "build_avo",
    "build_local_checks",
    "gate_candidate",
    "next_evolution_state",
    "run_evolution",
    "run_evolution_from_config",
)


def __getattr__(name: str) -> Any:
    """Load a public evolution export only when a caller requests it."""
    try:
        module_name, attribute_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc

    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Include lazy public exports in interactive and introspection views."""
    return sorted(set(globals()) | set(__all__))
