# ABOUTME: Tests ASW-8 v4 durable generations, replay, conservation, and evaluation v2.
# ABOUTME: Rejects changed stored state and checks all four balances on the complete journey.

from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

from aec_bench.contracts.world_interface import WorldActorBinding, WorldInterfaceError
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_evaluation import (
    PUMP_STATION_VERIFICATION_REPORT_VERSION_V2,
    STEWARDSHIP_EVALUATION_VERSION_V2,
    derive_conservation_report,
    evaluate_coupled_run,
    verify_coupled_run,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_execution import (
    execute_asw_8_reference_controller,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_interface import (
    PumpStationCoupledLocalRequest,
    execute_coupled_local_request,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_run import (
    PumpStationCoupledRunError,
    PumpStationCoupledRunRepository,
    create_coupled_run,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_runtime import (
    PUMP_STATION_WORLD_MANIFEST_VERSION_V2,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_work import (
    PumpStationBacklogStatus,
    PumpStationPoolReservationStatus,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PumpStationObligationStatus,
    RequestDutyAssignment,
    RequestFunctionalCheck,
    RequestVerification,
)


def test_complete_journey_replays_and_all_four_conservation_sections_balance() -> None:
    result = execute_asw_8_reference_controller(
        run_id="run-direct",
        world_branch_id="branch-direct",
    )

    report = verify_coupled_run(result.run)
    evaluation = evaluate_coupled_run(result.run)

    assert result.run.manifest.serialization_version == PUMP_STATION_WORLD_MANIFEST_VERSION_V2
    assert report.report_version == PUMP_STATION_VERIFICATION_REPORT_VERSION_V2
    assert report.valid
    assert report.actor_proposals_valid
    assert report.host_controls_valid
    assert report.conservation.duty.valid
    assert report.conservation.resources.valid
    assert report.conservation.work.valid
    assert report.conservation.liabilities.valid
    assert len(report.conservation.work.opening_ids) == 2
    assert len(report.conservation.work.generated_ids) == 4
    assert len(report.conservation.work.terminal_ids) == 5
    assert len(report.conservation.work.closing_ids) == 1
    assert len(report.conservation.liabilities.opening_ids) == 2
    assert len(report.conservation.liabilities.created_ids) == 3
    assert len(report.conservation.liabilities.discharged_ids) == 4
    assert len(report.conservation.liabilities.closing_ids) == 1
    assert evaluation.schema_version == STEWARDSHIP_EVALUATION_VERSION_V2
    assert evaluation.valid
    assert evaluation.reward == 1.0
    assert len(evaluation.terminal_liabilities) == 1


def test_evaluation_reports_actor_proposals_separately_from_host_controls() -> None:
    run = execute_asw_8_reference_controller(
        run_id="run-step-type-validation",
        world_branch_id="branch-step-type-validation",
    ).run

    valid_report = verify_coupled_run(run)
    invalid_report = verify_coupled_run(
        replace(run, proposals=run.proposals[:-1]),
    )
    evaluation = evaluate_coupled_run(run)

    assert valid_report.actor_proposals_valid
    assert valid_report.host_controls_valid
    assert not invalid_report.actor_proposals_valid
    assert "actor-proposal-integrity" in invalid_report.issue_codes
    assert dict(evaluation.integrity_gates)["actor_proposal_integrity"]
    assert dict(evaluation.integrity_gates)["host_control_integrity"]


def test_all_four_conservation_sections_detect_injected_mismatch() -> None:
    run = execute_asw_8_reference_controller(
        run_id="run-conservation-mismatch",
        world_branch_id="branch-conservation-mismatch",
    ).run

    episode_id, pump_id, seconds = run.state.collateral_runtime[0]
    duty_run = replace(
        run,
        state=replace(
            run.state,
            collateral_runtime=((episode_id, pump_id, seconds + 1),),
        ),
    )
    resource_run = replace(
        run,
        state=replace(
            run.state,
            resource_reservations=(
                replace(
                    run.state.resource_reservations[0],
                    status=PumpStationPoolReservationStatus.ACTIVE,
                ),
                *run.state.resource_reservations[1:],
            ),
        ),
    )
    work_run = replace(
        run,
        state=replace(
            run.state,
            backlog=(
                *run.state.backlog,
                replace(
                    run.state.backlog[0],
                    item_id="unexplained-work",
                    status=PumpStationBacklogStatus.CLOSED,
                ),
            ),
        ),
    )
    liability_run = replace(
        run,
        state=replace(
            run.state,
            obligations=(
                *run.state.obligations,
                replace(
                    run.state.obligations[0],
                    obligation_id="unexplained-liability",
                    status=PumpStationObligationStatus.ACTIVE,
                    created_sequence=0,
                ),
            ),
        ),
    )

    assert not derive_conservation_report(duty_run).duty.valid
    assert not derive_conservation_report(resource_run).resources.valid
    assert not derive_conservation_report(work_run).work.valid
    assert not derive_conservation_report(liability_run).liabilities.valid


def test_v4_receipt_names_each_changed_durable_owner() -> None:
    opening = create_coupled_run(
        run_id="run-receipt-owner-diff",
        world_branch_id="branch-receipt-owner-diff",
    )

    started = opening.apply_actor(
        request_id="receipt-clearance-001",
        action_name="request_obstruction_clearance",
        arguments={
            "pump_id": "pump-b",
            "backlog_item_id": "backlog-b-clearance-001",
            "inspection_evidence_id": "initial-b-inspection-accepted",
            "reason": "Start the named Pump B clearance work.",
        },
    )
    receipt = started.receipts[-1]

    assert receipt.changed_pool_ids == (
        "field-access-slot",
        "lifting-isolation-set-01",
        "maintenance-crew-01",
        "obstruction-clearance-kit",
    )
    assert receipt.changed_reservation_ids == tuple(
        reservation.reservation_id for reservation in started.state.resource_reservations
    )
    assert receipt.changed_backlog_item_ids == ("backlog-b-clearance-001",)
    assert receipt.generation_record_ids == ()
    assert receipt.changed_liability_owner_ids == ()

    completed = started.apply_actor(
        request_id="receipt-clearance-complete-001",
        action_name="continue_operation",
        arguments={"reason": "Advance to the clearance completion event."},
    )
    completion_receipt = completed.receipts[-1]

    assert "backlog-b-clearance-001" in completion_receipt.changed_backlog_item_ids
    assert len(completion_receipt.generation_record_ids) == 2
    assert any(
        item_id in completion_receipt.changed_liability_owner_ids for item_id in completed.state.active_liability_ids
    )
    assert completion_receipt.operating_interval_id is not None


def test_repository_resume_replays_exact_state_and_rejects_changed_snapshot(tmp_path: Path) -> None:
    result = execute_asw_8_reference_controller(
        run_id="run-persisted",
        world_branch_id="branch-persisted",
    )
    repository = PumpStationCoupledRunRepository(tmp_path / "run")
    repository.create(result.run)

    resumed = repository.open()

    assert resumed == result.run
    head = len(result.run.commands)
    state_path = tmp_path / "run" / "generations" / f"{head:08d}" / "state.json"
    state_value = json.loads(state_path.read_bytes())
    state_value["disclosed_through_calendar_seconds"] = 226_801
    state_path.write_text(
        json.dumps(state_value, separators=(",", ":"), sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(PumpStationCoupledRunError) as raised:
        repository.open()

    assert raised.value.code == "state-replay"


def test_generation_publication_recovers_before_head_without_duplicate_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = PumpStationCoupledRunRepository(tmp_path / "run")
    opening = create_coupled_run(
        run_id="run-publication-recovery",
        world_branch_id="branch-publication-recovery",
    )
    repository.create(opening)
    updated = opening.apply_actor(
        request_id="recovery-continue-001",
        action_name="continue_operation",
        arguments={"reason": "Continue once across an interrupted publication."},
    )
    original_replace = os.replace

    def interrupt_head(
        source: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        destination: str | bytes | os.PathLike[str] | os.PathLike[bytes],
    ) -> None:
        if Path(os.fsdecode(destination)).name == "HEAD":
            raise OSError("injected interruption before head publication")
        original_replace(source, destination)

    monkeypatch.setattr(
        "aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_run.os.replace",
        interrupt_head,
    )
    with pytest.raises(OSError, match="injected interruption"):
        repository.append(updated)
    monkeypatch.setattr(
        "aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_run.os.replace",
        original_replace,
    )

    repository.append(updated)
    recovered = repository.open()
    assert recovered == updated
    assert len(recovered.commands) == 1
    assert len(recovered.receipts) == 1


def test_installed_request_retry_recovers_after_head_without_duplicate_effects(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run"
    execute_coupled_local_request(
        run_root=run_root,
        request=PumpStationCoupledLocalRequest(
            operation="start",
            run_id="run-request-retry",
            world_branch_id="branch-request-retry",
        ),
    )
    observation = execute_coupled_local_request(
        run_root=run_root,
        request=PumpStationCoupledLocalRequest(
            operation="observe",
            agent_tenure_id="retry-tenure-001",
            session_id="retry-session-001",
        ),
    )
    binding = WorldActorBinding.model_validate(observation["payload"]["binding"])
    request = PumpStationCoupledLocalRequest(
        operation="actor_action",
        request_id="retry-continue-001",
        action_name="continue_operation",
        arguments={"reason": "Continue once and recover the exact published result."},
        binding=binding,
    )

    first = execute_coupled_local_request(run_root=run_root, request=request)
    repeated = execute_coupled_local_request(run_root=run_root, request=request)

    assert repeated == first
    assert PumpStationCoupledRunRepository(run_root).open().state.sequence == 1
    with pytest.raises(WorldInterfaceError, match="actor-binding"):
        execute_coupled_local_request(
            run_root=run_root,
            request=PumpStationCoupledLocalRequest(
                operation="actor_action",
                request_id="stale-continue-002",
                action_name="continue_operation",
                arguments={"reason": "This request still uses the prior observed state."},
                binding=binding,
            ),
        )
    with pytest.raises(ValueError, match="request id"):
        execute_coupled_local_request(
            run_root=run_root,
            request=PumpStationCoupledLocalRequest(
                operation="actor_action",
                request_id="retry-continue-001",
                action_name="continue_operation",
                arguments={"reason": "Try to reuse the identity with different content."},
                binding=binding,
            ),
        )


def test_v4_persists_bound_context_for_each_actor_decision_type(tmp_path: Path) -> None:
    duty_root = tmp_path / "duty-run"
    execute_coupled_local_request(
        run_root=duty_root,
        request=PumpStationCoupledLocalRequest(
            operation="start",
            run_id="run-bound-duty",
            world_branch_id="branch-bound-duty",
        ),
    )
    observed = execute_coupled_local_request(
        run_root=duty_root,
        request=PumpStationCoupledLocalRequest(
            operation="observe",
            agent_tenure_id="duty-tenure-001",
            session_id="duty-session-001",
        ),
    )
    binding = WorldActorBinding.model_validate(observed["payload"]["binding"])
    execute_coupled_local_request(
        run_root=duty_root,
        request=PumpStationCoupledLocalRequest(
            operation="actor_action",
            request_id="bound-duty-001",
            action_name="request_duty_assignment",
            arguments={
                "ordered_pump_ids": ["pump-c"],
                "reason": "Keep Pump C assigned for the visible normal-service interval.",
            },
            binding=binding,
        ),
    )
    duty_run = PumpStationCoupledRunRepository(duty_root).open()
    assert len(duty_run.proposals) == 1
    duty = duty_run.proposals[0]
    assert isinstance(duty, RequestDutyAssignment)
    assert duty.proposal_version == "request_duty_assignment.v1"
    assert duty.context.base_view_id == binding.actor_view_id
    assert duty.context.information_set_id == binding.information_set_id
    assert duty_run.receipts[-1].required_authorities == ("operations",)
    proposal_value = json.loads((duty_root / "generations" / "00000001" / "proposals.json").read_bytes())
    assert proposal_value[0]["$type"] == "RequestDutyAssignment"

    verification_root = tmp_path / "verification-run"
    execute_coupled_local_request(
        run_root=verification_root,
        request=PumpStationCoupledLocalRequest(
            operation="start",
            run_id="run-bound-verification",
            world_branch_id="branch-bound-verification",
        ),
    )
    verification_observation = execute_coupled_local_request(
        run_root=verification_root,
        request=PumpStationCoupledLocalRequest(
            operation="observe",
            agent_tenure_id="verification-tenure-001",
            session_id="verification-session-001",
        ),
    )
    verification_binding = WorldActorBinding.model_validate(verification_observation["payload"]["binding"])
    execute_coupled_local_request(
        run_root=verification_root,
        request=PumpStationCoupledLocalRequest(
            operation="actor_action",
            request_id="bound-verification-001",
            action_name="request_post_maintenance_verification",
            arguments={
                "pump_id": "pump-a",
                "backlog_item_id": "backlog-a-verification-001",
                "reason": "Verify Pump A before its run-in restriction can be released.",
            },
            binding=verification_binding,
        ),
    )
    verification_run = PumpStationCoupledRunRepository(verification_root).open()
    verification = verification_run.proposals[-1]
    assert isinstance(verification, RequestVerification)
    assert verification.context.base_view_id == verification_binding.actor_view_id
    assert verification.context.information_set_id == verification_binding.information_set_id

    functional = create_coupled_run(
        run_id="run-bound-functional",
        world_branch_id="branch-bound-functional",
    )
    functional = functional.apply_actor(
        request_id="bound-clearance-001",
        action_name="request_obstruction_clearance",
        arguments={
            "pump_id": "pump-b",
            "backlog_item_id": "backlog-b-clearance-001",
            "inspection_evidence_id": "initial-b-inspection-accepted",
            "reason": "Clear the accepted Pump B obstruction.",
        },
    )
    functional = functional.apply_actor(
        request_id="bound-clearance-complete-001",
        action_name="continue_operation",
        arguments={"reason": "Advance to the declared clearance completion."},
    )
    wg03 = next(item for item in functional.state.backlog if item.generation_rule_id == "WG-03")
    functional = functional.apply_actor(
        request_id="bound-functional-001",
        action_name="request_functional_check",
        arguments={
            "pump_id": "pump-b",
            "backlog_item_id": wg03.item_id,
            "reason": "Run the controlled Pump B functional check.",
        },
    )
    proposal = functional.proposals[-1]
    assert isinstance(proposal, RequestFunctionalCheck)
    assert proposal.proposal_version == "request_functional_check.v1"
    assert proposal.backlog_item_id == wg03.item_id
    assert functional.receipts[-1].required_authorities == (
        "maintenance",
        "operations",
    )
    assert functional.receipts[-1].permit_ids == ("controlled-test-permit-bound-functional-001",)
