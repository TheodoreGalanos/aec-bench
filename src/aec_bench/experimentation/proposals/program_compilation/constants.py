# ABOUTME: Defines compiler-owned operation and orchestration identifiers for proposal execution.
# ABOUTME: Keeps profile validation and lowering bound to one shared phase-neutral vocabulary.

_SESSION_OPERATION_ID = "run_proposal_session"
_SEMANTIC_OPERATION_ID = "run_semantic_subtask"
_CHECK_OPERATION_ID = "check_subtask_contract"
_FINALIZER_OPERATION_ID = "finalize_proposed_plan"
_STOP_NODE_ID = "stop.v1"
_COMPLETE_JOIN_NODE_ID = "join.finalizer.complete"
_PROPOSAL_OPERATION_IDS = (
    _SESSION_OPERATION_ID,
    _SEMANTIC_OPERATION_ID,
    _CHECK_OPERATION_ID,
    _FINALIZER_OPERATION_ID,
)
