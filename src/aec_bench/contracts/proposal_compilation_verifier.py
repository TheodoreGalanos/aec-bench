# ABOUTME: Verifies proposal compilation and rejection records outside persisted contracts.
# ABOUTME: Recomputes freeze, profile, source, budget, lowering, and diagnostic bindings.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aec_bench.contracts.execution_program import (
    ActionNode,
    ExecutionProgram,
    FanoutNode,
    VerifyNode,
)
from aec_bench.contracts.harness_instance import (
    HarnessInstanceRef,
    ProgramOperationScope,
)
from aec_bench.contracts.harness_kernel import (
    canonical_content_sha256,
)
from aec_bench.contracts.program_proposal.candidate import ProgramCandidateRef
from aec_bench.contracts.program_proposal.freeze import ProposalFreeze
from aec_bench.contracts.program_proposal.types import OptimizationSplit, ProgramCandidateKind
from aec_bench.contracts.proposal_execution.compilation import (
    ProposalCompilationRejection,
    ProposalCompilationSuccess,
)
from aec_bench.contracts.proposal_execution.graph import (
    ExecutableCandidateGraph,
    MonolithicIncumbentProgram,
    ProposedDecompositionGraph,
)
from aec_bench.contracts.proposal_execution_budget import CandidateBudgetPlan
from aec_bench.contracts.proposal_execution_context import ProposalSourceScopeManifest
from aec_bench.contracts.proposal_execution_profile import (
    ProposalExecutionProfile,
)
from aec_bench.contracts.proposal_execution_types import NodeInstructionVisibility, ProposalDiagnosticVisibility


@dataclass(frozen=True, slots=True)
class ProposalCompilationSuccessVerification:
    """Derived evidence for one valid compiled candidate."""

    compilation_id: str
    candidate_id: str
    profile_sha256: str
    graph_sha256: str
    node_ids: tuple[str, ...]
    operation_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProposalCompilationRejectionVerification:
    """Derived evidence for one valid learner-owned compilation rejection."""

    compilation_id: str
    candidate_id: str
    profile_sha256: str
    diagnostic_code: str
    diagnostic_visibility: str


def verify_proposal_compilation_success(
    compilation: ProposalCompilationSuccess,
    *,
    profile: ProposalExecutionProfile,
) -> ProposalCompilationSuccessVerification:
    """Recompute every cross-record binding for a compiled proposal."""

    _validate_common_compilation_bindings(
        candidate_ref=compilation.candidate_ref,
        raw_proposal_artifact_sha256=(compilation.raw_proposal_artifact_sha256),
        graph=compilation.proposal_graph,
        freeze=compilation.proposal_freeze,
        kernel_sha256=compilation.kernel_sha256,
        fixed_harness_ref=compilation.fixed_harness_ref,
        execution_profile=profile,
    )
    _validate_compiled_program_bindings(compilation)
    _validate_lowered_operations(
        compilation.lowered_program,
        profile=profile,
    )
    _validate_source_scope_manifest(
        graph=compilation.proposal_graph,
        freeze=compilation.proposal_freeze,
        manifest=compilation.source_scope_manifest,
    )
    _validate_budget_plan(
        graph=compilation.proposal_graph,
        freeze=compilation.proposal_freeze,
        plan=compilation.budget_plan,
        profile=profile,
    )
    return ProposalCompilationSuccessVerification(
        compilation_id=compilation.compilation_id,
        candidate_id=compilation.candidate_ref.candidate_id,
        profile_sha256=profile.content_sha256,
        graph_sha256=compilation.proposal_graph.content_sha256,
        node_ids=compilation.proposal_graph.node_ids,
        operation_ids=_invoked_operation_ids(compilation.lowered_program),
    )


def verify_proposal_compilation_rejection(
    rejection: ProposalCompilationRejection,
    *,
    profile: ProposalExecutionProfile,
) -> ProposalCompilationRejectionVerification:
    """Recompute every cross-record binding for a compilation rejection."""

    _validate_frozen_compilation_inputs(
        candidate_ref=rejection.candidate_ref,
        freeze=rejection.proposal_freeze,
        kernel_sha256=rejection.kernel_sha256,
        fixed_harness_ref=rejection.fixed_harness_ref,
    )
    if rejection.raw_proposal_artifact_sha256 != rejection.candidate_ref.candidate_artifact_sha256:
        raise ValueError("raw proposal artifact does not match the frozen candidate")
    expected_visibility = (
        ProposalDiagnosticVisibility.TRAINING_VISIBLE
        if rejection.proposal_freeze.split is OptimizationSplit.TRAINING
        else ProposalDiagnosticVisibility.HOST_ONLY
    )
    if rejection.diagnostic.feedback_visibility is not expected_visibility:
        raise ValueError(
            f"{rejection.proposal_freeze.split.value} compile diagnostics must be {expected_visibility.value}"
        )
    return ProposalCompilationRejectionVerification(
        compilation_id=rejection.compilation_id,
        candidate_id=rejection.candidate_ref.candidate_id,
        profile_sha256=profile.content_sha256,
        diagnostic_code=rejection.diagnostic.code.value,
        diagnostic_visibility=(rejection.diagnostic.feedback_visibility.value),
    )


def _validate_compiled_program_bindings(
    compilation: ProposalCompilationSuccess,
) -> None:
    if compilation.surface_sha256 != compilation.compiled_program.surface_sha256:
        raise ValueError("compiled proposal surface identity does not match")
    if compilation.lowered_program.harness_ref != compilation.fixed_harness_ref:
        raise ValueError("lowered proposal does not target the fixed harness")
    if compilation.compiled_program.harness_ref != compilation.fixed_harness_ref:
        raise ValueError("compiled proposal does not target the fixed harness")
    if compilation.compiled_program.source_program_sha256 != compilation.lowered_program.content_sha256:
        raise ValueError("compiled proposal does not bind the lowered program")


def _validate_graph_against_profile(
    graph: ExecutableCandidateGraph,
    *,
    profile: ProposalExecutionProfile,
) -> None:
    if isinstance(graph, MonolithicIncumbentProgram):
        return
    if len(graph.semantic_subtasks) > profile.lowering.max_semantic_subtasks:
        raise ValueError("proposal graph semantic-subtask count exceeds its execution profile")
    fan_in = {node_id: 0 for node_id in graph.node_ids}
    fan_out = {node_id: 0 for node_id in graph.node_ids}
    for handoff in graph.handoffs:
        fan_in[handoff.consumer_node_id] += 1
        fan_out[handoff.producer_node_id] += 1
    if max(fan_in.values(), default=0) > profile.lowering.max_fan_in:
        raise ValueError("proposal graph fan-in exceeds its execution profile")
    if max(fan_out.values(), default=0) > profile.lowering.max_fan_out:
        raise ValueError("proposal graph fan-out exceeds its execution profile")


def _validate_common_compilation_bindings(
    *,
    candidate_ref: ProgramCandidateRef,
    raw_proposal_artifact_sha256: str,
    graph: ExecutableCandidateGraph,
    freeze: ProposalFreeze,
    kernel_sha256: str,
    fixed_harness_ref: HarnessInstanceRef,
    execution_profile: ProposalExecutionProfile,
) -> None:
    _validate_frozen_compilation_inputs(
        candidate_ref=candidate_ref,
        freeze=freeze,
        kernel_sha256=kernel_sha256,
        fixed_harness_ref=fixed_harness_ref,
    )
    _validate_graph_against_profile(
        graph,
        profile=execution_profile,
    )
    if candidate_ref.candidate_artifact_sha256 != raw_proposal_artifact_sha256:
        raise ValueError("raw proposal artifact does not match the frozen candidate")
    if graph.candidate_id != candidate_ref.candidate_id:
        raise ValueError("candidate program identity does not match its candidate reference")
    _validate_candidate_kind_binding(
        candidate_ref=candidate_ref,
        graph=graph,
    )
    if graph.problem_view_sha256 != freeze.problem_view.content_sha256:
        raise ValueError("candidate program does not bind the frozen problem view")
    if isinstance(graph, ProposedDecompositionGraph) and (
        graph.proposal_policy_sha256 != freeze.proposal_policy_sha256
        or graph.policy_checkpoint_sha256 != freeze.policy_checkpoint_sha256
    ):
        raise ValueError("proposed graph does not bind the frozen proposal policy")
    expected_output_contract = canonical_content_sha256(freeze.problem_view.output_contract.model_dump(mode="json"))
    if graph.finalizer.output_completion_contract_sha256 != expected_output_contract:
        raise ValueError("proposal finalizer output contract does not match problem view")


def _validate_candidate_kind_binding(
    *,
    candidate_ref: ProgramCandidateRef,
    graph: ExecutableCandidateGraph,
) -> None:
    if isinstance(graph, ProposedDecompositionGraph):
        if (
            candidate_ref.kind is not ProgramCandidateKind.PROPOSAL
            or graph.generation_coordinate_id != candidate_ref.generation_coordinate_id
        ):
            raise ValueError("proposed graph identity does not match its candidate reference")
        return
    if candidate_ref.kind is not ProgramCandidateKind.INCUMBENT:
        raise ValueError("monolithic program requires the exact incumbent candidate reference")


def _validate_frozen_compilation_inputs(
    *,
    candidate_ref: ProgramCandidateRef,
    freeze: ProposalFreeze,
    kernel_sha256: str,
    fixed_harness_ref: HarnessInstanceRef,
) -> None:
    frozen = (
        freeze.incumbent_candidate
        if candidate_ref.kind is ProgramCandidateKind.INCUMBENT
        else next(
            (
                candidate
                for candidate in freeze.realized_candidates
                if candidate.candidate_id == candidate_ref.candidate_id
            ),
            None,
        )
    )
    if frozen != candidate_ref:
        raise ValueError("candidate artifact reference is outside the exact proposal freeze")
    if kernel_sha256 != freeze.problem_view.fixed_harness.kernel_sha256:
        raise ValueError("compilation kernel does not match the frozen kernel")
    if fixed_harness_ref.content_sha256 != freeze.fixed_harness_sha256:
        raise ValueError("compilation harness does not match the frozen harness")


def _validate_source_scope_manifest(
    *,
    graph: ExecutableCandidateGraph,
    freeze: ProposalFreeze,
    manifest: ProposalSourceScopeManifest,
) -> None:
    if (
        manifest.proposal_graph_sha256 != graph.content_sha256
        or manifest.problem_view_sha256 != graph.problem_view_sha256
    ):
        raise ValueError("source scope manifest does not bind the proposed graph")
    expected_sources = {
        source.source_id: (source.source_sha256, source.byte_size) for source in freeze.problem_view.public_sources
    }
    actual_sources = {source.source_id: (source.source_sha256, source.byte_size) for source in manifest.sources}
    if actual_sources != expected_sources:
        raise ValueError("source scope manifest does not match exact public sources")
    if _manifest_scope_bindings(graph) != _actual_scope_bindings(manifest):
        raise ValueError("source scope manifest does not match exact node scopes")


def _manifest_scope_bindings(
    graph: ExecutableCandidateGraph,
) -> dict[
    str,
    tuple[
        tuple[str, ...],
        tuple[str, ...],
        NodeInstructionVisibility,
    ],
]:
    expected = {
        subtask.node_id: (
            subtask.source_scope.source_ids,
            tuple(
                sorted(handoff.handoff_id for handoff in graph.handoffs if handoff.consumer_node_id == subtask.node_id)
            ),
            NodeInstructionVisibility.OBJECTIVE_ONLY,
        )
        for subtask in graph.semantic_subtasks
    }
    expected[graph.finalizer.node_id] = (
        graph.finalizer.source_scope.source_ids,
        tuple(
            sorted(
                handoff.handoff_id for handoff in graph.handoffs if handoff.consumer_node_id == graph.finalizer.node_id
            )
        ),
        NodeInstructionVisibility.PUBLIC_TASK,
    )
    return expected


def _actual_scope_bindings(
    manifest: ProposalSourceScopeManifest,
) -> dict[
    str,
    tuple[
        tuple[str, ...],
        tuple[str, ...],
        NodeInstructionVisibility,
    ],
]:
    return {
        scope.node_id: (
            scope.source_ids,
            scope.upstream_handoff_ids,
            scope.instruction_visibility,
        )
        for scope in manifest.node_scopes
    }


def _validate_budget_plan(
    *,
    graph: ExecutableCandidateGraph,
    freeze: ProposalFreeze,
    plan: CandidateBudgetPlan,
    profile: ProposalExecutionProfile,
) -> None:
    if (
        plan.candidate_id != graph.candidate_id
        or plan.proposal_graph_sha256 != graph.content_sha256
        or plan.proposal_freeze_sha256 != freeze.content_sha256
        or plan.fixed_harness_sha256 != freeze.fixed_harness_sha256
        or plan.aggregate_budget != freeze.problem_view.fixed_harness.aggregate_budget
    ):
        raise ValueError("candidate budget plan does not bind the exact frozen candidate")
    if plan.reservation_node_ids != graph.node_ids:
        raise ValueError("candidate budget plan must reserve every proposal node exactly")
    if plan.execution_semantics.value != profile.scheduling.semantics.value:
        raise ValueError("candidate budget plan scheduling differs from the proposal execution profile")


def _validate_lowered_operations(
    program: ExecutionProgram,
    *,
    profile: ProposalExecutionProfile,
) -> None:
    invoked = set(_invoked_operation_ids(program))
    allowed = {
        constraint.operation_id
        for constraint in profile.operation_constraints
        if constraint.required_scope is ProgramOperationScope.PROPOSAL_SESSION_INTERNAL
    }
    outside = sorted(invoked - allowed)
    if outside:
        raise ValueError("lowered proposal invokes operations outside its execution profile: " + ", ".join(outside))
    if program.limits.max_parallelism != profile.scheduling.max_parallelism:
        raise ValueError("lowered proposal parallelism differs from its execution profile")
    for node in program.nodes:
        _validate_operation_policy(
            node,
            profile=profile,
        )


def _invoked_operation_ids(
    program: ExecutionProgram,
) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                node.operation_id
                for node in program.nodes
                if isinstance(
                    node,
                    ActionNode | FanoutNode | VerifyNode,
                )
            }
        )
    )


def _validate_operation_policy(
    node: Any,
    *,
    profile: ProposalExecutionProfile,
) -> None:
    if not isinstance(node, ActionNode | FanoutNode | VerifyNode):
        return
    constraint = profile.operation(node.operation_id)
    if constraint is None:
        return
    retry = node.retry
    recursion = node.recursion if isinstance(node, ActionNode | FanoutNode) else None
    if retry is not None and (not profile.lowering.allow_retry or not constraint.supports_retry):
        raise ValueError(f"lowered proposal operation {node.operation_id!r} uses retry outside its execution profile")
    if recursion is not None and (not profile.lowering.allow_recursion or not constraint.supports_recursion):
        raise ValueError(
            f"lowered proposal operation {node.operation_id!r} uses recursion outside its execution profile"
        )
