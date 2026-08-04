# ABOUTME: Exercises the complete RunBundle to px runtime to Harbor import and lineage path.
# ABOUTME: Uses a real task package and Harbor-shaped job artifacts without a runtime mock mode.

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

import aec_bench.meta_harness.kernel_catalogue as kernel_catalogue
from aec_bench.contracts.authority import AuthorityAction
from aec_bench.contracts.evaluation_plane import EvaluationPlanRef
from aec_bench.contracts.execution_program import (
    ActionNode,
    ExecutionProgram,
    LiteralValue,
    ProgramArgument,
    ProgramLimits,
    RetryPolicy,
    StopNode,
    StopOutcome,
)
from aec_bench.contracts.harness_instance import HarnessBudget
from aec_bench.contracts.trial_record import Completeness, TrialRecord
from aec_bench.harness.harbor_workflow import SynchronousHarborWorkflow
from aec_bench.meta_harness.authority_ledger import AuthorityLedger
from aec_bench.meta_harness.compiler import compile_execution_program, compile_run_bundle
from aec_bench.meta_harness.kernel_catalogue import (
    KernelRuntimeRegistry,
    default_kernel_registry,
)
from aec_bench.meta_harness.program_runtime import ProgramExecutionStatus
from aec_bench.meta_harness.run_bundle_governed_attempt import (
    assess_run_bundle_governed_attempt,
    execute_run_bundle_with_governed_attempt_assessment,
    require_run_bundle_governed_attempt_ready,
)
from aec_bench.meta_harness.run_bundle_runtime import (
    MetaHarnessStudyContext,
    _operation_definition_for_dispatch,
    execute_run_bundle,
    load_harbor_invocation_receipt,
)
from tests.support.adaptive_harness import (
    build_adaptive_bundle,
    runtime_attestation_for_harbor_agent,
    write_adaptive_task,
)


class WritingHarborExecutor:
    """Writes one real Harbor result envelope at the jobs_dir declared by the generated config."""

    def __init__(
        self,
        *,
        model: str,
        input_tokens: int = 10,
        output_tokens: int = 2,
        elapsed_seconds: int = 1,
        cost_usd: float | None = 0.001,
        runtime_adapter: str | None = "tool_loop",
        verifier_completed: bool = True,
        attested_configuration_patch: dict[str, object] | None = None,
    ) -> None:
        self.model = model
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.elapsed_seconds = elapsed_seconds
        self.cost_usd = cost_usd
        self.runtime_adapter = runtime_adapter
        self.verifier_completed = verifier_completed
        self.attested_configuration_patch = attested_configuration_patch
        self.calls = 0
        self._lock = threading.Lock()

    def execute(self, *, command: list[str], cwd: Path) -> int:
        del cwd
        with self._lock:
            self.calls += 1
            call_index = self.calls
        config_path = Path(command[-1])
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert len(config["tasks"]) == 1
        agent = config["agents"][0]
        task_path = str(config["tasks"][0]["path"])
        jobs_dir = Path(config["jobs_dir"])
        trial_name = f"trial-real-{call_index}"
        trial_dir = jobs_dir / f"job-real-{call_index}" / trial_name
        (trial_dir / "artifacts" / "agent").mkdir(parents=True)
        (trial_dir / "verifier").mkdir(parents=True)
        (trial_dir / "artifacts" / "agent" / "output.md").write_text("42\n", encoding="utf-8")
        (trial_dir / "artifacts" / "agent" / "agent_result.json").write_text(
            json.dumps(
                {
                    "status": "completed",
                    "usage_model_calls": 1,
                    "input_tokens": self.input_tokens,
                    "output_tokens": self.output_tokens,
                    "usage_cache_read_tokens": 0,
                    "usage_cache_write_tokens": 0,
                }
            ),
            encoding="utf-8",
        )
        if self.verifier_completed:
            (trial_dir / "verifier" / "reward.json").write_text(
                json.dumps({"reward": 1.0}),
                encoding="utf-8",
            )
        (trial_dir / "result.json").write_text(
            json.dumps(
                {
                    "trial_name": trial_name,
                    "task_checksum": "sha256-task",
                    "config": {
                        "task": {"path": task_path},
                        "agent": agent,
                        "environment": {"type": "docker", "kwargs": {}},
                        "job_id": "harbor-job-real",
                    },
                    "agent_info": {"name": "entrypoint", "version": "1.0.0"},
                    "agent_result": {
                        "cost_usd": self.cost_usd,
                        "metadata": (
                            {}
                            if self.runtime_adapter is None
                            else {
                                "model": self.model,
                                "runtime_execution_attestation": _runtime_attestation(
                                    agent,
                                    adapter_kind=self.runtime_adapter,
                                    resolved_model=self.model,
                                    configuration_patch=self.attested_configuration_patch,
                                ),
                            }
                        ),
                    },
                    "started_at": "2026-07-22T00:00:00Z",
                    "finished_at": f"2026-07-22T00:00:{self.elapsed_seconds:02d}Z",
                }
            ),
            encoding="utf-8",
        )
        return 0


class FailingHarborExecutor:
    """Fail after dispatch begins and before any Harbor trial evidence exists."""

    def execute(self, *, command: list[str], cwd: Path) -> int:
        del command, cwd
        raise RuntimeError("Harbor process exited before writing trials")


class InterruptingAfterFirstHarborExecutor(WritingHarborExecutor):
    """Complete one Harbor invocation, then interrupt the next external dispatch."""

    def execute(self, *, command: list[str], cwd: Path) -> int:
        if self.calls:
            self.calls += 1
            raise RuntimeError("process interrupted after the first completed invocation")
        return super().execute(command=command, cwd=cwd)


def _runtime_attestation(
    agent: dict[str, object],
    *,
    adapter_kind: str,
    resolved_model: str,
    configuration_patch: dict[str, object] | None = None,
) -> dict[str, object]:
    kwargs = agent["kwargs"]
    assert isinstance(kwargs, dict)
    return runtime_attestation_for_harbor_agent(
        {
            **agent,
            "kwargs": {
                **kwargs,
                "adapter": adapter_kind,
                **(configuration_patch or {}),
            },
        },
        resolved_model=resolved_model,
    )


def test_execute_run_bundle_crosses_program_harbor_import_and_lineage_boundary(tmp_path: Path) -> None:
    task_id = "civil/calculation/adaptive"
    tasks_root = tmp_path / "tasks"
    write_adaptive_task(tasks_root, task_id=task_id)
    bundle = build_adaptive_bundle(tasks_root=tasks_root, task_id=task_id)
    workflow = SynchronousHarborWorkflow(
        project_root=tmp_path,
        repo_root=tmp_path,
        tasks_root=tasks_root,
        ledger_root=tmp_path / "ledger",
        jobs_root=tmp_path / "jobs",
    )
    executor = WritingHarborExecutor(model="claude-test-model")
    authority_ledger = AuthorityLedger(
        tmp_path / "authority",
        candidate_roots=(tmp_path / "meta-harness-artifacts",),
    )
    evaluation_plan_ref = EvaluationPlanRef(
        plan_id="evaluation-plan.stage-9",
        evaluation_generation="evaluation-generation-1",
        content_sha256="9" * 64,
    )
    registry = default_kernel_registry()
    batch_operation = bundle.harness.program_surface.operation("run_batch.v1")
    batch_definition = registry.operation_definition("run_batch.v1")
    assert batch_operation is not None
    assert batch_definition is not None
    assert (
        _operation_definition_for_dispatch(
            registry=registry,
            operation=batch_operation,
        )
        == batch_definition
    )

    execution = execute_run_bundle(
        bundle=bundle,
        registry=registry,
        workflow=workflow,
        artifacts_root=tmp_path / "meta-harness-artifacts",
        study=MetaHarnessStudyContext(
            run_id="run.stage-zero.001",
            policy_id="policy.fixed-k.stage-zero",
            harness_generator_sha256="1" * 64,
            program_generator_sha256="2" * 64,
            split="discovery",
            execution_seed=91,
            motif_ids=("motif.serial-review",),
            evaluation_plan_ref=evaluation_plan_ref,
        ),
        executor=executor,
        authority_ledger=authority_ledger,
    )

    assert execution.program.status is ProgramExecutionStatus.SUCCEEDED
    assert execution.program.total_attempts == 1
    assert executor.calls == 1
    assert len(execution.harbor_invocations) == 1
    invocation = execution.harbor_invocations[0]
    assert invocation.imported_trial_paths
    record = TrialRecord.model_validate_json(invocation.imported_trial_paths[0].read_text(encoding="utf-8"))
    provenance = record.meta_harness_provenance
    assert provenance is not None
    assert provenance.run_id == "run.stage-zero.001"
    assert provenance.kernel_sha256 == bundle.kernel_ref.content_sha256
    assert provenance.harness_sha256 == bundle.harness.content_sha256
    assert provenance.program_sha256 == bundle.program.content_sha256
    assert provenance.bundle_sha256 == bundle.content_sha256
    assert provenance.world_package_sha256 == bundle.task_snapshots[0].package_sha256
    assert provenance.repetition == 1
    assert provenance.execution_seed == 91
    assert provenance.execution_seed_semantics == "paired_repetition_label_only"
    assert provenance.motif_ids == ("motif.serial-review",)
    assert provenance.evaluation_plan_ref == evaluation_plan_ref
    assert record.cost is not None
    assert record.cost.model_calls == 1
    assert record.cost.cache_read_tokens == 0
    assert record.cost.cache_write_tokens == 0
    assert record.cost.estimated_cost_usd == 0.001
    assert record.outputs.artifacts is not None
    assert provenance.candidate_manifest in record.outputs.artifacts
    assert record.completeness is Completeness.COMPLETE
    expected_runtime_versions = {
        f"kernel:{binding.capability_ref.capability_id}": (
            f"{binding.capability_ref.version}@sha256:{binding.capability_ref.content_sha256}"
        )
        for binding in bundle.harness.bindings
    }
    assert record.environment.tool_versions == {
        **expected_runtime_versions,
        "task-package": "sha256:" + bundle.task_snapshots[0].package_sha256,
    }
    assert execution.candidate_manifest.path.exists()
    candidate_payload = json.loads(execution.candidate_manifest.path.read_text(encoding="utf-8"))
    assert candidate_payload["bundle"]["content_sha256"] == bundle.content_sha256
    assert "target_settings" not in candidate_payload
    assert evaluation_plan_ref.content_sha256 not in execution.candidate_manifest.path.read_text(encoding="utf-8")

    receipt_artifact = invocation.receipt
    assert receipt_artifact.path.parent.name == receipt_artifact.reference.sha256
    receipt = load_harbor_invocation_receipt(receipt_artifact.path)
    assert receipt == receipt_artifact.receipt
    assert receipt.bundle_id == bundle.bundle_id
    assert receipt.bundle_sha256 == bundle.content_sha256
    assert receipt.run_id == "run.stage-zero.001"
    assert receipt.program_node_id == "run"
    assert receipt.attempt == 1
    assert receipt.fanout_index is None
    assert receipt.experiment_id == invocation.experiment_id
    assert receipt.harbor_config.path.endswith("/harbor.yaml")
    assert evaluation_plan_ref.content_sha256 not in Path(receipt.harbor_config.path).read_text(encoding="utf-8")
    assert receipt.job_dir == str(invocation.job_dir.resolve())
    assert {item.relative_path for item in receipt.job_files} == {
        path.relative_to(invocation.job_dir).as_posix() for path in invocation.job_dir.rglob("*") if path.is_file()
    }
    assert tuple(item.path for item in receipt.imported_trial_records) == tuple(
        str(path.resolve()) for path in invocation.imported_trial_paths
    )
    assert invocation.governance is not None
    assert invocation.governance.authority_event.event.action is AuthorityAction.SCORED_EVIDENCE_IMPORT
    assert (
        authority_ledger.resolve_authority_event(
            event_id=invocation.governance.authority_event.event.event_id,
            content_sha256=invocation.governance.authority_event.event.content_sha256,
        )
        == invocation.governance.authority_event
    )


def test_governed_attempt_assessment_rejects_changed_run_bundle_evidence(
    tmp_path: Path,
) -> None:
    task_id = "civil/calculation/governed-attempt-evidence-change"
    tasks_root = tmp_path / "tasks"
    write_adaptive_task(tasks_root, task_id=task_id)
    bundle = build_adaptive_bundle(tasks_root=tasks_root, task_id=task_id)
    study = _study("run.governed-attempt-evidence-change.001")
    execution = execute_run_bundle(
        bundle=bundle,
        registry=default_kernel_registry(),
        workflow=_workflow(tmp_path, tasks_root),
        artifacts_root=tmp_path / "meta-harness-artifacts",
        study=study,
        executor=WritingHarborExecutor(model="claude-test-model"),
    )
    execution.candidate_manifest.path.write_text("{}\n", encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="candidate manifest differs from its evidence reference",
    ):
        assess_run_bundle_governed_attempt(
            bundle=bundle,
            study=study,
            execution=execution,
        )


def test_governed_attempt_boundary_reports_exact_run_bundle_terminal_parity(
    tmp_path: Path,
) -> None:
    task_id = "civil/calculation/governed-attempt-boundary"
    tasks_root = tmp_path / "tasks"
    write_adaptive_task(tasks_root, task_id=task_id)
    bundle = build_adaptive_bundle(tasks_root=tasks_root, task_id=task_id)
    executor = WritingHarborExecutor(model="claude-test-model")
    study = _study("run.governed-attempt-boundary.001")

    boundary = execute_run_bundle_with_governed_attempt_assessment(
        bundle=bundle,
        registry=default_kernel_registry(),
        workflow=_workflow(tmp_path, tasks_root),
        artifacts_root=tmp_path / "meta-harness-artifacts",
        study=study,
        executor=executor,
    )

    assert boundary.execution.program.status is ProgramExecutionStatus.SUCCEEDED
    assert executor.calls == 1
    assert boundary.assessment.ready is True
    assert boundary.assessment.bundle_sha256 == bundle.content_sha256
    assert boundary.assessment.run_id == study.run_id
    assert boundary.assessment.blockers == ()
    assert boundary.assessment.invocation_receipt_sha256s == (
        boundary.execution.harbor_invocations[0].receipt.reference.sha256,
    )
    assert len(boundary.assessment.governed_terminal_sha256s) == 1
    assert boundary.assessment.candidate_manifest_sha256 == (boundary.execution.candidate_manifest.reference.sha256)
    assert (
        tmp_path
        / "meta-harness-artifacts"
        / bundle.content_sha256
        / "runs"
        / study.run_id
        / "invocations"
        / "run-a1"
        / "governed-attempt-state"
    ).is_dir()

    require_run_bundle_governed_attempt_ready(boundary.assessment)

    assert executor.calls == 1


def test_scored_import_governance_failure_preserves_receipt_but_grants_no_authority(
    tmp_path: Path,
) -> None:
    task_id = "civil/calculation/governance-failure"
    tasks_root = tmp_path / "tasks"
    write_adaptive_task(tasks_root, task_id=task_id)
    bundle = build_adaptive_bundle(tasks_root=tasks_root, task_id=task_id)
    artifacts_root = tmp_path / "meta-harness-artifacts"
    authority_ledger = AuthorityLedger(
        tmp_path / "authority",
        candidate_roots=(artifacts_root,),
    )
    redirected = tmp_path / "redirected-authority"
    redirected.mkdir()
    (authority_ledger.root / "basis-objects").symlink_to(
        redirected,
        target_is_directory=True,
    )

    execution = execute_run_bundle(
        bundle=bundle,
        registry=default_kernel_registry(),
        workflow=_workflow(tmp_path, tasks_root),
        artifacts_root=artifacts_root,
        study=_study("run.governance-failure.001"),
        executor=WritingHarborExecutor(model="claude-test-model"),
        authority_ledger=authority_ledger,
    )

    assert execution.program.status is ProgramExecutionStatus.FAILED
    assert execution.program.error_code == "scored_import_authority_failed"
    assert len(execution.harbor_invocations) == 1
    invocation = execution.harbor_invocations[0]
    assert invocation.receipt.path.exists()
    assert invocation.imported_trial_paths[0].exists()
    assert invocation.governance is None
    assert not tuple(redirected.iterdir())


def test_completed_invocation_receipt_survives_a_later_process_interruption(tmp_path: Path) -> None:
    task_ids = ("civil/calculation/receipt-alpha", "civil/calculation/receipt-beta")
    tasks_root = tmp_path / "tasks"
    for task_id in task_ids:
        write_adaptive_task(tasks_root, task_id=task_id)
    registry = default_kernel_registry()
    base = build_adaptive_bundle(tasks_root=tasks_root, task_ids=task_ids)
    source = ExecutionProgram(
        program_id="px-receipt-interruption",
        version="1.0.0",
        harness_ref=base.harness.ref,
        nodes=(
            ActionNode(
                node_id="run-alpha",
                operation_id="run_batch.v1",
                arguments=(ProgramArgument(name="task_ref", value=LiteralValue(value=task_ids[0])),),
            ),
            ActionNode(
                node_id="run-beta",
                depends_on=("run-alpha",),
                operation_id="run_batch.v1",
                arguments=(ProgramArgument(name="task_ref", value=LiteralValue(value=task_ids[1])),),
            ),
            StopNode(node_id="stop", depends_on=("run-beta",), outcome=StopOutcome.SUCCEEDED),
        ),
        limits=ProgramLimits(max_parallelism=1),
    )
    program = compile_execution_program(source, harness=base.harness, registry=registry)
    bundle = compile_run_bundle(
        bundle_id="bundle-receipt-interruption",
        harness=base.harness,
        program=program,
        registry=registry,
        tasks_root=tasks_root,
        experiment_id="receipt-interruption",
    )
    executor = InterruptingAfterFirstHarborExecutor(model="claude-test-model")

    execution = execute_run_bundle(
        bundle=bundle,
        registry=registry,
        workflow=_workflow(tmp_path, tasks_root),
        artifacts_root=tmp_path / "meta-harness-artifacts",
        study=_study("run.receipt-interruption.001"),
        executor=executor,
    )

    assert execution.program.status is ProgramExecutionStatus.FAILED
    assert executor.calls == 2
    assert len(execution.harbor_invocations) == 1
    receipt_path = execution.harbor_invocations[0].receipt.path
    imported_paths = execution.harbor_invocations[0].imported_trial_paths
    del execution

    receipt = load_harbor_invocation_receipt(receipt_path)
    assert receipt.program_node_id == "run-alpha"
    assert tuple(item.path for item in receipt.imported_trial_records) == tuple(
        str(path.resolve()) for path in imported_paths
    )
    assert all(len(item.sha256) == 64 for item in receipt.job_files)

    first_job_file = Path(receipt.job_dir) / receipt.job_files[0].relative_path
    first_job_file.write_bytes(first_job_file.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="Harbor job file inventory or hashes changed"):
        load_harbor_invocation_receipt(receipt_path)


def test_execute_run_bundle_rejects_kernel_source_drift_before_harbor_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task_id = "civil/calculation/source-drift"
    tasks_root = tmp_path / "tasks"
    write_adaptive_task(tasks_root, task_id=task_id)
    bundle = build_adaptive_bundle(tasks_root=tasks_root, task_id=task_id)
    registry = default_kernel_registry()
    pinned_sources = registry.manifest.implementation.sources
    executor = WritingHarborExecutor(model="claude-test-model")
    monkeypatch.setattr(
        kernel_catalogue,
        "_kernel_source_inventory",
        lambda: pinned_sources[:-1],
    )

    with pytest.raises(
        kernel_catalogue.KernelRuntimeRegistryError,
        match="implementation source inventory drifted",
    ):
        execute_run_bundle(
            bundle=bundle,
            registry=registry,
            workflow=_workflow(tmp_path, tasks_root),
            artifacts_root=tmp_path / "meta-harness-artifacts",
            study=_study("run.source-drift.001"),
            executor=executor,
        )

    assert executor.calls == 0


@pytest.mark.parametrize("operation_id", ["run_batch.v1", "enumerate_tasks.v1"])
def test_execute_run_bundle_rejects_tampered_retry_taxonomy_before_harbor_dispatch(
    tmp_path: Path,
    operation_id: str,
) -> None:
    task_id = "civil/calculation/retry-taxonomy-tamper"
    tasks_root = tmp_path / "tasks"
    write_adaptive_task(tasks_root, task_id=task_id)
    bundle = build_adaptive_bundle(tasks_root=tasks_root, task_id=task_id)
    operation = bundle.harness.program_surface.operation(operation_id)
    assert operation is not None
    tampered_operation = operation.model_copy(
        update={
            "supports_retry": True,
            "retry_safe_error_codes": ("harbor_workflow_failed",),
        }
    )
    tampered_surface = bundle.harness.program_surface.model_copy(
        update={
            "operations": tuple(
                tampered_operation if candidate.operation_id == operation.operation_id else candidate
                for candidate in bundle.harness.program_surface.operations
            )
        }
    )
    tampered_harness = bundle.harness.model_copy(update={"program_surface": tampered_surface})
    tampered_program = (
        bundle.program.model_copy(
            update={
                "nodes": tuple(
                    node.model_copy(
                        update={
                            "retry": RetryPolicy(
                                max_attempts=2,
                                retry_on=("harbor_workflow_failed",),
                            )
                        }
                    )
                    if isinstance(node, ActionNode) and node.node_id == "run"
                    else node
                    for node in bundle.program.nodes
                )
            }
        )
        if operation_id == "run_batch.v1"
        else bundle.program
    )
    tampered_bundle = bundle.model_copy(
        update={
            "harness": tampered_harness,
            "program": tampered_program,
        }
    )
    executor = WritingHarborExecutor(model="claude-test-model")

    with pytest.raises(ValueError, match="retry taxonomy differs from the installed fixed-K primitive"):
        execute_run_bundle(
            bundle=tampered_bundle,
            registry=default_kernel_registry(),
            workflow=_workflow(tmp_path, tasks_root),
            artifacts_root=tmp_path / "meta-harness-artifacts",
            study=_study("run.retry-taxonomy-tamper.001"),
            executor=executor,
        )

    assert executor.calls == 0


def test_decomposed_px_enumerates_tasks_then_fans_out_real_harbor_runs(tmp_path: Path) -> None:
    task_ids = ("civil/calculation/alpha", "civil/calculation/beta")
    tasks_root = tmp_path / "tasks"
    for task_id in task_ids:
        write_adaptive_task(tasks_root, task_id=task_id)
    bundle = build_adaptive_bundle(
        tasks_root=tasks_root,
        task_ids=task_ids,
        program_kind="fanout",
    )
    workflow = SynchronousHarborWorkflow(
        project_root=tmp_path,
        repo_root=tmp_path,
        tasks_root=tasks_root,
        ledger_root=tmp_path / "ledger",
        jobs_root=tmp_path / "jobs",
    )
    executor = WritingHarborExecutor(model="claude-test-model")

    registry = default_kernel_registry()
    enumeration = bundle.harness.program_surface.operation("enumerate_tasks.v1")
    assert enumeration is not None
    definition = registry.operation_definition("enumerate_tasks.v1")
    assert definition is not None
    assert (
        _operation_definition_for_dispatch(
            registry=registry,
            operation=enumeration,
        )
        == definition
    )

    execution = execute_run_bundle(
        bundle=bundle,
        registry=registry,
        workflow=workflow,
        artifacts_root=tmp_path / "meta-harness-artifacts",
        study=MetaHarnessStudyContext(
            run_id="run.fanout.001",
            policy_id="policy.fixed-k.fanout",
            harness_generator_sha256="1" * 64,
            program_generator_sha256="2" * 64,
            split="discovery",
        ),
        executor=executor,
    )

    assert execution.program.status is ProgramExecutionStatus.SUCCEEDED
    assert executor.calls == 2
    assert [invocation.fanout_index for invocation in execution.harbor_invocations] == [0, 1]
    records = [
        TrialRecord.model_validate_json(path.read_text(encoding="utf-8"))
        for invocation in execution.harbor_invocations
        for path in invocation.imported_trial_paths
    ]
    assert {record.task.task_id for record in records} == set(task_ids)
    assert all(record.meta_harness_provenance is not None for record in records)


def test_legacy_registry_without_definitions_still_dispatches_v1_task_enumeration(
    tmp_path: Path,
) -> None:
    task_id = "civil/calculation/legacy-enumeration"
    tasks_root = tmp_path / "tasks"
    write_adaptive_task(tasks_root, task_id=task_id)
    current = default_kernel_registry()
    current_bundle = build_adaptive_bundle(
        tasks_root=tasks_root,
        task_id=task_id,
        program_kind="fanout",
        registry=current,
    )
    legacy = KernelRuntimeRegistry(
        manifest=current.manifest,
        primitives=current.primitives,
        package_fingerprint=current.package_fingerprint,
        operation_definitions=(),
    )
    assert legacy.operation_definition("enumerate_tasks.v1") is None
    assert legacy.operation_definition("run_batch.v1") is None
    bundle = build_adaptive_bundle(
        tasks_root=tasks_root,
        task_id=task_id,
        program_kind="fanout",
        registry=legacy,
    )
    operation = bundle.harness.program_surface.operation("enumerate_tasks.v1")
    batch_operation = bundle.harness.program_surface.operation("run_batch.v1")
    current_operation = current_bundle.harness.program_surface.operation("enumerate_tasks.v1")
    current_batch_operation = current_bundle.harness.program_surface.operation("run_batch.v1")
    assert operation is not None
    assert batch_operation is not None
    assert current_operation is not None
    assert current_batch_operation is not None
    assert operation == current_operation
    assert batch_operation == current_batch_operation
    executor = WritingHarborExecutor(model="claude-test-model")

    execution = execute_run_bundle(
        bundle=bundle,
        registry=legacy,
        workflow=_workflow(tmp_path, tasks_root),
        artifacts_root=tmp_path / "meta-harness-artifacts",
        study=_study("run.legacy-enumeration.001"),
        executor=executor,
    )

    assert execution.program.status is ProgramExecutionStatus.SUCCEEDED
    assert executor.calls == 1


def test_run_bundle_runtime_rejects_missing_runtime_execution_attestation(tmp_path: Path) -> None:
    task_id = "civil/calculation/missing-attestation"
    tasks_root = tmp_path / "tasks"
    write_adaptive_task(tasks_root, task_id=task_id)
    bundle = build_adaptive_bundle(tasks_root=tasks_root, task_id=task_id)

    execution = execute_run_bundle(
        bundle=bundle,
        registry=default_kernel_registry(),
        workflow=_workflow(tmp_path, tasks_root),
        artifacts_root=tmp_path / "meta-harness-artifacts",
        study=_study("run.missing-attestation.001"),
        executor=WritingHarborExecutor(
            model="claude-test-model",
            runtime_adapter=None,
        ),
    )

    assert execution.program.status is ProgramExecutionStatus.FAILED
    assert execution.program.error_code == "runtime_execution_attestation_missing"


def test_run_bundle_runtime_rejects_attested_adapter_different_from_hx(tmp_path: Path) -> None:
    task_id = "civil/calculation/wrong-adapter-attestation"
    tasks_root = tmp_path / "tasks"
    write_adaptive_task(tasks_root, task_id=task_id)
    bundle = build_adaptive_bundle(tasks_root=tasks_root, task_id=task_id)

    execution = execute_run_bundle(
        bundle=bundle,
        registry=default_kernel_registry(),
        workflow=_workflow(tmp_path, tasks_root),
        artifacts_root=tmp_path / "meta-harness-artifacts",
        study=_study("run.wrong-adapter-attestation.001"),
        executor=WritingHarborExecutor(
            model="claude-test-model",
            runtime_adapter="direct",
        ),
    )

    assert execution.program.status is ProgramExecutionStatus.FAILED
    assert execution.program.error_code == "runtime_execution_attestation_mismatch"


def test_run_bundle_runtime_rejects_different_attested_output_contract_request(tmp_path: Path) -> None:
    task_id = "civil/calculation/wrong-request-attestation"
    tasks_root = tmp_path / "tasks"
    output_contract = {
        "schema_version": "aecbench.output-completion-contract.v1",
        "output_path": "/workspace/output.md",
        "format": "markdown_final_fenced_json",
        "required_top_level_keys": ["answer"],
        "require_single_final_json_block": True,
    }
    write_adaptive_task(
        tasks_root,
        task_id=task_id,
        output_completion_contract=output_contract,
    )
    bundle = build_adaptive_bundle(
        tasks_root=tasks_root,
        task_id=task_id,
        agent_capability_id="aecbench.adapter.rlm-output-contract",
        include_tool_binding=False,
    )
    altered_contract = {
        **output_contract,
        "required_top_level_keys": ["answer", "confidence"],
    }

    execution = execute_run_bundle(
        bundle=bundle,
        registry=default_kernel_registry(),
        workflow=_workflow(tmp_path, tasks_root),
        artifacts_root=tmp_path / "meta-harness-artifacts",
        study=_study("run.wrong-request-attestation.001"),
        executor=WritingHarborExecutor(
            model="claude-test-model",
            runtime_adapter="rlm",
            attested_configuration_patch={"output_completion_contract": altered_contract},
        ),
    )

    assert execution.program.status is ProgramExecutionStatus.FAILED
    assert execution.program.error_code == "runtime_execution_attestation_mismatch"
    assert execution.program.error_message is not None
    assert "execution_request_sha256" in execution.program.error_message


def test_run_bundle_runtime_enforces_required_verifier_completion(tmp_path: Path) -> None:
    task_id = "civil/calculation/required-verifier"
    tasks_root = tmp_path / "tasks"
    write_adaptive_task(tasks_root, task_id=task_id)
    bundle = build_adaptive_bundle(tasks_root=tasks_root, task_id=task_id)

    execution = execute_run_bundle(
        bundle=bundle,
        registry=default_kernel_registry(),
        workflow=_workflow(tmp_path, tasks_root),
        artifacts_root=tmp_path / "meta-harness-artifacts",
        study=_study("run.required-verifier.001"),
        executor=WritingHarborExecutor(
            model="claude-test-model",
            verifier_completed=False,
        ),
    )

    assert execution.program.status is ProgramExecutionStatus.FAILED
    assert execution.program.error_code == "required_verifier_not_completed"


def test_run_bundle_runtime_requires_every_planned_task_repetition(tmp_path: Path) -> None:
    task_id = "civil/calculation/missing-repetition"
    tasks_root = tmp_path / "tasks"
    write_adaptive_task(tasks_root, task_id=task_id)
    bundle = build_adaptive_bundle(
        tasks_root=tasks_root,
        task_id=task_id,
        repetitions=2,
    )

    execution = execute_run_bundle(
        bundle=bundle,
        registry=default_kernel_registry(),
        workflow=_workflow(tmp_path, tasks_root),
        artifacts_root=tmp_path / "meta-harness-artifacts",
        study=_study("run.missing-repetition.001"),
        executor=WritingHarborExecutor(model="claude-test-model"),
    )

    assert execution.program.status is ProgramExecutionStatus.FAILED
    assert execution.program.error_code == "incomplete_harbor_trial_plan"


def test_run_bundle_runtime_marks_failed_dispatch_usage_evidence_incomplete(tmp_path: Path) -> None:
    task_id = "civil/calculation/failed-dispatch"
    tasks_root = tmp_path / "tasks"
    write_adaptive_task(tasks_root, task_id=task_id)
    bundle = build_adaptive_bundle(tasks_root=tasks_root, task_id=task_id)

    execution = execute_run_bundle(
        bundle=bundle,
        registry=default_kernel_registry(),
        workflow=_workflow(tmp_path, tasks_root),
        artifacts_root=tmp_path / "meta-harness-artifacts",
        study=_study("run.failed-dispatch.001"),
        executor=FailingHarborExecutor(),
    )

    assert execution.program.status is ProgramExecutionStatus.FAILED
    assert execution.budget.status == "breached"
    assert execution.budget.token_evidence_complete is False
    assert execution.budget.cost_evidence_complete is False
    assert execution.budget.unaccounted_dispatches == 1
    assert execution.budget.breach_code == "harness_dispatch_evidence_incomplete"


def test_decomposed_px_fails_before_second_dispatch_when_aggregate_turn_capacity_is_exceeded(
    tmp_path: Path,
) -> None:
    task_ids = ("civil/calculation/turn-alpha", "civil/calculation/turn-beta")
    tasks_root = tmp_path / "tasks"
    for task_id in task_ids:
        write_adaptive_task(tasks_root, task_id=task_id)
    bundle = build_adaptive_bundle(
        tasks_root=tasks_root,
        task_ids=task_ids,
        program_kind="fanout",
        budget=HarnessBudget(
            max_agent_turns=8,
            max_tool_calls=32,
            max_context_tokens=8_000,
        ),
    )
    executor = WritingHarborExecutor(model="claude-test-model")

    execution = execute_run_bundle(
        bundle=bundle,
        registry=default_kernel_registry(),
        workflow=_workflow(tmp_path, tasks_root),
        artifacts_root=tmp_path / "meta-harness-artifacts",
        study=_study("run.turn-capacity.001"),
        executor=executor,
    )

    assert execution.program.status is ProgramExecutionStatus.FAILED
    assert execution.program.error_code == "harness_agent_turn_capacity_exceeded"
    assert execution.budget.status == "breached"
    assert execution.budget.reserved_agent_turns == 8
    assert executor.calls == 1


def test_run_bundle_runtime_fails_closed_after_observed_token_budget_breach(tmp_path: Path) -> None:
    task_id = "civil/calculation/token-budget"
    tasks_root = tmp_path / "tasks"
    write_adaptive_task(tasks_root, task_id=task_id)
    bundle = build_adaptive_bundle(
        tasks_root=tasks_root,
        task_id=task_id,
        budget=HarnessBudget(max_tokens=11, max_cost_usd=None),
    )
    workflow = _workflow(tmp_path, tasks_root)

    execution = execute_run_bundle(
        bundle=bundle,
        registry=default_kernel_registry(),
        workflow=workflow,
        artifacts_root=tmp_path / "meta-harness-artifacts",
        study=_study("run.token-budget.001"),
        executor=WritingHarborExecutor(model="unknown-model", input_tokens=10, output_tokens=2),
    )

    assert execution.program.status is ProgramExecutionStatus.FAILED
    assert execution.program.error_code == "harness_token_budget_exceeded"
    assert execution.budget.status == "breached"
    assert execution.budget.observed_tokens == 12
    assert execution.budget.breach_code == "harness_token_budget_exceeded"


def test_run_bundle_runtime_requires_cost_evidence_when_hx_declares_cost_cap(tmp_path: Path) -> None:
    task_id = "civil/calculation/cost-evidence"
    tasks_root = tmp_path / "tasks"
    write_adaptive_task(tasks_root, task_id=task_id)
    bundle = build_adaptive_bundle(
        tasks_root=tasks_root,
        task_id=task_id,
        budget=HarnessBudget(max_tokens=None, max_cost_usd=1.0),
    )

    execution = execute_run_bundle(
        bundle=bundle,
        registry=default_kernel_registry(),
        workflow=_workflow(tmp_path, tasks_root),
        artifacts_root=tmp_path / "meta-harness-artifacts",
        study=_study("run.cost-evidence.001"),
        executor=WritingHarborExecutor(
            model="unknown-model",
            cost_usd=None,
        ),
    )

    assert execution.program.status is ProgramExecutionStatus.FAILED
    assert execution.program.error_code == "harness_cost_evidence_missing"
    assert execution.budget.breach_code == "harness_cost_evidence_missing"


def test_run_bundle_runtime_rejects_trial_duration_beyond_hx_runtime_cap(tmp_path: Path) -> None:
    task_id = "civil/calculation/runtime-budget"
    tasks_root = tmp_path / "tasks"
    write_adaptive_task(tasks_root, task_id=task_id)
    bundle = build_adaptive_bundle(
        tasks_root=tasks_root,
        task_id=task_id,
        budget=HarnessBudget(
            max_runtime_seconds=1,
            max_tokens=None,
            max_cost_usd=None,
        ),
    )

    execution = execute_run_bundle(
        bundle=bundle,
        registry=default_kernel_registry(),
        workflow=_workflow(tmp_path, tasks_root),
        artifacts_root=tmp_path / "meta-harness-artifacts",
        study=_study("run.runtime-budget.001"),
        executor=WritingHarborExecutor(model="unknown-model", elapsed_seconds=2),
    )

    assert execution.program.status is ProgramExecutionStatus.FAILED
    assert execution.program.error_code == "harness_runtime_budget_exceeded"
    assert execution.budget.observed_trial_seconds == 2.0


def _workflow(tmp_path: Path, tasks_root: Path) -> SynchronousHarborWorkflow:
    return SynchronousHarborWorkflow(
        project_root=tmp_path,
        repo_root=tmp_path,
        tasks_root=tasks_root,
        ledger_root=tmp_path / "ledger",
        jobs_root=tmp_path / "jobs",
    )


def _study(run_id: str) -> MetaHarnessStudyContext:
    return MetaHarnessStudyContext(
        run_id=run_id,
        policy_id="policy.fixed-k.budget",
        harness_generator_sha256="1" * 64,
        program_generator_sha256="2" * 64,
        split="discovery",
    )
