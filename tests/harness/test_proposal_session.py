# ABOUTME: Tests host-owned preparation and orchestration of one isolated proposal session.
# ABOUTME: Proves fixed-H0 lowering, node-local context, shared budgets, and fail-closed evidence.

from __future__ import annotations

import asyncio
import hashlib
import json
import shlex
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from aec_bench.adapters.base import (
    AdapterCompletionReason,
    AdapterFailureKind,
    AdapterResult,
    AdapterStopReason,
)
from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.harness_instance import AgentBindingConfig
from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.contracts.output_completion import (
    OutputCommitAttestation,
    OutputCompletionContract,
    evaluate_output_completion,
)
from aec_bench.contracts.pricing import estimate_cost_usd
from aec_bench.contracts.program_proposal import MatchedEvaluationCoordinate
from aec_bench.contracts.proposal_execution import (
    ProposalCandidateFailureCode,
    ProposalCompilationRejection,
    ProposalNodeReceiptStatus,
    ProposalNodeSkipCause,
    ProposalSessionExecutionRef,
    ProposalSessionStatus,
)
from aec_bench.contracts.provider_broker import (
    ProviderBrokerCallPlane,
    ProviderBrokerCallReceipt,
    ProviderBrokerEffectUnknownCallReceipt,
    ProviderBrokerPolicy,
    ProviderBrokerReceipt,
    ProviderBrokerStatus,
)
from aec_bench.contracts.trajectory import MetaHarnessTrajectoryContext
from aec_bench.harness.execution_payload import (
    ExecutionBundle,
    build_runtime_execution_attestation,
    execution_request_sha256,
    read_execution_bundle,
    write_execution_result,
)
from aec_bench.harness.proposal_session import (
    ProposalSessionRuntimeError,
    _operation_definition_for_proposal_runtime,
    _validate_provider_broker_call_budgets,
    build_proposal_session_execution_ref,
    prepare_proposal_node_invocation,
    run_proposal_session,
)
from aec_bench.harness.proposal_session_config import (
    load_proposal_session_host_inputs,
)
from aec_bench.meta_harness.kernel_catalogue import (
    KernelRuntimeRegistry,
    default_kernel_registry,
)
from aec_bench.meta_harness.program_proposal_compilation import (
    ProposalRunSessionBundle,
    compile_governed_proposal,
)
from tests.harness.test_proposal_session_config import _host_fixture
from tests.meta_harness.test_program_proposal_compilation import (
    _compile_arguments,
    _governed_graph_fixture,
)


def test_session_execution_ref_binds_host_validated_runtime_identities(
    tmp_path: Path,
) -> None:
    config, _bundle, derived_task = _host_fixture(tmp_path)
    inputs = load_proposal_session_host_inputs(
        config.model_dump(mode="json"),
        environment_dir=derived_task / "environment",
    )

    execution = build_proposal_session_execution_ref(
        inputs=inputs,
        session_id="proposal-session.test",
        environment_session_id="harbor-trial.test",
        backend="morph",
    )

    assert execution.session_id == "proposal-session.test"
    assert execution.environment_session_id == "harbor-trial.test"
    assert execution.backend == "morph"
    assert execution.source_task_package_sha256 == config.source_task_package_sha256
    assert execution.runtime_task_package_sha256 == inputs.derived_task_manifest.content_sha256
    assert execution.runtime_archive_sha256 == config.runtime_archive_sha256
    assert execution.runtime_archive_content_sha256 == config.runtime_archive_content_sha256
    assert execution.evaluation_coordinate == config.evaluation_coordinate
    assert execution.execution_schedule_sha256 == config.execution_schedule_sha256
    assert execution.execution_assignment_sha256 == config.execution_assignment_sha256


def test_semantic_node_preparation_lowers_exact_rlm_commit_h0_and_reservation(
    tmp_path: Path,
) -> None:
    bundle, source_task_root = _compiled_rlm_commit_bundle(tmp_path)
    workspace = tmp_path / "node-context"

    prepared = prepare_proposal_node_invocation(
        bundle=bundle,
        source_task_root=source_task_root,
        session_id="proposal-session.test",
        node_id="analyse",
        invocation_id="invoke.0001.analyse",
        invocation_workspace=workspace,
        upstream_handoff_artifacts=(),
        evaluation_coordinate=_evaluation_coordinate(bundle),
    )

    reservation = next(item for item in bundle.compilation.budget_plan.reservations if item.node_id == "analyse")
    execution = prepared.execution_bundle
    configuration = execution.request.configuration
    lineage = configuration["meta_harness_context"]
    assert execution.execution.adapter_kind == "rlm"
    assert execution.execution.resolved_model == _proposal_model(bundle)
    assert execution.execution.payload == {}
    assert prepared.provider_broker_policy.model == _proposal_model(bundle)
    assert prepared.provider_broker_policy.execution_request_sha256 == execution_request_sha256(execution)
    assert prepared.provider_broker_policy.call_budget_basis == ("rlm-main-plus-auxiliary.v1")
    assert prepared.provider_broker_policy.max_main_calls == reservation.max_agent_turns
    assert prepared.provider_broker_policy.max_auxiliary_calls == reservation.max_agent_turns
    assert configuration["max_turns"] == reservation.max_agent_turns
    assert configuration["context_budget_tokens"] == reservation.max_context_tokens
    assert configuration["prompt_cache"] is False
    assert configuration["output_completion_commit"] is True
    assert configuration["proposal_node_budget_sha256"] == reservation.content_sha256
    assert configuration["proposal_node_context_sha256"] == prepared.context_manifest.content_sha256
    assert lineage["proposal_session_id"] == "proposal-session.test"
    assert lineage["proposal_invocation_id"] == "invoke.0001.analyse"
    assert lineage["program_node_id"] == "analyse"
    assert lineage["kernel_sha256"] == bundle.compilation.kernel_sha256
    assert lineage["harness_sha256"] == bundle.fixed_harness.content_sha256
    assert lineage["program_sha256"] == bundle.compilation.lowered_program.content_sha256
    assert lineage["bundle_sha256"] == bundle.content_sha256
    assert lineage["execution_seed"] == _evaluation_coordinate(bundle).seed
    assert execution.request.output_path == "/workspace/node-output.md"
    assert execution.request.output_format == "markdown"
    assert execution.request.tools == []
    assert prepared.output_contract.output_path == "/workspace/node-output.md"
    assert prepared.output_contract.required_top_level_keys == (
        "outputs",
        "provenance",
    )
    assert (
        prepared.node_contract_sha256
        == next(
            node for node in bundle.compilation.proposal_graph.semantic_subtasks if node.node_id == "analyse"
        ).evidence_contract.content_sha256
    )
    assert prepared.context_manifest.node_id == "analyse"
    assert (workspace / "sources" / "0001.bin").is_file()
    assert "COMMIT_OUTPUT" in execution.request.instruction
    assert "outputs" in execution.request.instruction
    assert str(source_task_root) not in json.dumps(
        {
            "execution": execution.execution.__dict__,
            "request": execution.request.__dict__,
        },
        sort_keys=True,
    )


@pytest.mark.parametrize(
    ("call_plane", "max_main_calls", "max_auxiliary_calls", "message"),
    (
        (ProviderBrokerCallPlane.MAIN, 1, 2, "main"),
        (ProviderBrokerCallPlane.AUXILIARY, 2, 1, "auxiliary"),
    ),
)
def test_child_broker_evidence_rejects_per_plane_budget_drift(
    call_plane: ProviderBrokerCallPlane,
    max_main_calls: int,
    max_auxiliary_calls: int,
    message: str,
) -> None:
    now = datetime.now(UTC)
    policy = ProviderBrokerPolicy(
        broker_id="broker.plane-drift",
        execution_request_sha256="a" * 64,
        adapter_kind="rlm",
        model="bedrock:anthropic.claude-sonnet-test",
        max_main_calls=max_main_calls,
        max_auxiliary_calls=max_auxiliary_calls,
        max_calls=max_main_calls + max_auxiliary_calls,
        timeout_seconds=60,
    )
    calls = tuple(
        ProviderBrokerCallReceipt(
            call_index=index,
            call_plane=call_plane,
            method="generate",
            model=policy.model,
            request_sha256=hashlib.sha256(f"request-{index}".encode()).hexdigest(),
            response_sha256=hashlib.sha256(f"response-{index}".encode()).hexdigest(),
            input_tokens=0,
            output_tokens=0,
            cache_read_tokens=0,
            cache_write_tokens=0,
            cost_usd=0.0,
            started_at=now,
            finished_at=now,
        )
        for index in range(1, 3)
    )
    receipt = ProviderBrokerReceipt(
        broker_id=policy.broker_id,
        policy_sha256=policy.content_sha256,
        status=ProviderBrokerStatus.COMPLETED,
        calls=calls,
        denied_calls=0,
        total_calls=len(calls),
        total_input_tokens=0,
        total_output_tokens=0,
        total_cache_read_tokens=0,
        total_cache_write_tokens=0,
        total_cost_usd=0.0,
        started_at=now,
        finished_at=now,
    )

    with pytest.raises(ValueError, match=message):
        _validate_provider_broker_call_budgets(
            policy=policy,
            receipt=receipt,
        )


def test_child_broker_evidence_counts_effect_unknown_call_against_plane_budget() -> None:
    now = datetime.now(UTC)
    policy = ProviderBrokerPolicy(
        broker_id="broker.unknown-plane-drift",
        execution_request_sha256="b" * 64,
        adapter_kind="rlm",
        model="bedrock:anthropic.claude-sonnet-test",
        max_main_calls=1,
        max_auxiliary_calls=0,
        max_calls=1,
        timeout_seconds=60,
    )
    unknown_call = ProviderBrokerEffectUnknownCallReceipt(
        call_index=1,
        call_plane=ProviderBrokerCallPlane.AUXILIARY,
        method="generate",
        model=policy.model,
        request_sha256="c" * 64,
        failure_code="provider_effect_outcome_unknown",
        started_at=now,
        recorded_at=now,
    )
    receipt = ProviderBrokerReceipt(
        broker_id=policy.broker_id,
        policy_sha256=policy.content_sha256,
        status=ProviderBrokerStatus.EFFECT_UNKNOWN,
        effect_unknown_calls=(unknown_call,),
        denied_calls=0,
        total_calls=1,
        total_input_tokens=0,
        total_output_tokens=0,
        total_cache_read_tokens=0,
        total_cache_write_tokens=0,
        total_cost_usd=0.0,
        started_at=now,
        finished_at=now,
        failure_reason="provider broker effect outcome is unknown",
    )

    with pytest.raises(ValueError, match="auxiliary"):
        _validate_provider_broker_call_budgets(
            policy=policy,
            receipt=receipt,
        )


def test_finalizer_preparation_uses_exact_public_task_output_contract(
    tmp_path: Path,
) -> None:
    bundle, source_task_root = _compiled_rlm_commit_bundle(tmp_path)
    graph = bundle.compilation.proposal_graph
    source_contract = OutputCompletionContract.model_validate_json(
        (source_task_root / "environment" / "output_contract.json").read_bytes(),
    )

    with pytest.raises(ProposalSessionRuntimeError, match="upstream"):
        prepare_proposal_node_invocation(
            bundle=bundle,
            source_task_root=source_task_root,
            session_id="proposal-session.test",
            node_id=graph.finalizer.node_id,
            invocation_id="invoke.0003.finalize",
            invocation_workspace=tmp_path / "missing-upstream",
            upstream_handoff_artifacts=(),
            evaluation_coordinate=_evaluation_coordinate(bundle),
        )

    assert graph.finalizer.output_completion_contract_sha256 == canonical_content_sha256(
        source_contract.model_dump(mode="json"),
    )


def test_node_preparation_rejects_non_commit_h0_before_materializing_context(
    tmp_path: Path,
) -> None:
    fixture, governed, _graph = _governed_graph_fixture(
        tmp_path / "tool-loop",
        shape="serial",
    )
    compiled = compile_governed_proposal(
        **_compile_arguments(fixture, governed),
    )
    assert isinstance(compiled, ProposalRunSessionBundle)
    workspace = tmp_path / "must-not-exist"

    with pytest.raises(
        ProposalSessionRuntimeError,
        match="rlm-output-commit",
    ):
        prepare_proposal_node_invocation(
            bundle=compiled,
            source_task_root=fixture.ledger.root.parent / "tasks" / compiled.task_snapshot.task_id,
            session_id="proposal-session.test",
            node_id="analyse",
            invocation_id="invoke.0001.analyse",
            invocation_workspace=workspace,
            upstream_handoff_artifacts=(),
            evaluation_coordinate=_evaluation_coordinate(compiled),
        )

    assert not workspace.exists()


def test_run_proposal_session_executes_every_node_in_a_fresh_container(
    tmp_path: Path,
) -> None:
    bundle, source_task_root = _compiled_rlm_commit_bundle(tmp_path / "fixture")
    execution = _execution_ref(bundle)
    registry = default_kernel_registry()
    environment = _RecordingProposalEnvironment(
        root=tmp_path / "environment",
        bundle=bundle,
        runtime_archive_sha256=execution.runtime_archive_sha256,
    )
    for operation_id in (
        "run_proposal_session.v1",
        "run_semantic_subtask.v1",
        "check_subtask_contract.v1",
        "finalize_proposed_plan.v1",
    ):
        operation = bundle.fixed_harness.program_surface.operation(operation_id)
        definition = registry.operation_definition(operation_id)
        assert operation is not None
        assert definition is not None
        assert (
            _operation_definition_for_proposal_runtime(
                bundle=bundle,
                registry=registry,
                operation_id=operation_id,
            )
            == definition
        )

    receipt = asyncio.run(
        run_proposal_session(
            bundle=bundle,
            execution=execution,
            source_task_root=source_task_root,
            session_root=tmp_path / "session",
            environment=environment,
            registry=registry,
        )
    )

    assert receipt.status is ProposalSessionStatus.COMPLETED
    assert receipt.trial_record_permitted is True
    assert receipt.failure_code is None
    assert (
        receipt.final_output_artifact_sha256
        == hashlib.sha256(
            environment.output_by_node["finalize"],
        ).hexdigest()
    )
    assert receipt.output_commit_attestation_sha256 == environment.commit_by_node["finalize"].content_sha256
    assert {node.node_id: node.status for node in receipt.node_receipts} == {
        "analyse": ProposalNodeReceiptStatus.COMPLETED,
        "assess": ProposalNodeReceiptStatus.COMPLETED,
        "finalize": ProposalNodeReceiptStatus.COMPLETED,
    }
    assert environment.reset_node_ids == list(
        bundle.session_plan.topological_order,
    )
    assert len(environment.commands) == 3
    assert all("aec_bench.harness.provider_broker_bootstrap" in command for command in environment.commands)
    assert [
        target
        for target, _content in environment.uploaded_files
        if target == "/workspace/proposal-execution-bundle.json"
    ] == ["/workspace/proposal-execution-bundle.json"] * 3
    assert [
        target for target, _content in environment.uploaded_files if target == "/workspace/provider-broker-policy.json"
    ] == ["/workspace/provider-broker-policy.json"] * 3
    assert [sorted(snapshot) for snapshot in environment.uploaded_contexts] == [
        [
            "context-manifest.json",
            "instruction.md",
            "sources/0001.bin",
        ],
        [
            "context-manifest.json",
            "instruction.md",
            "upstream/0001.bin",
        ],
        [
            "context-manifest.json",
            "instruction.md",
            "upstream/0001.bin",
        ],
    ]
    assert len(environment.downloads) == 12
    transitions = [
        node.container_transition
        for node in sorted(
            receipt.node_receipts,
            key=lambda node: bundle.session_plan.topological_order.index(
                node.node_id,
            ),
        )
    ]
    assert all(transition is not None for transition in transitions)
    assert all(
        current.previous_container_identity == previous.current_container_identity
        for previous, current in zip(
            transitions,
            transitions[1:],
            strict=False,
        )
        if previous is not None and current is not None
    )
    assert (
        tuple(
            executed.request.configuration["meta_harness_context"]["program_node_id"]
            for executed in environment.executed_bundles
        )
        == bundle.session_plan.topological_order
    )


def test_legacy_registry_without_definitions_executes_proposal_contract_operations(
    tmp_path: Path,
) -> None:
    bundle, source_task_root = _compiled_rlm_commit_bundle(tmp_path / "fixture")
    execution = _execution_ref(bundle)
    current = default_kernel_registry()
    legacy = KernelRuntimeRegistry(
        manifest=current.manifest,
        primitives=current.primitives,
        package_fingerprint=current.package_fingerprint,
        operation_definitions=(),
    )
    environment = _RecordingProposalEnvironment(
        root=tmp_path / "environment",
        bundle=bundle,
        runtime_archive_sha256=execution.runtime_archive_sha256,
    )

    assert legacy.operation_definitions == ()
    assert legacy.is_legacy_definition_free is True
    for operation_id in (
        "run_proposal_session.v1",
        "run_semantic_subtask.v1",
        "check_subtask_contract.v1",
        "finalize_proposed_plan.v1",
    ):
        assert (
            _operation_definition_for_proposal_runtime(
                bundle=bundle,
                registry=legacy,
                operation_id=operation_id,
            )
            is None
        )

    receipt = asyncio.run(
        run_proposal_session(
            bundle=bundle,
            execution=execution,
            source_task_root=source_task_root,
            session_root=tmp_path / "session",
            environment=environment,
            registry=legacy,
        )
    )

    assert receipt.status is ProposalSessionStatus.COMPLETED
    assert tuple(node.node_id for node in receipt.node_receipts) == (
        "analyse",
        "assess",
        "finalize",
    )


def test_run_proposal_session_forwards_ephemeral_child_environment_without_persisting_it(
    tmp_path: Path,
) -> None:
    bundle, source_task_root = _compiled_rlm_commit_bundle(tmp_path / "fixture")
    execution = _execution_ref(bundle)
    environment = _RecordingProposalEnvironment(
        root=tmp_path / "environment",
        bundle=bundle,
        runtime_archive_sha256=execution.runtime_archive_sha256,
    )
    child_environment = {
        "AWS_BEARER_TOKEN_BEDROCK": "ephemeral-secret",
        "AWS_REGION": "ap-southeast-2",
    }

    receipt = asyncio.run(
        run_proposal_session(
            bundle=bundle,
            execution=execution,
            source_task_root=source_task_root,
            session_root=tmp_path / "session",
            environment=environment,
            child_environment=child_environment,
        )
    )

    assert environment.execution_environments == [
        child_environment,
        child_environment,
        child_environment,
    ]
    persisted = b"".join(path.read_bytes() for path in sorted((tmp_path / "session").rglob("*")) if path.is_file())
    bundles = b"".join(content for _target, content in environment.uploaded_files)
    assert b"ephemeral-secret" not in persisted
    assert b"ephemeral-secret" not in bundles
    assert receipt.status is ProposalSessionStatus.COMPLETED


def test_candidate_failure_records_exact_downstream_skip_cascade(
    tmp_path: Path,
) -> None:
    bundle, source_task_root = _compiled_rlm_commit_bundle(tmp_path / "fixture")
    execution = _execution_ref(bundle)
    environment = _RecordingProposalEnvironment(
        root=tmp_path / "environment",
        bundle=bundle,
        runtime_archive_sha256=execution.runtime_archive_sha256,
        failed_node_ids={"analyse"},
    )

    receipt = asyncio.run(
        run_proposal_session(
            bundle=bundle,
            execution=execution,
            source_task_root=source_task_root,
            session_root=tmp_path / "session",
            environment=environment,
        )
    )

    by_node = {node.node_id: node for node in receipt.node_receipts}
    assert receipt.status is ProposalSessionStatus.CANDIDATE_FAILURE
    assert receipt.trial_record_permitted is False
    assert receipt.failure_code is ProposalCandidateFailureCode.AGENT_TURN_BUDGET_EXHAUSTED
    assert receipt.final_output_artifact_sha256 is None
    assert receipt.output_commit_attestation_sha256 is None
    assert by_node["analyse"].status is ProposalNodeReceiptStatus.CANDIDATE_FAILURE
    assert by_node["analyse"].emitted_handoffs == ()
    assert by_node["assess"].status is ProposalNodeReceiptStatus.SKIPPED
    assert by_node["assess"].skip_cause is ProposalNodeSkipCause.UPSTREAM_FAILURE
    assert by_node["assess"].causal_receipt_sha256s == (by_node["analyse"].content_sha256,)
    assert by_node["finalize"].status is ProposalNodeReceiptStatus.SKIPPED
    assert by_node["finalize"].skip_cause is ProposalNodeSkipCause.UPSTREAM_FAILURE
    assert by_node["finalize"].causal_receipt_sha256s == tuple(
        sorted(
            (
                by_node["analyse"].content_sha256,
                by_node["assess"].content_sha256,
            )
        )
    )
    assert environment.reset_node_ids == ["analyse"]
    assert len(environment.commands) == 1


def test_run_proposal_session_rejects_trajectory_lineage_drift(
    tmp_path: Path,
) -> None:
    bundle, source_task_root = _compiled_rlm_commit_bundle(tmp_path / "fixture")
    execution = _execution_ref(bundle)
    environment = _RecordingProposalEnvironment(
        root=tmp_path / "environment",
        bundle=bundle,
        runtime_archive_sha256=execution.runtime_archive_sha256,
        tampered_trajectory_node_id="analyse",
    )

    with pytest.raises(ProposalSessionRuntimeError) as exc_info:
        asyncio.run(
            run_proposal_session(
                bundle=bundle,
                execution=execution,
                source_task_root=source_task_root,
                session_root=tmp_path / "session",
                environment=environment,
            )
        )

    assert exc_info.value.code == "trajectory_identity_mismatch"
    assert environment.reset_node_ids == ["analyse"]


def _compiled_rlm_commit_bundle(
    tmp_path: Path,
) -> tuple[ProposalRunSessionBundle, Path]:
    fixture, governed, _graph = _governed_graph_fixture(
        tmp_path,
        shape="serial",
        agent_capability_id="aecbench.adapter.rlm-output-commit",
        include_tool_binding=False,
    )
    compiled = compile_governed_proposal(
        **_compile_arguments(fixture, governed),
    )
    assert not isinstance(compiled, ProposalCompilationRejection)
    return (
        compiled,
        fixture.ledger.root.parent / "tasks" / compiled.task_snapshot.task_id,
    )


def _proposal_model(bundle: ProposalRunSessionBundle) -> str:
    configurations = tuple(
        binding.configuration
        for binding in bundle.fixed_harness.bindings
        if isinstance(binding.configuration, AgentBindingConfig)
    )
    assert len(configurations) == 1
    return configurations[0].model


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _execution_ref(
    bundle: ProposalRunSessionBundle,
) -> ProposalSessionExecutionRef:
    return ProposalSessionExecutionRef(
        session_id="proposal-session.test",
        environment_session_id="harbor-trial.test",
        backend="morph",
        source_task_package_sha256=(bundle.compilation.source_scope_manifest.task_package_sha256),
        runtime_task_package_sha256=_sha("runtime-task"),
        runtime_archive_content_sha256=_sha("runtime-content"),
        runtime_archive_sha256=_sha("runtime-archive"),
        evaluation_coordinate=_evaluation_coordinate(bundle),
        execution_schedule_sha256=_sha("execution-schedule"),
        execution_assignment_sha256=_sha("execution-assignment"),
    )


def _evaluation_coordinate(
    bundle: ProposalRunSessionBundle,
) -> MatchedEvaluationCoordinate:
    freeze = bundle.compilation.proposal_freeze
    return MatchedEvaluationCoordinate(
        coordinate_id="evaluation.proposal-session.3",
        task_id=bundle.task_snapshot.task_id,
        task_revision=bundle.task_snapshot.definition_sha256,
        split=freeze.split,
        world_lineage_id=freeze.selected_world_lineage_id,
        seed=2701,
        repetition=3,
    )


@dataclass(frozen=True)
class _RecordedExecResult:
    stdout: str
    stderr: str
    return_code: int


@dataclass(frozen=True)
class _RecordedTransition:
    invocation_id: str
    previous_container_identity: str
    current_container_identity: str
    runtime_archive_sha256: str
    receipt_path: Path


class _RecordingProposalEnvironment:
    """Provider-free recording boundary that returns real typed child evidence."""

    def __init__(
        self,
        *,
        root: Path,
        bundle: ProposalRunSessionBundle,
        runtime_archive_sha256: str,
        failed_node_ids: set[str] | None = None,
        tampered_trajectory_node_id: str | None = None,
    ) -> None:
        self.root = root
        self.bundle = bundle
        self.runtime_archive_sha256 = runtime_archive_sha256
        self.failed_node_ids = failed_node_ids or set()
        self.tampered_trajectory_node_id = tampered_trajectory_node_id
        self.remote_files: dict[str, bytes] = {}
        self.reset_node_ids: list[str] = []
        self.uploaded_contexts: list[dict[str, bytes]] = []
        self.uploaded_files: list[tuple[str, bytes]] = []
        self.commands: list[str] = []
        self.downloads: list[str] = []
        self.executed_bundles: list[ExecutionBundle] = []
        self.execution_environments: list[dict[str, str] | None] = []
        self.output_by_node: dict[str, bytes] = {}
        self.commit_by_node: dict[str, OutputCommitAttestation] = {}
        self._container_identity = "container.initial"

    async def reset_candidate_container_for_invocation(
        self,
        *,
        invocation_id: str,
        expected_runtime_digest: str,
    ) -> _RecordedTransition:
        assert expected_runtime_digest == self.runtime_archive_sha256
        node_id = invocation_id.rsplit(".", maxsplit=1)[-1]
        previous_identity = self._container_identity
        current_identity = f"container.{len(self.reset_node_ids) + 1}.{node_id}"
        self.reset_node_ids.append(node_id)
        self._container_identity = current_identity
        self.remote_files.clear()
        payload = {
            "schema_version": "aecbench.proposal-candidate-transition.v1",
            "status": "completed",
            "invocation_id": invocation_id,
            "runtime_archive_sha256": expected_runtime_digest,
            "previous_container_identity": previous_identity,
            "current_container_identity": current_identity,
            "previous_container_stopped": True,
            "workspace_wiped": True,
            "candidate_logs_wiped": True,
        }
        payload["content_sha256"] = canonical_content_sha256(payload)
        receipt_path = self.root / "transitions" / f"{invocation_id}.json"
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return _RecordedTransition(
            invocation_id=invocation_id,
            previous_container_identity=previous_identity,
            current_container_identity=current_identity,
            runtime_archive_sha256=expected_runtime_digest,
            receipt_path=receipt_path,
        )

    async def upload_dir(
        self,
        source_dir: Path | str,
        target_dir: str,
    ) -> None:
        assert target_dir == "/workspace"
        source = Path(source_dir)
        snapshot = {
            path.relative_to(source).as_posix(): path.read_bytes()
            for path in sorted(source.rglob("*"))
            if path.is_file()
        }
        self.uploaded_contexts.append(snapshot)
        for relative_path, content in snapshot.items():
            self.remote_files[f"{target_dir}/{relative_path}"] = content

    async def upload_file(
        self,
        source_path: Path | str,
        target_path: str,
    ) -> None:
        content = Path(source_path).read_bytes()
        self.uploaded_files.append((target_path, content))
        self.remote_files[target_path] = content

    async def download_file(
        self,
        source_path: str,
        target_path: Path | str,
    ) -> None:
        self.downloads.append(source_path)
        try:
            content = self.remote_files[source_path]
        except KeyError as error:
            raise FileNotFoundError(source_path) from error
        target = Path(target_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    async def exec(
        self,
        command: str,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout_sec: int | None = None,
    ) -> _RecordedExecResult:
        assert cwd == "/workspace"
        assert timeout_sec is not None
        self.execution_environments.append(env)
        self.commands.append(command)
        arguments = shlex.split(command)
        assert arguments[:3] == [
            "python",
            "-m",
            "aec_bench.harness.provider_broker_bootstrap",
        ]
        bundle_path = arguments[arguments.index("--bundle") + 1]
        result_path = arguments[arguments.index("--result") + 1]
        policy_path = arguments[arguments.index("--policy") + 1]
        receipt_path = arguments[arguments.index("--receipt") + 1]
        local_bundle_path = self.root / "child" / f"{len(self.commands)}.json"
        local_bundle_path.parent.mkdir(parents=True, exist_ok=True)
        local_bundle_path.write_bytes(self.remote_files[bundle_path])
        execution_bundle = read_execution_bundle(local_bundle_path)
        policy = ProviderBrokerPolicy.model_validate_json(
            self.remote_files[policy_path],
        )
        assert policy.execution_request_sha256 == execution_request_sha256(execution_bundle)
        self.executed_bundles.append(execution_bundle)
        context = MetaHarnessTrajectoryContext.model_validate(
            execution_bundle.request.configuration["meta_harness_context"],
        )
        node_id = context.program_node_id
        if node_id in self.failed_node_ids:
            result = self._failed_result(execution_bundle)
        else:
            output = self._successful_output(
                node_id=node_id,
                execution_bundle=execution_bundle,
            )
            self.remote_files[execution_bundle.request.output_path] = output
            self.output_by_node[node_id] = output
            result = self._completed_result(
                execution_bundle=execution_bundle,
                output=output,
            )
            assert result.completion_commit is not None
            self.commit_by_node[node_id] = result.completion_commit
        now = datetime.now(UTC)
        broker_cost_usd = (
            estimate_cost_usd(
                policy.model,
                input_tokens=result.usage_input_tokens or 0,
                output_tokens=result.usage_output_tokens or 0,
                cache_read_tokens=result.usage_cache_read_tokens or 0,
                cache_write_tokens=result.usage_cache_write_tokens or 0,
            )
            or 0.0
        )
        broker_call = ProviderBrokerCallReceipt(
            call_index=1,
            call_plane=ProviderBrokerCallPlane.MAIN,
            method="generate_with_tools",
            model=policy.model,
            request_sha256=_sha(f"{node_id}.broker.request"),
            response_sha256=_sha(f"{node_id}.broker.response"),
            input_tokens=result.usage_input_tokens or 0,
            output_tokens=result.usage_output_tokens or 0,
            cache_read_tokens=result.usage_cache_read_tokens or 0,
            cache_write_tokens=result.usage_cache_write_tokens or 0,
            cost_usd=broker_cost_usd,
            started_at=now,
            finished_at=now,
        )
        broker_receipt = ProviderBrokerReceipt(
            broker_id=policy.broker_id,
            policy_sha256=policy.content_sha256,
            status=ProviderBrokerStatus.COMPLETED,
            calls=(broker_call,),
            denied_calls=0,
            total_calls=1,
            total_input_tokens=broker_call.input_tokens,
            total_output_tokens=broker_call.output_tokens,
            total_cache_read_tokens=broker_call.cache_read_tokens,
            total_cache_write_tokens=broker_call.cache_write_tokens,
            total_cost_usd=broker_cost_usd,
            started_at=now,
            finished_at=now,
        )
        result = replace(
            result,
            configuration_record={
                **result.configuration_record,
                "provider_broker": {
                    "policy_sha256": policy.content_sha256,
                    "receipt": broker_receipt.model_dump(mode="json"),
                },
            },
        )
        attestation = build_runtime_execution_attestation(
            bundle=execution_bundle,
            result=result,
        )
        local_result_path = self.root / "child" / f"{len(self.commands)}.result.json"
        write_execution_result(
            path=local_result_path,
            result=result,
            runtime_attestation=attestation,
        )
        self.remote_files[result_path] = local_result_path.read_bytes()
        self.remote_files[receipt_path] = (broker_receipt.model_dump_json() + "\n").encode("utf-8")
        self.remote_files["/workspace/trajectory.jsonl"] = self._trajectory_bytes(
            context=context,
            tampered=(node_id == self.tampered_trajectory_node_id),
        )
        return _RecordedExecResult(
            stdout=f"completed {node_id}",
            stderr="",
            return_code=0,
        )

    def _successful_output(
        self,
        *,
        node_id: str,
        execution_bundle: ExecutionBundle,
    ) -> bytes:
        contract = OutputCompletionContract.model_validate(
            execution_bundle.request.configuration["output_completion_contract"],
        )
        semantic_node = next(
            (node for node in self.bundle.compilation.proposal_graph.semantic_subtasks if node.node_id == node_id),
            None,
        )
        if semantic_node is None:
            payload = {key: f"final {key}" for key in contract.required_top_level_keys}
        else:
            manifest = json.loads(
                self.remote_files["/workspace/context-manifest.json"],
            )
            upstream = [
                artifact["artifact_sha256"]
                for artifact in manifest["artifacts"]
                if artifact["kind"] == "upstream_handoff"
            ]
            payload = {
                "outputs": {
                    port.output_id: {
                        "evidence": f"{node_id}:{port.output_id}",
                    }
                    for port in semantic_node.output_ports
                },
                "provenance": sorted(
                    (
                        *semantic_node.source_scope.source_ids,
                        *upstream,
                    )
                ),
            }
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        return (f"# {node_id} result\n\n```json\n{encoded}\n```\n").encode()

    def _completed_result(
        self,
        *,
        execution_bundle: ExecutionBundle,
        output: bytes,
    ) -> AdapterResult:
        contract = OutputCompletionContract.model_validate(
            execution_bundle.request.configuration["output_completion_contract"],
        )
        evaluation = evaluate_output_completion(
            contract,
            output.decode("utf-8"),
        )
        commit = OutputCommitAttestation(
            schema_version="aecbench.output-commit-attestation.v1",
            mechanism="agent_explicit_output_commit",
            output_path=contract.output_path,
            output_sha256=hashlib.sha256(output).hexdigest(),
            output_size_bytes=len(output),
            completion_contract_sha256=canonical_content_sha256(
                contract.model_dump(mode="json"),
            ),
            completion_evaluation=evaluation,
            initial_output_sha256=None,
            commit_turn=1,
        )
        return AdapterResult(
            adapter_name=execution_bundle.execution.adapter_name,
            resolved_model=execution_bundle.execution.resolved_model,
            configuration_record={},
            agent_output=AgentOutput(
                status=AgentOutputStatus.COMPLETED,
                output_path=execution_bundle.request.output_path,
                output_format=execution_bundle.request.output_format,
            ),
            transcript=[],
            completion_reason=(AdapterCompletionReason.OUTPUT_CONTRACT_COMMITTED),
            completion_commit=commit,
            turns_used=1,
            max_turns=int(
                execution_bundle.request.configuration["max_turns"],
            ),
            raw_output_text=output.decode("utf-8"),
            usage_input_tokens=10,
            usage_output_tokens=10,
        )

    def _failed_result(
        self,
        execution_bundle: ExecutionBundle,
    ) -> AdapterResult:
        maximum_turns = int(
            execution_bundle.request.configuration["max_turns"],
        )
        return AdapterResult(
            adapter_name=execution_bundle.execution.adapter_name,
            resolved_model=execution_bundle.execution.resolved_model,
            configuration_record={},
            agent_output=AgentOutput(
                status=AgentOutputStatus.PARTIAL,
                output_path=execution_bundle.request.output_path,
                output_format=execution_bundle.request.output_format,
                error_message="turn limit reached",
            ),
            transcript=[],
            failure_kind=AdapterFailureKind.TURN_LIMIT_REACHED,
            stop_reason=AdapterStopReason.ITERATION_CAP,
            turns_used=maximum_turns,
            max_turns=maximum_turns,
            usage_input_tokens=10,
            usage_output_tokens=10,
        )

    @staticmethod
    def _trajectory_bytes(
        *,
        context: MetaHarnessTrajectoryContext,
        tampered: bool,
    ) -> bytes:
        context_payload = context.model_dump(mode="json")
        if tampered:
            context_payload["program_node_id"] = "tampered-node"
        lines = (
            {
                "version": 1,
                "format": "aec-bench-trajectory",
            },
            {
                "step": 1,
                "role": "assistant",
                "content": "Child execution completed.",
                "meta_harness": context_payload,
            },
        )
        return ("\n".join(json.dumps(line, sort_keys=True) for line in lines) + "\n").encode("utf-8")
