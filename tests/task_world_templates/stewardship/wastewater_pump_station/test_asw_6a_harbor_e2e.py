# ABOUTME: Runs the ASW-6A evidence-health journey through direct and local Harbor paths.
# ABOUTME: Proves public-state parity, handover privacy, tool binding, and independent replay.

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

import pytest
from harbor.models.trial.config import TrialConfig  # type: ignore[import-untyped]
from harbor.trial.trial import Trial  # type: ignore[import-untyped]
from test_asw_5_rich_work_e2e import _execute_direct

from aec_bench.contracts.world_session import (
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
    PUMP_STATION_EVIDENCE_HEALTH_TOOL_NAMES,
    PUMP_STATION_EVIDENCE_TREATMENT_VERSION_V1,
    PUMP_STATION_EVIDENCE_VISIBILITY_POLICY_V1,
    PUMP_STATION_TASK_WORLD_ID,
    PumpStationEvidenceTreatmentClass,
    PumpStationEvidenceTreatmentRequest,
    PumpStationWorldSession,
    PumpStationWorldSessionFactory,
    create_structured_handover,
    pump_station_artifact_bytes,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_export import (
    PUMP_STATION_HARBOR_BRIDGE_MODE,
    PUMP_STATION_HARBOR_EXECUTION_KIND,
    export_pump_station_harbor_task,
    load_pump_station_harbor_bridge,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_session import (
    PUMP_STATION_REFERENCE_CONTROLLER_ID,
    run_pump_station_evidence_health_reference_session,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_verifier import (
    _verify_stewardship_objective,
    verify_pump_station_harbor_run,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_verifier import (
    PumpStationVerificationReport,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_control import (
    PumpStationEvidenceControlRequest,
    PumpStationEvidenceControlResult,
    PumpStationWorldControl,
)

PROJECT_ROOT = Path(__file__).resolve().parents[4]


def _start_request(identity: str) -> WorldSessionRequest:
    return WorldSessionRequest(
        execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
        open_mode=WorldSessionOpenMode.START,
        session_id=f"session.{identity}",
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        agent_tenure_id=f"tenure.{identity}",
        run_id=f"run.{identity}",
        episode_id=f"episode.{identity}",
        world_branch_id=f"branch.{identity}",
    )


def _run_direct_evidence_health_journey(
    root: Path,
    identity: str,
) -> PumpStationWorldSession:
    start = _start_request(identity)
    factory = PumpStationWorldSessionFactory(root, evidence_health=True)
    first = factory.open(start)
    snapshot = first.run.snapshot()
    decision_point = min(
        event.scheduled_seconds
        for event in first.run.state.scheduled_events
        if event.event_type.value == "decision_point"
    )
    treatment = PumpStationEvidenceTreatmentRequest(
        request_id="treatment-reference-calibration",
        run_id=snapshot.run_id,
        episode_id=snapshot.episode_id,
        world_branch_id=snapshot.world_branch_id,
        base_state_id=snapshot.state_id,
        base_commit_id=snapshot.commit_id,
        based_on_sequence=snapshot.sequence,
        treatment_class=PumpStationEvidenceTreatmentClass.CALIBRATION_LAPSE,
        treatment_version=PUMP_STATION_EVIDENCE_TREATMENT_VERSION_V1,
        target_source_id="station-condition-sensor",
        effective_decision_point_seconds=decision_point,
        visibility_policy=PUMP_STATION_EVIDENCE_VISIBILITY_POLICY_V1,
    )
    scheduled = PumpStationWorldControl(
        root,
        authorised_principal_ids=("harbor-evidence-control",),
        evidence_health=True,
    ).execute(
        PumpStationEvidenceControlRequest(
            request_id=treatment.request_id,
            operation="schedule_evidence_treatment",
            task_world_id=PUMP_STATION_TASK_WORLD_ID,
            authority_id="harbor-evidence-control",
            treatment_request=treatment,
        )
    )
    assert isinstance(scheduled, PumpStationEvidenceControlResult)
    scheduled_snapshot = scheduled.receipt.result_snapshot
    assert scheduled_snapshot is not None
    activation = factory.open(
        WorldSessionRequest(
            execution_kind=start.execution_kind,
            open_mode=WorldSessionOpenMode.RESUME,
            session_id=f"session.{identity}.activation",
            task_world_id=start.task_world_id,
            agent_tenure_id=start.agent_tenure_id,
            run_id=start.run_id,
            episode_id=start.episode_id,
            world_branch_id=start.world_branch_id,
            start_snapshot=scheduled_snapshot,
        )
    )
    activation.continue_operation(
        "proposal-reference-activation",
        "Continue to the declared evidence-health decision point.",
    )
    recipient = factory.open(
        WorldSessionRequest(
            execution_kind=start.execution_kind,
            open_mode=WorldSessionOpenMode.RESUME,
            session_id=f"session.{identity}.handover",
            task_world_id=start.task_world_id,
            agent_tenure_id=f"tenure.{identity}.handover",
            run_id=start.run_id,
            episode_id=start.episode_id,
            world_branch_id=start.world_branch_id,
            start_snapshot=activation.result.snapshot,
        )
    )
    recipient.install_structured_handover(
        create_structured_handover(
            recipient.actor_view,
            from_tenure_id=start.agent_tenure_id,
            history=activation.actor_history,
            maximum_history_entries=8,
        )
    )
    recipient.request_condition_check(
        "proposal-reference-condition-check",
        "Record the visible sensor condition after handover.",
        "pump-a",
    )
    recipient.request_inspection(
        "proposal-reference-physical-inspection",
        "Request the separate physical inspection after the sensor check.",
        "pump-b",
    )
    return recipient


def _current_state(session: PumpStationWorldSession) -> dict[str, Any]:
    payload = json.loads(session.observe_pump_station())
    return cast(dict[str, Any], payload["current_state"])


def test_evidence_health_reference_has_direct_and_harbor_parity(
    tmp_path: Path,
) -> None:
    identity = "evidence-health-parity"
    direct = _run_direct_evidence_health_journey(tmp_path / "direct", identity)
    task_dir = tmp_path / "tasks" / "stewardship" / "wastewater-pump-station"
    exported = export_pump_station_harbor_task(
        task_dir,
        project_root=PROJECT_ROOT,
        evidence_health=True,
    )
    bridge = load_pump_station_harbor_bridge(task_dir / "environment")
    harbor = run_pump_station_evidence_health_reference_session(
        bridge=bridge,
        output_dir=tmp_path / "harbor",
        session_identity=identity,
    )
    verified = verify_pump_station_harbor_run(
        run_dir=harbor.output_dir,
        export_manifest_path=exported.manifest_path,
        package_dir=exported.package_dir,
    )
    resumed = PumpStationWorldSessionFactory(
        harbor.output_dir / "world-run",
        package_root=exported.package_dir,
        evidence_health=True,
    ).open(
        WorldSessionRequest(
            execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
            open_mode=WorldSessionOpenMode.RESUME,
            session_id="session.harbor-review",
            task_world_id=PUMP_STATION_TASK_WORLD_ID,
            agent_tenure_id="tenure.harbor-review",
            run_id=harbor.result.snapshot.run_id,
            episode_id=harbor.result.snapshot.episode_id,
            world_branch_id=harbor.result.snapshot.world_branch_id,
            start_snapshot=harbor.result.snapshot,
        )
    )

    assert harbor.result.tool_names == PUMP_STATION_EVIDENCE_HEALTH_TOOL_NAMES
    assert verified["valid"] is True
    assert harbor.result.snapshot.sequence == direct.result.snapshot.sequence
    assert harbor.result.snapshot.state_id == direct.result.snapshot.state_id
    assert _current_state(resumed) == _current_state(direct)
    assert _current_state(resumed)["observation_source"]["quality"] == "suspect"
    assert _current_state(resumed)["evidence"][-1]["quality"] == "suspect"
    assert any(
        item["kind"] == "inspection" and item["pump_id"] == "pump-b" for item in _current_state(resumed)["processes"]
    )
    history_text = json.dumps(
        [asdict(item) for item in resumed.actor_history],
        sort_keys=True,
    )
    handover = create_structured_handover(
        resumed.actor_view,
        from_tenure_id=harbor.request.agent_tenure_id,
        history=resumed.actor_history,
        maximum_history_entries=8,
    )
    handover_bytes = pump_station_artifact_bytes(handover)
    assert "treatment-reference-calibration" not in history_text
    assert "treatment_class" not in history_text
    assert len(resumed.actor_history) == 3
    assert handover.current_actor_view.current_state == resumed.actor_view.current_state
    assert b'"observation_source"' in handover_bytes
    assert b'"quality":"suspect"' in handover_bytes
    assert b"treatment_class" not in handover_bytes
    assert b"effective_decision_point_seconds" not in handover_bytes
    assert b"refresh_enabled" not in handover_bytes


def test_local_harbor_trial_selects_the_evidence_health_reference(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    exported = export_pump_station_harbor_task(
        repo_root / "tasks" / "stewardship" / "wastewater-pump-station",
        project_root=PROJECT_ROOT,
        evidence_health=True,
    )
    trial_name = "pump-station-evidence-health"
    config = TrialConfig.model_validate(
        {
            "task": {"path": str(exported.task_dir)},
            "trial_name": trial_name,
            "trials_dir": str(repo_root / "jobs" / "evidence-health"),
            "job_id": "7e2ac8b0-4b5f-4b6e-93b5-4add12025d9a",
            "agent": {
                "name": "pump-station-reference-controller",
                "import_path": "agents.entrypoint_agent:EntrypointAgent",
                "model_name": PUMP_STATION_REFERENCE_CONTROLLER_ID,
                "kwargs": {
                    "adapter": "tool_loop",
                    "execution_kind": PUMP_STATION_HARBOR_EXECUTION_KIND,
                    "world_session": {
                        "bridge_mode": PUMP_STATION_HARBOR_BRIDGE_MODE,
                    },
                },
            },
            "environment": {
                "import_path": ("tests.support.harbor_local_environment:LocalFilesystemHarborEnvironment"),
                "delete": False,
                "kwargs": {"compute_backend": "local"},
            },
            "artifacts": [
                {
                    "source": "/workspace/world-session",
                    "destination": "agent/world-session",
                },
                {
                    "source": "/workspace/output.md",
                    "destination": "agent/output.md",
                },
            ],
        }
    )

    result = asyncio.run(Trial(config).run())

    assert result.exception_info is None
    assert result.agent_result is not None
    assert result.agent_result.n_input_tokens == 0
    assert result.agent_result.n_output_tokens == 0
    assert result.agent_result.metadata["world_session_status"] == "completed"
    assert result.verifier_result is not None
    assert result.verifier_result.rewards == {"reward": 1.0}
    trial_dir = config.trials_dir / trial_name
    world_session_dir = next(
        candidate
        for candidate in (
            trial_dir / "agent" / "world-session",
            trial_dir / "artifacts" / "agent" / "world-session",
        )
        if candidate.exists()
    )
    inventory = json.loads((world_session_dir / "artifact-inventory.json").read_text(encoding="utf-8"))
    assert inventory["tool_names"] == list(PUMP_STATION_EVIDENCE_HEALTH_TOOL_NAMES)
    assert inventory["transition_count"] == 4


def test_version_three_rich_work_records_health_for_each_completed_evidence(
    tmp_path: Path,
) -> None:
    completed = _execute_direct(
        PumpStationWorldSessionFactory(
            tmp_path / "rich-evidence-health",
            evidence_health=True,
        )
    )

    assert completed.verify().valid is True
    assert all(item.health is not None for item in completed.run.state.evidence)
    visible_evidence = _current_state(completed)["evidence"]
    assert all(
        {
            "observed_at_seconds",
            "produced_at_seconds",
            "available_at_seconds",
            "age_seconds",
            "source_id",
            "component_scope",
            "baseline_id",
            "operating_regime_id",
            "accepted",
            "quality",
        }.issubset(item)
        for item in visible_evidence
    )


def test_evidence_health_verifier_requires_both_inspection_paths() -> None:
    report = PumpStationVerificationReport(
        valid=True,
        issues=(),
        replayed_transition_ids=(),
        final_state_id="state-after-evidence-health",
        active_restriction_ids=(),
        open_obligation_ids=(),
    )
    actor_view = {
        "current_state": {
            "observation_source": {"quality": "suspect"},
            "evidence": [
                {
                    "kind": "condition_check",
                    "quality": "suspect",
                }
            ],
            "processes": [],
            "work_orders": [],
        }
    }

    with pytest.raises(ValueError, match="objective is incomplete"):
        _verify_stewardship_objective(
            actor_view=actor_view,
            report=report,
            transition_count=4,
            rich_work_processes=True,
            evidence_health=True,
        )
