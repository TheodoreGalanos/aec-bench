# ABOUTME: Exercises pump-station recovery at the real filesystem commit boundary.
# ABOUTME: Proves retries cannot duplicate durable resource or physical effects.

from __future__ import annotations

from world_run_support import bind_proposal, create_world_run

from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
    PumpStationWorldRun,
    RequestConditionalDeferral,
    TransferDuty,
)


def test_crash_recovery_applies_resource_and_physical_effects_once(tmp_path) -> None:
    run = create_world_run(tmp_path / "run")

    deferral, deferral_information = bind_proposal(
        run,
        RequestConditionalDeferral,
        "proposal-resource-effect",
        pump_id="pump-a",
    )
    before_deferral = run.snapshot()
    run.stage(deferral, information_set=deferral_information)

    resumed = PumpStationWorldRun.resume(
        repository=run.repository,
        package=run.package,
        model=run.model,
        snapshot=before_deferral,
    )
    first_deferral = resumed.apply(
        deferral,
        information_set=deferral_information,
    )
    repeated_deferral = resumed.apply(
        deferral,
        information_set=deferral_information,
    )

    assert repeated_deferral == first_deferral
    assert len(resumed.state.restrictions) == 1
    assert len(resumed.state.obligations) == 1
    assert len(resumed.state.work_orders) == 1

    transfer, transfer_information = bind_proposal(
        resumed,
        TransferDuty,
        "proposal-physical-effect",
    )
    before_transfer = resumed.snapshot()
    resumed.stage(transfer, information_set=transfer_information)

    recovered = PumpStationWorldRun.resume(
        repository=resumed.repository,
        package=resumed.package,
        model=resumed.model,
        snapshot=before_transfer,
    )
    first_transfer = recovered.apply(
        transfer,
        information_set=transfer_information,
    )
    committed_snapshot = recovered.snapshot()

    response_lost = PumpStationWorldRun.resume(
        repository=recovered.repository,
        package=recovered.package,
        model=recovered.model,
        snapshot=committed_snapshot,
    )
    repeated_transfer = response_lost.apply(
        transfer,
        information_set=transfer_information,
    )

    assert repeated_transfer == first_transfer
    assert response_lost.state.sequence == 2
    assert response_lost.state.physical.duty_pump_id == "pump-b"
    assert response_lost.state.physical.duty_transfer_count == 1
    assert len(response_lost.steps()) == 2
