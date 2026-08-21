# ABOUTME: Runs one pump-station Harbor transport and returns the normal world TrialRecord contract.
# ABOUTME: Composes existing export, dispatch, verification, and strict import operations.

from __future__ import annotations

from pathlib import Path

from aec_bench.contracts.trial_record import AgentConfiguration, RunManifest, TrialInput, TrialRecord
from aec_bench.harness.harbor_importing.core import import_harbor_trial
from aec_bench.harness.pump_station_harbor.export import export_pump_station_harbor_task
from aec_bench.harness.pump_station_harbor.importing import load_pump_station_import_evidence
from aec_bench.harness.pump_station_harbor.job import run_pump_station_harbor_job
from aec_bench.trials import PlannedTrial
from aec_bench.worlds.stewardship.wastewater_pump_station.episode_runtime import (
    PUMP_STATION_TASK_WORLD_ID,
)
from aec_bench.worlds.tasks import WorldTask


async def run_pump_station_harbor_trial(
    task: WorldTask,
    trial: PlannedTrial,
    *,
    work_root: Path,
) -> TrialRecord:
    """Export, run, verify, and import one Harbor pump-station trial."""

    if task.world.task_world_id != PUMP_STATION_TASK_WORLD_ID:
        raise ValueError("pump-station Harbor trial requires the registered pump world")
    if trial.task_id != task.task_id:
        raise ValueError("pump-station Harbor trial plan does not match the task")
    if trial.agent.adapter not in {"deepseek_harness", "tool_loop"}:
        raise ValueError(f"unsupported pump-station Harbor adapter: {trial.agent.adapter}")
    root = Path(work_root).resolve()
    if root.exists():
        raise FileExistsError(f"pump-station Harbor work root already exists: {root}")
    root.mkdir(parents=True)
    project_root = Path(__file__).resolve().parents[4]
    exported = export_pump_station_harbor_task(
        root / "task",
        project_root=project_root,
        profile_ref=task.profile,
    )
    parameters = trial.agent.parameters
    dispatch = run_pump_station_harbor_job(
        task_dir=exported.task_dir,
        project_root=project_root,
        jobs_dir=root / "jobs",
        config_path=root / "harbor.yaml",
        backend=trial.compute.backend,
        model_name=trial.agent.model,
        adapter=trial.agent.adapter,
        max_turns=int(parameters.get("max_turns", 20)),
        max_world_actions=int(parameters.get("max_world_actions", 100)),
        max_tokens=(int(parameters.get("max_tokens", 20_000)) if trial.agent.adapter == "deepseek_harness" else None),
        timeout_sec=(
            int(parameters["timeout_sec"])
            if trial.agent.adapter == "deepseek_harness" and "timeout_sec" in parameters
            else None
        ),
        execute=True,
    )
    if dispatch.exit_code != 0:
        raise RuntimeError(f"pump-station Harbor execution failed with exit code {dispatch.exit_code}")
    result_files = sorted((root / "jobs").rglob("result.json"))
    if len(result_files) != 1:
        raise RuntimeError("pump-station Harbor execution must produce exactly one trial result")
    imported = import_harbor_trial(
        trial_dir=result_files[0].parent,
        repo_root=project_root,
        experiment_id=trial.experiment_id,
        evidence_loader=load_pump_station_import_evidence,
    )
    manifest = imported.run_manifest
    run_id = ":".join((trial.experiment_id, trial.agent.adapter, trial.agent.model, trial.compute.backend))
    imported.trial_id = trial.trial_id
    imported.run_id = run_id
    imported.task_id = task.task_id
    imported.input = TrialInput(
        instruction=task.instruction,
        task_revision=task.task_revision,
        task_kind="world",
        visibility=task.visibility,
        system_prompt=trial.agent.system_prompt,
        input_files=imported.input.input_files,
    )
    return imported.bind_run_manifest(
        RunManifest(
            **{
                **manifest.model_dump(mode="python"),
                "run_id": run_id,
                "experiment_id": trial.experiment_id,
                "agent": AgentConfiguration(
                    adapter=trial.agent.adapter,
                    model=trial.agent.model,
                    configuration={"imported_model": manifest.agent.model},
                ),
            }
        )
    )


__all__ = ("run_pump_station_harbor_trial",)
