# ABOUTME: Provides the stable public facade for proposal-execution contracts.
# ABOUTME: Re-exports graph, compilation, session, budget, context, profile, and policy types.

from aec_bench.contracts.proposal_execution.compilation import (
    _V1_COMPATIBILITY_PROFILE_CONTEXT_KEY as _V1_COMPATIBILITY_PROFILE_CONTEXT_KEY,
)
from aec_bench.contracts.proposal_execution.compilation import (
    ProposalCompilationRecord,
    ProposalCompilationRejection,
    ProposalCompilationSuccess,
    ProposalCompileDiagnostic,
    validate_proposal_compilation_v1_compatibility,
)
from aec_bench.contracts.proposal_execution.graph import (
    ExecutableCandidateGraph,
    FinalSynthesisSpec,
    MonolithicIncumbentProgram,
    NodeEvidenceContract,
    ProposalHandoff,
    ProposalInputPort,
    ProposalOutputPort,
    ProposalSourceScope,
    ProposedDecompositionGraph,
    SemanticSubtaskSpec,
)
from aec_bench.contracts.proposal_execution.session import (
    ProposalContainerTransitionRef,
    ProposalContractCheckResultRef,
    ProposalHandoffArtifactRef,
    ProposalNodeExecutionResultRef,
    ProposalNodeReceipt,
    ProposalSessionExecutionRef,
    ProposalSessionPlan,
    ProposalSessionReceipt,
)
from aec_bench.contracts.proposal_execution_budget import (
    CandidateBudgetPlan,
    NodeBudgetReservation,
)
from aec_bench.contracts.proposal_execution_context import (
    CompiledNodeContextScope,
    ProposalSourceScopeManifest,
    ScopedSourceMaterialization,
)
from aec_bench.contracts.proposal_execution_profile import ProposalExecutionProfile
from aec_bench.contracts.proposal_execution_types import (
    NodeInstructionVisibility,
    ProposalCandidateFailureCode,
    ProposalCompilationStatus,
    ProposalCompileRejectionCode,
    ProposalContractCheckStatus,
    ProposalDiagnosticVisibility,
    ProposalExecutionSemantics,
    ProposalNodeReceiptStatus,
    ProposalNodeSkipCause,
    ProposalPortKind,
    ProposalSessionStatus,
)

__all__ = (
    "CandidateBudgetPlan",
    "CompiledNodeContextScope",
    "ExecutableCandidateGraph",
    "FinalSynthesisSpec",
    "MonolithicIncumbentProgram",
    "NodeBudgetReservation",
    "NodeEvidenceContract",
    "NodeInstructionVisibility",
    "ProposalCandidateFailureCode",
    "ProposalCompilationRecord",
    "ProposalCompilationRejection",
    "ProposalCompilationStatus",
    "ProposalCompilationSuccess",
    "ProposalCompileDiagnostic",
    "ProposalCompileRejectionCode",
    "ProposalContainerTransitionRef",
    "ProposalContractCheckResultRef",
    "ProposalContractCheckStatus",
    "ProposalDiagnosticVisibility",
    "ProposalExecutionProfile",
    "ProposalExecutionSemantics",
    "ProposalHandoff",
    "ProposalHandoffArtifactRef",
    "ProposalInputPort",
    "ProposalNodeExecutionResultRef",
    "ProposalNodeReceipt",
    "ProposalNodeReceiptStatus",
    "ProposalNodeSkipCause",
    "ProposalOutputPort",
    "ProposalPortKind",
    "ProposalSessionExecutionRef",
    "ProposalSessionPlan",
    "ProposalSessionReceipt",
    "ProposalSessionStatus",
    "ProposalSourceScope",
    "ProposalSourceScopeManifest",
    "ProposedDecompositionGraph",
    "ScopedSourceMaterialization",
    "SemanticSubtaskSpec",
    "validate_proposal_compilation_v1_compatibility",
)
