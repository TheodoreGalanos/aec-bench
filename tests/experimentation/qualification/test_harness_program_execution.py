# ABOUTME: Exercises ordered harness-program execution through real RunBundle and Harbor workflow contracts.
# ABOUTME: Proves outer seed matching, one-attempt cells, content-addressed plans, and fail-closed outcomes.

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]

from aec_bench.contracts.harness_kernel import canonical_json_sha256
from aec_bench.contracts.trial_record import ExecutionStatus
from aec_bench.experimentation.qualification.harness_program_study.candidates import (
    HarnessProgramCandidateRequest,
    MaterializedHarnessProgramCandidateSet,
    ProgramFactorTemplate,
    materialize_harness_program_candidates,
)
from aec_bench.experimentation.qualification.harness_program_study.execution import (
    execute_harness_program_study,
    validate_harness_program_record_lineage,
)
from aec_bench.experimentation.qualification.harness_program_study.plan import (
    HarnessProgramCell,
    HarnessProgramStudyManifest,
)
from aec_bench.harness.harbor_workflow import SynchronousHarborWorkflow
from tests.experimentation.qualification.test_harness_program_candidates import _factory_inputs
from tests.support.adaptive_harness import runtime_attestation_for_harbor_agent


@dataclass(frozen=True)
class CapturedHarborCall:
    execution_seed: int
    bundle_id: str
    n_attempts: int


class HarnessProgramHarborExecutor:
    """Writes one Harbor-shaped trial per call and captures the exact lowered seed surface."""

    def __init__(
        self,
        *,
        rewards_by_bundle_id: dict[str, float],
        verified: bool = True,
        valid_output: bool = True,
    ) -> None:
        self.rewards_by_bundle_id = rewards_by_bundle_id
        self.verified = verified
        self.valid_output = valid_output
        self.calls: list[CapturedHarborCall] = []
        self._lock = threading.Lock()

    def execute(self, *, command: list[str], cwd: Path) -> int:
        del cwd
        config = yaml.safe_load(Path(command[-1]).read_text(encoding="utf-8"))
        agent = config["agents"][0]
        kwargs: dict[str, Any] = agent["kwargs"]
        lineage: dict[str, Any] = kwargs["meta_harness_context"]
        execution_seed = int(kwargs["execution_seed"])
        bundle_id = str(lineage["bundle_id"])
        assert lineage["execution_seed"] == execution_seed
        call = CapturedHarborCall(
            execution_seed=execution_seed,
            bundle_id=bundle_id,
            n_attempts=int(config["n_attempts"]),
        )
        with self._lock:
            self.calls.append(call)
            call_index = len(self.calls)

        jobs_dir = Path(config["jobs_dir"])
        for task_index, task in enumerate(config["tasks"], start=1):
            task_path = str(task["path"])
            trial_name = f"trial-harness-program-study-{call_index}-{task_index}"
            trial_dir = jobs_dir / f"job-harness-program-study-{call_index}" / trial_name
            (trial_dir / "artifacts" / "agent").mkdir(parents=True)
            (trial_dir / "verifier").mkdir(parents=True)
            if self.valid_output:
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
            if self.verified:
                (trial_dir / "verifier" / "reward.json").write_text(
                    json.dumps({"reward": self.rewards_by_bundle_id[bundle_id] if self.valid_output else 0.0}),
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
                            "job_id": f"harbor-job-harness-program-study-{call_index}",
                        },
                        "agent_info": {"name": "entrypoint", "version": "1.0.0"},
                        "agent_result": {
                            "cost_usd": 0.001,
                            "metadata": {"runtime_execution_attestation": runtime_attestation_for_harbor_agent(agent)},
                        },
                        "started_at": "2026-07-22T00:00:00Z",
                        "finished_at": "2026-07-22T00:00:01Z",
                    }
                ),
                encoding="utf-8",
            )
        return 0


def test_execute_harness_program_study_runs_williams_plan_once_per_seeded_trial(tmp_path: Path) -> None:
    registry, tasks_root, request = _factory_inputs(tmp_path)
    candidates = materialize_harness_program_candidates(request, registry=registry, tasks_root=tasks_root)
    workflow = _workflow(tmp_path, tasks_root)
    rewards_by_cell = {
        HarnessProgramCell.H0_P0: 0.2,
        HarnessProgramCell.HX_P0: 0.4,
        HarnessProgramCell.H0_PX: 0.5,
        HarnessProgramCell.HX_PX: 0.9,
    }
    rewards_by_bundle_id = {
        candidate.bundle.bundle_id: rewards_by_cell[candidate.cell] for candidate in candidates.candidates
    }
    executor = HarnessProgramHarborExecutor(rewards_by_bundle_id=rewards_by_bundle_id)

    result = execute_harness_program_study(
        candidates=candidates,
        manifest=_manifest(candidates, randomization_seed=73),
        registry=registry,
        workflow=workflow,
        artifacts_root=tmp_path / "meta-harness-artifacts",
        policy_id="policy.harness-program.matched",
        harness_generator_sha256="1" * 64,
        program_generator_sha256="2" * 64,
        split="calibration",
        motif_ids=("motif.alpha", "motif.beta"),
        executor=executor,
        bootstrap_replicates=16,
        bootstrap_seed=97,
    )

    assert result.plan.repetitions == request.repetitions
    assert result.plan.trial_count == len(HarnessProgramCell) * request.repetitions
    assert tuple(item.trial for item in result.trial_executions) == result.plan.trials
    assert [call.execution_seed for call in executor.calls] == [
        request.seeds[trial.repetition - 1] for trial in result.plan.trials
    ]
    assert all(call.n_attempts == 1 for call in executor.calls)
    assert len(executor.calls) == result.plan.trial_count
    assert all(len(item.execution.harbor_invocations) == 1 for item in result.trial_executions)
    assert all(len(item.records) == 1 for item in result.trial_executions)

    candidate_by_cell = {candidate.cell: candidate for candidate in candidates.candidates}
    for item in result.trial_executions:
        expected = candidate_by_cell[item.trial.cell]
        assert item.candidate_reference == expected.reference
        assert item.execution_seed == request.seeds[item.trial.repetition - 1]
        record = item.records[0]
        provenance = record.meta_harness_provenance
        assert provenance is not None
        assert provenance.run_id == item.trial.trial_id
        assert provenance.execution_seed == item.execution_seed
        assert provenance.harness_program_cell == item.trial.cell.value
        assert provenance.paired_block_id == item.trial.block_id
        assert provenance.harness_program_plan == result.plan_artifact.reference
        assert provenance.bundle_sha256 == canonical_json_sha256(expected.bundle.model_dump(mode="json"))
        assert provenance.program_sha256 == canonical_json_sha256(expected.bundle.program.model_dump(mode="json"))
        assert provenance.motif_ids == ("motif.alpha", "motif.beta")
        assert record.execution_status is ExecutionStatus.COMPLETED
        assert record.outputs.artifacts is not None
        assert any(
            artifact.kind == "harness-program-plan" and artifact.sha256 == result.plan_artifact.reference.sha256
            for artifact in record.outputs.artifacts
        )

    assert result.plan_artifact.path.parent.name == result.plan_artifact.reference.sha256
    assert result.plan_artifact.execution_seeds == request.seeds
    encoded_plan = result.plan_artifact.path.read_bytes()
    assert hashlib.sha256(encoded_plan).hexdigest() == result.plan_artifact.reference.sha256
    plan_payload = json.loads(encoded_plan)
    assert plan_payload["plan"]["plan_sha256"] == result.plan.plan_sha256
    assert plan_payload["execution_seeds"] == list(request.seeds)
    assert tuple(outcome.trial_id for outcome in result.outcomes) == tuple(
        trial.trial_id for trial in result.plan.trials
    )
    assert result.analysis.observation_count == result.plan.trial_count
    assert result.analysis.cell_means == rewards_by_cell

    first = result.trial_executions[0]
    first_candidate = candidate_by_cell[first.trial.cell]
    first_record = first.records[0]
    assert first_record.meta_harness_provenance is not None
    tampered_record = type(first_record).model_validate(first_record.model_dump(mode="python"))
    tampered_record.bind_run_manifest(first_record.run_manifest).attach_extension(
        "meta_harness_provenance",
        first_record.meta_harness_provenance.model_copy(update={"program_id": "program.tampered"}),
    )
    with pytest.raises(ValueError, match="lineage does not match"):
        validate_harness_program_record_lineage(
            record=tampered_record,
            trial=first.trial,
            candidate=first_candidate,
            execution_seed=first.execution_seed,
            plan_artifact=result.plan_artifact.reference,
        )


def test_execute_harness_program_study_rejects_unverified_trial_records(tmp_path: Path) -> None:
    registry, tasks_root, request = _factory_inputs(tmp_path)
    candidates = materialize_harness_program_candidates(request, registry=registry, tasks_root=tasks_root)
    executor = HarnessProgramHarborExecutor(
        rewards_by_bundle_id={candidate.bundle.bundle_id: 1.0 for candidate in candidates.candidates},
        verified=False,
    )

    with pytest.raises(ValueError, match="did not complete the required Hx verifier"):
        execute_harness_program_study(
            candidates=candidates,
            manifest=_manifest(candidates, randomization_seed=73),
            registry=registry,
            workflow=_workflow(tmp_path, tasks_root),
            artifacts_root=tmp_path / "meta-harness-artifacts",
            policy_id="policy.harness-program.matched",
            harness_generator_sha256="1" * 64,
            program_generator_sha256="2" * 64,
            split="calibration",
            executor=executor,
            bootstrap_replicates=4,
        )

    assert len(executor.calls) == 1


def test_execute_harness_program_study_preserves_verifier_completed_invalid_zero_outcomes(
    tmp_path: Path,
) -> None:
    registry, tasks_root, request = _factory_inputs(tmp_path)
    candidates = materialize_harness_program_candidates(request, registry=registry, tasks_root=tasks_root)
    executor = HarnessProgramHarborExecutor(
        rewards_by_bundle_id={candidate.bundle.bundle_id: 1.0 for candidate in candidates.candidates},
        valid_output=False,
    )

    result = execute_harness_program_study(
        candidates=candidates,
        manifest=_manifest(candidates, randomization_seed=73),
        registry=registry,
        workflow=_workflow(tmp_path, tasks_root),
        artifacts_root=tmp_path / "meta-harness-artifacts",
        policy_id="policy.harness-program.matched",
        harness_generator_sha256="1" * 64,
        program_generator_sha256="2" * 64,
        split="calibration",
        executor=executor,
        bootstrap_replicates=4,
    )

    assert len(executor.calls) == result.plan.trial_count
    assert all(outcome.value == 0.0 for outcome in result.outcomes)
    assert set(result.analysis.cell_means.values()) == {0.0}
    assert all(
        record.evaluation.validity.verifier_completed
        and not record.evaluation.validity.output_parseable
        and not record.evaluation.validity.schema_valid
        and record.evaluation.reward == 0.0
        for execution in result.trial_executions
        for record in execution.records
    )


def test_execute_harness_program_study_aggregates_multi_invocation_programs_once_per_trial(tmp_path: Path) -> None:
    task_refs = ("civil/calculation/harness-program-alpha", "civil/calculation/harness-program-beta")
    registry, tasks_root, request = _factory_inputs(tmp_path, task_refs=task_refs)
    candidates = materialize_harness_program_candidates(request, registry=registry, tasks_root=tasks_root)
    executor = HarnessProgramHarborExecutor(
        rewards_by_bundle_id={candidate.bundle.bundle_id: 0.5 for candidate in candidates.candidates}
    )

    result = execute_harness_program_study(
        candidates=candidates,
        manifest=_manifest(candidates, randomization_seed=73),
        registry=registry,
        workflow=_workflow(tmp_path, tasks_root),
        artifacts_root=tmp_path / "meta-harness-artifacts",
        policy_id="policy.harness-program.multi-task",
        harness_generator_sha256="1" * 64,
        program_generator_sha256="2" * 64,
        split="calibration",
        executor=executor,
        bootstrap_replicates=4,
    )

    assert len(result.trial_executions) == 8
    assert {len(item.execution.harbor_invocations) for item in result.trial_executions} == {1, 2}
    assert all({record.task.task_id for record in item.records} == set(task_refs) for item in result.trial_executions)
    assert all(len(item.records) == 2 for item in result.trial_executions)
    assert all(call.n_attempts == 1 for call in executor.calls)
    assert len(executor.calls) == 12


def test_execute_harness_program_study_blocks_multiple_task_sets_under_one_schedule(tmp_path: Path) -> None:
    registry, tasks_root, request_alpha = _factory_inputs(
        tmp_path,
        task_refs=("civil/calculation/harness-program-alpha",),
        candidate_set_id="harness-program.alpha",
        task_set_id="task-set.alpha",
    )
    _, _, request_beta = _factory_inputs(
        tmp_path,
        task_refs=("civil/calculation/harness-program-beta",),
        candidate_set_id="harness-program.beta",
        task_set_id="task-set.beta",
    )
    alpha = materialize_harness_program_candidates(request_alpha, registry=registry, tasks_root=tasks_root)
    beta = materialize_harness_program_candidates(request_beta, registry=registry, tasks_root=tasks_root)
    executor = HarnessProgramHarborExecutor(
        rewards_by_bundle_id={
            candidate.bundle.bundle_id: 0.5 for candidate_set in (alpha, beta) for candidate in candidate_set.candidates
        }
    )

    result = execute_harness_program_study(
        candidates=(beta, alpha),
        manifest=_manifest(alpha, beta, randomization_seed=73),
        registry=registry,
        workflow=_workflow(tmp_path, tasks_root),
        artifacts_root=tmp_path / "meta-harness-artifacts",
        policy_id="policy.harness-program.multi-task-set",
        harness_generator_sha256="1" * 64,
        program_generator_sha256="2" * 64,
        split="calibration",
        executor=executor,
        bootstrap_replicates=4,
    )

    assert result.plan.trial_count == 16
    assert tuple(dict.fromkeys(block.task_set_id for block in result.plan.blocks)) == (
        "task-set.alpha",
        "task-set.beta",
    )
    assert [call.execution_seed for call in executor.calls] == [
        request_alpha.seeds[trial.repetition - 1] for trial in result.plan.trials
    ]
    assert all(call.n_attempts == 1 for call in executor.calls)
    assert result.analysis.observation_count == 16
    assert result.analysis.block_count == 4
    assert result.analysis.task_set_cluster_count == 2


@pytest.mark.parametrize(
    ("candidate_selection", "manifest_selection", "message"),
    [
        ("alpha", "both", "missing materialized harness-program task sets"),
        ("both", "alpha", "extra materialized harness-program task sets"),
        ("duplicate", "alpha", "materialized harness-program task-set ids must be unique"),
    ],
)
def test_execute_harness_program_study_rejects_inexact_manifest_task_set_coverage_before_running(
    tmp_path: Path,
    candidate_selection: str,
    manifest_selection: str,
    message: str,
) -> None:
    registry, tasks_root, request_alpha = _factory_inputs(
        tmp_path,
        task_refs=("civil/calculation/harness-program-alpha",),
        candidate_set_id="harness-program.alpha",
        task_set_id="task-set.alpha",
    )
    _, _, request_beta = _factory_inputs(
        tmp_path,
        task_refs=("civil/calculation/harness-program-beta",),
        candidate_set_id="harness-program.beta",
        task_set_id="task-set.beta",
    )
    alpha = materialize_harness_program_candidates(request_alpha, registry=registry, tasks_root=tasks_root)
    beta = materialize_harness_program_candidates(request_beta, registry=registry, tasks_root=tasks_root)
    candidate_options = {
        "alpha": (alpha,),
        "both": (alpha, beta),
        "duplicate": (alpha, alpha),
    }
    manifest_options = {
        "alpha": _manifest(alpha, randomization_seed=73),
        "both": _manifest(alpha, beta, randomization_seed=73),
    }
    executor = HarnessProgramHarborExecutor(rewards_by_bundle_id={})

    with pytest.raises(ValueError, match=message):
        execute_harness_program_study(
            candidates=candidate_options[candidate_selection],
            manifest=manifest_options[manifest_selection],
            registry=registry,
            workflow=_workflow(tmp_path, tasks_root),
            artifacts_root=tmp_path / "meta-harness-artifacts",
            policy_id="policy.harness-program.coverage",
            harness_generator_sha256="1" * 64,
            program_generator_sha256="2" * 64,
            split="calibration",
            executor=executor,
            bootstrap_replicates=4,
        )

    assert not executor.calls


def test_execute_harness_program_study_rejects_manifest_schedule_mismatch_before_running(tmp_path: Path) -> None:
    registry, tasks_root, request = _factory_inputs(tmp_path)
    candidates = materialize_harness_program_candidates(request, registry=registry, tasks_root=tasks_root)
    manifest = _manifest(candidates, randomization_seed=73, repetitions=1)
    executor = HarnessProgramHarborExecutor(rewards_by_bundle_id={})

    with pytest.raises(ValueError, match="manifest repetitions must match the shared execution seed schedule"):
        execute_harness_program_study(
            candidates=candidates,
            manifest=manifest,
            registry=registry,
            workflow=_workflow(tmp_path, tasks_root),
            artifacts_root=tmp_path / "meta-harness-artifacts",
            policy_id="policy.harness-program.schedule",
            harness_generator_sha256="1" * 64,
            program_generator_sha256="2" * 64,
            split="calibration",
            executor=executor,
            bootstrap_replicates=4,
        )

    assert not executor.calls


def test_execute_harness_program_study_rejects_cross_task_set_factor_semantic_drift_before_running(
    tmp_path: Path,
) -> None:
    registry, tasks_root, request_alpha = _factory_inputs(
        tmp_path,
        task_refs=("civil/calculation/harness-program-alpha",),
        candidate_set_id="harness-program.alpha",
        task_set_id="task-set.alpha",
    )
    _, _, request_beta = _factory_inputs(
        tmp_path,
        task_refs=("civil/calculation/harness-program-beta",),
        candidate_set_id="harness-program.beta",
        task_set_id="task-set.beta",
    )
    program_payload = request_beta.learned_program.model_dump(mode="python")
    program_payload.pop("content_sha256")
    changed_program = ProgramFactorTemplate.model_validate(program_payload | {"version": "2.0.0"})
    request_payload = request_beta.model_dump(mode="python")
    request_payload.pop("content_sha256")
    changed_request = HarnessProgramCandidateRequest.model_validate(
        request_payload | {"learned_program": changed_program}
    )
    alpha = materialize_harness_program_candidates(request_alpha, registry=registry, tasks_root=tasks_root)
    beta = materialize_harness_program_candidates(changed_request, registry=registry, tasks_root=tasks_root)
    executor = HarnessProgramHarborExecutor(rewards_by_bundle_id={})

    with pytest.raises(ValueError, match="identical four-cell factor semantics"):
        execute_harness_program_study(
            candidates=(alpha, beta),
            manifest=_manifest(alpha, beta, randomization_seed=73),
            registry=registry,
            workflow=_workflow(tmp_path, tasks_root),
            artifacts_root=tmp_path / "meta-harness-artifacts",
            policy_id="policy.harness-program.factor-drift",
            harness_generator_sha256="1" * 64,
            program_generator_sha256="2" * 64,
            split="calibration",
            executor=executor,
            bootstrap_replicates=4,
        )

    assert not executor.calls


def test_execute_harness_program_study_revalidates_reference_to_bundle_mapping(tmp_path: Path) -> None:
    registry, tasks_root, request = _factory_inputs(tmp_path)
    candidates = materialize_harness_program_candidates(request, registry=registry, tasks_root=tasks_root)
    swapped = candidates.candidates[0].model_copy(update={"bundle": candidates.candidates[1].bundle})
    tampered = candidates.model_copy(update={"candidates": (swapped, *candidates.candidates[1:])})

    with pytest.raises(ValueError, match="materialized candidate harness does not match its RunBundle"):
        execute_harness_program_study(
            candidates=tampered,
            manifest=_manifest(candidates, randomization_seed=73),
            registry=registry,
            workflow=_workflow(tmp_path, tasks_root),
            artifacts_root=tmp_path / "meta-harness-artifacts",
            policy_id="policy.harness-program.matched",
            harness_generator_sha256="1" * 64,
            program_generator_sha256="2" * 64,
            split="calibration",
            executor=HarnessProgramHarborExecutor(rewards_by_bundle_id={}),
            bootstrap_replicates=4,
        )


def _workflow(tmp_path: Path, tasks_root: Path) -> SynchronousHarborWorkflow:
    return SynchronousHarborWorkflow(
        project_root=tmp_path,
        repo_root=tmp_path,
        tasks_root=tasks_root,
        ledger_root=tmp_path / "ledger",
        jobs_root=tmp_path / "jobs",
    )


def _manifest(
    *candidate_sets: MaterializedHarnessProgramCandidateSet,
    randomization_seed: int,
    repetitions: int | None = None,
) -> HarnessProgramStudyManifest:
    first = candidate_sets[0]
    return HarnessProgramStudyManifest(
        experiment_id=first.request.experiment_id,
        randomization_seed=randomization_seed,
        repetitions=first.request.repetitions if repetitions is None else repetitions,
        candidate_sets=tuple(candidate_set.references for candidate_set in candidate_sets),
    )
