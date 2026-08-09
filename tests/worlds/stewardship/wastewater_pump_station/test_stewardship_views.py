# ABOUTME: Unit-tests the current actor view and private information-set binding.
# ABOUTME: Proves the opaque actor response excludes host-only decision and persistence context.

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from aec_bench.worlds.stewardship.wastewater_pump_station.episode_runtime import (
    PumpStationEpisodeHost,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.stewardship_views import (
    PumpStationContinuityCarrier,
    PumpStationCurrentContext,
    PumpStationObservationHistory,
    bind_information_set,
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
        run_id="view-run",
        episode_id="view-episode",
        world_branch_id="view-branch",
    )
    return run, PumpStationEpisodeHost(root)


def test_actor_observation_excludes_private_host_binding(tmp_path: Path) -> None:
    _, host = _start(tmp_path / "run")

    observation = host.observe()

    assert set(observation.model_dump(mode="python")) == {"decision_id", "view"}
    assert "information_set_id" not in observation.view
    assert "commit_id" not in observation.view
    assert "run_id" not in observation.view
    assert "current_context" not in observation.view
    assert "scheduled_events" not in observation.view


def test_information_set_identity_binds_history_and_visible_context(tmp_path: Path) -> None:
    run, host = _start(tmp_path / "run")
    information_set = host._information_set(run.manifest, run.state, run.snapshot().sequence)
    view = information_set.base_view
    repeated_history = PumpStationObservationHistory(
        agent_tenure_id=view.agent_tenure_id,
        view_ids=(view.view_id, view.view_id),
    )
    current_context = PumpStationCurrentContext(
        continuity_carrier=PumpStationContinuityCarrier.CURRENT_ACTOR_VIEW,
        conversation_prefix_id=None,
        workspace_tool_ids=("pump-station-actor-interface",),
        visible_material_ids=(),
    )

    repeated = bind_information_set(view, repeated_history, current_context)
    visible = bind_information_set(
        view,
        information_set.observation_history,
        replace(current_context, visible_material_ids=("evidence-ref",)),
    )

    assert repeated.information_set_id != information_set.information_set_id
    assert visible.information_set_id != information_set.information_set_id
