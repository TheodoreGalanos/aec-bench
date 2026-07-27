# ABOUTME: Guards the stable compiled-program runtime surface during fixed-kernel decomposition.
# ABOUTME: Proves public contracts, registry types, contexts, and execution retain exact object identity.

from __future__ import annotations

from aec_bench.meta_harness import program_runtime
from aec_bench.meta_harness.program_execution import budget, contracts, executor, registry


def test_program_runtime_facade_preserves_public_object_identity() -> None:
    owners = {
        "OperationExecutionStatus": contracts,
        "NodeExecutionStatus": contracts,
        "ProgramExecutionStatus": contracts,
        "OperationResult": contracts,
        "OperationHandlerFailure": contracts,
        "InputBindingLineage": contracts,
        "OperationLineage": contracts,
        "OperationAttemptEvidence": contracts,
        "NodeExecutionEvidence": contracts,
        "ProgramExecutionResult": contracts,
        "OperationHandler": registry,
        "OperationRegistration": registry,
        "OperationRegistry": registry,
        "OperationExecutionContext": budget,
        "BoundedRecursionContext": budget,
        "execute_program": executor,
    }

    for name, owner in owners.items():
        assert getattr(program_runtime, name) is getattr(owner, name)
