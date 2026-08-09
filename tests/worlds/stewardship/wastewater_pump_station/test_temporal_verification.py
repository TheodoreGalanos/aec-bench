# ABOUTME: Tests temporal access verification through the current episode host.
# ABOUTME: Proves separate calls resolve durable context and fail closed on artifact drift.

from __future__ import annotations

from pathlib import Path

from aec_bench.contracts.world_interface import WorldActorActionRequest
from aec_bench.worlds.stewardship.wastewater_pump_station.episode_runtime import (
    PumpStationEpisodeHost,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)


def _start(root: Path) -> tuple[PumpStationWorldRun, PumpStationEpisodeHost]:
    run = PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(root),
        run_id="temporal-run",
        episode_id="temporal-episode",
        world_branch_id="temporal-branch",
    )
    return run, PumpStationEpisodeHost(root)


def _search(host: PumpStationEpisodeHost) -> None:
    observation = host.observe()
    host.invoke(
        WorldActorActionRequest(
            request_id="temporal-search",
            decision_id=observation.decision_id,
            action_name="search_evidence",
            arguments={"query": "pump obstruction procedure", "scope": "procedures", "limit": 3},
        )
    )


def test_temporal_access_replays_from_current_durable_context(tmp_path: Path) -> None:
    run, host = _start(tmp_path / "world")
    _search(host)

    report = run.verify()

    assert report.valid
    assert report.issues == ()


def test_temporal_verification_rejects_drifted_visible_result(tmp_path: Path) -> None:
    root = tmp_path / "world"
    run, host = _start(root)
    _search(host)
    result_path = next((root / "temporal-evidence" / "public" / "results").iterdir())
    result_path.write_text("{}\n", encoding="utf-8")

    report = run.verify()

    assert not report.valid
    assert any(issue.startswith("temporal-evidence-invalid:artifact-integrity") for issue in report.issues)
