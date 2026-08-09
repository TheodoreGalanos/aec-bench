# ABOUTME: Tests proposal-owned semantic graphs, compilation evidence, and session receipts.
# ABOUTME: Proves Phase 9.1 candidates stay source-scoped, budget-shared, and fail closed.

from __future__ import annotations

import hashlib
import json

import pytest
from pydantic import TypeAdapter, ValidationError

from aec_bench.contracts.authority import OperatorRole, operator_authority_for
from aec_bench.contracts.evaluation_plane import EvaluationPlanRef
from aec_bench.contracts.execution_program import (
    ActionNode,
    CompiledExecutionProgram,
    ExecutionProgram,
    OutputValue,
    ProgramArgument,
    ProgramLimits,
    ProgramOutputRef,
    StopNode,
    StopOutcome,
)
from aec_bench.contracts.harness_instance import (
    HarnessBudget,
    HarnessInstanceRef,
    ProgramOperationRef,
    ProgramOperationScope,
)
from aec_bench.contracts.harness_kernel import (
    KernelCapabilityRef,
    canonical_content_sha256,
)
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
    PublicSourceRef,
)
from aec_bench.contracts.program_proposal.study import MatchedEvaluationCoordinate
from aec_bench.contracts.program_proposal.types import OptimizationSplit, ProgramCandidateKind
from aec_bench.contracts.proposal_compilation_verifier import (
    verify_proposal_compilation_success,
)
from aec_bench.contracts.proposal_execution.compilation import (
    ProposalCompilationRecord,
    ProposalCompilationRejection,
    ProposalCompilationSuccess,
    ProposalCompileDiagnostic,
)
from aec_bench.contracts.proposal_execution.graph import (
    FinalSynthesisSpec,
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
from aec_bench.contracts.proposal_execution_budget import CandidateBudgetPlan, NodeBudgetReservation
from aec_bench.contracts.proposal_execution_context import (
    CompiledNodeContextScope,
    ProposalSourceScopeManifest,
    ScopedSourceMaterialization,
)
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
from aec_bench.contracts.proposal_graph_verifier import (
    verify_proposed_decomposition_graph,
)
from aec_bench.contracts.proposal_session_verifier import (
    verify_proposal_session_receipt,
)
from aec_bench.contracts.stage_execution import StageResourceEvidence


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _budget() -> HarnessBudget:
    return HarnessBudget(
        max_parallelism=2,
        max_total_attempts=4,
        max_agent_turns=32,
        max_tool_calls=64,
        max_context_tokens=300_000,
        max_runtime_seconds=3_600,
        max_tokens=300_000,
        max_cost_usd=1.25,
    )


def _execution_profile() -> ProposalExecutionProfile:
    operation_capabilities = {
        "check_subtask_contract.v1": "aecbench.operation.proposal.check-subtask-contract",
        "finalize_proposed_plan.v1": "aecbench.operation.proposal.finalize-proposed-plan",
        "run_proposal_session.v1": "aecbench.operation.proposal.run-session",
        "run_semantic_subtask.v1": "aecbench.operation.proposal.run-semantic-subtask",
    }
    return ProposalExecutionProfile(
        profile_id="proposal-execution.test-v1",
        version="1.0.0",
        required_kernel_id="aec-bench.adaptive-harness",
        required_kernel_version="1.6.0",
        operation_constraints=tuple(
            ProposalOperationConstraint(
                operation_id=operation_id,
                operation_definition_sha256=_sha(f"definition.{operation_id}"),
                capability_ref=KernelCapabilityRef(
                    capability_id=capability_id,
                    version="1.0.0",
                    content_sha256=_sha(f"capability.{operation_id}"),
                ),
                required_scope=(
                    ProgramOperationScope.PUBLIC
                    if operation_id == "run_proposal_session.v1"
                    else ProgramOperationScope.PROPOSAL_SESSION_INTERNAL
                ),
                max_parallelism=1,
                supports_retry=False,
                supports_recursion=False,
            )
            for operation_id, capability_id in operation_capabilities.items()
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
        scheduling=ProposalSchedulingPolicy(
            semantics=ProposalSchedulingSemantics.SEQUENTIAL_DATAFLOW,
            max_parallelism=1,
            environment_policy=ProposalEnvironmentPolicy.ROTATED_SINGLE_ENVIRONMENT,
            deterministic_commit_order=True,
        ),
    )


def _view() -> DecompositionProblemView:
    return DecompositionProblemView(
        problem_id="problem.drainage",
        task_id="civil/review/drainage",
        task_revision=_sha("task-definition"),
        public_task_snapshot_sha256=_sha("public-task-snapshot"),
        public_instruction="Review the supplied drainage package and issue a response.",
        public_sources=(
            PublicSourceRef(
                source_id="source.report",
                opaque_handle="public-source:report",
                media_type="application/pdf",
                byte_size=1_024,
                source_sha256=_sha("report-bytes"),
            ),
        ),
        output_contract={
            "schema_version": "aecbench.output-completion-contract.v1",
            "output_path": "answer.md",
            "format": "markdown_final_fenced_json",
            "required_top_level_keys": ("decision", "evidence"),
            "require_single_final_json_block": True,
        },
        fixed_harness=FixedHarnessCapabilityProjection(
            kernel_sha256=_sha("kernel"),
            harness_policy_sha256=_sha("h0-policy"),
            capability_ids=(
                "check_subtask_contract.v1",
                "finalize_proposed_plan.v1",
                "join_evidence.v1",
                "run_semantic_subtask.v1",
            ),
            aggregate_budget=_budget(),
        ),
        public_domain_id="civil",
        public_task_family_id="drainage-review",
    )


def _manifest(view: DecompositionProblemView) -> CandidateGenerationManifest:
    return CandidateGenerationManifest(
        manifest_id="manifest.drainage",
        problem_view_sha256=view.content_sha256,
        proposal_policy_sha256=_sha("proposal-policy"),
        policy_checkpoint_sha256=_sha("policy-checkpoint"),
        selection_policy_sha256=_sha("selection-policy"),
        expected_candidate_count=1,
        coordinates=(
            CandidateGenerationCoordinate(
                coordinate_id="proposal-coordinate.1",
                candidate_id="candidate.1",
                seed=17,
            ),
        ),
        stopping_policy_sha256=_sha("stopping-policy"),
    )


def _graph() -> ProposedDecompositionGraph:
    view = _view()
    manifest = _manifest(view)
    output = ProposalOutputPort(
        output_id="findings",
        kind=ProposalPortKind.FINDING_SET,
    )
    subtask = SemanticSubtaskSpec(
        node_id="analyse",
        objective="Extract decision-relevant drainage findings from the public report.",
        source_scope=ProposalSourceScope(source_ids=("source.report",)),
        input_ports=(),
        output_ports=(output,),
        evidence_contract=NodeEvidenceContract(
            required_output_ids=("findings",),
            require_provenance=True,
            allow_explicit_data_gap=True,
        ),
    )
    assessment = SemanticSubtaskSpec(
        node_id="assess",
        objective="Turn the extracted findings into a drainage decision record.",
        source_scope=ProposalSourceScope(source_ids=()),
        input_ports=(
            ProposalInputPort(
                input_id="findings",
                kind=ProposalPortKind.FINDING_SET,
            ),
        ),
        output_ports=(
            ProposalOutputPort(
                output_id="decision",
                kind=ProposalPortKind.DECISION_RECORD,
            ),
        ),
        evidence_contract=NodeEvidenceContract(
            required_output_ids=("decision",),
            require_provenance=True,
            allow_explicit_data_gap=True,
        ),
    )
    finalizer = FinalSynthesisSpec(
        node_id="finalize",
        objective="Synthesize the final response from verified findings.",
        source_scope=ProposalSourceScope(source_ids=()),
        input_ports=(
            ProposalInputPort(
                input_id="decision",
                kind=ProposalPortKind.DECISION_RECORD,
            ),
        ),
        output_completion_contract_sha256=canonical_content_sha256(view.output_contract.model_dump(mode="json")),
    )
    return ProposedDecompositionGraph(
        candidate_id="candidate.1",
        generation_coordinate_id="proposal-coordinate.1",
        problem_view_sha256=view.content_sha256,
        proposal_policy_sha256=manifest.proposal_policy_sha256,
        policy_checkpoint_sha256=manifest.policy_checkpoint_sha256,
        proposal_grammar_sha256=_sha("pilot-grammar"),
        semantic_subtasks=(subtask, assessment),
        finalizer=finalizer,
        handoffs=(
            ProposalHandoff(
                handoff_id="handoff.findings",
                producer_node_id="analyse",
                producer_output_id="findings",
                consumer_node_id="assess",
                consumer_input_id="findings",
            ),
            ProposalHandoff(
                handoff_id="handoff.decision",
                producer_node_id="assess",
                producer_output_id="decision",
                consumer_node_id="finalize",
                consumer_input_id="decision",
            ),
        ),
    )


def _parallel_graph() -> ProposedDecompositionGraph:
    view = _view()
    manifest = _manifest(view)
    analyse = SemanticSubtaskSpec(
        node_id="analyse",
        objective="Extract drainage findings from the public report.",
        source_scope=ProposalSourceScope(source_ids=("source.report",)),
        input_ports=(),
        output_ports=(
            ProposalOutputPort(
                output_id="findings",
                kind=ProposalPortKind.FINDING_SET,
            ),
        ),
        evidence_contract=NodeEvidenceContract(
            required_output_ids=("findings",),
            require_provenance=True,
            allow_explicit_data_gap=True,
        ),
    )
    assess = SemanticSubtaskSpec(
        node_id="assess",
        objective="Independently assess the drainage decision.",
        source_scope=ProposalSourceScope(source_ids=("source.report",)),
        input_ports=(),
        output_ports=(
            ProposalOutputPort(
                output_id="decision",
                kind=ProposalPortKind.DECISION_RECORD,
            ),
        ),
        evidence_contract=NodeEvidenceContract(
            required_output_ids=("decision",),
            require_provenance=True,
            allow_explicit_data_gap=True,
        ),
    )
    finalizer = FinalSynthesisSpec(
        node_id="finalize",
        objective="Synthesize the independent drainage findings and decision.",
        source_scope=ProposalSourceScope(source_ids=()),
        input_ports=(
            ProposalInputPort(
                input_id="findings",
                kind=ProposalPortKind.FINDING_SET,
            ),
            ProposalInputPort(
                input_id="decision",
                kind=ProposalPortKind.DECISION_RECORD,
            ),
        ),
        output_completion_contract_sha256=canonical_content_sha256(view.output_contract.model_dump(mode="json")),
    )
    return ProposedDecompositionGraph(
        candidate_id="candidate.1",
        generation_coordinate_id="proposal-coordinate.1",
        problem_view_sha256=view.content_sha256,
        proposal_policy_sha256=manifest.proposal_policy_sha256,
        policy_checkpoint_sha256=manifest.policy_checkpoint_sha256,
        proposal_grammar_sha256=_sha("pilot-grammar"),
        semantic_subtasks=(analyse, assess),
        finalizer=finalizer,
        handoffs=(
            ProposalHandoff(
                handoff_id="handoff.findings",
                producer_node_id="analyse",
                producer_output_id="findings",
                consumer_node_id="finalize",
                consumer_input_id="findings",
            ),
            ProposalHandoff(
                handoff_id="handoff.decision",
                producer_node_id="assess",
                producer_output_id="decision",
                consumer_node_id="finalize",
                consumer_input_id="decision",
            ),
        ),
    )


def _freeze(
    graph: ProposedDecompositionGraph,
    *,
    candidate_artifact_sha256: str | None = None,
) -> ProposalFreeze:
    view = _view()
    manifest = _manifest(view)
    candidate = ProgramCandidateRef(
        candidate_id=graph.candidate_id,
        kind=ProgramCandidateKind.PROPOSAL,
        candidate_artifact_sha256=candidate_artifact_sha256 or graph.content_sha256,
        generation_coordinate_id=graph.generation_coordinate_id,
    )
    audit = DecompositionLeakageAudit(
        audit_id="audit.drainage",
        audited_input_sha256=_sha("audited-input"),
        audit_policy_sha256=_sha("leak-policy"),
        passed=True,
        finding_codes=(),
        problem_view_sha256=view.content_sha256,
    )
    return ProposalFreeze(
        freeze_id="freeze.drainage",
        evaluation_plan_ref=EvaluationPlanRef(
            plan_id="plan.phase9",
            evaluation_generation="generation-1",
            content_sha256=_sha("evaluation-plan"),
        ),
        evaluation_plan_candidate_manifest_sha256=manifest.content_sha256,
        structural_split_sha256=_sha("structural-split"),
        selected_structural_item_sha256=_sha("structural-item"),
        selected_review_lineage_id=_sha("review-lineage"),
        fixed_harness_sha256=_sha("compiled-h0"),
        operator_authority=operator_authority_for(
            "optimizer.phase9",
            OperatorRole.PERFORMANCE_OPTIMIZATION,
        ),
        split=OptimizationSplit.DEVELOPMENT,
        leakage_audit=audit,
        problem_view=view,
        candidate_manifest=manifest,
        proposal_policy_sha256=manifest.proposal_policy_sha256,
        policy_checkpoint_sha256=manifest.policy_checkpoint_sha256,
        realized_candidates=(candidate,),
        proposal_set_closed=True,
        late_candidates_permitted=False,
    )


def _source_manifest(
    graph: ProposedDecompositionGraph,
    freeze: ProposalFreeze,
) -> ProposalSourceScopeManifest:
    node_scopes = tuple(
        CompiledNodeContextScope(
            node_id=subtask.node_id,
            source_ids=subtask.source_scope.source_ids,
            upstream_handoff_ids=tuple(
                handoff.handoff_id for handoff in graph.handoffs if handoff.consumer_node_id == subtask.node_id
            ),
            instruction_visibility=NodeInstructionVisibility.OBJECTIVE_ONLY,
        )
        for subtask in graph.semantic_subtasks
    )
    finalizer_scope = CompiledNodeContextScope(
        node_id=graph.finalizer.node_id,
        source_ids=graph.finalizer.source_scope.source_ids,
        upstream_handoff_ids=tuple(
            handoff.handoff_id for handoff in graph.handoffs if handoff.consumer_node_id == graph.finalizer.node_id
        ),
        instruction_visibility=NodeInstructionVisibility.PUBLIC_TASK,
    )
    return ProposalSourceScopeManifest(
        proposal_graph_sha256=graph.content_sha256,
        problem_view_sha256=graph.problem_view_sha256,
        task_package_sha256=_sha("task-package"),
        sources=(
            ScopedSourceMaterialization(
                source_id="source.report",
                source_sha256=_sha("report-bytes"),
                byte_size=1_024,
                task_relative_path="sources/report.pdf",
            ),
        ),
        node_scopes=(*node_scopes, finalizer_scope),
    )


def _reservation(node_id: str, *, turns: int = 8) -> NodeBudgetReservation:
    return NodeBudgetReservation(
        node_id=node_id,
        max_attempts=1,
        max_agent_turns=turns,
        max_tool_calls=12,
        max_context_tokens=60_000,
        max_runtime_seconds=900,
        max_tokens=100_000,
        max_cost_usd=0.4,
    )


def _budget_plan(
    graph: ProposedDecompositionGraph,
    freeze: ProposalFreeze,
) -> CandidateBudgetPlan:
    return CandidateBudgetPlan(
        candidate_id=graph.candidate_id,
        proposal_graph_sha256=graph.content_sha256,
        proposal_freeze_sha256=freeze.content_sha256,
        fixed_harness_sha256=freeze.fixed_harness_sha256,
        allocation_policy_sha256=_sha("equal-budget-allocation"),
        aggregate_budget=freeze.problem_view.fixed_harness.aggregate_budget,
        execution_semantics=ProposalExecutionSemantics.SEQUENTIAL_DATAFLOW,
        session_overhead_seconds=300,
        reservations=tuple(_reservation(node_id) for node_id in graph.node_ids),
    )


def _programs(
    harness_ref: HarnessInstanceRef,
    surface_sha256: str,
) -> tuple[ExecutionProgram, CompiledExecutionProgram]:
    nodes = (
        ActionNode(
            node_id="analyse",
            operation_id="run_semantic_subtask.v1",
        ),
        ActionNode(
            node_id="check.analyse",
            depends_on=("analyse",),
            operation_id="check_subtask_contract.v1",
            arguments=(
                ProgramArgument(
                    name="subject",
                    value=OutputValue(
                        ref=ProgramOutputRef(
                            node_id="analyse",
                            output_port="result",
                        )
                    ),
                ),
            ),
        ),
        ActionNode(
            node_id="assess",
            depends_on=("check.analyse",),
            operation_id="run_semantic_subtask.v1",
        ),
        ActionNode(
            node_id="check.assess",
            depends_on=("assess",),
            operation_id="check_subtask_contract.v1",
            arguments=(
                ProgramArgument(
                    name="subject",
                    value=OutputValue(
                        ref=ProgramOutputRef(
                            node_id="assess",
                            output_port="result",
                        )
                    ),
                ),
            ),
        ),
        ActionNode(
            node_id="finalize",
            depends_on=("check.assess",),
            operation_id="finalize_proposed_plan.v1",
            arguments=(
                ProgramArgument(
                    name="findings",
                    value=OutputValue(
                        ref=ProgramOutputRef(
                            node_id="check.assess",
                            output_port="result",
                        )
                    ),
                ),
            ),
        ),
        StopNode(
            node_id="stop",
            depends_on=("finalize",),
            outcome=StopOutcome.SUCCEEDED,
            result=ProgramOutputRef(node_id="finalize", output_port="result"),
        ),
    )
    source = ExecutionProgram(
        program_id="px.proposal.candidate-1",
        version="1.0.0",
        harness_ref=harness_ref,
        nodes=nodes,
        limits=ProgramLimits(
            max_parallelism=1,
            max_recursion_depth=0,
            max_recursive_calls=0,
        ),
    )
    refs = tuple(
        ProgramOperationRef(
            operation_id=operation_id,
            content_sha256=_sha(f"operation:{operation_id}"),
        )
        for operation_id in (
            "check_subtask_contract.v1",
            "finalize_proposed_plan.v1",
            "run_semantic_subtask.v1",
        )
    )
    compiled = CompiledExecutionProgram(
        program_id=source.program_id,
        version=source.version,
        harness_ref=harness_ref,
        source_program_sha256=source.content_sha256,
        surface_sha256=surface_sha256,
        nodes=source.nodes,
        limits=source.limits,
        topological_order=(
            "analyse",
            "check.analyse",
            "assess",
            "check.assess",
            "finalize",
            "stop",
        ),
        operation_refs=refs,
    )
    return source, compiled


def _success(
    *,
    graph: ProposedDecompositionGraph | None = None,
    raw_proposal_artifact_sha256: str | None = None,
) -> ProposalCompilationSuccess:
    proposal_graph = graph or _graph()
    raw_sha256 = raw_proposal_artifact_sha256 or proposal_graph.content_sha256
    freeze = _freeze(
        proposal_graph,
        candidate_artifact_sha256=raw_sha256,
    )
    harness_ref = HarnessInstanceRef(
        instance_id="h0.phase9",
        content_sha256=freeze.fixed_harness_sha256,
    )
    surface_sha256 = _sha("program-surface")
    source, compiled = _programs(harness_ref, surface_sha256)
    return ProposalCompilationSuccess(
        compilation_id="compile.candidate-1",
        status=ProposalCompilationStatus.COMPILED,
        candidate_ref=freeze.realized_candidates[0],
        raw_proposal_artifact_sha256=raw_sha256,
        proposal_graph=proposal_graph,
        proposal_freeze=freeze,
        freeze_authority_event_sha256=_sha("freeze-authority-event"),
        kernel_sha256=freeze.problem_view.fixed_harness.kernel_sha256,
        fixed_harness_ref=harness_ref,
        surface_sha256=surface_sha256,
        lowering_policy_sha256=_sha("fixed-lowering-policy"),
        task_snapshot_sha256=_sha("full-task-snapshot"),
        execution_profile=_execution_profile(),
        source_scope_manifest=_source_manifest(proposal_graph, freeze),
        budget_plan=_budget_plan(proposal_graph, freeze),
        lowered_program=source,
        compiled_program=compiled,
    )


def _node_receipts(
    plan: ProposalSessionPlan,
) -> tuple[ProposalNodeReceipt, ProposalNodeReceipt, ProposalNodeReceipt]:
    compilation = plan.compilation
    source_scopes = {scope.node_id: scope for scope in compilation.source_scope_manifest.node_scopes}
    reservations = {reservation.node_id: reservation for reservation in compilation.budget_plan.reservations}
    contracts = {
        subtask.node_id: subtask.evidence_contract.content_sha256
        for subtask in compilation.proposal_graph.semantic_subtasks
    }
    execution = _session_execution()
    analyse = ProposalNodeReceipt(
        receipt_id="receipt.analyse",
        session_id="session.1",
        session_execution_sha256=execution.content_sha256,
        session_plan_sha256=plan.content_sha256,
        compilation_sha256=compilation.content_sha256,
        candidate_id=compilation.candidate_ref.candidate_id,
        proposal_graph_sha256=compilation.proposal_graph.content_sha256,
        problem_view_sha256=compilation.proposal_graph.problem_view_sha256,
        kernel_sha256=compilation.kernel_sha256,
        fixed_harness_sha256=compilation.fixed_harness_ref.content_sha256,
        proposal_policy_sha256=compilation.proposal_graph.proposal_policy_sha256,
        node_id="analyse",
        attempt=1,
        node_source_scope_sha256=source_scopes["analyse"].content_sha256,
        node_budget_reservation_sha256=reservations["analyse"].content_sha256,
        node_contract_sha256=contracts["analyse"],
        upstream_receipt_sha256s=(),
        status=ProposalNodeReceiptStatus.COMPLETED,
        invocation_id="invocation.analyse",
        container_transition=_container_transition("analyse"),
        node_context_sha256=_sha("analyse-node-context"),
        execution_request_sha256=_sha("analyse-execution-request"),
        runtime_execution_attestation_sha256=_sha("analyse-runtime-execution-attestation"),
        execution_result=_child_result("analyse"),
        contract_check_result=_contract_check("analyse"),
        output_artifact_sha256=_sha("analyse-output"),
        emitted_handoffs=_emitted_handoffs(compilation, "analyse"),
        failure_code=None,
        resources=StageResourceEvidence(
            wall_seconds=100,
            tokens_in=20_000,
            tokens_out=5_000,
            estimated_cost_usd=0.2,
            agent_turns=6,
            tool_calls=4,
        ),
        skip_cause=None,
        causal_receipt_sha256s=(),
    )
    assess_producer_ids = {
        handoff.producer_node_id
        for handoff in compilation.proposal_graph.handoffs
        if handoff.consumer_node_id == "assess"
    }
    assess_upstream = tuple(
        sorted(receipt.content_sha256 for receipt in (analyse,) if receipt.node_id in assess_producer_ids)
    )
    assess = ProposalNodeReceipt(
        receipt_id="receipt.assess",
        session_id="session.1",
        session_execution_sha256=execution.content_sha256,
        session_plan_sha256=plan.content_sha256,
        compilation_sha256=compilation.content_sha256,
        candidate_id=compilation.candidate_ref.candidate_id,
        proposal_graph_sha256=compilation.proposal_graph.content_sha256,
        problem_view_sha256=compilation.proposal_graph.problem_view_sha256,
        kernel_sha256=compilation.kernel_sha256,
        fixed_harness_sha256=compilation.fixed_harness_ref.content_sha256,
        proposal_policy_sha256=compilation.proposal_graph.proposal_policy_sha256,
        node_id="assess",
        attempt=1,
        node_source_scope_sha256=source_scopes["assess"].content_sha256,
        node_budget_reservation_sha256=reservations["assess"].content_sha256,
        node_contract_sha256=contracts["assess"],
        upstream_receipt_sha256s=assess_upstream,
        status=ProposalNodeReceiptStatus.COMPLETED,
        invocation_id="invocation.assess",
        container_transition=_container_transition("assess"),
        node_context_sha256=_sha("assess-node-context"),
        execution_request_sha256=_sha("assess-execution-request"),
        runtime_execution_attestation_sha256=_sha("assess-runtime-execution-attestation"),
        execution_result=_child_result("assess"),
        contract_check_result=_contract_check("assess"),
        output_artifact_sha256=_sha("assess-output"),
        emitted_handoffs=_emitted_handoffs(compilation, "assess"),
        failure_code=None,
        resources=StageResourceEvidence(
            wall_seconds=100,
            tokens_in=20_000,
            tokens_out=5_000,
            estimated_cost_usd=0.2,
            agent_turns=6,
            tool_calls=4,
        ),
        skip_cause=None,
        causal_receipt_sha256s=(),
    )
    finalizer = ProposalNodeReceipt(
        receipt_id="receipt.finalize",
        session_id="session.1",
        session_execution_sha256=execution.content_sha256,
        session_plan_sha256=plan.content_sha256,
        compilation_sha256=compilation.content_sha256,
        candidate_id=compilation.candidate_ref.candidate_id,
        proposal_graph_sha256=compilation.proposal_graph.content_sha256,
        problem_view_sha256=compilation.proposal_graph.problem_view_sha256,
        kernel_sha256=compilation.kernel_sha256,
        fixed_harness_sha256=compilation.fixed_harness_ref.content_sha256,
        proposal_policy_sha256=compilation.proposal_graph.proposal_policy_sha256,
        node_id="finalize",
        attempt=1,
        node_source_scope_sha256=source_scopes["finalize"].content_sha256,
        node_budget_reservation_sha256=reservations["finalize"].content_sha256,
        node_contract_sha256=compilation.proposal_graph.finalizer.output_completion_contract_sha256,
        upstream_receipt_sha256s=tuple(sorted((analyse.content_sha256, assess.content_sha256))),
        status=ProposalNodeReceiptStatus.COMPLETED,
        invocation_id="invocation.finalize",
        container_transition=_container_transition("finalize"),
        node_context_sha256=_sha("finalize-node-context"),
        execution_request_sha256=_sha("finalize-execution-request"),
        runtime_execution_attestation_sha256=_sha("finalize-runtime-execution-attestation"),
        execution_result=_child_result("finalize"),
        contract_check_result=_contract_check("finalize"),
        output_artifact_sha256=_sha("final-output"),
        emitted_handoffs=(),
        failure_code=None,
        resources=StageResourceEvidence(
            wall_seconds=120,
            tokens_in=30_000,
            tokens_out=8_000,
            estimated_cost_usd=0.3,
            agent_turns=7,
            tool_calls=2,
        ),
        skip_cause=None,
        causal_receipt_sha256s=(),
    )
    return analyse, assess, finalizer


def _child_result(
    node_id: str,
    *,
    digest_label: str | None = None,
) -> ProposalNodeExecutionResultRef:
    return ProposalNodeExecutionResultRef(
        node_id=node_id,
        session_relative_path=f"artifacts/nodes/{node_id}/adapter-result.json",
        artifact_sha256=_sha(digest_label or f"{node_id}-adapter-result"),
        byte_size=512,
        media_type="application/json",
    )


def _contract_check(
    node_id: str,
    *,
    status: ProposalContractCheckStatus = ProposalContractCheckStatus.PASSED,
    failure_code: ProposalCandidateFailureCode | None = None,
) -> ProposalContractCheckResultRef:
    return ProposalContractCheckResultRef(
        node_id=node_id,
        session_relative_path=(f"artifacts/nodes/{node_id}/contract-check-result.json"),
        artifact_sha256=_sha(f"{node_id}-contract-check-{status.value}-{failure_code or 'none'}"),
        byte_size=256,
        media_type="application/json",
        status=status,
        failure_code=failure_code,
    )


def _session_execution() -> ProposalSessionExecutionRef:
    freeze = _freeze(_graph())
    return ProposalSessionExecutionRef(
        session_id="session.1",
        environment_session_id="harbor-environment.session-1",
        backend="morph",
        source_task_package_sha256=_sha("task-package"),
        runtime_task_package_sha256=_sha("proposal-task-package"),
        runtime_archive_content_sha256=_sha("proposal-runtime-content"),
        runtime_archive_sha256=_sha("proposal-runtime-archive"),
        evaluation_coordinate=MatchedEvaluationCoordinate(
            coordinate_id="evaluation.contract.1",
            task_id=freeze.problem_view.task_id,
            task_revision=freeze.problem_view.task_revision,
            split=freeze.split,
            review_lineage_id=freeze.selected_review_lineage_id,
            seed=3101,
            repetition=1,
        ),
        execution_schedule_sha256=_sha("execution-schedule"),
        execution_assignment_sha256=_sha("execution-assignment"),
    )


def _container_transition(node_id: str) -> ProposalContainerTransitionRef:
    previous_identity = {
        "analyse": "container.candidate.initial",
        "assess": "container.for.analyse",
        "finalize": "container.for.assess",
    }[node_id]
    return ProposalContainerTransitionRef(
        invocation_id=f"invocation.{node_id}",
        session_relative_path=f"artifacts/transitions/{node_id}.json",
        artifact_sha256=_sha(f"{node_id}-container-transition"),
        byte_size=384,
        media_type="application/json",
        previous_container_identity=previous_identity,
        current_container_identity=f"container.for.{node_id}",
        runtime_archive_sha256=_sha("proposal-runtime-archive"),
        previous_container_stopped=True,
        workspace_wiped=True,
        candidate_logs_wiped=True,
    )


def _emitted_handoffs(
    compilation: ProposalCompilationSuccess,
    node_id: str,
) -> tuple[ProposalHandoffArtifactRef, ...]:
    return tuple(
        ProposalHandoffArtifactRef(
            handoff_id=handoff.handoff_id,
            producer_node_id=handoff.producer_node_id,
            producer_output_id=handoff.producer_output_id,
            consumer_node_id=handoff.consumer_node_id,
            consumer_input_id=handoff.consumer_input_id,
            session_relative_path=(f"artifacts/handoffs/{handoff.producer_node_id}/{handoff.producer_output_id}.json"),
            artifact_sha256=_sha(f"handoff-{handoff.producer_node_id}-{handoff.producer_output_id}"),
            byte_size=256,
            media_type="application/json",
        )
        for handoff in compilation.proposal_graph.handoffs
        if handoff.producer_node_id == node_id
    )


def test_graph_is_canonical_typed_and_has_one_finalizer_sink() -> None:
    graph = _graph()
    verification = verify_proposed_decomposition_graph(graph)

    assert graph.node_ids == ("analyse", "assess", "finalize")
    assert graph.topological_order == ("analyse", "assess", "finalize")
    assert graph.finalizer.node_id == "finalize"
    assert graph.semantic_subtasks[0].evidence_contract.required_output_ids == ("findings",)
    assert verification.topological_order == graph.topological_order
    assert verification.finalizer_reachable_node_ids == graph.node_ids


def test_graph_rejects_missing_mismatched_and_cyclic_handoffs() -> None:
    graph = _graph()
    base = graph.model_dump(mode="json", exclude={"content_sha256"})

    with pytest.raises(ValidationError, match="every input port exactly once"):
        ProposedDecompositionGraph.model_validate({**base, "handoffs": []})

    mismatched = graph.handoffs[0].model_dump(mode="json")
    mismatched["producer_output_id"] = "unknown"
    with pytest.raises(ValidationError, match="unknown producer output"):
        ProposedDecompositionGraph.model_validate({**base, "handoffs": [mismatched]})

    subtask = graph.semantic_subtasks[0].model_dump(mode="json")
    subtask["input_ports"] = [
        {
            "input_id": "loop",
            "kind": ProposalPortKind.FINDING_SET,
        }
    ]
    handoffs = [
        *(handoff.model_dump(mode="json") for handoff in graph.handoffs),
        {
            "handoff_id": "handoff.loop",
            "producer_node_id": "finalize",
            "producer_output_id": "result",
            "consumer_node_id": "analyse",
            "consumer_input_id": "loop",
        },
    ]
    with pytest.raises(ValidationError, match="finalizer cannot produce handoffs"):
        ProposedDecompositionGraph.model_validate(
            {
                **base,
                "semantic_subtasks": [
                    subtask,
                    graph.semantic_subtasks[1].model_dump(mode="json"),
                ],
                "handoffs": handoffs,
            }
        )


def test_graph_rejects_orphans_independently_of_profile_owned_size_limits() -> None:
    graph = _graph()
    base_subtask = graph.semantic_subtasks[0]
    orphan = base_subtask.model_copy(update={"node_id": "orphan"})
    with pytest.raises(ValidationError, match="reach the finalizer"):
        ProposedDecompositionGraph(
            candidate_id=graph.candidate_id,
            generation_coordinate_id=graph.generation_coordinate_id,
            problem_view_sha256=graph.problem_view_sha256,
            proposal_policy_sha256=graph.proposal_policy_sha256,
            policy_checkpoint_sha256=graph.policy_checkpoint_sha256,
            proposal_grammar_sha256=graph.proposal_grammar_sha256,
            semantic_subtasks=(
                base_subtask,
                graph.semantic_subtasks[1],
                orphan,
            ),
            finalizer=graph.finalizer,
            handoffs=graph.handoffs,
        )


@pytest.mark.parametrize("field", ["operation_id", "retry", "recursion", "branch"])
def test_semantic_subtask_rejects_compiler_owned_orchestration_fields(field: str) -> None:
    payload = _graph().semantic_subtasks[0].model_dump(mode="json")
    payload[field] = "candidate-controlled"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        SemanticSubtaskSpec.model_validate(payload)


def test_source_manifest_binds_exact_public_sources_scopes_and_safe_paths() -> None:
    success = _success()
    manifest = success.source_scope_manifest

    assert manifest.sources[0].task_relative_path == "sources/report.pdf"
    assert {scope.node_id for scope in manifest.node_scopes} == {
        "analyse",
        "assess",
        "finalize",
    }

    source = manifest.sources[0].model_dump(mode="json")
    for unsafe in (
        "/tmp/report.pdf",
        "../report.pdf",
        "task-review.json",
        "world.json",
        "hidden/case.json",
        "tests/case.json",
        "verifier/rubric.json",
        "gold/answer.md",
        "world/source.pdf",
    ):
        source["task_relative_path"] = unsafe
        with pytest.raises(ValidationError, match="contained public source path"):
            ScopedSourceMaterialization.model_validate(source)

    scope = manifest.node_scopes[0].model_dump(mode="json")
    scope["source_ids"] = ["source.secret"]
    scope.pop("content_sha256")
    with pytest.raises(ValidationError, match="source scope manifest"):
        ProposalCompilationSuccess.model_validate(
            {
                **success.model_dump(mode="json", exclude={"content_sha256"}),
                "source_scope_manifest": {
                    **manifest.model_dump(mode="json", exclude={"content_sha256"}),
                    "node_scopes": [
                        scope,
                        *(item.model_dump(mode="json") for item in manifest.node_scopes[1:]),
                    ],
                },
            }
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("max_agent_turns", 24, "agent-turn"),
        ("max_tool_calls", 40, "tool-call"),
        ("max_context_tokens", 200_000, "context"),
        ("max_runtime_seconds", 1_800, "runtime"),
        ("max_tokens", 200_000, "token"),
        ("max_cost_usd", 0.8, "cost"),
    ],
)
def test_candidate_budget_rejects_sum_over_every_aggregate_dimension(
    field: str,
    value: int | float,
    message: str,
) -> None:
    graph = _graph()
    freeze = _freeze(graph)
    reservation_payloads = []
    for node_id in graph.node_ids:
        payload = _reservation(node_id).model_dump(
            mode="json",
            exclude={"content_sha256"},
        )
        payload[field] = value
        reservation_payloads.append(payload)

    with pytest.raises(ValidationError, match=message):
        CandidateBudgetPlan(
            candidate_id=graph.candidate_id,
            proposal_graph_sha256=graph.content_sha256,
            proposal_freeze_sha256=freeze.content_sha256,
            fixed_harness_sha256=freeze.fixed_harness_sha256,
            allocation_policy_sha256=_sha("allocator"),
            aggregate_budget=_budget(),
            execution_semantics=ProposalExecutionSemantics.SEQUENTIAL_DATAFLOW,
            session_overhead_seconds=300,
            reservations=reservation_payloads,
        )


def test_compilation_success_binds_candidate_freeze_sources_budget_and_program() -> None:
    success = _success()
    assert success.execution_profile is not None
    verification = verify_proposal_compilation_success(
        success,
        profile=success.execution_profile,
    )

    assert success.candidate_ref.candidate_artifact_sha256 == success.proposal_graph.content_sha256
    assert success.compiled_program.source_program_sha256 == success.lowered_program.content_sha256
    assert success.budget_plan.reservation_node_ids == success.proposal_graph.node_ids
    assert verification.candidate_id == success.candidate_ref.candidate_id
    assert verification.node_ids == success.proposal_graph.node_ids
    assert verification.profile_sha256 == success.execution_profile.content_sha256

    payload = success.model_dump(mode="json", exclude={"content_sha256"})
    payload["surface_sha256"] = _sha("other-surface")
    with pytest.raises(ValidationError, match="surface"):
        ProposalCompilationSuccess.model_validate(payload)

    payload = success.model_dump(mode="json", exclude={"content_sha256"})
    payload["candidate_ref"]["candidate_artifact_sha256"] = _sha("other-proposal")
    payload["candidate_ref"].pop("content_sha256")
    with pytest.raises(ValidationError, match="candidate artifact"):
        ProposalCompilationSuccess.model_validate(payload)


def test_grammar_invalid_rejection_binds_raw_frozen_candidate_without_a_graph() -> None:
    raw_proposal = b'{"semantic_subtasks": ['
    raw_proposal_sha256 = hashlib.sha256(raw_proposal).hexdigest()
    graph = _graph()
    freeze = _freeze(
        graph,
        candidate_artifact_sha256=raw_proposal_sha256,
    )
    rejection = ProposalCompilationRejection(
        compilation_id="compile.rejected",
        status=ProposalCompilationStatus.REJECTED,
        candidate_ref=freeze.realized_candidates[0],
        raw_proposal_artifact_sha256=raw_proposal_sha256,
        proposal_freeze=freeze,
        freeze_authority_event_sha256=_sha("freeze-authority"),
        kernel_sha256=freeze.problem_view.fixed_harness.kernel_sha256,
        fixed_harness_ref=HarnessInstanceRef(
            instance_id="h0.phase9",
            content_sha256=freeze.fixed_harness_sha256,
        ),
        surface_sha256=_sha("surface"),
        lowering_policy_sha256=_sha("lowering"),
        task_snapshot_sha256=_sha("task-snapshot"),
        execution_profile=_execution_profile(),
        diagnostic=ProposalCompileDiagnostic(
            owner="candidate",
            code=ProposalCompileRejectionCode.GRAMMAR_INVALID,
            subject_ids=("candidate.1",),
            message="candidate proposal bytes are not parseable",
            feedback_visibility=ProposalDiagnosticVisibility.HOST_ONLY,
        ),
        trial_record_permitted=False,
        run_bundle_permitted=False,
    )
    parsed = TypeAdapter(ProposalCompilationRecord).validate_python(rejection.model_dump(mode="json"))
    assert isinstance(parsed, ProposalCompilationRejection)
    assert rejection.raw_proposal_artifact_sha256 == raw_proposal_sha256
    assert "proposal_graph" not in type(rejection).model_fields
    assert "compiled_program" not in type(rejection).model_fields
    assert "trial_record_sha256" not in type(rejection).model_fields

    payload = rejection.model_dump(mode="json", exclude={"content_sha256"})
    payload["raw_proposal_artifact_sha256"] = _sha("different raw bytes")
    with pytest.raises(ValidationError, match="raw proposal artifact"):
        ProposalCompilationRejection.model_validate(payload)

    payload = rejection.model_dump(mode="json", exclude={"content_sha256"})
    payload["diagnostic"]["feedback_visibility"] = "training_visible"
    with pytest.raises(ValidationError, match="host_only"):
        ProposalCompilationRejection.model_validate(payload)


def test_session_plan_and_receipts_bind_the_exact_planned_node_multiset() -> None:
    success = _success()
    plan = ProposalSessionPlan(
        session_plan_id="session-plan.1",
        compilation=success,
        planned_node_ids=success.proposal_graph.node_ids,
        topological_order=success.proposal_graph.topological_order,
    )
    analyse, assess, finalizer = _node_receipts(plan)
    session = ProposalSessionReceipt(
        session_id="session.1",
        execution=_session_execution(),
        plan=plan,
        planned_node_ids=plan.planned_node_ids,
        node_receipts=(finalizer, assess, analyse),
        status=ProposalSessionStatus.COMPLETED,
        final_output_artifact_sha256=_sha("final-output"),
        output_commit_attestation_sha256=_sha("output-commit"),
        trial_record_permitted=True,
        failure_code=None,
    )

    assert tuple(receipt.node_id for receipt in session.node_receipts) == (
        "analyse",
        "assess",
        "finalize",
    )
    assert "final_trial_record_sha256" not in type(session).model_fields
    assert session.node_receipts[0].execution_result == _child_result("analyse")
    verification = verify_proposal_session_receipt(session)
    assert verification.attempted_node_ids == plan.topological_order
    assert verification.completed_node_ids == plan.topological_order
    assert verification.candidate_failure_node_ids == ()
    assert verification.skipped_node_ids == ()
    assert verification.final_output_verified is True

    mismatched_payload = session.model_dump(mode="json", exclude={"content_sha256"})
    mismatched_execution = mismatched_payload["execution"]
    mismatched_execution.pop("content_sha256")
    mismatched_coordinate = mismatched_execution["evaluation_coordinate"]
    mismatched_coordinate.pop("content_sha256")
    mismatched_coordinate["task_revision"] = _sha("different-task-revision")
    with pytest.raises(ValidationError, match="evaluation coordinate"):
        ProposalSessionReceipt.model_validate(mismatched_payload)

    with pytest.raises(ValidationError, match="exact planned node receipt multiset"):
        ProposalSessionReceipt(
            session_id="session.1",
            execution=_session_execution(),
            plan=plan,
            planned_node_ids=plan.planned_node_ids,
            node_receipts=(analyse, assess),
            status=ProposalSessionStatus.CANDIDATE_FAILURE,
            final_output_artifact_sha256=None,
            output_commit_attestation_sha256=None,
            trial_record_permitted=False,
            failure_code=ProposalCandidateFailureCode.CONTRACT_CHECK_FAILED,
        )

    bad_finalizer = finalizer.model_dump(mode="json", exclude={"content_sha256"})
    bad_finalizer["upstream_receipt_sha256s"] = (assess.content_sha256,)
    with pytest.raises(ValidationError, match="upstream receipt"):
        ProposalSessionReceipt(
            session_id="session.1",
            execution=_session_execution(),
            plan=plan,
            planned_node_ids=plan.planned_node_ids,
            node_receipts=(
                analyse,
                assess,
                ProposalNodeReceipt.model_validate(bad_finalizer),
            ),
            status=ProposalSessionStatus.COMPLETED,
            final_output_artifact_sha256=_sha("final-output"),
            output_commit_attestation_sha256=_sha("output-commit"),
            trial_record_permitted=True,
            failure_code=None,
        )

    payload = session.model_dump(mode="json", exclude={"content_sha256"})
    payload["final_output_artifact_sha256"] = _sha("different output")
    with pytest.raises(ValidationError, match="final output artifact"):
        ProposalSessionReceipt.model_validate(payload)


def test_session_candidate_failure_never_fabricates_a_trial_record() -> None:
    success = _success()
    plan = ProposalSessionPlan(
        session_plan_id="session-plan.1",
        compilation=success,
        planned_node_ids=success.proposal_graph.node_ids,
        topological_order=success.proposal_graph.topological_order,
    )
    analyse, assess, finalizer = _node_receipts(plan)
    failed_finalizer = ProposalNodeReceipt.model_validate(
        {
            **finalizer.model_dump(mode="json", exclude={"content_sha256"}),
            "status": ProposalNodeReceiptStatus.CANDIDATE_FAILURE,
            "execution_result": _child_result(
                "finalize",
                digest_label="failed-finalizer-adapter-result",
            ),
            "contract_check_result": _contract_check(
                "finalize",
                status=ProposalContractCheckStatus.FAILED,
                failure_code=ProposalCandidateFailureCode.TOKEN_BUDGET_EXHAUSTED,
            ),
            "output_artifact_sha256": None,
            "emitted_handoffs": (),
            "failure_code": ProposalCandidateFailureCode.TOKEN_BUDGET_EXHAUSTED,
        }
    )
    failed = ProposalSessionReceipt(
        session_id="session.1",
        execution=_session_execution(),
        plan=plan,
        planned_node_ids=plan.planned_node_ids,
        node_receipts=(analyse, assess, failed_finalizer),
        status=ProposalSessionStatus.CANDIDATE_FAILURE,
        final_output_artifact_sha256=None,
        output_commit_attestation_sha256=None,
        trial_record_permitted=False,
        failure_code=ProposalCandidateFailureCode.TOKEN_BUDGET_EXHAUSTED,
    )
    assert failed.trial_record_permitted is False

    with pytest.raises(
        ValidationError,
        match="candidate failure cannot permit TrialRecord import",
    ):
        ProposalSessionReceipt(
            session_id="session.1",
            execution=_session_execution(),
            plan=plan,
            planned_node_ids=plan.planned_node_ids,
            node_receipts=(analyse, assess, failed_finalizer),
            status=ProposalSessionStatus.CANDIDATE_FAILURE,
            final_output_artifact_sha256=None,
            output_commit_attestation_sha256=None,
            trial_record_permitted=True,
            failure_code=ProposalCandidateFailureCode.TOKEN_BUDGET_EXHAUSTED,
        )


def test_attempted_node_receipts_bind_persisted_child_results_and_reject_tamper() -> None:
    success = _success()
    plan = ProposalSessionPlan(
        session_plan_id="session-plan.1",
        compilation=success,
        planned_node_ids=success.proposal_graph.node_ids,
        topological_order=success.proposal_graph.topological_order,
    )
    analyse, assess, finalizer = _node_receipts(plan)

    assert analyse.execution_result is not None
    assert analyse.execution_result.session_relative_path == "artifacts/nodes/analyse/adapter-result.json"
    assert analyse.execution_result.artifact_sha256 == _sha("analyse-adapter-result")

    tampered = analyse.model_dump(mode="json", exclude={"content_sha256"})
    tampered["execution_result"]["artifact_sha256"] = _sha("tampered")
    tampered["execution_result"].pop("content_sha256")
    tampered_analyse = ProposalNodeReceipt.model_validate(tampered)
    assert tampered_analyse.content_sha256 != analyse.content_sha256

    with pytest.raises(ValidationError, match="upstream receipt"):
        ProposalSessionReceipt(
            session_id="session.1",
            execution=_session_execution(),
            plan=plan,
            planned_node_ids=plan.planned_node_ids,
            node_receipts=(tampered_analyse, assess, finalizer),
            status=ProposalSessionStatus.COMPLETED,
            final_output_artifact_sha256=_sha("final-output"),
            output_commit_attestation_sha256=_sha("output-commit"),
            trial_record_permitted=True,
            failure_code=None,
        )


def test_candidate_failure_records_a_truthful_skipped_cascade() -> None:
    success = _success()
    plan = ProposalSessionPlan(
        session_plan_id="session-plan.1",
        compilation=success,
        planned_node_ids=success.proposal_graph.node_ids,
        topological_order=success.proposal_graph.topological_order,
    )
    analyse, assess, finalizer = _node_receipts(plan)
    failed_analyse = ProposalNodeReceipt.model_validate(
        {
            **analyse.model_dump(mode="json", exclude={"content_sha256"}),
            "status": ProposalNodeReceiptStatus.CANDIDATE_FAILURE,
            "execution_result": _child_result(
                "analyse",
                digest_label="failed-analyse-adapter-result",
            ),
            "contract_check_result": _contract_check(
                "analyse",
                status=ProposalContractCheckStatus.FAILED,
                failure_code=ProposalCandidateFailureCode.CONTRACT_CHECK_FAILED,
            ),
            "output_artifact_sha256": None,
            "emitted_handoffs": (),
            "failure_code": ProposalCandidateFailureCode.CONTRACT_CHECK_FAILED,
        }
    )
    skipped_assess = ProposalNodeReceipt.model_validate(
        {
            **assess.model_dump(mode="json", exclude={"content_sha256"}),
            "attempt": None,
            "upstream_receipt_sha256s": (failed_analyse.content_sha256,),
            "status": ProposalNodeReceiptStatus.SKIPPED,
            "invocation_id": None,
            "container_transition": None,
            "node_context_sha256": None,
            "execution_request_sha256": None,
            "runtime_execution_attestation_sha256": None,
            "execution_result": None,
            "contract_check_result": None,
            "output_artifact_sha256": None,
            "emitted_handoffs": (),
            "failure_code": None,
            "resources": None,
            "skip_cause": ProposalNodeSkipCause.UPSTREAM_FAILURE,
            "causal_receipt_sha256s": (failed_analyse.content_sha256,),
        }
    )
    skipped_finalizer = ProposalNodeReceipt.model_validate(
        {
            **finalizer.model_dump(mode="json", exclude={"content_sha256"}),
            "attempt": None,
            "upstream_receipt_sha256s": tuple(
                sorted(
                    (
                        failed_analyse.content_sha256,
                        skipped_assess.content_sha256,
                    )
                )
            ),
            "status": ProposalNodeReceiptStatus.SKIPPED,
            "invocation_id": None,
            "container_transition": None,
            "node_context_sha256": None,
            "execution_request_sha256": None,
            "runtime_execution_attestation_sha256": None,
            "execution_result": None,
            "contract_check_result": None,
            "output_artifact_sha256": None,
            "emitted_handoffs": (),
            "failure_code": None,
            "resources": None,
            "skip_cause": ProposalNodeSkipCause.UPSTREAM_FAILURE,
            "causal_receipt_sha256s": tuple(
                sorted(
                    (
                        failed_analyse.content_sha256,
                        skipped_assess.content_sha256,
                    )
                )
            ),
        }
    )

    session = ProposalSessionReceipt(
        session_id="session.1",
        execution=_session_execution(),
        plan=plan,
        planned_node_ids=plan.planned_node_ids,
        node_receipts=(failed_analyse, skipped_assess, skipped_finalizer),
        status=ProposalSessionStatus.CANDIDATE_FAILURE,
        final_output_artifact_sha256=None,
        output_commit_attestation_sha256=None,
        trial_record_permitted=False,
        failure_code=ProposalCandidateFailureCode.CONTRACT_CHECK_FAILED,
    )

    assert tuple(receipt.status for receipt in session.node_receipts) == (
        ProposalNodeReceiptStatus.CANDIDATE_FAILURE,
        ProposalNodeReceiptStatus.SKIPPED,
        ProposalNodeReceiptStatus.SKIPPED,
    )
    assert session.node_receipts[1].execution_result is None
    assert session.node_receipts[1].resources is None

    skipped_with_result = skipped_assess.model_dump(
        mode="json",
        exclude={"content_sha256"},
    )
    skipped_with_result["execution_result"] = _child_result("assess").model_dump(mode="json")
    with pytest.raises(ValidationError, match="skipped node"):
        ProposalNodeReceipt.model_validate(skipped_with_result)


def test_compilation_success_keeps_raw_and_canonical_proposal_identities_distinct() -> None:
    graph = _graph()
    raw_proposal = json.dumps(
        graph.model_dump(mode="json", exclude={"content_sha256"}),
        indent=2,
        ensure_ascii=False,
    ).encode("utf-8")
    raw_sha256 = hashlib.sha256(raw_proposal).hexdigest()
    assert raw_sha256 != graph.content_sha256

    success = _success(
        graph=graph,
        raw_proposal_artifact_sha256=raw_sha256,
    )

    assert success.raw_proposal_artifact_sha256 == raw_sha256
    assert success.candidate_ref.candidate_artifact_sha256 == raw_sha256
    assert success.proposal_graph.content_sha256 == graph.content_sha256

    payload = success.model_dump(mode="json", exclude={"content_sha256"})
    payload["raw_proposal_artifact_sha256"] = _sha("other-raw-proposal")
    with pytest.raises(ValidationError, match="raw proposal artifact"):
        ProposalCompilationSuccess.model_validate(payload)


def test_session_binds_one_sandbox_and_unique_fresh_invocation_evidence() -> None:
    success = _success()
    plan = ProposalSessionPlan(
        session_plan_id="session-plan.1",
        compilation=success,
        planned_node_ids=success.proposal_graph.node_ids,
        topological_order=success.proposal_graph.topological_order,
    )
    execution = _session_execution()
    analyse, assess, finalizer = _node_receipts(plan)
    session = ProposalSessionReceipt(
        session_id="session.1",
        execution=execution,
        plan=plan,
        planned_node_ids=plan.planned_node_ids,
        node_receipts=(analyse, assess, finalizer),
        status=ProposalSessionStatus.COMPLETED,
        final_output_artifact_sha256=_sha("final-output"),
        output_commit_attestation_sha256=_sha("output-commit"),
        trial_record_permitted=True,
        failure_code=None,
    )

    assert all(receipt.session_execution_sha256 == execution.content_sha256 for receipt in session.node_receipts)
    assert len({receipt.invocation_id for receipt in session.node_receipts}) == 3
    assert (
        len(
            {
                receipt.container_transition.current_container_identity
                for receipt in session.node_receipts
                if receipt.container_transition is not None
            }
        )
        == 3
    )
    assert all(receipt.execution_request_sha256 for receipt in session.node_receipts)
    assert all(receipt.runtime_execution_attestation_sha256 for receipt in session.node_receipts)
    assert tuple(reference.handoff_id for reference in session.node_receipts[0].emitted_handoffs) == (
        "handoff.findings",
    )

    wrong_execution = assess.model_dump(mode="json", exclude={"content_sha256"})
    wrong_execution["session_execution_sha256"] = _sha("other-session-execution")
    with pytest.raises(ValidationError, match="receipt lineage"):
        ProposalSessionReceipt(
            session_id="session.1",
            execution=execution,
            plan=plan,
            planned_node_ids=plan.planned_node_ids,
            node_receipts=(
                analyse,
                ProposalNodeReceipt.model_validate(wrong_execution),
                finalizer,
            ),
            status=ProposalSessionStatus.COMPLETED,
            final_output_artifact_sha256=_sha("final-output"),
            output_commit_attestation_sha256=_sha("output-commit"),
            trial_record_permitted=True,
            failure_code=None,
        )

    duplicate = assess.model_dump(mode="json", exclude={"content_sha256"})
    duplicate["invocation_id"] = analyse.invocation_id
    duplicate["container_transition"]["invocation_id"] = analyse.invocation_id
    duplicate["container_transition"].pop("content_sha256")
    with pytest.raises(ValidationError, match="invocation ids"):
        ProposalSessionReceipt(
            session_id="session.1",
            execution=execution,
            plan=plan,
            planned_node_ids=plan.planned_node_ids,
            node_receipts=(
                analyse,
                ProposalNodeReceipt.model_validate(duplicate),
                finalizer,
            ),
            status=ProposalSessionStatus.COMPLETED,
            final_output_artifact_sha256=_sha("final-output"),
            output_commit_attestation_sha256=_sha("output-commit"),
            trial_record_permitted=True,
            failure_code=None,
        )

    missing_transition = analyse.model_dump(mode="json", exclude={"content_sha256"})
    missing_transition["container_transition"] = None
    with pytest.raises(ValidationError, match="container transition"):
        ProposalNodeReceipt.model_validate(missing_transition)

    mismatched_transition = analyse.model_dump(mode="json", exclude={"content_sha256"})
    mismatched_transition["container_transition"]["invocation_id"] = "invocation.other"
    mismatched_transition["container_transition"].pop("content_sha256")
    with pytest.raises(ValidationError, match="container transition invocation"):
        ProposalNodeReceipt.model_validate(mismatched_transition)

    tampered_handoff = analyse.model_dump(mode="json", exclude={"content_sha256"})
    tampered_handoff["emitted_handoffs"][0]["consumer_node_id"] = "finalize"
    tampered_handoff["emitted_handoffs"][0].pop("content_sha256")
    tampered_analyse = ProposalNodeReceipt.model_validate(tampered_handoff)
    tampered_finalizer_payload = finalizer.model_dump(
        mode="json",
        exclude={"content_sha256"},
    )
    tampered_finalizer_payload["upstream_receipt_sha256s"] = tuple(
        sorted((tampered_analyse.content_sha256, assess.content_sha256))
    )
    tampered_finalizer = ProposalNodeReceipt.model_validate(tampered_finalizer_payload)
    with pytest.raises(ValidationError, match="emitted handoff"):
        ProposalSessionReceipt(
            session_id="session.1",
            execution=execution,
            plan=plan,
            planned_node_ids=plan.planned_node_ids,
            node_receipts=(tampered_analyse, assess, tampered_finalizer),
            status=ProposalSessionStatus.COMPLETED,
            final_output_artifact_sha256=_sha("final-output"),
            output_commit_attestation_sha256=_sha("output-commit"),
            trial_record_permitted=True,
            failure_code=None,
        )


def test_completed_and_candidate_failure_receipts_require_typed_contract_checks() -> None:
    success = _success()
    plan = ProposalSessionPlan(
        session_plan_id="session-plan.1",
        compilation=success,
        planned_node_ids=success.proposal_graph.node_ids,
        topological_order=success.proposal_graph.topological_order,
    )
    analyse, _, _ = _node_receipts(plan)
    assert analyse.contract_check_result is not None
    assert analyse.contract_check_result.status is ProposalContractCheckStatus.PASSED

    failed_check = _contract_check(
        "analyse",
        status=ProposalContractCheckStatus.FAILED,
        failure_code=ProposalCandidateFailureCode.CONTRACT_CHECK_FAILED,
    )
    completed_with_failed_check = analyse.model_dump(
        mode="json",
        exclude={"content_sha256"},
    )
    completed_with_failed_check["contract_check_result"] = failed_check.model_dump(mode="json")
    with pytest.raises(ValidationError, match="passed contract check"):
        ProposalNodeReceipt.model_validate(completed_with_failed_check)

    candidate_failure = {
        **analyse.model_dump(mode="json", exclude={"content_sha256"}),
        "status": ProposalNodeReceiptStatus.CANDIDATE_FAILURE,
        "contract_check_result": failed_check.model_dump(mode="json"),
        "output_artifact_sha256": None,
        "emitted_handoffs": (),
        "failure_code": ProposalCandidateFailureCode.CONTRACT_CHECK_FAILED,
    }
    failed = ProposalNodeReceipt.model_validate(candidate_failure)
    assert failed.failure_code is ProposalCandidateFailureCode.CONTRACT_CHECK_FAILED

    candidate_failure["failure_code"] = "provider_error"
    with pytest.raises(ValidationError):
        ProposalNodeReceipt.model_validate(candidate_failure)


def test_session_budget_abort_can_skip_a_later_independent_node() -> None:
    graph = _parallel_graph()
    success = _success(graph=graph)
    plan = ProposalSessionPlan(
        session_plan_id="session-plan.1",
        compilation=success,
        planned_node_ids=success.proposal_graph.node_ids,
        topological_order=success.proposal_graph.topological_order,
    )
    analyse, assess, finalizer = _node_receipts(plan)
    failed_check = _contract_check(
        "analyse",
        status=ProposalContractCheckStatus.FAILED,
        failure_code=ProposalCandidateFailureCode.TOKEN_BUDGET_EXHAUSTED,
    )
    failed_analyse = ProposalNodeReceipt.model_validate(
        {
            **analyse.model_dump(mode="json", exclude={"content_sha256"}),
            "status": ProposalNodeReceiptStatus.CANDIDATE_FAILURE,
            "contract_check_result": failed_check.model_dump(mode="json"),
            "output_artifact_sha256": None,
            "emitted_handoffs": (),
            "failure_code": ProposalCandidateFailureCode.TOKEN_BUDGET_EXHAUSTED,
        }
    )
    skipped_assess = ProposalNodeReceipt.model_validate(
        {
            **assess.model_dump(mode="json", exclude={"content_sha256"}),
            "attempt": None,
            "upstream_receipt_sha256s": (),
            "status": ProposalNodeReceiptStatus.SKIPPED,
            "invocation_id": None,
            "container_transition": None,
            "node_context_sha256": None,
            "execution_request_sha256": None,
            "runtime_execution_attestation_sha256": None,
            "execution_result": None,
            "contract_check_result": None,
            "output_artifact_sha256": None,
            "emitted_handoffs": (),
            "failure_code": None,
            "resources": None,
            "skip_cause": ProposalNodeSkipCause.SESSION_BUDGET_EXHAUSTED,
            "causal_receipt_sha256s": (failed_analyse.content_sha256,),
        }
    )
    skipped_finalizer = ProposalNodeReceipt.model_validate(
        {
            **finalizer.model_dump(mode="json", exclude={"content_sha256"}),
            "attempt": None,
            "upstream_receipt_sha256s": tuple(
                sorted(
                    (
                        failed_analyse.content_sha256,
                        skipped_assess.content_sha256,
                    )
                )
            ),
            "status": ProposalNodeReceiptStatus.SKIPPED,
            "invocation_id": None,
            "container_transition": None,
            "node_context_sha256": None,
            "execution_request_sha256": None,
            "runtime_execution_attestation_sha256": None,
            "execution_result": None,
            "contract_check_result": None,
            "output_artifact_sha256": None,
            "emitted_handoffs": (),
            "failure_code": None,
            "resources": None,
            "skip_cause": ProposalNodeSkipCause.UPSTREAM_FAILURE,
            "causal_receipt_sha256s": tuple(
                sorted(
                    (
                        failed_analyse.content_sha256,
                        skipped_assess.content_sha256,
                    )
                )
            ),
        }
    )

    session = ProposalSessionReceipt(
        session_id="session.1",
        execution=_session_execution(),
        plan=plan,
        planned_node_ids=plan.planned_node_ids,
        node_receipts=(failed_analyse, skipped_assess, skipped_finalizer),
        status=ProposalSessionStatus.CANDIDATE_FAILURE,
        final_output_artifact_sha256=None,
        output_commit_attestation_sha256=None,
        trial_record_permitted=False,
        failure_code=ProposalCandidateFailureCode.TOKEN_BUDGET_EXHAUSTED,
    )

    assert session.node_receipts[1].upstream_receipt_sha256s == ()
    assert session.node_receipts[1].causal_receipt_sha256s == (failed_analyse.content_sha256,)
