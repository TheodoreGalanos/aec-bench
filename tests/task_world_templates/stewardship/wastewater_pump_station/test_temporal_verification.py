# ABOUTME: Tests independent replay of temporal access and evidence-reliance records.
# ABOUTME: Proves exact A/O/U/G separation and fail-closed artifact drift detection.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from aec_bench.contracts.world_interface import WorldActorActionRequest
from aec_bench.contracts.world_session import (
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PUMP_STATION_TASK_WORLD_ID,
    PumpStationWorldSession,
    PumpStationWorldSessionFactory,
)


def _session(tmp_path: Path) -> PumpStationWorldSession:
    return PumpStationWorldSessionFactory(
        tmp_path / "world",
        temporal_evidence=True,
    ).open(
        WorldSessionRequest(
            execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
            open_mode=WorldSessionOpenMode.START,
            session_id="session-verification",
            task_world_id=PUMP_STATION_TASK_WORLD_ID,
            agent_tenure_id="tenure-verification",
            run_id="run-verification",
            episode_id="episode-verification",
            world_branch_id="branch-verification",
        )
    )


def test_verifier_recomputes_access_and_separates_evidence_authorities(
    tmp_path: Path,
) -> None:
    session = _session(tmp_path)
    result = cast(
        dict[str, Any],
        json.loads(
            session.search_evidence(
                request_id="search-verification",
                query="pump obstruction procedure",
                scope="procedures",
            )
        )["receipt"],
    )
    reference = result["references"][0]["opaque_reference"]
    session.invoke_actor_action(
        WorldActorActionRequest(
            request_id="action-verification",
            action_name="continue_operation",
            binding=session.current_actor_binding,
            arguments={
                "reason": "Continue and rely on the supplied maintenance procedure.",
                "relied_on_evidence_refs": [reference],
            },
        )
    )

    report = session.verify_temporal_evidence()

    assert report.valid
    assert report.issues == ()
    assert report.access_count == 1
    assert report.reliance_count == 1
    action_sets = report.action_evidence_sets[0]
    assert action_sets.accessible_version_ids
    assert action_sets.observed_version_ids
    assert action_sets.relied_on_version_ids
    assert action_sets.recorded_evidence_refs == ()
    assert action_sets.accepted_evidence_refs == ()


def test_verifier_rejects_drifted_visible_result(tmp_path: Path) -> None:
    session = _session(tmp_path)
    session.search_evidence(
        request_id="search-drift",
        query="pump obstruction procedure",
        scope="procedures",
    )
    result_path = next(
        (tmp_path / "world" / "temporal-evidence" / "public" / "results").iterdir()
    )
    result_path.write_text("{}\n", encoding="utf-8")

    report = session.verify_temporal_evidence()

    assert not report.valid
    assert "artifact-integrity" in {item.code for item in report.issues}
