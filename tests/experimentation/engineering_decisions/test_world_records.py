# ABOUTME: Exercises experiment planning, normal trial records, and portable world evidence.
# ABOUTME: Checks negative controls, deterministic reproduction, and action-limit failures.

import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from aec_bench import worlds
from aec_bench.contracts.trial_record import EvidenceStatus, ExecutionStatus
from aec_bench.experimentation.engineering_decisions.dam_investigation import run_dam_experiment
from aec_bench.experimentation.engineering_decisions.definitions import DamExperiment, PumpExperiment
from aec_bench.experimentation.engineering_decisions.pump_continuation import run_pump_experiment
from aec_bench.experimentation.engineering_decisions.records import diagnostics
from aec_bench.worlds.monitoring.dam_seepage.definition import DamSeepageProfile
from aec_bench.worlds.monitoring.dam_seepage.investigation import investigation_scenarios
from aec_bench.worlds.monitoring.dam_seepage.world import DAM_SEEPAGE_TASK_WORLD_ID


def test_costed_profiles_resolve_exact_authored_scenarios() -> None:
    for scenario in investigation_scenarios():
        task = worlds.task(DAM_SEEPAGE_TASK_WORLD_ID, profile=scenario.profile_id, instruction="Investigate.")
        loaded = worlds.load_profile(task).value
        assert isinstance(loaded, DamSeepageProfile)
        assert loaded.scenario == scenario


def test_saved_dam_definition_reproduces_results_and_retains_failed_controls(tmp_path: Path) -> None:
    definition = DamExperiment(profiles=("investigation-urgent-fault",))
    first = run_dam_experiment(tmp_path / "first", definition)
    saved = json.loads((tmp_path / "first" / "experiment.json").read_text())
    second = run_dam_experiment(tmp_path / "second", DamExperiment.model_validate(saved["definition"]))
    assert [r.trial_id for r in first] == [r.trial_id for r in second]
    assert all(r.evaluation is not None for r in first)
    assert [r.evaluation for r in first] == [r.evaluation for r in second]
    assert [r.evaluation.reward for r in first if r.evaluation is not None] == [1.0, 0.0, 0.0]
    for record in first:
        assert record.output is not None and record.evaluation is not None
        assert record.evidence_status is EvidenceStatus.VERIFIED
        assert record.authority_evidence
        assert record.output.artifact_path("experiment_definition")
        assert record.output.artifact_path("source_digests")
        report = diagnostics(record)
        assert record.evaluation.breakdown == report["evaluation"]
        assert report["replay_valid"]
    with pytest.raises(ValueError, match="empty"):
        run_dam_experiment(tmp_path / "first", definition)


def test_action_limit_is_recorded_as_incomplete_execution(tmp_path: Path) -> None:
    dam = run_dam_experiment(
        tmp_path / "dam",
        DamExperiment(
            profiles=("investigation-routine",),
            policies=("evidence_first",),
            max_actions=1,
        ),
    )[0]
    assert dam.output is not None and dam.evaluation is not None
    assert dam.execution_status is ExecutionStatus.FAILED
    assert dam.output.truncated
    assert dam.evaluation.reward == 0
    assert dam.evidence_status is EvidenceStatus.VERIFIED
    pump = run_pump_experiment(tmp_path / "pump", PumpExperiment(max_actions=1, omit_verification_work=(False,)))[0]
    assert pump.output is not None and pump.evaluation is not None
    assert pump.execution_status is ExecutionStatus.FAILED
    assert pump.output.truncated
    assert pump.evaluation.reward == 0
    report = diagnostics(pump)
    assert report["actor_actions"] == 1
    assert not report["horizon_reached"]
    assert report["closing_calendar_seconds"] < report["horizon_seconds"]
    assert pump.evidence_status is EvidenceStatus.VERIFIED
    archive = pump.output.artifact_path("world_run")
    assert archive is not None
    restored = tmp_path / "restored-world"
    with ZipFile(archive) as bundle:
        bundle.extractall(restored)
    # Archive extraction must restore the host-private permissions required by the byte store.
    for path in restored.rglob("*"):
        path.chmod(0o700 if path.is_dir() else 0o600)
    from aec_bench.worlds.stewardship.wastewater_pump_station.world_run import PumpStationWorldRun
    from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_repository import PumpStationWorldRunRepository

    repository = PumpStationWorldRunRepository(restored)
    run = PumpStationWorldRun.resume_reference_system(repository=repository, snapshot=repository.current_snapshot())
    assert run.verify().valid
