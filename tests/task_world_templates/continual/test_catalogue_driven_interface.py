# ABOUTME: Tests catalogue-driven actor and host-control dispatch for one real continual world.
# ABOUTME: Proves exact profile binding, separate envelopes, and shared rollout operations.

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Literal, cast

import pytest
from pydantic import ValidationError

from aec_bench.contracts.continual_world import (
    ContinualRolloutChildRequest,
    ContinualRolloutChildRunRef,
    ContinualRolloutGroupRequest,
    ContinualRolloutGroupState,
    ContinualRolloutGroupStatus,
    ContinualRolloutLineage,
    ContinualWorldActorRequest,
    ContinualWorldControlRequest,
    ContinualWorldDefinitionRef,
    ContinualWorldProfileRef,
    ContinualWorldSnapshotRef,
)
from aec_bench.contracts.world_interface import (
    WorldActorActionRequest,
    WorldActorActionResult,
    WorldActorObservation,
    WorldControlRequest,
    WorldControlResult,
)
from aec_bench.contracts.world_session import (
    StewardshipStateSnapshotRef,
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
)
from aec_bench.meta_harness.evidence_lifecycle import run_evidence_lifecycle
from aec_bench.task_world_templates.continual.interface import (
    ContinualWorldInterfaceContext,
    dispatch_continual_actor,
    dispatch_continual_control,
)
from aec_bench.task_world_templates.continual.rollout_control import ContinualRolloutControl
from aec_bench.task_world_templates.continual_catalogue import default_continual_world_catalogue
from aec_bench.task_world_templates.lifecycles.ssc03_hydraulic_continual_definition import (
    Ssc03HydraulicContinualProfile,
    ssc03_hydraulic_continual_world_definition,
)
from aec_bench.task_world_templates.lifecycles.ssc03_hydraulic_rollout_adapter import (
    ssc03_hydraulic_rollout_origin,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.episode_runtime import (
    PUMP_STATION_TASK_WORLD_ID,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PumpStationRegisteredWorldRunManifest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_serialization import (
    pump_station_artifact_id,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _registered_run(root: Path, *, identity: str) -> PumpStationWorldRun:
    return PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(root),
        run_id=f"{identity}-run",
        episode_id=f"{identity}-episode",
        world_branch_id=f"{identity}-branch",
    )


def _shared_snapshot(run: PumpStationWorldRun) -> StewardshipStateSnapshotRef:
    snapshot = run.snapshot()
    return StewardshipStateSnapshotRef(
        run_id=snapshot.run_id,
        episode_id=snapshot.episode_id,
        world_branch_id=snapshot.world_branch_id,
        sequence=snapshot.sequence,
        state_id=snapshot.state_id,
        commit_id=snapshot.commit_id,
    )


def _continual_snapshot(run: PumpStationWorldRun) -> ContinualWorldSnapshotRef:
    snapshot = run.snapshot()
    return ContinualWorldSnapshotRef(
        run_id=snapshot.run_id,
        episode_id=snapshot.episode_id,
        world_branch_id=snapshot.world_branch_id,
        sequence=snapshot.sequence,
        state_id=snapshot.state_id,
        commit_id=snapshot.commit_id,
    )


def _resume_request(run: PumpStationWorldRun) -> WorldSessionRequest:
    snapshot = _shared_snapshot(run)
    return WorldSessionRequest(
        execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
        open_mode=WorldSessionOpenMode.RESUME,
        session_id="catalogue-interface-session",
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        agent_tenure_id="catalogue-interface-tenure",
        run_id=snapshot.run_id,
        episode_id=snapshot.episode_id,
        world_branch_id=snapshot.world_branch_id,
        start_snapshot=snapshot,
    )


def _context(tmp_path: Path, *, run_root: Path) -> ContinualWorldInterfaceContext:
    definition_ref, profile_ref = _exact_refs()
    return ContinualWorldInterfaceContext(
        catalogue=default_continual_world_catalogue(),
        run_root=run_root,
        rollout_repository_root=tmp_path / "rollouts",
        authorised_principal_ids=("catalogue-interface-host",),
        actor_definition_ref=definition_ref,
        actor_profile_ref=profile_ref,
    )


def _exact_refs() -> tuple[ContinualWorldDefinitionRef, ContinualWorldProfileRef]:
    definition = default_continual_world_catalogue().get(PUMP_STATION_TASK_WORLD_ID)
    return definition.ref, definition.spec.profiles[0]


def _actor_request(
    run: PumpStationWorldRun,
    *,
    definition_ref: ContinualWorldDefinitionRef,
    profile_ref: ContinualWorldProfileRef,
    operation: Literal["capabilities", "observe", "invoke"] = "observe",
    action_request: WorldActorActionRequest | None = None,
) -> ContinualWorldActorRequest:
    del run, definition_ref, profile_ref
    return ContinualWorldActorRequest(
        operation=operation,
        request_id=None if action_request is None else action_request.request_id,
        decision_id=None if action_request is None else action_request.decision_id,
        action_name=None if action_request is None else action_request.action_name,
        arguments=None if action_request is None else action_request.arguments,
    )


def _control_request(
    *,
    operation: str,
    definition_ref: ContinualWorldDefinitionRef,
    profile_ref: ContinualWorldProfileRef,
    control_request: WorldControlRequest | None = None,
    rollout_group_request: ContinualRolloutGroupRequest | None = None,
    group_id: str | None = None,
    child_id: str | None = None,
    authority_id: str = "catalogue-interface-host",
) -> ContinualWorldControlRequest:
    return ContinualWorldControlRequest.model_validate_json(
        json.dumps(
            {
                "definition_ref": definition_ref.model_dump(mode="json"),
                "profile_ref": profile_ref.model_dump(mode="json"),
                "operation": operation,
                "authority_id": authority_id,
                "control_request": control_request.model_dump(mode="json") if control_request is not None else None,
                "rollout_group_request": (
                    rollout_group_request.model_dump(mode="json") if rollout_group_request is not None else None
                ),
                "group_id": group_id,
                "child_id": child_id,
            }
        )
    )


def _group_request(run: PumpStationWorldRun) -> ContinualRolloutGroupRequest:
    definition_ref, profile_ref = _exact_refs()
    manifest = run.manifest
    assert isinstance(manifest, PumpStationRegisteredWorldRunManifest)
    return ContinualRolloutGroupRequest(
        request_id="catalogue-rollout-request",
        group_id="catalogue-rollout-group",
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        authority_id="catalogue-interface-host",
        definition_ref=definition_ref,
        profile_ref=profile_ref,
        parent_manifest_content_sha256=pump_station_artifact_id(manifest),
        parent_snapshot=_continual_snapshot(run),
        origin_verification_content_sha256=pump_station_artifact_id(run.verify()),
        reason="Create two isolated continuations through the registered world port.",
        children=tuple(
            ContinualRolloutChildRequest(
                child_id=child_id,
                run_id=f"catalogue-{child_id}-run",
                episode_id=f"catalogue-{child_id}-episode",
                world_branch_id=f"catalogue-{child_id}-branch",
            )
            for child_id in ("control", "candidate")
        ),
    )


def _ready_ssc03_rollout(
    tmp_path: Path,
) -> tuple[ContinualWorldInterfaceContext, ContinualRolloutGroupRequest]:
    definition = ssc03_hydraulic_continual_world_definition()
    profile_ref = definition.profile_ref("major_idf_revision", "1")
    loaded = definition.load_profile(profile_ref)
    assert isinstance(loaded.value, Ssc03HydraulicContinualProfile)
    compiled = loaded.value.compile(tmp_path / "ssc03-package")
    environment = loaded.value.build_smoke_environment(compiled.package_dir)
    assert environment is not None
    parent_run = tmp_path / "ssc03-parent-run"
    run_evidence_lifecycle(
        compiled.package_dir,
        parent_run,
        episode_environment=environment,
    )
    origin = ssc03_hydraulic_rollout_origin(
        compiled.package_dir,
        parent_run,
        checkpoint_id="revision_analysis",
    )
    request = ContinualRolloutGroupRequest(
        request_id="catalogue-ssc03-request",
        group_id="catalogue-ssc03-group",
        task_world_id=definition.ref.task_world_id,
        authority_id="catalogue-ssc03-host",
        definition_ref=definition.ref,
        profile_ref=profile_ref,
        parent_manifest_content_sha256=origin.parent_manifest_content_sha256,
        parent_snapshot=origin.parent_snapshot,
        origin_verification_content_sha256=origin.origin_verification_content_sha256,
        reason="Read one ready SSC-03 rollout through the catalogue control route.",
        children=(
            ContinualRolloutChildRequest(
                child_id="catalogue-ssc03-child",
                run_id="catalogue-ssc03-child-run",
                episode_id="catalogue-ssc03-child-episode",
                world_branch_id="catalogue-ssc03-child-branch",
            ),
        ),
    )
    rollout_root = tmp_path / "ssc03-rollouts"
    ContinualRolloutControl(
        definition,
        parent_run_root=parent_run,
        rollout_repository_root=rollout_root,
        authorised_principal_ids=("catalogue-ssc03-host",),
        package_root=compiled.package_dir,
    ).create_group(request)
    return (
        ContinualWorldInterfaceContext(
            catalogue=default_continual_world_catalogue(),
            run_root=parent_run,
            rollout_repository_root=rollout_root,
            authorised_principal_ids=("catalogue-ssc03-host",),
            package_root=compiled.package_dir,
        ),
        request,
    )


def _run_installed_interface(
    *,
    command: str,
    run_root: Path,
    request_path: Path,
    host_authority_id: str | None = None,
) -> dict[str, Any]:
    executable = Path(sys.executable).parent / "aec-bench"
    arguments = [
        str(executable),
        "--json",
        "task",
        "pump-station-world",
        command,
        "--run-dir",
        str(run_root),
        "--request-path",
        str(request_path),
    ]
    if host_authority_id is not None:
        arguments.extend(("--host-authority-id", host_authority_id))
    environment = dict(os.environ)
    source_root = str(PROJECT_ROOT / "src")
    current_pythonpath = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = (
        source_root if not current_pythonpath else f"{source_root}{os.pathsep}{current_pythonpath}"
    )
    completed = subprocess.run(
        arguments,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        env=environment,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    return cast(dict[str, Any], json.loads(completed.stdout)["data"])


def test_actor_and_control_json_requests_are_separate_exact_envelopes(tmp_path: Path) -> None:
    run = _registered_run(tmp_path / "world", identity="catalogue-envelope")
    definition_ref, profile_ref = _exact_refs()
    actor = _actor_request(
        run,
        definition_ref=definition_ref,
        profile_ref=profile_ref,
    )
    control = _control_request(
        operation="execute",
        definition_ref=definition_ref,
        profile_ref=profile_ref,
        control_request=WorldControlRequest(
            request_id="catalogue-envelope-verify",
            operation="verify",
            task_world_id=PUMP_STATION_TASK_WORLD_ID,
            authority_id="catalogue-interface-host",
        ),
    )

    assert actor.__class__ is ContinualWorldActorRequest
    assert control.__class__ is ContinualWorldControlRequest
    assert "definition_ref" not in type(actor).model_fields
    assert "profile_ref" not in type(actor).model_fields
    assert "surface" not in type(actor).model_fields
    assert "surface" not in type(control).model_fields
    assert "control_request" not in type(actor).model_fields
    assert "session_request" not in type(control).model_fields

    with pytest.raises(ValidationError):
        ContinualWorldActorRequest.model_validate(
            {
                **actor.model_dump(mode="json"),
                "authority_id": "catalogue-interface-host",
            }
        )
    with pytest.raises(ValidationError):
        ContinualWorldControlRequest.model_validate(
            {
                **control.model_dump(mode="json"),
                "session_request": _resume_request(run).model_dump(mode="json"),
            }
        )


def test_control_execute_rejects_a_nested_authority_when_both_principals_are_authorised(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "world"
    run = _registered_run(run_root, identity="catalogue-authority")
    definition_ref, profile_ref = _exact_refs()
    context = ContinualWorldInterfaceContext(
        catalogue=default_continual_world_catalogue(),
        run_root=run_root,
        rollout_repository_root=None,
        authorised_principal_ids=("envelope-host", "payload-host"),
    )

    with pytest.raises(ValidationError, match="task control request differs from its control envelope"):
        dispatch_continual_control(
            context=context,
            request=_control_request(
                operation="execute",
                definition_ref=definition_ref,
                profile_ref=profile_ref,
                authority_id="envelope-host",
                control_request=WorldControlRequest(
                    request_id="catalogue-authority-verify",
                    operation="verify",
                    task_world_id=PUMP_STATION_TASK_WORLD_ID,
                    authority_id="payload-host",
                ),
            ),
        )

    assert run.snapshot().sequence == 0


def test_control_execute_rejects_a_nested_task_world_before_dispatch() -> None:
    definition_ref, profile_ref = _exact_refs()

    with pytest.raises(ValidationError, match="task control request differs from its control envelope"):
        _control_request(
            operation="execute",
            definition_ref=definition_ref,
            profile_ref=profile_ref,
            control_request=WorldControlRequest(
                request_id="catalogue-foreign-world-verify",
                operation="verify",
                task_world_id="foreign-task-world",
                authority_id="catalogue-interface-host",
            ),
        )


def test_catalogue_dispatch_resolves_exact_profile_for_actor_and_generic_verify(tmp_path: Path) -> None:
    run_root = tmp_path / "world"
    run = _registered_run(run_root, identity="catalogue-actor")
    context = _context(tmp_path, run_root=run_root)
    definition_ref, profile_ref = _exact_refs()
    stale_definition = definition_ref.model_copy(update={"content_sha256": "f" * 64})
    stale_profile = profile_ref.model_copy(update={"profile_content_sha256": "f" * 64})

    with pytest.raises(ValueError, match="content-pinned definition does not match"):
        dispatch_continual_actor(
            context=replace(context, actor_definition_ref=stale_definition),
            request=_actor_request(
                run,
                definition_ref=stale_definition,
                profile_ref=profile_ref,
            ),
        )
    with pytest.raises(ValueError, match="content-pinned profile does not match"):
        dispatch_continual_actor(
            context=replace(context, actor_profile_ref=stale_profile),
            request=_actor_request(
                run,
                definition_ref=definition_ref,
                profile_ref=stale_profile,
            ),
        )

    observed = dispatch_continual_actor(
        context=context,
        request=_actor_request(
            run,
            definition_ref=definition_ref,
            profile_ref=profile_ref,
        ),
    )
    assert isinstance(observed, WorldActorObservation)
    action = WorldActorActionRequest(
        request_id="catalogue-condition-check",
        decision_id=observed.decision_id,
        action_name="request_condition_check",
        arguments={
            "pump_id": "pump-a",
            "reason": "Record the current condition through the registered actor port.",
        },
    )

    invoked = dispatch_continual_actor(
        context=context,
        request=_actor_request(
            run,
            definition_ref=definition_ref,
            profile_ref=profile_ref,
            operation="invoke",
            action_request=action,
        ),
    )
    verified = dispatch_continual_control(
        context=context,
        request=_control_request(
            operation="execute",
            definition_ref=definition_ref,
            profile_ref=profile_ref,
            control_request=WorldControlRequest(
                request_id="catalogue-verify",
                operation="verify",
                task_world_id=PUMP_STATION_TASK_WORLD_ID,
                authority_id="catalogue-interface-host",
            ),
        ),
    )

    assert isinstance(invoked, WorldActorActionResult)
    assert invoked.request_id == action.request_id
    assert invoked.next_observation is not None
    assert invoked.next_observation.decision_id != observed.decision_id
    assert isinstance(verified, WorldControlResult)
    assert verified.verification is not None
    assert verified.verification.valid is True
    assert verified.verification.final_state_id == run.snapshot().state_id


def test_installed_json_uses_the_catalogue_actor_and_control_routes(tmp_path: Path) -> None:
    run_root = tmp_path / "world"
    run = _registered_run(run_root, identity="catalogue-installed")
    definition_ref, profile_ref = _exact_refs()
    actor_request = _actor_request(
        run,
        definition_ref=definition_ref,
        profile_ref=profile_ref,
    )
    actor_path = tmp_path / "actor-request.json"
    actor_path.write_text(actor_request.model_dump_json(), encoding="utf-8")
    observed = _run_installed_interface(
        command="actor-interface",
        run_root=run_root,
        request_path=actor_path,
    )
    control_request = _control_request(
        operation="execute",
        definition_ref=definition_ref,
        profile_ref=profile_ref,
        control_request=WorldControlRequest(
            request_id="catalogue-installed-verify",
            operation="verify",
            task_world_id=PUMP_STATION_TASK_WORLD_ID,
            authority_id="catalogue-interface-host",
        ),
    )
    control_path = tmp_path / "control-request.json"
    control_path.write_text(control_request.model_dump_json(), encoding="utf-8")
    verified = _run_installed_interface(
        command="control-interface",
        run_root=run_root,
        request_path=control_path,
        host_authority_id="catalogue-interface-host",
    )

    assert isinstance(observed["decision_id"], str)
    assert observed["view"]["state_id"] == run.snapshot().state_id
    assert verified["verification"]["valid"] is True
    assert verified["verification"]["final_state_id"] == run.snapshot().state_id


def test_catalogue_control_dispatch_runs_every_shared_rollout_operation(tmp_path: Path) -> None:
    run_root = tmp_path / "world"
    run = _registered_run(run_root, identity="catalogue-rollout")
    context = _context(tmp_path, run_root=run_root)
    definition_ref, profile_ref = _exact_refs()
    group_request = _group_request(run)

    created = dispatch_continual_control(
        context=context,
        request=_control_request(
            operation="create_rollout_group",
            definition_ref=definition_ref,
            profile_ref=profile_ref,
            rollout_group_request=group_request,
        ),
    )
    status = dispatch_continual_control(
        context=context,
        request=_control_request(
            operation="rollout_group_status",
            definition_ref=definition_ref,
            profile_ref=profile_ref,
            group_id=group_request.group_id,
        ),
    )
    inspected = dispatch_continual_control(
        context=context,
        request=_control_request(
            operation="inspect_rollout_group",
            definition_ref=definition_ref,
            profile_ref=profile_ref,
            group_id=group_request.group_id,
        ),
    )
    child_ref = dispatch_continual_control(
        context=context,
        request=_control_request(
            operation="rollout_child_run_ref",
            definition_ref=definition_ref,
            profile_ref=profile_ref,
            group_id=group_request.group_id,
            child_id="candidate",
        ),
    )

    assert isinstance(created, ContinualRolloutLineage)
    assert created.request_content_sha256 == group_request.content_sha256
    assert isinstance(status, ContinualRolloutGroupStatus)
    assert status.state is ContinualRolloutGroupState.READY
    assert status.created_child_ids == ("control", "candidate")
    assert isinstance(inspected, ContinualRolloutLineage)
    assert inspected == created
    assert isinstance(child_ref, ContinualRolloutChildRunRef)
    assert child_ref.group_id == group_request.group_id
    assert child_ref.child_id == "candidate"
    assert child_ref.initial_snapshot.sequence == group_request.parent_snapshot.sequence
    assert _continual_snapshot(run) == group_request.parent_snapshot


def test_catalogue_rollout_status_does_not_require_an_actor_execution_port(tmp_path: Path) -> None:
    context, group_request = _ready_ssc03_rollout(tmp_path)

    status = dispatch_continual_control(
        context=context,
        request=_control_request(
            operation="rollout_group_status",
            definition_ref=group_request.definition_ref,
            profile_ref=group_request.profile_ref,
            group_id=group_request.group_id,
            authority_id="catalogue-ssc03-host",
        ),
    )

    assert isinstance(status, ContinualRolloutGroupStatus)
    assert status.state is ContinualRolloutGroupState.READY
    assert status.created_child_ids == ("catalogue-ssc03-child",)
