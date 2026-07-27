# ABOUTME: Exposes the canonical phase-neutral factorial-experiment library surface.
# ABOUTME: Reexports one implementation per symbol while Stage 0 callers retain exact aliases.

from .contracts import (
    FactorialExperimentCandidateSetEvidence,
    FactorialExperimentCellEvidence,
    FactorialExperimentReport,
    FactorialExperimentRunResult,
    FactorialExperimentSpec,
    FactorialExperimentSplit,
    FactorialExperimentTrialEvidence,
)
from .motif_evidence import (
    factorial_experiment_evidence,
    factorial_experiment_learned_subject,
)
from .persistence import load_factorial_experiment_report
from .runtime import prepare_factorial_experiment_spec, run_factorial_experiment
from .verification import verify_factorial_experiment_report

__all__ = [
    "FactorialExperimentCandidateSetEvidence",
    "FactorialExperimentCellEvidence",
    "FactorialExperimentReport",
    "FactorialExperimentRunResult",
    "FactorialExperimentSpec",
    "FactorialExperimentSplit",
    "FactorialExperimentTrialEvidence",
    "factorial_experiment_evidence",
    "factorial_experiment_learned_subject",
    "load_factorial_experiment_report",
    "prepare_factorial_experiment_spec",
    "run_factorial_experiment",
    "verify_factorial_experiment_report",
]
