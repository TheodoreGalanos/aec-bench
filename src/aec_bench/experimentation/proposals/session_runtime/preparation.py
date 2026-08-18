# ABOUTME: Lowers one compiled proposal node into an exact fixed-H0 child request.
# ABOUTME: Materializes reward-blind context, prompt, output, and provider-budget contracts.

from __future__ import annotations

import stat
from pathlib import Path

from aec_bench.adapters.base import SerializedAdapterExecution
from aec_bench.contracts.harness_instance import ContextBindingConfig
from aec_bench.contracts.harness_kernel import canonical_json_sha256
from aec_bench.contracts.output_completion import OutputCompletionContract
from aec_bench.contracts.program_proposal.study import MatchedEvaluationCoordinate
from aec_bench.contracts.proposal_execution.graph import FinalSynthesisSpec, SemanticSubtaskSpec
from aec_bench.contracts.proposal_execution_budget import NodeBudgetReservation
from aec_bench.contracts.provider_broker import ProviderBrokerPolicy
from aec_bench.contracts.trajectory import MetaHarnessTrajectoryContext
from aec_bench.experimentation.proposals.node_context import (
    PersistedProposalHandoffArtifact,
    ProposalNodeContextError,
    ProposalNodeContextManifest,
    materialize_proposal_node_context,
)
from aec_bench.experimentation.proposals.program_compilation import (
    ProposalRunSessionBundle,
)
from aec_bench.harness.execution_payload import (
    AdapterRequestPayload,
    ExecutionBundle,
    execution_request_sha256,
)
from aec_bench.harness.kernel_catalogue import (
    ContextProviderRuntime,
    KernelOperationHandlerKey,
    KernelRuntimeRegistry,
    default_kernel_registry,
)

from .contracts import (
    PreparedProposalNodeInvocation,
    ProposalSessionRuntimeError,
)
from .kernel import (
    _require_proposal_operation_handler,
    _resolve_agent_runtime,
    _validate_kernel,
    _validate_tool_surface,
)
from .receipts import (
    _node,
    _reservation,
    _validate_evaluation_coordinate,
)

_SEMANTIC_OUTPUT_PATH = "/workspace/node-output.md"


def prepare_proposal_node_invocation(
    *,
    bundle: ProposalRunSessionBundle,
    source_task_root: Path,
    session_id: str,
    node_id: str,
    invocation_id: str,
    invocation_workspace: Path,
    upstream_handoff_artifacts: tuple[
        PersistedProposalHandoffArtifact,
        ...,
    ],
    evaluation_coordinate: MatchedEvaluationCoordinate,
    registry: KernelRuntimeRegistry | None = None,
) -> PreparedProposalNodeInvocation:
    """Lower one proposal node into an exact fixed-H0 child execution request."""

    resolved_registry = registry or default_kernel_registry()
    _validate_evaluation_coordinate(
        bundle=bundle,
        coordinate=evaluation_coordinate,
    )
    _validate_kernel(bundle=bundle, registry=resolved_registry)
    agent_configuration, agent_runtime, binding_ids = _resolve_agent_runtime(
        bundle=bundle,
        registry=resolved_registry,
    )
    _validate_tool_surface(
        bundle=bundle,
        registry=resolved_registry,
    )
    reservation = _reservation(bundle, node_id=node_id)
    node = _node(bundle, node_id=node_id)
    if isinstance(node, SemanticSubtaskSpec):
        _require_proposal_operation_handler(
            bundle=bundle,
            registry=resolved_registry,
            operation_id="run_semantic_subtask.v1",
            expected=KernelOperationHandlerKey.RUN_SEMANTIC_SUBTASK,
        )
    else:
        _require_proposal_operation_handler(
            bundle=bundle,
            registry=resolved_registry,
            operation_id="finalize_proposed_plan.v1",
            expected=KernelOperationHandlerKey.FINALIZE_PROPOSED_PLAN,
        )
    output_contract, node_contract_sha256 = _output_contract(
        bundle=bundle,
        source_task_root=Path(source_task_root),
        node=node,
    )
    try:
        context_manifest = materialize_proposal_node_context(
            bundle=bundle,
            node_id=node_id,
            source_task_root=Path(source_task_root),
            invocation_workspace=Path(invocation_workspace),
            upstream_handoff_artifacts=upstream_handoff_artifacts,
        )
    except ProposalNodeContextError as error:
        raise ProposalSessionRuntimeError(
            "context_materialization_failed",
            f"proposal node context could not be materialized: {error}",
        ) from error
    system_prompt = _system_prompt(
        bundle=bundle,
        registry=resolved_registry,
        source_task_root=Path(source_task_root),
        reservation=reservation,
        context_manifest=context_manifest,
    )
    lineage = MetaHarnessTrajectoryContext(
        kernel_ref=bundle.fixed_harness.kernel_ref,
        harness_ref=bundle.fixed_harness.ref,
        program_ref=bundle.compilation.lowered_program.ref,
        bundle_id=bundle.bundle_id,
        program_node_id=node_id,
        binding_ids=binding_ids,
        attempt=1,
        proposal_session_id=session_id,
        proposal_invocation_id=invocation_id,
        execution_seed=evaluation_coordinate.seed,
    )
    configuration: dict[str, object] = {
        "max_turns": reservation.max_agent_turns,
        "context_budget_tokens": reservation.max_context_tokens,
        "prompt_cache": agent_runtime.prompt_cache,
        "timeout_sec": min(
            agent_configuration.timeout_seconds,
            reservation.max_runtime_seconds,
        ),
        "output_completion_contract": output_contract.model_dump(mode="json"),
        "output_completion_commit": True,
        "proposal_node_budget_sha256": reservation.content_sha256,
        "proposal_node_context_sha256": context_manifest.content_sha256,
        "meta_harness_context": lineage.model_dump(mode="json"),
    }
    if reservation.max_tokens is not None:
        configuration["token_budget"] = reservation.max_tokens
    if reservation.max_cost_usd is not None:
        configuration["max_cost_usd"] = reservation.max_cost_usd

    execution_bundle = ExecutionBundle(
        execution=SerializedAdapterExecution(
            adapter_kind=agent_runtime.adapter_kind,
            adapter_name=agent_configuration.agent_name,
            resolved_model=agent_configuration.model,
            payload={},
        ),
        request=AdapterRequestPayload(
            instruction=_execution_instruction(
                node=node,
                output_contract=output_contract,
                upstream_handoff_artifacts=upstream_handoff_artifacts,
            ),
            system_prompt=system_prompt,
            tools=[],
            configuration=configuration,
            output_path=output_contract.output_path,
            output_format="markdown",
        ),
    )
    provider_broker_policy = ProviderBrokerPolicy(
        broker_id=f"{session_id}.{invocation_id}",
        execution_request_sha256=execution_request_sha256(
            execution_bundle,
        ),
        adapter_kind="rlm",
        model=agent_configuration.model,
        max_main_calls=reservation.max_agent_turns,
        max_auxiliary_calls=reservation.max_agent_turns,
        max_calls=reservation.max_agent_turns * 2,
        max_total_tokens=reservation.max_tokens,
        max_cost_usd=reservation.max_cost_usd,
        timeout_seconds=min(
            agent_configuration.timeout_seconds,
            reservation.max_runtime_seconds,
        ),
    )
    return PreparedProposalNodeInvocation(
        node_id=node_id,
        invocation_id=invocation_id,
        context_manifest=context_manifest,
        execution_bundle=execution_bundle,
        provider_broker_policy=provider_broker_policy,
        output_contract=output_contract,
        node_contract_sha256=node_contract_sha256,
    )


def _output_contract(
    *,
    bundle: ProposalRunSessionBundle,
    source_task_root: Path,
    node: SemanticSubtaskSpec | FinalSynthesisSpec,
) -> tuple[OutputCompletionContract, str]:
    if isinstance(node, SemanticSubtaskSpec):
        return (
            OutputCompletionContract(
                schema_version="aecbench.output-completion-contract.v1",
                output_path=_SEMANTIC_OUTPUT_PATH,
                format="markdown_final_fenced_json",
                required_top_level_keys=("outputs", "provenance"),
                require_single_final_json_block=True,
            ),
            node.evidence_contract.content_sha256,
        )
    finalizer = bundle.compilation.proposal_graph.finalizer
    if node != finalizer:
        raise ProposalSessionRuntimeError(
            "session_plan_mismatch",
            "proposal finalizer identity changed during preparation",
        )
    path = source_task_root / "environment" / "output_contract.json"
    try:
        path_stat = path.stat(follow_symlinks=False)
        if path.is_symlink() or not stat.S_ISREG(path_stat.st_mode):
            raise OSError("not a regular file")
        contract = OutputCompletionContract.model_validate_json(
            path.read_bytes(),
        )
    except (OSError, ValueError) as error:
        raise ProposalSessionRuntimeError(
            "output_contract_invalid",
            f"proposal finalizer output contract cannot be loaded safely: {error}",
        ) from error
    if canonical_json_sha256(contract.model_dump(mode="json")) != finalizer.output_completion_contract_sha256:
        raise ProposalSessionRuntimeError(
            "output_contract_invalid",
            "proposal finalizer output contract differs from the compiled graph",
        )
    return contract, finalizer.output_completion_contract_sha256


def _system_prompt(
    *,
    bundle: ProposalRunSessionBundle,
    registry: KernelRuntimeRegistry,
    source_task_root: Path,
    reservation: NodeBudgetReservation,
    context_manifest: ProposalNodeContextManifest,
) -> str | None:
    context_bindings = tuple(
        binding for binding in bundle.fixed_harness.bindings if isinstance(binding.configuration, ContextBindingConfig)
    )
    if len(context_bindings) > 1:
        raise ProposalSessionRuntimeError(
            "harness_binding_invalid",
            "proposal session supports at most one fixed-H0 context binding",
        )
    context_bytes = sum(artifact.byte_size for artifact in context_manifest.artifacts)
    if not context_bindings:
        if context_bytes > reservation.max_context_tokens:
            raise ProposalSessionRuntimeError(
                "context_reservation_exceeded",
                "proposal node materialized context exceeds its fixed reservation",
            )
        return None
    binding = context_bindings[0]
    configuration = binding.configuration
    if not isinstance(configuration, ContextBindingConfig):
        raise ProposalSessionRuntimeError(
            "harness_binding_invalid",
            "proposal context binding has the wrong configuration type",
        )
    try:
        primitive = registry.resolve(binding.capability_ref)
    except ValueError as error:
        raise ProposalSessionRuntimeError(
            "kernel_capability_mismatch",
            f"proposal context capability does not resolve against fixed K: {error}",
        ) from error
    if not isinstance(primitive.runtime, ContextProviderRuntime) or configuration.source_ids != (
        "workspace.system_prompt",
    ):
        raise ProposalSessionRuntimeError(
            "harness_context_boundary_unsupported",
            "proposal context binding must resolve the fixed workspace system prompt",
        )
    path = source_task_root / "environment" / "system_prompt.md"
    try:
        path_stat = path.stat(follow_symlinks=False)
        if path.is_symlink() or not stat.S_ISREG(path_stat.st_mode):
            raise OSError("not a regular file")
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise ProposalSessionRuntimeError(
            "context_materialization_failed",
            f"proposal system prompt cannot be loaded safely: {error}",
        ) from error
    total_bytes = context_bytes + len(content.encode("utf-8"))
    if total_bytes > configuration.max_tokens or total_bytes > reservation.max_context_tokens:
        raise ProposalSessionRuntimeError(
            "context_reservation_exceeded",
            "proposal node materialized context exceeds its fixed reservation",
        )
    return content


def _execution_instruction(
    *,
    node: SemanticSubtaskSpec | FinalSynthesisSpec,
    output_contract: OutputCompletionContract,
    upstream_handoff_artifacts: tuple[
        PersistedProposalHandoffArtifact,
        ...,
    ],
) -> str:
    if isinstance(node, SemanticSubtaskSpec):
        source_ids = ", ".join(node.source_scope.source_ids) or "(none)"
        upstream_ids = ", ".join(artifact.artifact_sha256 for artifact in upstream_handoff_artifacts) or "(none)"
        output_ids = ", ".join(
            node.evidence_contract.required_output_ids,
        )
        return (
            f"{node.objective}\n\n"
            "Use only the files in the current workspace. Write "
            f"{output_contract.output_path} as Markdown ending in exactly one "
            "fenced JSON object with exactly two top-level keys: `outputs` and "
            "`provenance`. `outputs` must contain exactly these output IDs: "
            f"{output_ids}. `provenance` must contain exactly the declared public "
            f"source IDs ({source_ids}) and upstream artifact SHA-256 IDs "
            f"({upstream_ids}), without duplicates. Then call COMMIT_OUTPUT()."
        )
    return (
        f"{node.objective}\n\n"
        "Use only the checked upstream files in the current workspace. Follow the "
        "public task instruction in instruction.md, write the declared final "
        f"artifact at {output_contract.output_path}, and call COMMIT_OUTPUT()."
    )
