# ABOUTME: Tests durable ASW-6A-R case publication, idempotence, and crash recovery.
# ABOUTME: Proves derived review cases remain separate from their immutable source world.

from __future__ import annotations

import stat
from pathlib import Path

import pytest
from test_asw_5_rich_work_e2e import _execute_direct
from test_asw_6a_r_case_derivation import _request

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review import (
    PreparedPumpStationReviewCase,
    PumpStationReviewerRole,
    PumpStationReviewPreparationRequest,
    derive_pump_station_review_case,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review_repository import (
    PumpStationReviewCaseRepository,
    PumpStationReviewRepositoryError,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PumpStationWorldSessionFactory,
)


def _prepared(source_root: Path) -> PreparedPumpStationReviewCase:
    completed = _execute_direct(
        PumpStationWorldSessionFactory(
            source_root,
            evidence_health=True,
        )
    )
    return derive_pump_station_review_case(
        source_run_root=source_root,
        request=_request(completed.run.snapshot()),
    )


def test_staged_case_recovers_after_restart_and_exact_retry_is_idempotent(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source-world"
    review_root = tmp_path / "review-cases"
    prepared = _prepared(source_root)
    repository = PumpStationReviewCaseRepository(review_root)

    staged = repository.stage_case(prepared)

    assert staged.case_id == prepared.public_case.case_id
    assert repository.find_published_case(prepared.request.request_id) is None
    restarted = PumpStationReviewCaseRepository(review_root)
    recovered = restarted.recover_case(prepared.request.request_id)
    selected = restarted.publish_case(prepared)

    assert recovered == prepared
    assert selected == prepared
    assert restarted.find_published_case(prepared.request.request_id) == prepared
    assert restarted.list_case_ids() == (prepared.public_case.case_id,)
    assert len(tuple((review_root / "public-cases").glob("*.json"))) == 1
    assert len(tuple((review_root / "private-issues").glob("*.json"))) == 1
    assert all(stat.S_IMODE(path.stat().st_mode) & 0o077 == 0 for path in review_root.rglob("*.json"))


def test_request_collision_fails_but_a_new_request_creates_a_new_case(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source-world"
    review_root = tmp_path / "review-cases"
    prepared = _prepared(source_root)
    repository = PumpStationReviewCaseRepository(review_root)
    first = repository.publish_case(prepared)
    snapshot = prepared.request.source_snapshot
    conflicting_request = PumpStationReviewPreparationRequest(
        **{
            **prepared.request.model_dump(
                mode="json",
                exclude={"content_sha256"},
            ),
            "reviewer_role": PumpStationReviewerRole.MAINTENANCE_ASSURANCE_ENGINEER,
        }
    )
    conflicting = derive_pump_station_review_case(
        source_run_root=source_root,
        request=conflicting_request,
    )

    with pytest.raises(
        PumpStationReviewRepositoryError,
        match="review-request-id-conflict",
    ):
        repository.publish_case(conflicting)

    second_request = PumpStationReviewPreparationRequest(
        **{
            **prepared.request.model_dump(
                mode="json",
                exclude={"content_sha256"},
            ),
            "request_id": "prepare-review-002",
        }
    )
    second = repository.publish_case(
        derive_pump_station_review_case(
            source_run_root=source_root,
            request=second_request,
        )
    )

    assert first.public_case.case_id != second.public_case.case_id
    assert first.public_case.source_snapshot == snapshot
    assert second.public_case.source_snapshot == snapshot
    assert repository.list_case_ids() == tuple(
        sorted(
            (
                first.public_case.case_id,
                second.public_case.case_id,
            )
        )
    )
