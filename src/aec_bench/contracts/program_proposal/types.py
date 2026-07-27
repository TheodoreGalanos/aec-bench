# ABOUTME: Defines the closed vocabularies shared by phase-neutral program-proposal contracts.
# ABOUTME: Keeps candidate, split, evidence, and disposition values independent of contract ownership.

from enum import StrEnum


class OptimizationSplit(StrEnum):
    """Closed task splits on which proposal candidates may be generated or studied."""

    CALIBRATION = "calibration"
    # Historical Phase 9.1a split value remains valid for v1 replay.
    PROVIDER_CALIBRATION = "provider_calibration"
    TRAINING = "training"
    DEVELOPMENT = "development"
    STRUCTURAL_HOLDOUT = "structural_holdout"


class ProgramCandidateKind(StrEnum):
    """Candidate origin within a decomposition-optimization study."""

    INCUMBENT = "incumbent"
    PROPOSAL = "proposal"


class CandidateEvidenceKind(StrEnum):
    """Closed provenance shape for one candidate-coordinate outcome."""

    TRIAL_RECORD = "trial_record"
    COMPILE_REJECTION = "compile_rejection"
    CANDIDATE_FAILURE = "candidate_failure"


class OptimizationDisposition(StrEnum):
    """Closed paired-comparison and cycle terminal outcomes."""

    ACCEPT = "accept"
    DEVELOPMENT_SELECTED = "development_selected"
    REJECT = "reject"
    ABSTAIN = "abstain"
    EXPERIMENT_ERROR = "experiment_error"
