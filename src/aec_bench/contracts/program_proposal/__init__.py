# ABOUTME: Exposes the stable public facade for phase-neutral program-proposal contracts.
# ABOUTME: Reexports problem, candidate, freeze, and matched-study types from their owning modules.

from aec_bench.contracts.program_proposal.candidate import (
    CandidateGenerationCoordinate,
    CandidateGenerationManifest,
    ProgramCandidateRef,
)
from aec_bench.contracts.program_proposal.freeze import ProposalFreeze
from aec_bench.contracts.program_proposal.problem import (
    DecompositionLeakageAudit,
    DecompositionProblemView,
    FixedHarnessCapabilityProjection,
    PublicAuthorityBoundary,
    PublicDataGapBoundary,
    PublicSourceRef,
)
from aec_bench.contracts.program_proposal.study import (
    DecompositionOptimizationCycle,
    MatchedCandidateEvidenceRef,
    MatchedEvaluationCoordinate,
    PairedCandidateComparison,
    ProgramCandidateStudy,
)
from aec_bench.contracts.program_proposal.types import (
    CandidateEvidenceKind,
    OptimizationDisposition,
    OptimizationSplit,
    ProgramCandidateKind,
)

__all__ = (
    "CandidateEvidenceKind",
    "CandidateGenerationCoordinate",
    "CandidateGenerationManifest",
    "DecompositionLeakageAudit",
    "DecompositionOptimizationCycle",
    "DecompositionProblemView",
    "FixedHarnessCapabilityProjection",
    "MatchedCandidateEvidenceRef",
    "MatchedEvaluationCoordinate",
    "OptimizationDisposition",
    "OptimizationSplit",
    "PairedCandidateComparison",
    "ProgramCandidateKind",
    "ProgramCandidateRef",
    "ProgramCandidateStudy",
    "ProposalFreeze",
    "PublicAuthorityBoundary",
    "PublicDataGapBoundary",
    "PublicSourceRef",
)
