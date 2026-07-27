# ABOUTME: Tests the phase-neutral profile that pins proposal compilation and execution policy.
# ABOUTME: Proves operation, harness, lowering, and scheduling constraints are exact and immutable.

import pytest
from pydantic import ValidationError

from aec_bench.contracts.harness_instance import ProgramOperationScope
from aec_bench.contracts.harness_kernel import KernelCapabilityRef
from aec_bench.contracts.proposal_execution_profile import (
    ProposalEnvironmentPolicy,
    ProposalExecutionProfile,
    ProposalExecutionSurfacePolicy,
    ProposalHarnessTopologyPolicy,
    ProposalLoweringPolicy,
    ProposalOperationConstraint,
    ProposalSchedulingPolicy,
    ProposalSchedulingSemantics,
)


def _operation(
    operation_id: str,
    *,
    capability_id: str,
    definition_sha256: str,
    scope: ProgramOperationScope,
) -> ProposalOperationConstraint:
    return ProposalOperationConstraint(
        operation_id=operation_id,
        operation_definition_sha256=definition_sha256,
        capability_ref=KernelCapabilityRef(
            capability_id=capability_id,
            version="1.0.0",
            content_sha256="a" * 64,
        ),
        required_scope=scope,
        max_parallelism=1,
        supports_retry=False,
        supports_recursion=False,
    )


def _profile(
    *,
    scheduling: ProposalSchedulingPolicy | None = None,
) -> ProposalExecutionProfile:
    return ProposalExecutionProfile(
        profile_id="proposal-execution.sequential-v1",
        version="1.0.0",
        required_kernel_id="aecbench.default",
        required_kernel_version="1.6.0",
        operation_constraints=(
            _operation(
                "run_semantic_subtask.v1",
                capability_id="aecbench.operation.proposal.run-semantic-subtask",
                definition_sha256="b" * 64,
                scope=ProgramOperationScope.PROPOSAL_SESSION_INTERNAL,
            ),
            _operation(
                "run_proposal_session.v1",
                capability_id="aecbench.operation.proposal.run-session",
                definition_sha256="c" * 64,
                scope=ProgramOperationScope.PUBLIC,
            ),
        ),
        harness_topology=ProposalHarnessTopologyPolicy(
            required_agent_binding_count=1,
            max_context_binding_count=1,
            max_tool_binding_count=1,
        ),
        execution_surface=ProposalExecutionSurfacePolicy(
            adapter_kind="rlm",
            completion_policy="task_output_commit",
            allowed_tool_ids=("bash",),
            allowed_backends=("morph",),
            provider_broker_required=True,
        ),
        lowering=ProposalLoweringPolicy(
            max_semantic_subtasks=4,
            max_fan_in=2,
            max_fan_out=2,
            allow_retry=False,
            allow_recursion=False,
        ),
        scheduling=scheduling
        or ProposalSchedulingPolicy(
            semantics=ProposalSchedulingSemantics.SEQUENTIAL_DATAFLOW,
            max_parallelism=1,
            environment_policy=ProposalEnvironmentPolicy.ROTATED_SINGLE_ENVIRONMENT,
            deterministic_commit_order=True,
        ),
    )


def test_profile_canonicalizes_exact_operations_and_is_deeply_immutable() -> None:
    profile = _profile()

    assert tuple(item.operation_id for item in profile.operation_constraints) == (
        "run_proposal_session.v1",
        "run_semantic_subtask.v1",
    )
    assert profile.required_operation_ids == (
        "run_proposal_session.v1",
        "run_semantic_subtask.v1",
    )
    assert len(profile.content_sha256) == 64

    with pytest.raises(ValidationError, match="Instance is frozen"):
        profile.required_kernel_version = "changed"  # type: ignore[misc]


def test_profile_rejects_ambiguous_operation_or_capability_bindings() -> None:
    profile = _profile()
    first = profile.operation_constraints[0]
    duplicate_operation = first.model_copy(
        update={
            "capability_ref": KernelCapabilityRef(
                capability_id="another.capability",
                version="1.0.0",
                content_sha256="d" * 64,
            ),
            "operation_definition_sha256": "e" * 64,
        },
    )

    with pytest.raises(ValidationError, match="operation ids"):
        ProposalExecutionProfile(
            **{
                **profile.model_dump(
                    mode="python",
                    exclude={"content_sha256", "operation_constraints"},
                ),
                "operation_constraints": (first, duplicate_operation),
            },
        )

    duplicate_capability = profile.operation_constraints[1].model_copy(
        update={
            "operation_id": "another-operation.v1",
            "operation_definition_sha256": "f" * 64,
            "capability_ref": first.capability_ref,
        },
    )
    with pytest.raises(ValidationError, match="capability refs"):
        ProposalExecutionProfile(
            **{
                **profile.model_dump(
                    mode="python",
                    exclude={"content_sha256", "operation_constraints"},
                ),
                "operation_constraints": (first, duplicate_capability),
            },
        )


def test_scheduling_policy_requires_an_environment_model_that_can_realize_it() -> None:
    with pytest.raises(ValidationError, match="sequential"):
        ProposalSchedulingPolicy(
            semantics=ProposalSchedulingSemantics.SEQUENTIAL_DATAFLOW,
            max_parallelism=2,
            environment_policy=ProposalEnvironmentPolicy.ROTATED_SINGLE_ENVIRONMENT,
            deterministic_commit_order=True,
        )

    with pytest.raises(ValidationError, match="isolated environment pool"):
        ProposalSchedulingPolicy(
            semantics=ProposalSchedulingSemantics.READY_SET_DATAFLOW,
            max_parallelism=2,
            environment_policy=ProposalEnvironmentPolicy.ROTATED_SINGLE_ENVIRONMENT,
            deterministic_commit_order=True,
        )

    ready_set = ProposalSchedulingPolicy(
        semantics=ProposalSchedulingSemantics.READY_SET_DATAFLOW,
        max_parallelism=2,
        environment_policy=ProposalEnvironmentPolicy.ISOLATED_ENVIRONMENT_POOL,
        deterministic_commit_order=True,
    )
    profile = _profile(scheduling=ready_set)
    assert profile.scheduling == ready_set
