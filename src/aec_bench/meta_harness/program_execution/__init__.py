# ABOUTME: Exposes canonical compiled-program contracts, registry, budgets, and execution.
# ABOUTME: Keeps the fixed-kernel runtime surface explicit while preserving stable public identities.

from .budget import BoundedRecursionContext, OperationExecutionContext
from .contracts import (
    InputBindingLineage,
    NodeExecutionEvidence,
    NodeExecutionStatus,
    OperationAttemptEvidence,
    OperationExecutionStatus,
    OperationHandlerFailure,
    OperationLineage,
    OperationResult,
    ProgramExecutionResult,
    ProgramExecutionStatus,
)
from .executor import execute_program
from .registry import OperationHandler, OperationRegistration, OperationRegistry

__all__ = [
    "BoundedRecursionContext",
    "InputBindingLineage",
    "NodeExecutionEvidence",
    "NodeExecutionStatus",
    "OperationAttemptEvidence",
    "OperationExecutionContext",
    "OperationExecutionStatus",
    "OperationHandler",
    "OperationHandlerFailure",
    "OperationLineage",
    "OperationRegistration",
    "OperationRegistry",
    "OperationResult",
    "ProgramExecutionResult",
    "ProgramExecutionStatus",
    "execute_program",
]
