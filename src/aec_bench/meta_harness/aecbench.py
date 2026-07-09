# ABOUTME: Binds meta-harness task-run resolvers to AEC-Bench Harbor workflow APIs.
# ABOUTME: Converts imported TrialRecords into evaluator-ready task_run evidence.

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aec_bench.contracts.experiment_manifest import ExperimentManifest
from aec_bench.harness.harbor_import import import_harbor_trial
from aec_bench.harness.harbor_workflow import SynchronousHarborWorkflow


@dataclass(frozen=True)
class AecBenchWorkflowConfig:
    project_root: Path
    repo_root: Path | None = None
    tasks_root: Path | None = None
    ledger_root: Path | None = None
    jobs_root: Path | None = None
    config_path: Path | None = None

    def resolved_repo_root(self) -> Path:
        return self.repo_root or self.project_root

    def resolved_tasks_root(self) -> Path:
        return self.tasks_root or self.resolved_repo_root() / "tasks"

    def resolved_ledger_root(self) -> Path:
        return self.ledger_root or self.resolved_repo_root() / "ledger"

    def resolved_jobs_root(self) -> Path:
        return self.jobs_root or self.project_root / "jobs"

    def resolved_config_path(self, experiment_id: str) -> Path:
        return self.config_path or self.project_root / f".aec-bench-{experiment_id}.yaml"


def build_aecbench_harbor_task_run_resolver(
    *,
    manifest: ExperimentManifest | dict[str, Any],
    workflow_config: AecBenchWorkflowConfig,
    executor: Any | None = None,
    progress_callback: Callable[[Any], None] | None = None,
    reviewer_config: Any | None = None,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    resolved_manifest = _coerce_manifest(manifest)

    def resolve(runtime_result: dict[str, Any]) -> dict[str, Any]:
        workflow_result = run_aecbench_harbor_workflow(
            manifest=resolved_manifest,
            workflow_config=workflow_config,
            executor=executor,
            progress_callback=progress_callback,
            reviewer_config=reviewer_config,
        )
        return aecbench_workflow_result_to_task_run(
            workflow_result,
            runtime_result=runtime_result,
        )

    return resolve


def run_aecbench_harbor_workflow(
    *,
    manifest: ExperimentManifest | dict[str, Any],
    workflow_config: AecBenchWorkflowConfig,
    executor: Any | None = None,
    progress_callback: Callable[[Any], None] | None = None,
    reviewer_config: Any | None = None,
) -> Any:
    resolved_manifest = _coerce_manifest(manifest)
    workflow = SynchronousHarborWorkflow(
        project_root=workflow_config.project_root,
        repo_root=workflow_config.resolved_repo_root(),
        tasks_root=workflow_config.resolved_tasks_root(),
        ledger_root=workflow_config.resolved_ledger_root(),
        jobs_root=workflow_config.resolved_jobs_root(),
    )
    return workflow.run(
        manifest=resolved_manifest,
        config_path=workflow_config.resolved_config_path(resolved_manifest.experiment_id),
        executor=executor,
        progress_callback=progress_callback,
        reviewer_config=reviewer_config,
    )


def import_aecbench_harbor_trial_to_task_run(
    *,
    trial_dir: Path,
    repo_root: Path,
    runtime_result: dict[str, Any] | None = None,
    experiment_id: str | None = None,
    dataset_id: str | None = None,
) -> dict[str, Any]:
    record = import_harbor_trial(
        trial_dir=trial_dir,
        repo_root=repo_root,
        experiment_id=experiment_id,
        dataset_id=dataset_id,
    )
    return aecbench_trial_record_to_task_run(
        record,
        runtime_result=runtime_result,
        artifact_refs={"trial_dir": str(trial_dir)},
    )


def aecbench_workflow_result_to_task_run(
    workflow_result: Any,
    *,
    runtime_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    import_result = workflow_result.import_result
    trial_records = _read_trial_record_payloads(import_result.output_paths)
    evidence = {
        "score": _score_from_trial_records(trial_records, import_result),
        "artifacts": {
            "job_dir": str(workflow_result.job_dir),
            "ledger_records": [str(path) for path in import_result.output_paths],
            "config_path": str(workflow_result.dispatch.config_path),
        },
        "aecbench": {
            "workflow": "SynchronousHarborWorkflow",
            "experiment_id": import_result.experiment_id,
            "selected_task_count": import_result.selected_task_count,
            "planned_trial_count": import_result.planned_trial_count,
            "discovered_trials": import_result.discovered_trials,
            "imported_trials": import_result.imported_trials,
            "duplicate_trials": import_result.duplicate_trials,
            "invalid_trials": import_result.invalid_trials,
            "unexpected_task_ids": list(import_result.unexpected_task_ids),
            "unexpected_agents": list(import_result.unexpected_agents),
            "unexpected_backends": list(import_result.unexpected_backends),
            "command": list(workflow_result.dispatch.command),
            "reviewer": _reviewer_payload(workflow_result.reviewer_result),
        },
        "trial_records": trial_records,
    }
    _attach_agentic_review_if_present(evidence, trial_records)
    return {
        "run_id": _workflow_run_id(runtime_result, import_result.experiment_id),
        "evidence": evidence,
    }


def aecbench_trial_record_to_task_run(
    record: Any,
    *,
    runtime_result: dict[str, Any] | None = None,
    artifact_refs: dict[str, str] | None = None,
) -> dict[str, Any]:
    payload = _model_payload(record)
    evidence = {
        "score": _score_from_record_payload(payload),
        "artifacts": copy.deepcopy(artifact_refs or {}),
        "aecbench": {
            "trial_id": payload.get("trial_id"),
            "experiment_id": payload.get("experiment_id"),
            "task_id": _path_get(payload, ["task", "task_id"]),
            "agent_model": _path_get(payload, ["agent", "model"]),
            "compute_backend": _path_get(payload, ["environment", "compute_backend"]),
        },
        "trial_records": [payload],
    }
    _attach_agentic_review_if_present(evidence, [payload])
    return {
        "run_id": _trial_run_id(runtime_result, payload),
        "evidence": evidence,
    }


def _coerce_manifest(manifest: ExperimentManifest | dict[str, Any]) -> ExperimentManifest:
    if isinstance(manifest, ExperimentManifest):
        return manifest
    return ExperimentManifest.model_validate(manifest)


def _read_trial_record_payloads(paths: list[Path]) -> list[dict[str, Any]]:
    payloads = []
    for path in paths:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads


def _score_from_trial_records(
    records: list[dict[str, Any]],
    import_result: Any,
) -> dict[str, Any]:
    rewards = [
        float(reward)
        for reward in (_path_get(record, ["evaluation", "reward"]) for record in records)
        if isinstance(reward, int | float) and not isinstance(reward, bool)
    ]
    score: dict[str, Any] = {
        "passed": (
            import_result.discovered_trials > 0
            and import_result.invalid_trials == 0
            and not import_result.unexpected_task_ids
            and not import_result.unexpected_backends
            and (import_result.imported_trials + import_result.duplicate_trials) == import_result.discovered_trials
        )
    }
    if rewards:
        score["reward"] = sum(rewards) / len(rewards)
    return score


def _score_from_record_payload(payload: dict[str, Any]) -> dict[str, Any]:
    reward = _path_get(payload, ["evaluation", "reward"])
    if isinstance(reward, int | float) and not isinstance(reward, bool):
        return {"reward": float(reward), "passed": float(reward) >= 1.0}
    return {}


def _reviewer_payload(reviewer_result: Any | None) -> dict[str, Any] | None:
    if reviewer_result is None:
        return None
    if hasattr(reviewer_result, "to_dict"):
        return reviewer_result.to_dict()
    if hasattr(reviewer_result, "model_dump"):
        return reviewer_result.model_dump(mode="json")
    if hasattr(reviewer_result, "__dict__"):
        return dict(reviewer_result.__dict__)
    return None


def _attach_agentic_review_if_present(
    evidence: dict[str, Any],
    records: list[dict[str, Any]],
) -> None:
    for record in records:
        reviewer = _path_get(record, ["evaluation", "breakdown", "llm_reviewer"])
        if isinstance(reviewer, dict):
            evidence["agentic_review"] = copy.deepcopy(reviewer)
            return


def _model_payload(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        payload = value.model_dump(mode="json")
    elif hasattr(value, "dict"):
        payload = value.dict()
    elif isinstance(value, dict):
        payload = value
    else:
        raise TypeError(f"unsupported AEC-Bench record type: {type(value).__name__}")
    if not isinstance(payload, dict):
        raise TypeError("AEC-Bench record payload must be a dictionary")
    return copy.deepcopy(payload)


def _workflow_run_id(
    runtime_result: dict[str, Any] | None,
    experiment_id: str,
) -> str:
    process_id = (runtime_result or {}).get("process_id")
    if isinstance(process_id, str) and process_id:
        return f"{process_id}.{experiment_id}"
    return f"{experiment_id}.aecbench"


def _trial_run_id(
    runtime_result: dict[str, Any] | None,
    payload: dict[str, Any],
) -> str:
    trial_id = payload.get("trial_id") or "trial"
    process_id = (runtime_result or {}).get("process_id")
    if isinstance(process_id, str) and process_id:
        return f"{process_id}.{trial_id}"
    return str(trial_id)


def _path_get(payload: dict[str, Any], path: list[str]) -> Any:
    current: Any = payload
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current
