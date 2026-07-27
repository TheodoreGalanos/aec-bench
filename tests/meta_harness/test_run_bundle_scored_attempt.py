# ABOUTME: Proves scored RunBundle Harbor invocations use the durable governed-attempt lifecycle.
# ABOUTME: Covers exact replay, reconciliation, usage, budget, authority, and import-integrity failures.

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from aec_bench.contracts.harness_instance import HarnessBudget
from aec_bench.contracts.run_bundle import RunBundle
from aec_bench.harness.harbor_workflow import SynchronousHarborWorkflow
from aec_bench.meta_harness.authority_ledger import AuthorityLedger
from aec_bench.meta_harness.kernel_catalogue import default_kernel_registry
from aec_bench.meta_harness.program_runtime import ProgramExecutionStatus
from aec_bench.meta_harness.run_bundle_evidence import MetaHarnessStudyContext
from aec_bench.meta_harness.run_bundle_runtime import execute_run_bundle
from tests.meta_harness.test_run_bundle_runtime import (
    WritingHarborExecutor,
    _study,
    _workflow,
)
from tests.support.adaptive_harness import build_adaptive_bundle, write_adaptive_task


class WritingThenInterruptingHarborExecutor(WritingHarborExecutor):
    """Write one complete Harbor job, then lose the in-process dispatch receipt."""

    def __init__(self, *, model: str) -> None:
        super().__init__(model=model)
        self._interrupt = True

    def execute(self, *, command: list[str], cwd: Path) -> int:
        exit_code = super().execute(command=command, cwd=cwd)
        if self._interrupt:
            self._interrupt = False
            raise RuntimeError("process interrupted after Harbor wrote the completed job")
        return exit_code


class MissingUsageHarborExecutor(WritingHarborExecutor):
    """Write a real result envelope whose model-call evidence is incomplete."""

    def execute(self, *, command: list[str], cwd: Path) -> int:
        exit_code = super().execute(command=command, cwd=cwd)
        config = yaml.safe_load(Path(command[-1]).read_text(encoding="utf-8"))
        jobs_root = Path(config["jobs_dir"])
        paths = tuple(jobs_root.rglob("artifacts/agent/agent_result.json"))
        assert len(paths) == 1
        payload = json.loads(paths[0].read_text(encoding="utf-8"))
        del payload["usage_model_calls"]
        paths[0].write_text(json.dumps(payload), encoding="utf-8")
        return exit_code


def test_scored_invocation_persists_complete_governed_lifecycle(
    tmp_path: Path,
) -> None:
    bundle, workflow, artifacts_root, study = _case(
        tmp_path,
        task_id="civil/calculation/governed-success",
        run_id="run.governed-success.001",
    )

    execution = execute_run_bundle(
        bundle=bundle,
        registry=default_kernel_registry(),
        workflow=workflow,
        artifacts_root=artifacts_root,
        study=study,
        executor=WritingHarborExecutor(model="claude-test-model"),
    )

    assert execution.program.status is ProgramExecutionStatus.SUCCEEDED
    attempt_root = _attempt_root(
        artifacts_root=artifacts_root,
        bundle_sha256=bundle.content_sha256,
        run_id=study.run_id,
    )
    assert len(tuple(_claims(attempt_root, "terminal"))) == 1
    assert len(tuple(_claims(attempt_root, "dispatch_intent"))) == 1
    assert (attempt_root / "standing-monitor" / "model-claims" / "authority-event").is_dir()


def test_terminal_replay_does_not_redispatch_and_reaccounts_exact_trial(
    tmp_path: Path,
) -> None:
    bundle, workflow, artifacts_root, study = _case(
        tmp_path,
        task_id="civil/calculation/governed-replay",
        run_id="run.governed-replay.001",
    )
    executor = WritingHarborExecutor(model="claude-test-model")

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
    assert executor.calls == 1
    assert second.harbor_invocations[0].receipt == first.harbor_invocations[0].receipt
    assert second.harbor_invocations[0].imported_trial_paths == first.harbor_invocations[0].imported_trial_paths
    assert second.budget.imported_trials == 1
    assert second.budget.observed_tokens == first.budget.observed_tokens


def test_durable_intent_reconciles_completed_job_without_redispatch(
    tmp_path: Path,
) -> None:
    bundle, workflow, artifacts_root, study = _case(
        tmp_path,
        task_id="civil/calculation/governed-reconcile",
        run_id="run.governed-reconcile.001",
    )
    executor = WritingThenInterruptingHarborExecutor(model="claude-test-model")

    interrupted = execute_run_bundle(
        bundle=bundle,
        registry=default_kernel_registry(),
        workflow=workflow,
        artifacts_root=artifacts_root,
        study=study,
        executor=executor,
    )
    recovered = execute_run_bundle(
        bundle=bundle,
        registry=default_kernel_registry(),
        workflow=workflow,
        artifacts_root=artifacts_root,
        study=study,
        executor=executor,
    )

    assert interrupted.program.status is ProgramExecutionStatus.FAILED
    assert recovered.program.status is ProgramExecutionStatus.SUCCEEDED
    assert executor.calls == 1
    assert len(recovered.harbor_invocations) == 1


def test_missing_exact_usage_fails_closed_before_terminal(
    tmp_path: Path,
) -> None:
    bundle, workflow, artifacts_root, study = _case(
        tmp_path,
        task_id="civil/calculation/governed-missing-usage",
        run_id="run.governed-missing-usage.001",
    )

    execution = execute_run_bundle(
        bundle=bundle,
        registry=default_kernel_registry(),
        workflow=workflow,
        artifacts_root=artifacts_root,
        study=study,
        executor=MissingUsageHarborExecutor(model="claude-test-model"),
    )

    assert execution.program.status is ProgramExecutionStatus.FAILED
    assert execution.program.error_code == "governed_usage_evidence_missing"
    attempt_root = _attempt_root(
        artifacts_root=artifacts_root,
        bundle_sha256=bundle.content_sha256,
        run_id=study.run_id,
    )
    assert not tuple(_claims(attempt_root, "terminal"))


def test_budget_breach_closes_exact_usage_but_never_publishes_terminal(
    tmp_path: Path,
) -> None:
    bundle, workflow, artifacts_root, study = _case(
        tmp_path,
        task_id="civil/calculation/governed-budget-breach",
        run_id="run.governed-budget-breach.001",
        budget=HarnessBudget(max_tokens=11, max_cost_usd=None),
    )
    executor = WritingHarborExecutor(
        model="claude-test-model",
        input_tokens=10,
        output_tokens=2,
    )

    execution = execute_run_bundle(
        bundle=bundle,
        registry=default_kernel_registry(),
        workflow=workflow,
        artifacts_root=artifacts_root,
        study=study,
        executor=executor,
    )

    assert execution.program.error_code == "harness_token_budget_exceeded"
    assert execution.budget.observed_tokens == 12
    assert execution.budget.unaccounted_dispatches == 0
    attempt_root = _attempt_root(
        artifacts_root=artifacts_root,
        bundle_sha256=bundle.content_sha256,
        run_id=study.run_id,
    )
    assert not tuple(_claims(attempt_root, "terminal"))


def test_scored_authority_failure_preserves_governed_backend_without_terminal(
    tmp_path: Path,
) -> None:
    bundle, workflow, artifacts_root, study = _case(
        tmp_path,
        task_id="civil/calculation/governed-authority-failure",
        run_id="run.governed-authority-failure.001",
    )
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
        workflow=workflow,
        artifacts_root=artifacts_root,
        study=study,
        executor=WritingHarborExecutor(model="claude-test-model"),
        authority_ledger=authority_ledger,
    )

    assert execution.program.error_code == "scored_import_authority_failed"
    assert len(execution.harbor_invocations) == 1
    attempt_root = _attempt_root(
        artifacts_root=artifacts_root,
        bundle_sha256=bundle.content_sha256,
        run_id=study.run_id,
    )
    assert tuple(_claims(attempt_root, "backend_receipt"))
    assert not tuple(_claims(attempt_root, "terminal"))


def test_terminal_replay_rejects_changed_imported_trial_without_redispatch(
    tmp_path: Path,
) -> None:
    bundle, workflow, artifacts_root, study = _case(
        tmp_path,
        task_id="civil/calculation/governed-import-collision",
        run_id="run.governed-import-collision.001",
    )
    executor = WritingHarborExecutor(model="claude-test-model")
    first = execute_run_bundle(
        bundle=bundle,
        registry=default_kernel_registry(),
        workflow=workflow,
        artifacts_root=artifacts_root,
        study=study,
        executor=executor,
    )
    trial_path = first.harbor_invocations[0].imported_trial_paths[0]
    trial_path.write_bytes(trial_path.read_bytes() + b"\n")

    replay = execute_run_bundle(
        bundle=bundle,
        registry=default_kernel_registry(),
        workflow=workflow,
        artifacts_root=artifacts_root,
        study=study,
        executor=executor,
    )

    assert replay.program.status is ProgramExecutionStatus.FAILED
    assert replay.program.error_code == "governed_import_integrity_failed"
    assert executor.calls == 1


def _case(
    tmp_path: Path,
    *,
    task_id: str,
    run_id: str,
    budget: HarnessBudget | None = None,
) -> tuple[RunBundle, SynchronousHarborWorkflow, Path, MetaHarnessStudyContext]:
    tasks_root = tmp_path / "tasks"
    write_adaptive_task(tasks_root, task_id=task_id)
    bundle = build_adaptive_bundle(
        tasks_root=tasks_root,
        task_id=task_id,
        budget=budget,
    )
    artifacts_root = tmp_path / "meta-harness-artifacts"
    return bundle, _workflow(tmp_path, tasks_root), artifacts_root, _study(run_id)


def _attempt_root(
    *,
    artifacts_root: Path,
    bundle_sha256: str,
    run_id: str,
) -> Path:
    return artifacts_root / bundle_sha256 / "runs" / run_id / "invocations" / "run-a1"


def _claims(attempt_root: Path, stage: str) -> Iterator[Path]:
    return (attempt_root / "governed-attempt-state" / "governed-attempt" / "claims" / stage).glob("*/claim.json")
