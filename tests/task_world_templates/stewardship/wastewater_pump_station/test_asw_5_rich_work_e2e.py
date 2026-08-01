# ABOUTME: Runs the complete rich-work scenario through direct and local Harbor paths.
# ABOUTME: Proves interruption, fresh-tenure handover, resume, replay, and path parity.

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from harbor.models.trial.config import TrialConfig  # type: ignore[import-untyped]
from harbor.trial.trial import Trial  # type: ignore[import-untyped]

from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.contracts.world_session import (
    StewardshipStateSnapshotRef,
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
)
from aec_bench.evaluation.stewardship import (
    evaluate_pump_station_stewardship_run,
)
from aec_bench.harness.harbor_importing.core import import_harbor_trial
from aec_bench.harness.world_session import open_world_session
from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
    PUMP_STATION_RICH_WORK_TOOL_NAMES,
    PUMP_STATION_TASK_WORLD_ID,
    PumpStationProcessStatus,
    PumpStationWorldSession,
    PumpStationWorldSessionFactory,
    create_structured_handover,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_export import (
    PUMP_STATION_HARBOR_BRIDGE_MODE,
    PUMP_STATION_HARBOR_EXECUTION_KIND,
    export_pump_station_harbor_task,
    load_pump_station_harbor_bridge,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_session import (
    PUMP_STATION_REFERENCE_CONTROLLER_ID,
    _model_instruction,
    _model_system_prompt,
    run_pump_station_rich_work_reference_session,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_verifier import (
    verify_pump_station_harbor_run,
)

JsonObject = dict[str, Any]


def test_rich_work_model_contract_uses_the_rich_world_goal() -> None:
    rich_system = _model_system_prompt(rich_work_processes=True)
    rich_instruction = _model_instruction(rich_work_processes=True)
    legacy_instruction = _model_instruction(rich_work_processes=False)

    assert "blocked, active, or suspended" in rich_system
    assert "post-maintenance verification for pump-a" in rich_instruction
    assert "inspection for pump-b" in rich_instruction
    assert "resume" in rich_instruction
    assert "conditionally defer pump-a" not in rich_instruction
    assert "conditionally defer pump-a" in legacy_instruction


def _request(
    *,
    open_mode: WorldSessionOpenMode,
    tenure_id: str,
    snapshot: StewardshipStateSnapshotRef | None = None,
) -> WorldSessionRequest:
    return WorldSessionRequest(
        execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
        open_mode=open_mode,
        session_id=f"session.{tenure_id}",
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        agent_tenure_id=tenure_id,
        run_id="run-rich-e2e",
        episode_id="episode-rich-e2e",
        world_branch_id="branch-rich-e2e",
        start_snapshot=snapshot,
    )


def _current_payload(session: PumpStationWorldSession) -> JsonObject:
    document = cast(JsonObject, json.loads(session.observe_pump_station()))
    return cast(JsonObject, document["current_state"])


def _process(payload: JsonObject, kind: str, pump_id: str) -> JsonObject:
    processes = cast(list[JsonObject], payload["processes"])
    return next(item for item in processes if item["kind"] == kind and item["pump_id"] == pump_id)


def _continue_until(
    session: PumpStationWorldSession,
    *,
    prefix: str,
    predicate: Callable[[JsonObject], bool],
) -> JsonObject:
    for index in range(1, 12):
        session.continue_operation(
            f"{prefix}-{index:02d}",
            "Advance to the next declared event.",
        )
        payload = _current_payload(session)
        if predicate(payload):
            return payload
    raise AssertionError("rich-work event did not arrive")


def _execute_direct(factory: PumpStationWorldSessionFactory) -> PumpStationWorldSession:
    first = open_world_session(
        _request(open_mode=WorldSessionOpenMode.START, tenure_id="tenure-1"),
        factory,
    )
    assert isinstance(first, PumpStationWorldSession)
    reason = "Execute the rich-work reference path."
    verification_result = json.loads(
        first.request_post_maintenance_verification(
            "proposal-verification",
            reason,
            "pump-a",
        )
    )
    verification_process = _process(
        verification_result["view"]["current_state"],
        "post_maintenance_verification",
        "pump-a",
    )
    first.request_inspection("proposal-inspection", reason, "pump-b")
    first.transfer_duty("proposal-transfer", reason)
    resources_ready = _continue_until(
        first,
        prefix="proposal-ready",
        predicate=lambda value: value["resources"]["repair_kit_available"],
    )
    dependency = next(
        item
        for item in resources_ready["dependencies"]
        if item["process_id"] == verification_process["process_id"] and item["kind"] == "administrative_closeout"
    )
    evidence = next(
        item
        for item in resources_ready["evidence"]
        if item["kind"] == "functional_checks" and item["pump_id"] == "pump-a"
    )
    first.request_dependency_waiver(
        "proposal-waiver",
        reason,
        verification_process["process_id"],
        dependency["dependency_id"],
        evidence["evidence_id"],
    )
    first.resume_process(
        "proposal-resume-verification",
        reason,
        verification_process["process_id"],
    )
    _continue_until(
        first,
        prefix="proposal-withdraw",
        predicate=lambda value: _process(
            value,
            "post_maintenance_verification",
            "pump-a",
        )["status"]
        == "suspended",
    )

    snapshot = first.result.snapshot
    second = open_world_session(
        _request(
            open_mode=WorldSessionOpenMode.RESUME,
            tenure_id="tenure-2",
            snapshot=snapshot,
        ),
        factory,
    )
    assert isinstance(second, PumpStationWorldSession)
    second.install_structured_handover(
        create_structured_handover(
            second.actor_view,
            from_tenure_id="tenure-1",
            history=first.actor_history,
            maximum_history_entries=16,
        )
    )
    restored = _continue_until(
        second,
        prefix="proposal-restore",
        predicate=lambda value: value["resources"]["access_window_seconds"] > 0,
    )
    verification_process = _process(
        restored,
        "post_maintenance_verification",
        "pump-a",
    )
    second.resume_process(
        "proposal-resume-after-handover",
        reason,
        verification_process["process_id"],
    )
    _continue_until(
        second,
        prefix="proposal-complete-verification",
        predicate=lambda value: not any(
            item["kind"] == "post_maintenance_verification" and item["pump_id"] == "pump-a"
            for item in value["processes"]
        ),
    )
    inspection = _process(_current_payload(second), "inspection", "pump-b")
    second.resume_process(
        "proposal-resume-inspection",
        reason,
        inspection["process_id"],
    )
    inspected = _continue_until(
        second,
        prefix="proposal-complete-inspection",
        predicate=lambda value: any(
            item["kind"] == "inspection" and item["pump_id"] == "pump-b" for item in value["evidence"]
        ),
    )
    inspection_evidence = next(
        item for item in inspected["evidence"] if item["kind"] == "inspection" and item["pump_id"] == "pump-b"
    )
    second.request_obstruction_clearance(
        "proposal-clearance",
        reason,
        "pump-b",
        inspection_evidence["evidence_id"],
    )
    _continue_until(
        second,
        prefix="proposal-complete-clearance",
        predicate=lambda value: not value["resources"]["repair_kit_available"],
    )
    _continue_until(
        second,
        prefix="proposal-complete-checks",
        predicate=lambda value: any(
            item["kind"] == "functional_checks" and item["pump_id"] == "pump-b" for item in value["evidence"]
        ),
    )
    return second


def test_complete_rich_work_scenario_has_direct_and_local_harbor_parity(
    tmp_path: Path,
) -> None:
    direct = _execute_direct(
        PumpStationWorldSessionFactory(
            tmp_path / "direct" / "world-run",
            rich_work_processes=True,
        )
    )
    assert direct.result.tool_names == PUMP_STATION_RICH_WORK_TOOL_NAMES
    assert direct.verify().valid is True
    assert all(
        process.status not in {PumpStationProcessStatus.ACTIVE, PumpStationProcessStatus.SUSPENDED}
        for process in direct.run.state.processes
    )

    task_dir = tmp_path / "tasks" / "stewardship" / "wastewater-pump-station"
    exported = export_pump_station_harbor_task(
        task_dir,
        project_root=Path(__file__).resolve().parents[4],
        rich_work_processes=True,
    )
    bridge = load_pump_station_harbor_bridge(task_dir / "environment")
    harbor = run_pump_station_rich_work_reference_session(
        bridge=bridge,
        output_dir=tmp_path / "harbor",
        session_identity="rich-work",
    )
    verified = verify_pump_station_harbor_run(
        run_dir=harbor.output_dir,
        export_manifest_path=exported.manifest_path,
        package_dir=exported.package_dir,
    )

    assert harbor.verification.valid is True
    assert verified["valid"] is True
    assert harbor.result.snapshot.sequence == direct.result.snapshot.sequence
    assert harbor.result.snapshot.state_id == direct.result.snapshot.state_id
    direct_evaluation = evaluate_pump_station_stewardship_run(
        run_dir=direct.run.repository.root,
    )
    harbor_evaluation = evaluate_pump_station_stewardship_run(
        run_dir=harbor.output_dir / "world-run",
        package_root=exported.package_dir,
    )
    assert harbor_evaluation.metrics == direct_evaluation.metrics
    assert harbor_evaluation.gates == direct_evaluation.gates
    assert harbor_evaluation.metrics.obligation_breach_count == 1
    assert harbor_evaluation.metrics.handover_count == 1
    assert harbor_evaluation.metrics.handover_omission_count == 0


def test_exported_rich_work_harbor_trial_imports_evaluated_record(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    exported = export_pump_station_harbor_task(
        repo_root / "tasks" / "stewardship" / "wastewater-pump-station",
        project_root=Path(__file__).resolve().parents[4],
        rich_work_processes=True,
    )
    trial_name = "pump-station-rich-work"
    config = TrialConfig.model_validate(
        {
            "task": {"path": str(exported.task_dir)},
            "trial_name": trial_name,
            "trials_dir": str(repo_root / "jobs" / "rich-work"),
            "job_id": "e35b5d90-7d64-49d1-a616-f771873c7a64",
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
    assert result.verifier_result is not None
    assert result.verifier_result.rewards == {"reward": 1.0}

    record = import_harbor_trial(
        trial_dir=config.trials_dir / trial_name,
        repo_root=repo_root,
    )
    assert TrialRecord.model_validate_json(record.model_dump_json()) == record
    assert record.world_execution is not None
    assert record.evaluation.stewardship is not None
    assert record.evaluation.reward == 0.0
    assert record.evaluation.stewardship.metrics.obligation_breach_count == 1
    assert record.evaluation.stewardship.metrics.restriction_breach_count == 0
    assert record.evaluation.stewardship.gates.errors == ("obligation or restriction integrity failed",)
    assert record.evaluation.stewardship.valid is False
    assert record.evaluation.stewardship.metrics.handover_count == 1
    assert record.evaluation.stewardship.metrics.handover_omission_count == 0
