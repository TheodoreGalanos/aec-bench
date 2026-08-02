# ABOUTME: Tests the host-only closeout case-preparation and session-open controls.
# ABOUTME: Covers exact retry, inspection, recovery, stale binding, and authority separation.

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from test_closeout_review_case_derivation import _request
from test_rich_work_harbor_parity_e2e import _execute_direct

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review_control import (
    PUMP_STATION_REVIEW_CONTROL_OPERATIONS,
    PUMP_STATION_REVIEW_TASK_ID,
    PumpStationReviewControl,
    PumpStationReviewControlRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review_repository import (
    PumpStationReviewCaseRepository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review_session import (
    PumpStationReviewSessionOpenMode,
    PumpStationReviewSessionRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PumpStationWorldSessionFactory,
)


def test_host_control_prepares_retries_inspects_recovers_and_opens_case(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source-world"
    review_root = tmp_path / "review-cases"
    completed = _execute_direct(
        PumpStationWorldSessionFactory(
            source_root,
            evidence_health=True,
        )
    )
    preparation = _request(completed.run.snapshot())
    control = PumpStationReviewControl(
        source_run_root=source_root,
        review_repository_root=review_root,
        authorised_principal_ids=("host-review",),
    )
    prepare_request = PumpStationReviewControlRequest(
        request_id=preparation.request_id,
        operation="prepare_case",
        task_review_id=PUMP_STATION_REVIEW_TASK_ID,
        authority_id="host-review",
        preparation_request=preparation,
    )

    prepared = control.execute(prepare_request)
    restarted = PumpStationReviewControl(
        source_run_root=source_root,
        review_repository_root=review_root,
        authorised_principal_ids=("host-review",),
    )
    repeated = restarted.execute(prepare_request)
    inspected = restarted.execute(
        PumpStationReviewControlRequest(
            request_id="inspect-review-001",
            operation="inspect_preparation",
            task_review_id=PUMP_STATION_REVIEW_TASK_ID,
            authority_id="host-review",
            preparation_request_id=preparation.request_id,
        )
    )
    recovered = restarted.execute(
        PumpStationReviewControlRequest(
            request_id="recover-review-001",
            operation="recover_preparation",
            task_review_id=PUMP_STATION_REVIEW_TASK_ID,
            authority_id="host-review",
            preparation_request_id=preparation.request_id,
        )
    )
    session_request = PumpStationReviewSessionRequest(
        open_mode=PumpStationReviewSessionOpenMode.OPEN,
        session_id="review-session-control",
        case_id=prepared.public_case.case_id,
        public_case_content_sha256=(prepared.public_case.content_sha256),
        reviewer_tenure_id="review-tenure-control",
    )
    opened = restarted.execute(
        PumpStationReviewControlRequest(
            request_id="open-review-001",
            operation="open_review_session",
            task_review_id=PUMP_STATION_REVIEW_TASK_ID,
            authority_id="host-review",
            session_request=session_request,
        )
    )

    assert (
        tuple(item.operation for item in control.capabilities("host-review").operations)
        == PUMP_STATION_REVIEW_CONTROL_OPERATIONS
    )
    assert prepared == repeated
    assert prepared.receipt.state_changed is True
    assert prepared.public_case == inspected.public_case
    assert inspected.receipt.state_changed is False
    assert recovered.public_case == prepared.public_case
    assert opened.session_observation is not None
    assert opened.session_observation.public_case == prepared.public_case
    assert opened.receipt.state_changed is False
    assert PumpStationReviewCaseRepository(review_root).list_case_ids() == (prepared.public_case.case_id,)


def test_host_control_rejects_unauthorised_and_stale_preparation(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source-world"
    review_root = tmp_path / "review-cases"
    completed = _execute_direct(
        PumpStationWorldSessionFactory(
            source_root,
            evidence_health=True,
        )
    )
    preparation = _request(completed.run.snapshot())
    control = PumpStationReviewControl(
        source_run_root=source_root,
        review_repository_root=review_root,
        authorised_principal_ids=("host-review",),
    )

    with pytest.raises(ValueError, match="review-control-unauthorised"):
        control.execute(
            PumpStationReviewControlRequest(
                request_id=preparation.request_id,
                operation="prepare_case",
                task_review_id=PUMP_STATION_REVIEW_TASK_ID,
                authority_id="reviewer-agent",
                preparation_request=preparation,
            )
        )
    stale = type(preparation)(
        **{
            **preparation.model_dump(
                mode="json",
                exclude={"content_sha256", "source_snapshot"},
            ),
            "request_id": "prepare-review-stale",
            "source_snapshot": replace(
                preparation.source_snapshot,
                sequence=preparation.source_snapshot.sequence - 1,
            ),
        }
    )
    with pytest.raises(ValueError, match="review source binding differs"):
        control.execute(
            PumpStationReviewControlRequest(
                request_id=stale.request_id,
                operation="prepare_case",
                task_review_id=PUMP_STATION_REVIEW_TASK_ID,
                authority_id="host-review",
                preparation_request=stale,
            )
        )
    assert PumpStationReviewCaseRepository(review_root).list_case_ids() == ()
