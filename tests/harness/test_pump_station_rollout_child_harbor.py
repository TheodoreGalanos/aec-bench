# ABOUTME: Proves Harbor can resume one exact registered continual-rollout child.
# ABOUTME: Binds immutable child bytes through the integration and runs one bounded actor action.

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from harbor.models.trial.config import TrialConfig  # type: ignore[import-untyped]

from aec_bench.contracts.continual_world import (
    ContinualRolloutChildRequest,
    ContinualRolloutChildRunRef,
    ContinualRolloutGroupRequest,
    ContinualWorldSnapshotRef,
)
from aec_bench.contracts.world_interface import WorldActorActionRequest
from aec_bench.contracts.world_session import (
    WorldSessionRequest,
    WorldSessionResult,
)
from aec_bench.harness.harbor_importing.core import import_harbor_trial
from aec_bench.harness.harbor_task_exporting.stable_io import directory_sha256
from aec_bench.harness.pump_station_harbor.export import (
    PUMP_STATION_HARBOR_BRIDGE_MODE,
    PUMP_STATION_HARBOR_EXECUTION_KIND,
    export_pump_station_harbor_task,
    load_pump_station_harbor_bridge,
)
from aec_bench.harness.pump_station_harbor.importing import load_pump_station_import_evidence
from aec_bench.worlds.runtime.rollout_control import ContinualRolloutControl
from aec_bench.worlds.runtime.rollout_repository import ContinualRolloutRepository
from aec_bench.worlds.stewardship.wastewater_pump_station.continual_definition import (
    pump_station_continual_world_definition,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.continual_rollout_adapter import (
    PumpStationContinualWorldBranchPort,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.episode_runtime import (
    PumpStationEpisodeHost,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.evaluation import (
    evaluate_pump_station_reference_run,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.reference_controller import (
    PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_models import (
    PumpStationStateSnapshotRef,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_serialization import (
    pump_station_artifact_id,
)
from tests.support.harbor_local_environment import run_harbor_trial

PROJECT_ROOT = Path(__file__).resolve().parents[2]
_INITIAL_RUN_PATH = "tests/initial-world-run"


def _tree_bytes(root: Path) -> tuple[tuple[str, bytes], ...]:
    return tuple(
        sorted((path.relative_to(root).as_posix(), path.read_bytes()) for path in root.rglob("*") if path.is_file())
    )


def _continual_snapshot(snapshot: PumpStationStateSnapshotRef) -> ContinualWorldSnapshotRef:
    return ContinualWorldSnapshotRef(
        run_id=snapshot.run_id,
        episode_id=snapshot.episode_id,
        world_branch_id=snapshot.world_branch_id,
        sequence=snapshot.sequence,
        state_id=snapshot.state_id,
        commit_id=snapshot.commit_id,
    )


def _create_registered_rollout(
    tmp_path: Path,
) -> tuple[
    Path,
    Path,
    Path,
    ContinualRolloutChildRunRef,
    ContinualRolloutChildRunRef,
]:
    definition = pump_station_continual_world_definition()
    profile_ref = definition.profiles[0]
    parent_root = tmp_path / "parent-world"
    parent = PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(parent_root),
        run_id="harbor-rollout-parent-run",
        episode_id="harbor-rollout-parent-episode",
        world_branch_id="harbor-rollout-parent-branch",
    )
    parent_host = PumpStationEpisodeHost(parent_root)
    observation = parent_host.observe()
    parent_host.invoke(
        WorldActorActionRequest(
            request_id="harbor-rollout-parent-condition-check",
            decision_id=observation.decision_id,
            action_name="request_condition_check",
            arguments={
                "pump_id": "pump-b",
                "reason": "Select one later verified world position for the rollout.",
            },
        ),
    )
    parent_snapshot = parent.snapshot()
    request = ContinualRolloutGroupRequest(
        request_id="harbor-rollout-request",
        group_id="harbor-rollout-group",
        task_world_id=definition.ref.task_world_id,
        authority_id="harbor-rollout-host",
        world_build=definition.build,
        profile_ref=profile_ref,
        parent_manifest_content_sha256=pump_station_artifact_id(parent.manifest),
        parent_snapshot=_continual_snapshot(parent_snapshot),
        origin_verification_content_sha256=pump_station_artifact_id(parent.verify()),
        reason="Run two isolated checks from this selected world position.",
        children=(
            ContinualRolloutChildRequest(
                child_id="selected",
                run_id="harbor-rollout-selected-run",
                episode_id="harbor-rollout-selected-episode",
                world_branch_id="harbor-rollout-selected-branch",
            ),
            ContinualRolloutChildRequest(
                child_id="sibling",
                run_id="harbor-rollout-sibling-run",
                episode_id="harbor-rollout-sibling-episode",
                world_branch_id="harbor-rollout-sibling-branch",
            ),
        ),
    )
    rollout_root = tmp_path / "rollouts"
    control = ContinualRolloutControl(
        definition,
        PumpStationContinualWorldBranchPort(),
        parent_run_root=parent_root,
        rollout_repository_root=rollout_root,
        authorised_principal_ids=("harbor-rollout-host",),
    )
    control.create_group(request)
    selected_ref = control.child_run_ref(request.group_id, "selected")
    sibling_ref = control.child_run_ref(request.group_id, "sibling")
    repository = ContinualRolloutRepository(
        rollout_root,
        disjoint_roots=(parent_root,),
    )
    selected_root = repository.child_world_root(request.group_id, "selected")
    sibling_root = repository.child_world_root(request.group_id, "sibling")
    return parent_root, selected_root, sibling_root, selected_ref, sibling_ref


def _world_session_dir(trial_dir: Path) -> Path:
    return next(
        candidate
        for candidate in (
            trial_dir / "agent" / "world-session",
            trial_dir / "artifacts" / "agent" / "world-session",
        )
        if candidate.is_dir()
    )


def test_registered_rollout_child_export_binds_the_exact_immutable_initial_run(
    tmp_path: Path,
) -> None:
    parent_root, selected_root, sibling_root, selected_ref, sibling_ref = _create_registered_rollout(tmp_path)
    parent_before = _tree_bytes(parent_root)
    selected_before = _tree_bytes(selected_root)
    sibling_before = _tree_bytes(sibling_root)
    profile_ref = pump_station_continual_world_definition().profiles[0]
    assert selected_ref.initial_snapshot.sequence > 0

    exported = export_pump_station_harbor_task(
        tmp_path / "task",
        project_root=PROJECT_ROOT,
        profile_ref=profile_ref,
        initial_run_root=selected_root,
        rollout_child_ref=selected_ref,
    )

    manifest = json.loads(exported.manifest_path.read_text(encoding="utf-8"))
    assert manifest["initial_run"] == {
        "path": _INITIAL_RUN_PATH,
        "directory_sha256": directory_sha256(selected_root),
        "rollout_child_ref": selected_ref.model_dump(mode="json"),
    }
    bridge = load_pump_station_harbor_bridge(exported.task_dir / "environment")
    assert bridge.initial_run_root == exported.task_dir / _INITIAL_RUN_PATH
    assert bridge.rollout_child_ref == selected_ref
    assert directory_sha256(bridge.initial_run_root) == manifest["initial_run"]["directory_sha256"]
    assert _tree_bytes(parent_root) == parent_before
    assert _tree_bytes(selected_root) == selected_before
    assert _tree_bytes(sibling_root) == sibling_before

    manifest_bytes = exported.manifest_path.read_bytes()
    manifest["initial_run"]["rollout_child_ref"] = sibling_ref.model_dump(mode="json")
    exported.manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="initial run identity differs"):
        load_pump_station_harbor_bridge(exported.task_dir / "environment")
    exported.manifest_path.write_bytes(manifest_bytes)

    initial_manifest = bridge.initial_run_root / "manifest.json"
    initial_manifest.write_bytes(initial_manifest.read_bytes() + b" ")
    with pytest.raises(ValueError, match="initial run differs from the export"):
        load_pump_station_harbor_bridge(exported.task_dir / "environment")


def test_local_harbor_trial_resumes_one_rollout_child_for_one_bounded_actor_action(
    tmp_path: Path,
) -> None:
    parent_root, selected_root, sibling_root, selected_ref, sibling_ref = _create_registered_rollout(tmp_path)
    parent_before = _tree_bytes(parent_root)
    selected_before = _tree_bytes(selected_root)
    sibling_before = _tree_bytes(sibling_root)
    profile_ref = pump_station_continual_world_definition().profiles[0]
    repo_root = tmp_path / "repo"
    exported = export_pump_station_harbor_task(
        repo_root / "tasks" / "stewardship" / "wastewater-pump-station",
        project_root=PROJECT_ROOT,
        profile_ref=profile_ref,
        initial_run_root=selected_root,
        rollout_child_ref=selected_ref,
    )
    trial_name = "registered-rollout-child"
    config = TrialConfig.model_validate(
        {
            "task": {"path": str(exported.task_dir)},
            "trial_name": trial_name,
            "trials_dir": str(tmp_path / "trials"),
            "job_id": "b3276871-7c09-4554-9459-785354c94bc9",
            "agent": {
                "name": "pump-station-rollout-child-reference-controller",
                "import_path": "agents.entrypoint_agent:EntrypointAgent",
                "model_name": PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID,
                "kwargs": {
                    "adapter": "tool_loop",
                    "execution_kind": PUMP_STATION_HARBOR_EXECUTION_KIND,
                    "world_session": {"bridge_mode": PUMP_STATION_HARBOR_BRIDGE_MODE},
                },
            },
            "environment": {
                "import_path": "tests.support.harbor_local_environment:LocalFilesystemHarborEnvironment",
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

    result = asyncio.run(run_harbor_trial(config))

    assert result.exception_info is None
    assert result.agent_result is not None
    assert result.agent_result.metadata["world_session_status"] == "completed"
    assert result.verifier_result is not None
    assert result.verifier_result.rewards == {"reward": 1.0}
    trial_dir = config.trials_dir / trial_name
    world_session_dir = _world_session_dir(trial_dir)
    request = WorldSessionRequest.model_validate_json((world_session_dir / "world-session-request.json").read_bytes())
    session_result = WorldSessionResult.model_validate_json(
        (world_session_dir / "world-session-result.json").read_bytes()
    )
    inventory = json.loads((world_session_dir / "artifact-inventory.json").read_text(encoding="utf-8"))
    assert request.open_mode.value == "resume"
    assert (
        request.run_id,
        request.episode_id,
        request.world_branch_id,
    ) == (
        selected_ref.run_id,
        selected_ref.episode_id,
        selected_ref.world_branch_id,
    )
    assert request.start_snapshot is not None
    assert (
        request.start_snapshot.sequence,
        request.start_snapshot.state_id,
        request.start_snapshot.commit_id,
    ) == (
        selected_ref.initial_snapshot.sequence,
        selected_ref.initial_snapshot.state_id,
        selected_ref.initial_snapshot.commit_id,
    )
    assert (
        session_result.snapshot.run_id,
        session_result.snapshot.episode_id,
        session_result.snapshot.world_branch_id,
    ) == (
        selected_ref.run_id,
        selected_ref.episode_id,
        selected_ref.world_branch_id,
    )
    assert session_result.snapshot.sequence == selected_ref.initial_snapshot.sequence + 1
    assert inventory["transition_count"] == 1
    completed = PumpStationWorldRun.resume_reference_system(
        repository=PumpStationWorldRunRepository(world_session_dir / "world-run"),
        snapshot=PumpStationWorldRunRepository(world_session_dir / "world-run").current_snapshot(),
    )
    steps = completed.repository.command_steps()
    assert len(steps) == 1
    assert steps[0].command.kind == "actor"
    assert steps[0].command.action_name == "request_condition_check"
    assert not hasattr(steps[0].command, "session_id")
    assert completed.verify().valid is True
    assert pump_station_artifact_id(completed.manifest) == selected_ref.child_manifest_content_sha256
    assert _tree_bytes(parent_root) == parent_before
    assert _tree_bytes(selected_root) == selected_before
    assert _tree_bytes(sibling_root) == sibling_before
    assert sibling_ref.initial_snapshot.sequence == selected_ref.initial_snapshot.sequence

    record = import_harbor_trial(
        trial_dir=trial_dir,
        repo_root=repo_root,
        evidence_loader=load_pump_station_import_evidence,
    )
    assert record.evaluation.stewardship is not None
    assert record.evaluation.stewardship.evaluation_scope == "bounded_continuation"
    assert record.evaluation.stewardship.valid is True
    assert record.evaluation.reward == 1.0
    assert record.episode_artifact is not None
    assert record.episode_artifact.path.endswith("world-session/artifact-inventory.json")
    imported_hashes = tuple(sorted({artifact.sha256 for artifact in record.outputs.artifacts or ()}))
    direct_evaluation = evaluate_pump_station_reference_run(
        completed,
        imported_artifact_sha256=imported_hashes,
        evaluation_scope="bounded_continuation",
    )
    assert record.evaluation.stewardship == direct_evaluation
