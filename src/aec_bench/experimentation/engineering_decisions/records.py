# ABOUTME: Publishes deterministic world experiment results through the normal trial ledger.
# ABOUTME: Retains declared plans and actual world evidence without impersonating a model provider.

import json
import platform
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.authority_evidence import AuthorityEvidenceKind
from aec_bench.contracts.evaluation_result import EvaluationResult
from aec_bench.contracts.trial_record import (
    AgentConfiguration,
    AuthorityExpectation,
    CostRecord,
    EvaluationStatus,
    EvidenceStatus,
    ExecutionEnvironmentRef,
    ExecutionStatus,
    ProviderRoute,
    RunManifest,
    TimingRecord,
    TrialInput,
    TrialOutput,
    TrialRecord,
    UnresolvedSourceRef,
)
from aec_bench.contracts.validators import StrictModel
from aec_bench.trials import PlannedTrial, planned_trial_to_data
from aec_bench.worlds.tasks import WorldTask


def write_plan(output: Path, definition: StrictModel, trials: list[PlannedTrial]) -> None:
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("experiment output must be empty")
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    (output / "experiment.json").write_text(
        json.dumps(
            {
                "definition": definition.model_dump(mode="json"),
                "trials": [planned_trial_to_data(trial) for trial in trials],
                "scope": "deterministic synthetic controls; no model performance or training",
                "acceptance_sealed": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def world_record(
    *,
    task: WorldTask,
    trial: PlannedTrial,
    evaluation: EvaluationResult,
    evidence: dict[str, Any],
    evidence_file: Path,
    started_at: datetime,
    completed_at: datetime,
    terminated: bool,
) -> TrialRecord:
    """Translate observed task results; world semantics and evaluation stay with their owners."""
    evidence_file.parent.mkdir(parents=True, exist_ok=True)
    evidence_file.write_text(
        json.dumps(
            {
                "world": asdict(task.world),
                "profile": asdict(task.profile),
                **evidence,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    manifest = RunManifest(
        run_id=trial.trial_id,
        experiment_id=trial.experiment_id,
        source=UnresolvedSourceRef(reason="deterministic control run has no retained library source reference"),
        agent=AgentConfiguration(
            adapter=trial.agent.adapter, model=trial.agent.model, configuration=trial.agent.parameters
        ),
        execution_environment=ExecutionEnvironmentRef(
            runtime_image=f"python:{platform.python_version()}", compute_backend=trial.compute.backend
        ),
        provider_route=ProviderRoute(provider="aec-bench", route="deterministic-control"),
        expected_authorities=(
            AuthorityExpectation(
                authority_kind=AuthorityEvidenceKind.WORLD, protocol="aec-bench/deterministic-world-trial/1"
            ),
        ),
    )
    record = TrialRecord(
        trial_id=trial.trial_id,
        run_id=manifest.run_id,
        task_id=task.task_id,
        execution_status=ExecutionStatus.COMPLETED if terminated else ExecutionStatus.FAILED,
        evaluation_status=EvaluationStatus.COMPLETED,
        evidence_status=EvidenceStatus.PENDING,
        started_at=started_at,
        completed_at=completed_at,
        input=TrialInput(
            instruction=task.instruction,
            task_revision=task.task_revision,
            task_kind="world",
            visibility=task.visibility,
        ),
        output=TrialOutput(
            agent_output=AgentOutput(
                status=AgentOutputStatus.COMPLETED if terminated else AgentOutputStatus.PARTIAL,
                output_path="world-evidence.json",
                output_format="json",
            ),
            agent_result={"controller": trial.agent.name},
            terminated=terminated,
            truncated=not terminated,
            final_reason="declared control completed" if terminated else "action limit reached",
        ),
        evaluation=evaluation,
        timing=TimingRecord(total_seconds=max(0.0, (completed_at - started_at).total_seconds())),
        cost=CostRecord(model_calls=0, tokens_in=0, tokens_out=0, estimated_cost_usd=0.0),
    ).bind_run_manifest(manifest)
    record.attach_artifact(
        "authority:world:aec-bench/deterministic-world-trial/1", evidence_file, media_type="application/json"
    )
    return record


def publish_record(output: Path, record: TrialRecord) -> TrialRecord:
    from aec_bench.ledger.reader import read_trial_record
    from aec_bench.ledger.writer import write_trial_record

    record.attach_artifact("experiment_definition", output / "experiment.json", media_type="application/json")
    ledger = output / "ledger"
    path = write_trial_record(ledger_root=ledger, record=record)
    return read_trial_record(path, ledger_root=ledger)


def diagnostics(record: TrialRecord) -> dict[str, Any]:
    if "experiment_diagnostics" in record.pending_artifacts:
        path = record.pending_artifacts["experiment_diagnostics"][0]
    else:
        if record.output is None:
            raise ValueError("trial output is missing")
        located = record.output.artifact_path("experiment_diagnostics")
        if located is None:
            raise ValueError("experiment diagnostics are missing")
        path = Path(located)
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError("experiment diagnostics must be an object")
    return payload
