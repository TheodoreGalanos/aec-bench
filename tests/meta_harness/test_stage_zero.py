# ABOUTME: Exercises the production stage-zero candidate-search workflow through the real Harbor boundary contracts.
# ABOUTME: Proves content-addressed reporting, exact evidence coverage, tamper rejection, and motif evidence conversion.

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]

from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.harness.harbor_workflow import SynchronousHarborWorkflow
from aec_bench.meta_harness.factorial_candidates import FactorialCandidateFactoryRequest
from aec_bench.meta_harness.factorial_experiment import (
    FactorialExperimentReport as StageZeroReport,
)
from aec_bench.meta_harness.factorial_experiment import (
    factorial_experiment_evidence as stage_zero_factorial_evidence,
)
from aec_bench.meta_harness.factorial_experiment import (
    load_factorial_experiment_report as load_stage_zero_report,
)
from aec_bench.meta_harness.factorial_experiment import (
    prepare_factorial_experiment_spec as prepare_stage_zero_spec,
)
from aec_bench.meta_harness.factorial_experiment import (
    run_factorial_experiment as run_stage_zero,
)
from tests.meta_harness.test_factorial_candidates import _factory_inputs
from tests.support.adaptive_harness import runtime_attestation_for_harbor_agent


class StageZeroHarborExecutor:
    """Writes verified, costed Harbor result trees while exercising the real importer and study runtime."""

    def __init__(
        self,
        *,
        include_cost: bool = True,
        invalid_call_indices: frozenset[int] = frozenset(),
    ) -> None:
        self.include_cost = include_cost
        self.invalid_call_indices = invalid_call_indices
        self.calls = 0
        self._lock = threading.Lock()

    def execute(self, *, command: list[str], cwd: Path) -> int:
        config = yaml.safe_load(Path(command[-1]).read_text(encoding="utf-8"))
        agent = config["agents"][0]
        with self._lock:
            self.calls += 1
            call_index = self.calls
        jobs_dir = Path(config["jobs_dir"])
        for task_index, task in enumerate(config["tasks"], start=1):
            trial_name = f"trial-stage-zero-{call_index}-{task_index}"
            trial_dir = jobs_dir / f"job-stage-zero-{call_index}" / trial_name
            (trial_dir / "artifacts" / "agent").mkdir(parents=True)
            (trial_dir / "verifier").mkdir(parents=True)
            valid_output = call_index not in self.invalid_call_indices
            if valid_output:
                (trial_dir / "artifacts" / "agent" / "output.md").write_text("42\n", encoding="utf-8")
            (trial_dir / "artifacts" / "agent" / "agent_result.json").write_text(
                json.dumps(
                    {
                        "status": "completed",
                        "usage_model_calls": 1,
                        "input_tokens": 10,
                        "output_tokens": 2,
                        "usage_cache_read_tokens": 0,
                        "usage_cache_write_tokens": 0,
                    }
                ),
                encoding="utf-8",
            )
            (trial_dir / "verifier" / "reward.json").write_text(
                json.dumps({"reward": _reward(agent) if valid_output else 0.0}),
                encoding="utf-8",
            )
            agent_result: dict[str, Any] = {}
            if self.include_cost:
                agent_result["cost_usd"] = 0.001
            (trial_dir / "result.json").write_text(
                json.dumps(
                    {
                        "trial_name": trial_name,
                        "task_checksum": "sha256-stage-zero-task",
                        "config": {
                            "task": {"path": str(task["path"])},
                            "agent": agent,
                            "environment": {"type": "docker", "kwargs": {}},
                            "job_id": f"harbor-job-stage-zero-{call_index}",
                        },
                        "agent_info": {"name": "entrypoint", "version": "1.0.0"},
                        "agent_result": {
                            **agent_result,
                            "metadata": {
                                "runtime_execution_attestation": runtime_attestation_for_harbor_agent(
                                    agent,
                                    instruction=(cwd / str(task["path"]) / "instruction.md").read_text(
                                        encoding="utf-8"
                                    ),
                                )
                            },
                        },
                        "started_at": "2026-07-22T00:00:00Z",
                        "finished_at": "2026-07-22T00:00:01Z",
                    }
                ),
                encoding="utf-8",
            )
        return 0


def test_stage_zero_runs_strict_preregistered_candidate_search_and_persists_report(tmp_path: Path) -> None:
    registry, tasks_root, request = _one_repetition_factory(tmp_path)
    spec = prepare_stage_zero_spec(
        candidate_requests=(request,),
        registry=registry,
        tasks_root=tasks_root,
        policy_id="policy.stage-zero.fixed-k",
        randomization_seed=73,
        harness_generator_sha256="1" * 64,
        program_generator_sha256="2" * 64,
        split="calibration",
        bootstrap_replicates=8,
        bootstrap_seed=97,
    )
    executor = StageZeroHarborExecutor()

    result = run_stage_zero(
        spec=spec,
        registry=registry,
        workflow=_workflow(tmp_path, tasks_root),
        artifacts_root=tmp_path / "stage-zero-artifacts",
        executor=executor,
    )

    assert result.report.conclusion == "candidate_search"
    assert result.report.spec_sha256 == spec.content_sha256
    assert result.report.kernel_ref == registry.manifest.ref
    assert result.report.manifest == spec.study_manifest
    assert result.report.plan.plan_sha256 == result.report.analysis.plan_sha256
    assert result.report.trial_count == 4
    assert len(result.report.trials) == 4
    assert len(result.report.candidates) == 1
    assert {cell.cell.value for cell in result.report.candidates[0].cells} == {
        "h0_p0",
        "hx_p0",
        "h0_px",
        "hx_px",
    }
    assert result.report.validity_rate == 1.0
    assert result.report.cost_evidence_complete is True
    assert result.report.token_evidence_complete is True
    assert result.report.estimated_cost_usd == pytest.approx(0.004)
    assert result.report.observed_tokens == 48
    assert executor.calls == 4
    assert result.path.parent.name == result.report.content_sha256
    assert load_stage_zero_report(result.path) == result.report

    evidence = stage_zero_factorial_evidence(result.report)
    assert evidence.analysis_sha256 == result.report.analysis_sha256
    assert evidence.world_lineage_ids == result.report.world_lineage_ids
    assert evidence.split == "calibration"
    assert evidence.validity_rate == 1.0
    assert evidence.estimated_cost_usd == pytest.approx(0.004)
    assert evidence.joint_incremental_uplift == pytest.approx(result.report.analysis.joint_incremental_uplift.estimate)
    assert evidence.joint_incremental_uplift_lower_bound == pytest.approx(
        result.report.analysis.joint_incremental_uplift.interval.lower
    )
    assert evidence.holdout_accessed_during_selection is False


def test_stage_zero_persists_verifier_completed_invalid_zero_outcomes(
    tmp_path: Path,
) -> None:
    registry, tasks_root, request = _one_repetition_factory(tmp_path)
    spec = prepare_stage_zero_spec(
        candidate_requests=(request,),
        registry=registry,
        tasks_root=tasks_root,
        policy_id="policy.stage-zero.invalid-output",
        randomization_seed=73,
        harness_generator_sha256="1" * 64,
        program_generator_sha256="2" * 64,
        split="calibration",
        bootstrap_replicates=4,
    )
    executor = StageZeroHarborExecutor(invalid_call_indices=frozenset({1}))

    result = run_stage_zero(
        spec=spec,
        registry=registry,
        workflow=_workflow(tmp_path, tasks_root),
        artifacts_root=tmp_path / "stage-zero-artifacts",
        executor=executor,
    )

    assert executor.calls == result.report.plan.trial_count
    assert result.report.validity_rate == pytest.approx(0.75)
    assert [trial.validity_rate for trial in result.report.trials].count(0.0) == 1
    assert [trial.mean_reward for trial in result.report.trials].count(0.0) == 1
    assert load_stage_zero_report(result.path) == result.report

    evidence = stage_zero_factorial_evidence(result.report)
    assert evidence.validity_rate == result.report.validity_rate


def test_stage_zero_rejects_changed_task_input_before_harbor_execution(tmp_path: Path) -> None:
    registry, tasks_root, request = _one_repetition_factory(tmp_path)
    spec = prepare_stage_zero_spec(
        candidate_requests=(request,),
        registry=registry,
        tasks_root=tasks_root,
        policy_id="policy.stage-zero.fixed-k",
        randomization_seed=73,
        harness_generator_sha256="1" * 64,
        program_generator_sha256="2" * 64,
        split="discovery",
        bootstrap_replicates=4,
    )
    task_path = tasks_root / request.task_refs[0] / "instruction.md"
    task_path.write_text(task_path.read_text(encoding="utf-8") + "Changed after preregistration.\n", encoding="utf-8")
    executor = StageZeroHarborExecutor()

    with pytest.raises(ValueError, match="applicability changed after preregistration"):
        run_stage_zero(
            spec=spec,
            registry=registry,
            workflow=_workflow(tmp_path, tasks_root),
            artifacts_root=tmp_path / "stage-zero-artifacts",
            executor=executor,
        )

    assert executor.calls == 0


def test_stage_zero_report_loader_rejects_trial_artifact_tamper(tmp_path: Path) -> None:
    registry, tasks_root, request = _one_repetition_factory(tmp_path)
    spec = prepare_stage_zero_spec(
        candidate_requests=(request,),
        registry=registry,
        tasks_root=tasks_root,
        policy_id="policy.stage-zero.fixed-k",
        randomization_seed=73,
        harness_generator_sha256="1" * 64,
        program_generator_sha256="2" * 64,
        split="calibration",
        bootstrap_replicates=4,
    )
    result = run_stage_zero(
        spec=spec,
        registry=registry,
        workflow=_workflow(tmp_path, tasks_root),
        artifacts_root=tmp_path / "stage-zero-artifacts",
        executor=StageZeroHarborExecutor(),
    )
    trial_artifact = result.report.trials[0].trial_records[0]
    Path(trial_artifact.path).write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="artifact digest mismatch"):
        load_stage_zero_report(result.path)


@pytest.mark.parametrize(
    "forgery",
    ("trial-outcome", "resource-metrics", "world-aggregate", "factorial-analysis"),
)
def test_stage_zero_report_loader_rejects_rehashed_invented_derived_evidence(
    tmp_path: Path,
    forgery: str,
) -> None:
    registry, tasks_root, request = _one_repetition_factory(tmp_path)
    spec = prepare_stage_zero_spec(
        candidate_requests=(request,),
        registry=registry,
        tasks_root=tasks_root,
        policy_id="policy.stage-zero.fixed-k",
        randomization_seed=73,
        harness_generator_sha256="1" * 64,
        program_generator_sha256="2" * 64,
        split="calibration",
        bootstrap_replicates=4,
        bootstrap_seed=97,
    )
    result = run_stage_zero(
        spec=spec,
        registry=registry,
        workflow=_workflow(tmp_path, tasks_root),
        artifacts_root=tmp_path / "stage-zero-artifacts",
        executor=StageZeroHarborExecutor(),
    )
    payload = result.report.model_dump(mode="json", exclude={"content_sha256"})
    forged_trial = payload["trials"][0]
    if forgery == "trial-outcome":
        forged_trial["mean_reward"] = 0.99
    elif forgery == "resource-metrics":
        forged_trial["budget"]["imported_trials"] += 99
        forged_trial["budget"]["observed_trial_seconds"] = 999.0
    elif forgery == "world-aggregate":
        payload["world_lineage_ids"] = ["f" * 64]
    else:
        payload["analysis"]["cell_means"]["h0_p0"] = 0.99
        payload["analysis"]["joint_uplift"]["estimate"] = -0.09
        payload["analysis_sha256"] = canonical_content_sha256(payload["analysis"])
    if forgery == "world-aggregate":
        with pytest.raises(ValueError, match="applicability does not bind its world lineages"):
            StageZeroReport.model_validate(payload)
        return
    forged = StageZeroReport.model_validate(payload)
    forged_path = (
        tmp_path / "stage-zero-artifacts" / "stage-zero-reports" / forged.content_sha256 / "stage-zero-report.json"
    )
    forged_path.parent.mkdir(parents=True)
    forged_path.write_text(
        json.dumps(forged.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="derived evidence"):
        load_stage_zero_report(forged_path)


def test_stage_zero_fails_closed_when_cost_evidence_is_incomplete(tmp_path: Path) -> None:
    registry, tasks_root, request = _one_repetition_factory(tmp_path)
    spec = prepare_stage_zero_spec(
        candidate_requests=(request,),
        registry=registry,
        tasks_root=tasks_root,
        policy_id="policy.stage-zero.fixed-k",
        randomization_seed=73,
        harness_generator_sha256="1" * 64,
        program_generator_sha256="2" * 64,
        split="discovery",
        bootstrap_replicates=4,
    )

    with pytest.raises(ValueError, match="lacks complete cost evidence"):
        run_stage_zero(
            spec=spec,
            registry=registry,
            workflow=_workflow(tmp_path, tasks_root),
            artifacts_root=tmp_path / "stage-zero-artifacts",
            executor=StageZeroHarborExecutor(include_cost=False),
        )


def _one_repetition_factory(
    tmp_path: Path,
) -> tuple[Any, Path, FactorialCandidateFactoryRequest]:
    registry, tasks_root, request = _factory_inputs(tmp_path)
    payload = request.model_dump(mode="python", exclude={"content_sha256"})
    payload.update({"seeds": (17,), "repetitions": 1})
    return registry, tasks_root, FactorialCandidateFactoryRequest.model_validate(payload)


def _workflow(tmp_path: Path, tasks_root: Path) -> SynchronousHarborWorkflow:
    return SynchronousHarborWorkflow(
        project_root=tmp_path,
        repo_root=tmp_path,
        tasks_root=tasks_root,
        ledger_root=tmp_path / "ledger",
        jobs_root=tmp_path / "jobs",
    )


def _reward(agent: dict[str, Any]) -> float:
    lineage = agent["kwargs"]["meta_harness_context"]
    cell = str(lineage["bundle_id"]).rsplit(".", maxsplit=1)[-1]
    return {
        "h0_p0": 0.2,
        "hx_p0": 0.4,
        "h0_px": 0.5,
        "hx_px": 0.9,
    }[cell]
