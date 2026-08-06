# ABOUTME: Exercises declared task-world stages through isolated Harbor dispatches and one scored finalization.
# ABOUTME: Proves routed receipt lineage, resource accounting, tamper detection, and TrialRecord isolation.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]

from aec_bench.contracts.execution_program import (
    ActionNode,
    ExecutionProgram,
    JoinNode,
    LiteralValue,
    OutputValue,
    ProgramArgument,
    ProgramOutputRef,
    StopNode,
    StopOutcome,
)
from aec_bench.contracts.stage_execution import KernelInstructionOverride, StageContextManifest
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.harness.harbor_workflow import SynchronousHarborWorkflow
from aec_bench.meta_harness.compilation import compile_execution_program, compile_run_bundle
from aec_bench.meta_harness.kernel_catalogue import default_kernel_registry
from aec_bench.meta_harness.program_execution import ProgramExecutionStatus
from aec_bench.meta_harness.run_bundle_runtime import (
    MetaHarnessStudyContext,
    execute_run_bundle,
    load_stage_execution_receipt,
)
from tests.support.adaptive_harness import (
    build_adaptive_bundle,
    runtime_attestation_for_harbor_agent,
    write_adaptive_task,
)


class DeclaredStageHarborExecutor:
    """Write genuine Harbor-shaped evidence for stage dispatch and finalization boundaries."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None, bool]] = []

    def execute(self, *, command: list[str], cwd: Path) -> int:
        del cwd
        config = yaml.safe_load(Path(command[-1]).read_text(encoding="utf-8"))
        assert len(config["tasks"]) == 1
        agent = config["agents"][0]
        task_path = str(config["tasks"][0]["path"])
        kwargs: dict[str, Any] = agent["kwargs"]
        override = KernelInstructionOverride.model_validate(kwargs["kernel_instruction_override"])
        task_id = override.task_id
        verification_disabled = bool(config.get("verifier", {}).get("disable", False))
        self.calls.append((override.mode, override.stage_id, verification_disabled))

        call_index = len(self.calls)
        trial_dir = Path(config["jobs_dir"]) / f"job-declared-stage-{call_index}" / f"trial-declared-stage-{call_index}"
        (trial_dir / "artifacts" / "agent").mkdir(parents=True)
        if override.mode == "task_finalization":
            (trial_dir / "verifier").mkdir()
        output = (
            _stage_output(task_id=task_id, stage_id=override.stage_id or "")
            if override.mode == "declared_stage"
            else "# Final review\nThe declared evidence supports a conditional readiness decision.\n"
        )
        (trial_dir / "artifacts" / "agent" / "output.md").write_text(output, encoding="utf-8")
        (trial_dir / "artifacts" / "agent" / "agent_result.json").write_text(
            json.dumps(
                {
                    "status": "completed",
                    "input_tokens": 11,
                    "output_tokens": 3,
                    "usage_model_calls": 1,
                    "usage_input_tokens": 11,
                    "usage_output_tokens": 3,
                    "usage_cache_read_tokens": 2,
                    "usage_cache_write_tokens": 1,
                    "turns_used": 1,
                    "tool_calls_used": 1,
                }
            ),
            encoding="utf-8",
        )
        if override.mode == "task_finalization":
            (trial_dir / "verifier" / "reward.json").write_text(
                json.dumps({"reward": 1.0}),
                encoding="utf-8",
            )
        (trial_dir / "result.json").write_text(
            json.dumps(
                {
                    "trial_name": f"trial-declared-stage-{call_index}",
                    "task_checksum": "sha256-task",
                    "config": {
                        "task": {"path": task_path},
                        "agent": agent,
                        "environment": {"type": "docker", "kwargs": {}},
                        "job_id": f"harbor-job-declared-stage-{call_index}",
                    },
                    "agent_info": {"name": "entrypoint", "version": "1.0.0"},
                    "agent_result": {
                        "cost_usd": 0.001,
                        "metadata": {
                            "runtime_execution_attestation": runtime_attestation_for_harbor_agent(
                                agent,
                                instruction=override.effective_instruction,
                            )
                        },
                    },
                    "started_at": "2026-07-23T00:00:00Z",
                    "finished_at": "2026-07-23T00:00:01Z",
                }
            ),
            encoding="utf-8",
        )
        return 0


class IncompleteStageMeteringExecutor(DeclaredStageHarborExecutor):
    """Remove one required usage field after writing otherwise valid Harbor evidence."""

    def execute(self, *, command: list[str], cwd: Path) -> int:
        exit_code = super().execute(command=command, cwd=cwd)
        config = yaml.safe_load(Path(command[-1]).read_text(encoding="utf-8"))
        call_index = len(self.calls)
        agent_result_path = (
            Path(config["jobs_dir"])
            / f"job-declared-stage-{call_index}"
            / f"trial-declared-stage-{call_index}"
            / "artifacts"
            / "agent"
            / "agent_result.json"
        )
        payload = json.loads(agent_result_path.read_text(encoding="utf-8"))
        del payload["usage_cache_write_tokens"]
        agent_result_path.write_text(
            json.dumps(payload),
            encoding="utf-8",
        )
        return exit_code


def test_declared_stage_program_runs_isolated_stages_then_one_scored_finalization(
    tmp_path: Path,
) -> None:
    task_id = "civil/review/declared-stage"
    tasks_root = tmp_path / "tasks"
    task_dir = write_adaptive_task(tasks_root, task_id=task_id)
    _write_stage_world(task_dir)
    bundle = _staged_bundle(tasks_root=tasks_root, task_id=task_id)
    executor = DeclaredStageHarborExecutor()

    execution = execute_run_bundle(
        bundle=bundle,
        registry=default_kernel_registry(),
        workflow=_workflow(tmp_path, tasks_root),
        artifacts_root=tmp_path / "artifacts",
        study=_study(),
        executor=executor,
    )

    assert execution.program.status is ProgramExecutionStatus.SUCCEEDED
    assert executor.calls == [
        ("declared_stage", "inventory", True),
        ("declared_stage", "authority", True),
        ("declared_stage", "decision", True),
        ("task_finalization", None, False),
    ]
    assert len(execution.stage_executions) == 3
    assert len(execution.harbor_invocations) == 1
    assert execution.budget.recorded_stage_executions == 3
    assert execution.budget.imported_trials == 1
    assert execution.budget.observed_tokens == 56
    assert execution.budget.observed_cost_usd == pytest.approx(0.004)
    governed_attempt_roots = tuple(
        sorted(
            (tmp_path / "artifacts").glob(
                "*/runs/run.declared-stage.001/invocations/*/governed-attempt",
            ),
        )
    )
    assert len(governed_attempt_roots) == 3
    assert all(
        len(
            tuple(
                root.glob(
                    "governed-attempt/claims/terminal/*/claim.json",
                )
            )
        )
        == 1
        for root in governed_attempt_roots
    )

    by_stage = {evidence.receipt.receipt.stage_id: evidence.receipt for evidence in execution.stage_executions}
    inventory = load_stage_execution_receipt(by_stage["inventory"].path)
    authority = load_stage_execution_receipt(by_stage["authority"].path)
    decision = load_stage_execution_receipt(by_stage["decision"].path)
    assert inventory.upstream_receipts == ()
    assert authority.upstream_receipts == (by_stage["inventory"].reference,)
    assert decision.upstream_receipts == (
        by_stage["inventory"].reference,
        by_stage["authority"].reference,
    )
    decision_context = StageContextManifest.model_validate_json(
        Path(decision.context_manifest.path).read_text(encoding="utf-8")
    )
    assert {(route.input_id, route.producer_stage_id) for route in decision_context.routes} == {
        ("packet_id", "inventory"),
        ("provenance_ledger", "authority"),
    }

    final_trial_path = execution.harbor_invocations[0].imported_trial_paths[0]
    final_trial = TrialRecord.model_validate_json(final_trial_path.read_text(encoding="utf-8"))
    assert final_trial.task.task_id == task_id
    assert list((tmp_path / "ledger").rglob("trial-*.json")) == [final_trial_path]


def test_declared_stage_attempts_replay_without_provider_redispatch(
    tmp_path: Path,
) -> None:
    task_id = "civil/review/declared-stage-replay"
    tasks_root = tmp_path / "tasks"
    task_dir = write_adaptive_task(tasks_root, task_id=task_id)
    _write_stage_world(task_dir)
    bundle = _staged_bundle(tasks_root=tasks_root, task_id=task_id)
    executor = DeclaredStageHarborExecutor()
    workflow = _workflow(tmp_path, tasks_root)
    artifacts_root = tmp_path / "artifacts"
    study = _study()

    first = execute_run_bundle(
        bundle=bundle,
        registry=default_kernel_registry(),
        workflow=workflow,
        artifacts_root=artifacts_root,
        study=study,
        executor=executor,
    )
    second = execute_run_bundle(
        bundle=bundle,
        registry=default_kernel_registry(),
        workflow=workflow,
        artifacts_root=artifacts_root,
        study=study,
        executor=executor,
    )

    assert first.program.status is ProgramExecutionStatus.SUCCEEDED
    assert second.program.status is ProgramExecutionStatus.SUCCEEDED
    assert executor.calls == [
        ("declared_stage", "inventory", True),
        ("declared_stage", "authority", True),
        ("declared_stage", "decision", True),
        ("task_finalization", None, False),
    ]
    assert tuple(evidence.receipt.reference.sha256 for evidence in second.stage_executions) == tuple(
        evidence.receipt.reference.sha256 for evidence in first.stage_executions
    )


def test_declared_stage_missing_exact_usage_fails_closed_without_redispatch(
    tmp_path: Path,
) -> None:
    task_id = "civil/review/declared-stage-incomplete-usage"
    tasks_root = tmp_path / "tasks"
    task_dir = write_adaptive_task(tasks_root, task_id=task_id)
    _write_stage_world(task_dir)
    bundle = _staged_bundle(tasks_root=tasks_root, task_id=task_id)
    executor = IncompleteStageMeteringExecutor()
    workflow = _workflow(tmp_path, tasks_root)
    artifacts_root = tmp_path / "artifacts"
    study = _study()

    first = execute_run_bundle(
        bundle=bundle,
        registry=default_kernel_registry(),
        workflow=workflow,
        artifacts_root=artifacts_root,
        study=study,
        executor=executor,
    )
    second = execute_run_bundle(
        bundle=bundle,
        registry=default_kernel_registry(),
        workflow=workflow,
        artifacts_root=artifacts_root,
        study=study,
        executor=executor,
    )

    assert first.program.status is ProgramExecutionStatus.FAILED
    assert first.program.error_code == "governed_stage_attempt_failed"
    assert second.program.status is ProgramExecutionStatus.FAILED
    assert second.program.error_code == "governed_stage_attempt_failed"
    assert executor.calls == [
        ("declared_stage", "inventory", True),
    ]
    engine_root = next(
        artifacts_root.glob(
            "*/runs/run.declared-stage.001/invocations/inventory-a1/governed-attempt",
        )
    )
    assert (
        len(
            tuple(
                engine_root.glob(
                    "governed-attempt/claims/dispatch_intent/*/claim.json",
                )
            )
        )
        == 1
    )
    assert not tuple(
        engine_root.glob(
            "governed-attempt/claims/backend_receipt/*/claim.json",
        )
    )
    assert not tuple(
        engine_root.glob(
            "governed-attempt/claims/terminal/*/claim.json",
        )
    )


def test_stage_receipt_reverification_rejects_mutated_intermediate_output(tmp_path: Path) -> None:
    task_id = "civil/review/declared-stage-tamper"
    tasks_root = tmp_path / "tasks"
    task_dir = write_adaptive_task(tasks_root, task_id=task_id)
    _write_stage_world(task_dir)
    execution = execute_run_bundle(
        bundle=_staged_bundle(tasks_root=tasks_root, task_id=task_id),
        registry=default_kernel_registry(),
        workflow=_workflow(tmp_path, tasks_root),
        artifacts_root=tmp_path / "artifacts",
        study=_study(),
        executor=DeclaredStageHarborExecutor(),
    )
    receipt_artifact = execution.stage_executions[0].receipt
    receipt = load_stage_execution_receipt(receipt_artifact.path)
    parsed_output = Path(receipt.parsed_output.path)
    parsed_output.write_bytes(parsed_output.read_bytes() + b"\n")

    with pytest.raises(ValueError, match="stage output artifact hash changed"):
        load_stage_execution_receipt(receipt_artifact.path)


def _stage_output(*, task_id: str, stage_id: str) -> str:
    values = {
        "inventory": {
            "packet_id": "PKT-001",
            "source_inventory": ["register.csv"],
        },
        "authority": {
            "provenance_ledger": {"register.csv": "current"},
        },
        "decision": {
            "readiness_decision": "conditional",
        },
    }[stage_id]
    payload = {
        "schema_version": "aecbench.stage-output.v1",
        "task_id": task_id,
        "stage_id": stage_id,
        "outputs": values,
    }
    return "# Stage result\n```json\n" + json.dumps(payload, sort_keys=True) + "\n```\n"


def _write_stage_world(task_dir: Path) -> None:
    (task_dir / "world.json").write_text(
        json.dumps(
            {
                "world_id": "aec.world.civil.declared-stage",
                "name": "Declared stage review",
                "task_unit": "generated-task-instance",
                "logic_profile": {"agentic_review": {"required": True}},
                "stages": [
                    {
                        "id": "inventory",
                        "title": "Inventory",
                        "discipline": "civil",
                        "consumes": ["document_register"],
                        "produces": ["source_inventory"],
                    },
                    {
                        "id": "authority",
                        "title": "Authority",
                        "discipline": "civil",
                        "consumes": ["source_inventory"],
                        "produces": ["provenance_ledger"],
                    },
                    {
                        "id": "decision",
                        "title": "Decision",
                        "discipline": "civil",
                        "consumes": ["provenance_ledger"],
                        "produces": ["readiness_decision"],
                    },
                ],
                "handoffs": [
                    {
                        "id": "packet_id",
                        "producer_stage": "inventory",
                        "consumer_stages": ["decision"],
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _staged_bundle(*, tasks_root: Path, task_id: str):
    registry = default_kernel_registry()
    base = build_adaptive_bundle(tasks_root=tasks_root, task_id=task_id, registry=registry)
    task = ProgramArgument(name="task_ref", value=LiteralValue(value=task_id))

    def stage(stage_id: str) -> ProgramArgument:
        return ProgramArgument(name="stage_id", value=LiteralValue(value=stage_id))

    program = compile_execution_program(
        ExecutionProgram(
            program_id="px-declared-stage",
            version="1.0.0",
            harness_ref=base.harness.ref,
            nodes=(
                ActionNode(
                    node_id="inventory",
                    operation_id="run_stage.v1",
                    arguments=(task, stage("inventory")),
                ),
                ActionNode(
                    node_id="authority",
                    depends_on=("inventory",),
                    operation_id="run_stage.v1",
                    arguments=(
                        task,
                        stage("authority"),
                        ProgramArgument(
                            name="upstream_receipts",
                            value=OutputValue(
                                ref=ProgramOutputRef(
                                    node_id="inventory",
                                    output_port="stage_receipt",
                                )
                            ),
                        ),
                    ),
                ),
                JoinNode(
                    node_id="decision-inputs",
                    depends_on=("inventory", "authority"),
                    sources=(
                        ProgramOutputRef(node_id="inventory", output_port="stage_receipt"),
                        ProgramOutputRef(node_id="authority", output_port="stage_receipt"),
                    ),
                ),
                ActionNode(
                    node_id="decision",
                    depends_on=("decision-inputs",),
                    operation_id="run_stage.v1",
                    arguments=(
                        task,
                        stage("decision"),
                        ProgramArgument(
                            name="upstream_receipts",
                            value=OutputValue(
                                ref=ProgramOutputRef(
                                    node_id="decision-inputs",
                                    output_port="result",
                                )
                            ),
                        ),
                    ),
                ),
                JoinNode(
                    node_id="all-stages",
                    depends_on=("inventory", "authority", "decision"),
                    sources=(
                        ProgramOutputRef(node_id="inventory", output_port="stage_receipt"),
                        ProgramOutputRef(node_id="authority", output_port="stage_receipt"),
                        ProgramOutputRef(node_id="decision", output_port="stage_receipt"),
                    ),
                ),
                ActionNode(
                    node_id="finalize",
                    depends_on=("all-stages",),
                    operation_id="finalize_task.v1",
                    arguments=(
                        task,
                        ProgramArgument(
                            name="stage_receipts",
                            value=OutputValue(
                                ref=ProgramOutputRef(
                                    node_id="all-stages",
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
                    result=ProgramOutputRef(node_id="finalize", output_port="trials"),
                ),
            ),
        ),
        harness=base.harness,
        registry=registry,
    )
    return compile_run_bundle(
        bundle_id="bundle-declared-stage",
        harness=base.harness,
        program=program,
        registry=registry,
        tasks_root=tasks_root,
        experiment_id="declared-stage-experiment",
    )


def _workflow(tmp_path: Path, tasks_root: Path) -> SynchronousHarborWorkflow:
    return SynchronousHarborWorkflow(
        project_root=tmp_path,
        repo_root=tmp_path,
        tasks_root=tasks_root,
        ledger_root=tmp_path / "ledger",
        jobs_root=tmp_path / "jobs",
    )


def _study() -> MetaHarnessStudyContext:
    return MetaHarnessStudyContext(
        run_id="run.declared-stage.001",
        policy_id="policy.fixed-k.declared-stage",
        harness_generator_sha256="1" * 64,
        program_generator_sha256="2" * 64,
        split="repair_gate",
        execution_seed=17,
    )
