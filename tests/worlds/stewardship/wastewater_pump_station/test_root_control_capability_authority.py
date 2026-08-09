# ABOUTME: Proves the root-control catalogue follows pump-task authority and active process state.
# ABOUTME: Keeps Operations controls separate from authority-owned process outcome controls.

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest
from pydantic import JsonValue

from aec_bench.contracts.world_interface import WorldActorActionRequest
from aec_bench.worlds.stewardship.wastewater_pump_station.coupled_work import (
    PumpStationCoupledProcessStatus,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.episode_runtime import (
    PumpStationEpisodeHost,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.physical_models import (
    PumpStationCoupledModel,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.stewardship_models import (
    PumpStationBoundControlRequest,
    PumpStationProcessOutcomeRequest,
    PumpStationStewardshipState,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_control import (
    PUMP_STATION_ROOT_CONTROL_OPERATIONS,
    PumpStationWorldControl,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_models import (
    PumpStationWorldRunError,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)

type RegisteredRun = PumpStationWorldRun[
    PumpStationCoupledModel,
    PumpStationStewardshipState,
]

_OPERATIONS_PRINCIPAL = "operations-controller"
_MAINTENANCE_PRINCIPAL = "maintenance-controller"
_VERIFICATION_PRINCIPAL = "verification-engineer-01"
_CONTROL_PRINCIPALS = (
    _OPERATIONS_PRINCIPAL,
    _MAINTENANCE_PRINCIPAL,
    _VERIFICATION_PRINCIPAL,
)


def _create_run(root: Path) -> RegisteredRun:
    return PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(root),
        run_id="root-control-authority-run",
        episode_id="root-control-authority-episode",
        world_branch_id="root-control-authority-branch",
    )


def _invoke(
    host: PumpStationEpisodeHost,
    *,
    request_id: str,
    action_name: str,
    arguments: dict[str, object] | None = None,
) -> None:
    observation = host.observe()
    host.invoke(
        WorldActorActionRequest(
            request_id=request_id,
            decision_id=observation.decision_id,
            action_name=action_name,
            arguments=cast(
                dict[str, JsonValue],
                {
                    **(arguments or {}),
                    "reason": f"Exercise {action_name} for root-control authority checks.",
                },
            ),
        ),
    )


def _root_operations(
    control: PumpStationWorldControl,
    authority_id: str,
) -> set[str]:
    advertised = {capability.operation for capability in control.capabilities(authority_id).operations}
    return advertised.intersection(PUMP_STATION_ROOT_CONTROL_OPERATIONS)


def _control(root: Path) -> PumpStationWorldControl:
    return PumpStationWorldControl(
        root,
        authorised_principal_ids=_CONTROL_PRINCIPALS,
    )


def _bound_process_outcome(
    run: RegisteredRun,
    *,
    request_id: str,
    authority_id: str,
    process_id: str,
    evidence_id: str,
) -> PumpStationBoundControlRequest:
    snapshot = run.snapshot()
    return PumpStationBoundControlRequest(
        request_id=request_id,
        run_id=snapshot.run_id,
        episode_id=snapshot.episode_id,
        world_branch_id=snapshot.world_branch_id,
        base_state_id=snapshot.state_id,
        base_commit_id=snapshot.commit_id,
        based_on_sequence=snapshot.sequence,
        control=PumpStationProcessOutcomeRequest(
            request_id=request_id,
            authority_id=authority_id,
            process_id=process_id,
            outcome="failed",
            evidence_id=evidence_id,
            base_state_id=snapshot.state_id,
        ),
    )


def test_operations_controls_are_advertised_only_to_operations_controller(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    _create_run(root)
    control = _control(root)

    assert _root_operations(control, _OPERATIONS_PRINCIPAL) == {
        "operations_review",
        "common_boundary",
    }
    assert _root_operations(control, _MAINTENANCE_PRINCIPAL) == set()
    assert _root_operations(control, _VERIFICATION_PRINCIPAL) == set()


def test_process_outcome_capability_follows_active_verification_authority(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    run = _create_run(root)
    host = PumpStationEpisodeHost(root)
    control = _control(root)

    _invoke(
        host,
        request_id="start-authority-verification",
        action_name="request_post_maintenance_verification",
        arguments={
            "pump_id": "pump-a",
            "backlog_item_id": "backlog-a-verification-001",
        },
    )

    assert run.state.processes[-1].status is PumpStationCoupledProcessStatus.ACTIVE
    assert _root_operations(control, _VERIFICATION_PRINCIPAL) == {
        "process_outcome",
    }
    assert "process_outcome" not in _root_operations(
        control,
        _MAINTENANCE_PRINCIPAL,
    )

    _invoke(
        host,
        request_id="finish-authority-verification",
        action_name="continue_operation",
    )

    assert "process_outcome" not in _root_operations(
        control,
        _VERIFICATION_PRINCIPAL,
    )


def test_committed_process_outcome_retry_survives_dynamic_capability_removal(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    run = _create_run(root)
    host = PumpStationEpisodeHost(root)
    _invoke(
        host,
        request_id="start-retry-verification",
        action_name="request_post_maintenance_verification",
        arguments={
            "pump_id": "pump-a",
            "backlog_item_id": "backlog-a-verification-001",
        },
    )
    process = run.state.processes[-1]
    request = _bound_process_outcome(
        run,
        request_id="failed-verification-retry",
        authority_id=_VERIFICATION_PRINCIPAL,
        process_id=process.process_id,
        evidence_id="evidence-failed-verification-retry",
    )
    control = _control(root)

    first = control.execute(request)

    assert "process_outcome" not in _root_operations(
        control,
        _VERIFICATION_PRINCIPAL,
    )
    repeated = _control(root).execute(request)
    assert repeated == first

    assert isinstance(request.control, PumpStationProcessOutcomeRequest)
    changed = replace(
        request,
        control=replace(
            request.control,
            evidence_id="evidence-changed-verification-retry",
        ),
    )
    with pytest.raises(PumpStationWorldRunError) as raised:
        _control(root).execute(changed)

    assert raised.value.code == "command-id-conflict"


def test_process_outcome_capability_follows_active_functional_check_authority(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    run = _create_run(root)
    host = PumpStationEpisodeHost(root)
    control = _control(root)

    _invoke(
        host,
        request_id="start-authority-clearance",
        action_name="request_obstruction_clearance",
        arguments={
            "pump_id": "pump-b",
            "backlog_item_id": "backlog-b-clearance-001",
            "inspection_evidence_id": "initial-b-inspection-accepted",
        },
    )
    _invoke(
        host,
        request_id="finish-authority-clearance",
        action_name="continue_operation",
    )
    functional_item = next(item for item in run.state.backlog if item.generation_rule_id == "WG-03")
    _invoke(
        host,
        request_id="start-authority-functional-check",
        action_name="request_functional_check",
        arguments={
            "pump_id": "pump-b",
            "backlog_item_id": functional_item.item_id,
        },
    )

    assert run.state.processes[-1].status is PumpStationCoupledProcessStatus.ACTIVE
    assert _root_operations(control, _MAINTENANCE_PRINCIPAL) == {
        "process_outcome",
    }
    assert "process_outcome" not in _root_operations(
        control,
        _VERIFICATION_PRINCIPAL,
    )

    _invoke(
        host,
        request_id="finish-authority-functional-check",
        action_name="continue_operation",
    )

    assert "process_outcome" not in _root_operations(
        control,
        _MAINTENANCE_PRINCIPAL,
    )
