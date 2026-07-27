# ABOUTME: Defines the closed enum vocabulary shared by proposal graph, compilation, and session contracts.
# ABOUTME: Keeps stable execution statuses and failure codes independent from their larger evidence models.

from enum import StrEnum


class ProposalPortKind(StrEnum):
    """Small allowlisted evidence vocabulary available to proposal-owned nodes."""

    CITATION_SET = "citation_set"
    FACT_SET = "fact_set"
    CALCULATION_SET = "calculation_set"
    FINDING_SET = "finding_set"
    DECISION_RECORD = "decision_record"
    DATA_GAP_REGISTER = "data_gap_register"
    ARTIFACT_MANIFEST = "artifact_manifest"


class NodeInstructionVisibility(StrEnum):
    """Instruction surface materialized for one proposal node."""

    OBJECTIVE_ONLY = "objective_only"
    PUBLIC_TASK = "public_task"


class ProposalExecutionSemantics(StrEnum):
    """Runtime scheduling semantics whose scientific claim is safe to make."""

    SEQUENTIAL_DATAFLOW = "sequential_dataflow"
    READY_SET_DATAFLOW = "ready_set_dataflow"


class ProposalCompilationStatus(StrEnum):
    """Closed terminal status of deterministic proposal compilation."""

    COMPILED = "compiled"
    REJECTED = "rejected"


class ProposalCompileRejectionCode(StrEnum):
    """Learner-owned compile failures that receive intention-to-treat utility zero."""

    GRAMMAR_INVALID = "grammar_invalid"
    PUBLIC_SOURCE_UNKNOWN = "public_source_unknown"
    PORT_CONTRACT_INVALID = "port_contract_invalid"
    HANDOFF_CONTRACT_INVALID = "handoff_contract_invalid"
    GRAPH_CYCLIC = "graph_cyclic"
    GRAPH_DISCONNECTED = "graph_disconnected"
    NODE_LIMIT_EXCEEDED = "node_limit_exceeded"
    FAN_IN_LIMIT_EXCEEDED = "fan_in_limit_exceeded"
    FAN_OUT_LIMIT_EXCEEDED = "fan_out_limit_exceeded"
    OUTPUT_CONTRACT_MISMATCH = "output_contract_mismatch"
    BUDGET_ALLOCATION_INFEASIBLE = "budget_allocation_infeasible"


class ProposalDiagnosticVisibility(StrEnum):
    """Whether one compile diagnostic may be returned to the proposer."""

    TRAINING_VISIBLE = "training_visible"
    HOST_ONLY = "host_only"


class ProposalNodeReceiptStatus(StrEnum):
    """Terminal status of one planned model-bearing proposal node."""

    COMPLETED = "completed"
    CANDIDATE_FAILURE = "candidate_failure"
    SKIPPED = "skipped"


class ProposalCandidateFailureCode(StrEnum):
    """Closed candidate-owned failures that may receive utility zero."""

    AGENT_TURN_BUDGET_EXHAUSTED = "agent_turn_budget_exhausted"
    TOKEN_BUDGET_EXHAUSTED = "token_budget_exhausted"
    COST_BUDGET_EXHAUSTED = "cost_budget_exhausted"
    TOOL_CALL_BUDGET_EXHAUSTED = "tool_call_budget_exhausted"
    CONTEXT_BUDGET_EXHAUSTED = "context_budget_exhausted"
    RUNTIME_BUDGET_EXHAUSTED = "runtime_budget_exhausted"
    MISSING_HANDOFF = "missing_handoff"
    BRANCH_FAILED = "branch_failed"
    CONTRACT_CHECK_FAILED = "contract_check_failed"
    OUTPUT_COMMIT_MISSING = "output_commit_missing"


class ProposalContractCheckStatus(StrEnum):
    """Closed structural result of checking one attempted node output."""

    PASSED = "passed"
    FAILED = "failed"


class ProposalNodeSkipCause(StrEnum):
    """Candidate-owned reason why one planned node was not attempted."""

    UPSTREAM_FAILURE = "upstream_failure"
    SESSION_BUDGET_EXHAUSTED = "session_budget_exhausted"


class ProposalSessionStatus(StrEnum):
    """Terminal status of one complete task-resident candidate session."""

    COMPLETED = "completed"
    CANDIDATE_FAILURE = "candidate_failure"
