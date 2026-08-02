# ABOUTME: Proves registered V4 actions use the existing pump world-run commit chain.
# ABOUTME: Checks exact actor bindings, retry identity, and the absence of duplicate generation storage.

from __future__ import annotations

import multiprocessing
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from pydantic import JsonValue

from aec_bench.contracts.world_interface import WorldActorActionRequest
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_models import (
    PumpStationCoupledModel,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PUMP_STATION_BOUND_CONTROL_VERSION,
    PUMP_STATION_COMMON_BOUNDARY_CONTROL_VERSION,
    PUMP_STATION_OPERATIONS_REVIEW_VERSION,
    PUMP_STATION_PROCESS_OUTCOME_VERSION,
    PumpStationBoundControlRequest,
    PumpStationCommonBoundaryRequest,
    PumpStationCoupledStewardshipState,
    PumpStationOperationsBoundaryReviewRequest,
    PumpStationProcessOutcomeRequest,
    PumpStationRootControl,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_verifier import (
    PumpStationRunStepV4,
    PumpStationVerificationReportV4,
    verify_stewardship_run_v4,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_views import (
    PumpStationCoupledActorView,
    coupled_actor_view_id,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PUMP_STATION_SERIALIZATION_VERSION,
    PumpStationStagedTransitionV4,
    PumpStationStateSnapshotRef,
    PumpStationWorldRunCommit,
    PumpStationWorldRunCommitV2,
    PumpStationWorldRunError,
    PumpStationWorldRunManifestV2,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_serialization import (
    pump_station_artifact_id,
)

type PumpStationReferenceRun = PumpStationWorldRun[
    PumpStationCoupledModel,
    PumpStationCoupledStewardshipState,
]


def _apply_registered_actor_in_child(
    root: Path,
    snapshot: PumpStationStateSnapshotRef,
    request_value: dict[str, Any],
    ready: Any,
    start: Any,
    results: Any,
) -> None:
    run = PumpStationWorldRun.resume_reference_system(
        repository=PumpStationWorldRunRepository(root),
        snapshot=snapshot,
    )
    request = WorldActorActionRequest.model_validate(request_value)
    ready.set()
    if not start.wait(10):
        results.put(("error", "start-timeout"))
        return
    try:
        transition = run.apply_v4_actor_action(request)
    except PumpStationWorldRunError as error:
        results.put(("error", error.code))
        return
    results.put(
        (
            "applied",
            transition.receipt.transition_id,
            transition.state.state_id,
            run.snapshot().commit_id,
        )
    )


def _start_reference_run(root: Path) -> PumpStationReferenceRun:
    return PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(root),
        run_id="run-v4-transitions",
        episode_id="episode-v4-transitions",
        world_branch_id="branch-v4-transitions",
    )


def _actor_request(
    run: PumpStationReferenceRun,
    *,
    request_id: str,
    action_name: str = "request_post_maintenance_verification",
    arguments: dict[str, JsonValue] | None = None,
    reason: str,
) -> WorldActorActionRequest:
    observation = run.observe_v4_actor(
        session_id="session-v4-transitions",
        agent_tenure_id="reference-controller",
    )
    return WorldActorActionRequest(
        request_id=request_id,
        action_name=action_name,
        binding=observation.binding,
        arguments={
            **(
                arguments
                if arguments is not None
                else {
                    "pump_id": "pump-a",
                    "backlog_item_id": "backlog-a-verification-001",
                }
            ),
            "reason": reason,
        },
    )


def _bound_control(
    run: PumpStationReferenceRun,
    control: PumpStationRootControl,
) -> PumpStationBoundControlRequest:
    snapshot = run.snapshot()
    request_id = (
        control.review_id if isinstance(control, PumpStationOperationsBoundaryReviewRequest) else control.request_id
    )
    return PumpStationBoundControlRequest(
        control_envelope_version=PUMP_STATION_BOUND_CONTROL_VERSION,
        request_id=request_id,
        run_id=snapshot.run_id,
        episode_id=snapshot.episode_id,
        world_branch_id=snapshot.world_branch_id,
        base_state_id=snapshot.state_id,
        base_commit_id=snapshot.commit_id,
        based_on_sequence=snapshot.sequence,
        control=control,
    )


def _verify_recorded_v4_steps(
    run: PumpStationReferenceRun,
    initial_state: PumpStationCoupledStewardshipState,
    steps: tuple[PumpStationRunStepV4, ...],
    *,
    expected_final_state_id: str,
) -> PumpStationVerificationReportV4:
    manifest = run.manifest
    assert isinstance(manifest, PumpStationWorldRunManifestV2)
    return verify_stewardship_run_v4(
        run.model,
        initial_state,
        steps,
        expected_final_state_id=expected_final_state_id,
        expected_task_world_id=manifest.task_world_id,
        expected_run_id=manifest.run_id,
        expected_episode_id=manifest.episode_id,
        expected_world_branch_id=manifest.world_branch_id,
        expected_actor_id="pump-station-actor",
        expected_source_artifact_ids=(
            manifest.reference_system_content_id,
            manifest.package_content_id,
            manifest.temporal_bundle_content_id,
        ),
    )


def _record_one_v4_actor_step(
    root: Path,
) -> tuple[
    PumpStationReferenceRun,
    PumpStationCoupledStewardshipState,
    WorldActorActionRequest,
    PumpStationRunStepV4,
]:
    run = _start_reference_run(root)
    initial_state = run.state
    request = _actor_request(
        run,
        request_id="recorded-v4-actor-step",
        reason="Record one actor step for integrity checks.",
    )
    run.apply_v4_actor_action(request)
    return run, initial_state, request, run.repository.v4_steps()[0]


def _stage_unselected_v4_actor_outcome(
    run: PumpStationReferenceRun,
    request: WorldActorActionRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> PumpStationStagedTransitionV4:
    captured: list[PumpStationStagedTransitionV4] = []

    def interrupt_after_staging(staged: PumpStationStagedTransitionV4) -> None:
        captured.append(staged)
        raise OSError("interrupt after immutable V4 staging")

    with monkeypatch.context() as patch:
        patch.setattr(
            run.repository,
            "_publish_staged_v4_transition_under_lock",
            interrupt_after_staging,
        )
        with pytest.raises(OSError, match="after immutable V4 staging"):
            run.apply_v4_actor_action(request)
    assert len(captured) == 1
    return captured[0]


def _publish_duplicate_v4_outcome(
    repository: PumpStationWorldRunRepository,
    staged: PumpStationStagedTransitionV4,
) -> str:
    duplicate_receipt = replace(
        staged.transition.receipt,
        reason=f"{staged.transition.receipt.reason} Duplicate durable outcome.",
    )
    duplicate_receipt_id = pump_station_artifact_id(
        duplicate_receipt,
        record_profile="v4",
    )
    repository._publish_content(
        "receipts",
        duplicate_receipt_id,
        duplicate_receipt,
        record_profile="v4",
    )
    duplicate_commit = replace(
        staged.commit,
        receipt_content_id=duplicate_receipt_id,
    )
    duplicate_commit_id = pump_station_artifact_id(
        duplicate_commit,
        record_profile="v4",
    )
    repository._publish_content(
        "commits",
        duplicate_commit_id,
        duplicate_commit,
        record_profile="v4",
    )
    return duplicate_commit_id


def test_registered_actor_action_selects_one_existing_world_run_commit(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    run = _start_reference_run(root)
    request = _actor_request(
        run,
        request_id="verify-a-001",
        reason="Start the required independent Pump A verification.",
    )
    opening = run.snapshot()

    assert request.binding.commit_id == opening.commit_id
    assert request.binding.commit_id != request.binding.state_id

    transition = run.apply_v4_actor_action(request)
    selected = run.snapshot()
    commits = run.repository.commits()

    assert transition.receipt.request_id == request.request_id
    assert transition.receipt.actor_action
    assert selected.sequence == 1
    assert selected.state_id == transition.state.state_id
    assert isinstance(commits[-1], PumpStationWorldRunCommitV2)
    assert commits[-1].request_id == request.request_id
    assert len(commits) == 2
    assert not (root / "HEAD").exists()
    assert not (root / "generations").exists()

    repeated = run.apply_v4_actor_action(request)

    assert repeated == transition
    assert run.snapshot() == selected
    assert run.repository.commits() == commits


def test_registered_actor_request_id_rejects_changed_content(
    tmp_path: Path,
) -> None:
    run = _start_reference_run(tmp_path / "run")
    original = _actor_request(
        run,
        request_id="verify-a-conflict",
        reason="Start the required independent Pump A verification.",
    )
    run.apply_v4_actor_action(original)
    changed = WorldActorActionRequest(
        request_id=original.request_id,
        action_name=original.action_name,
        binding=original.binding,
        arguments={
            **original.arguments,
            "reason": "Use different content under the same request identity.",
        },
    )

    with pytest.raises(PumpStationWorldRunError) as raised:
        run.apply_v4_actor_action(changed)

    assert raised.value.code == "v4-command-id-conflict"
    assert run.snapshot().sequence == 1
    assert len(run.repository.commits()) == 2


def test_legacy_request_identity_cannot_be_reused_by_a_registered_action(
    tmp_path: Path,
) -> None:
    run = _start_reference_run(tmp_path / "run")
    opening = run.snapshot()
    request_id = "cross-profile-legacy-to-v4"
    legacy_commit = PumpStationWorldRunCommit(
        serialization_version=PUMP_STATION_SERIALIZATION_VERSION,
        run_id=run.manifest.run_id,
        sequence=1,
        parent_commit_id=opening.commit_id,
        state_id=opening.state_id,
        proposal_id=request_id,
        proposal_content_id=None,
        information_set_content_id=None,
        receipt_content_id=None,
        event_batch_content_id=None,
    )
    legacy_commit_id = pump_station_artifact_id(legacy_commit)
    run.repository._publish_content("commits", legacy_commit_id, legacy_commit)
    request = _actor_request(
        run,
        request_id=request_id,
        reason="Try to reuse one legacy transition identity.",
    )

    with pytest.raises(PumpStationWorldRunError) as raised:
        run.apply_v4_actor_action(request)

    assert raised.value.code == "v4-command-id-conflict"
    assert run.snapshot() == opening
    assert run.repository.v4_steps() == ()


def test_registered_request_identity_cannot_enter_the_legacy_proposal_path(
    tmp_path: Path,
) -> None:
    run = _start_reference_run(tmp_path / "run")
    opening = run.snapshot()
    request = _actor_request(
        run,
        request_id="cross-profile-v4-to-legacy",
        reason="Create one registered request identity.",
    )
    run.apply_v4_actor_action(request)
    step = run.repository.v4_steps()[0]
    assert step.proposal is not None
    assert step.information_set is not None

    with pytest.raises(PumpStationWorldRunError) as raised:
        run.repository._reject_proposal_collision(
            step.proposal,
            information_set=step.information_set,
            parent_commit_id=opening.commit_id,
        )

    assert raised.value.code == "proposal-id-conflict"
    assert run.snapshot().sequence == 1


def test_repository_rejects_false_actor_request_content_before_selection(
    tmp_path: Path,
) -> None:
    _, _, _, step = _record_one_v4_actor_step(tmp_path / "donor")
    target = _start_reference_run(tmp_path / "target")
    opening = target.snapshot()
    manifest = target.manifest
    assert isinstance(manifest, PumpStationWorldRunManifestV2)
    assert step.proposal is not None
    assert step.information_set is not None
    false_command = replace(step.command, request_content_id="0" * 64)

    with pytest.raises(PumpStationWorldRunError) as raised:
        staged = target.repository.stage_v4_transition(
            manifest=manifest,
            prior_snapshot=opening,
            command=false_command,
            proposal=step.proposal,
            information_set=step.information_set,
            transition=step.transition,
        )
        target.repository.publish_staged_v4_transition(staged)

    assert raised.value.code == "command-content"
    assert target.snapshot() == opening


def test_repository_rejects_caller_manifest_that_differs_from_the_stored_run(
    tmp_path: Path,
) -> None:
    _, _, request, step = _record_one_v4_actor_step(tmp_path / "donor")
    target = _start_reference_run(tmp_path / "target")
    opening = target.snapshot()
    manifest = target.manifest
    assert isinstance(manifest, PumpStationWorldRunManifestV2)
    assert step.proposal is not None
    assert step.information_set is not None
    foreign_task_world_id = "foreign-task-world"
    foreign_binding = request.binding.model_copy(
        update={"task_world_id": foreign_task_world_id},
    )
    foreign_request = WorldActorActionRequest(
        request_id=request.request_id,
        action_name=request.action_name,
        binding=foreign_binding,
        arguments=request.arguments,
    )
    foreign_command = replace(
        step.command,
        task_world_id=foreign_task_world_id,
        request_content_id=foreign_request.content_sha256,
    )
    foreign_manifest = replace(
        manifest,
        task_world_id=foreign_task_world_id,
    )

    with pytest.raises(PumpStationWorldRunError) as raised:
        staged = target.repository.stage_v4_transition(
            manifest=foreign_manifest,
            prior_snapshot=opening,
            command=foreign_command,
            proposal=step.proposal,
            information_set=step.information_set,
            transition=step.transition,
        )
        target.repository.publish_staged_v4_transition(staged)

    assert raised.value.code == "world-run-identity"
    assert target.snapshot() == opening


def test_v4_replay_rejects_forged_actor_view_content(
    tmp_path: Path,
) -> None:
    run, initial_state, _, step = _record_one_v4_actor_step(tmp_path / "run")
    assert step.information_set is not None
    view = step.information_set.base_view
    assert isinstance(view, PumpStationCoupledActorView)
    pending_forged_view = replace(
        view,
        view_id="pending",
        episode_id="foreign-episode",
        world_branch_id="foreign-branch",
        source_artifact_ids=("foreign-source",),
    )
    forged_view = replace(
        pending_forged_view,
        view_id=coupled_actor_view_id(pending_forged_view),
    )
    forged_step = replace(
        step,
        information_set=replace(step.information_set, base_view=forged_view),
    )

    report = _verify_recorded_v4_steps(
        run,
        initial_state,
        (forged_step,),
        expected_final_state_id=step.transition.state.state_id,
    )

    assert report.valid is False
    assert any("actor-view" in issue for issue in report.issues)


def test_v4_replay_rejects_self_consistent_foreign_command_scope(
    tmp_path: Path,
) -> None:
    run, initial_state, request, step = _record_one_v4_actor_step(tmp_path / "run")
    foreign_binding = request.binding.model_copy(
        update={
            "episode_id": "foreign-episode",
            "world_branch_id": "foreign-branch",
        },
    )
    foreign_request = WorldActorActionRequest(
        request_id=request.request_id,
        action_name=request.action_name,
        binding=foreign_binding,
        arguments=request.arguments,
    )
    foreign_step = replace(
        step,
        command=replace(
            step.command,
            episode_id="foreign-episode",
            world_branch_id="foreign-branch",
            request_content_id=foreign_request.content_sha256,
        ),
    )

    report = _verify_recorded_v4_steps(
        run,
        initial_state,
        (foreign_step,),
        expected_final_state_id=step.transition.state.state_id,
    )

    assert report.valid is False
    assert any("command-scope" in issue for issue in report.issues)


def test_v4_replay_reports_malformed_actor_action_as_invalid(
    tmp_path: Path,
) -> None:
    run, initial_state, request, step = _record_one_v4_actor_step(tmp_path / "run")
    malformed_request = WorldActorActionRequest(
        request_id=request.request_id,
        action_name="unknown-actor-action",
        binding=request.binding,
        arguments=request.arguments,
    )
    malformed_step = replace(
        step,
        command=replace(
            step.command,
            action_name=malformed_request.action_name,
            request_content_id=malformed_request.content_sha256,
        ),
    )

    report = _verify_recorded_v4_steps(
        run,
        initial_state,
        (malformed_step,),
        expected_final_state_id=step.transition.state.state_id,
    )

    assert report.valid is False
    assert any("transition-replay-error" in issue for issue in report.issues)


def test_stale_actor_binding_fails_before_a_second_transition(
    tmp_path: Path,
) -> None:
    run = _start_reference_run(tmp_path / "run")
    first = _actor_request(
        run,
        request_id="condition-check-first",
        action_name="request_condition_check",
        arguments={"pump_id": "pump-a"},
        reason="Record the first Pump A condition check.",
    )
    stale = WorldActorActionRequest(
        request_id="condition-check-stale",
        action_name="request_condition_check",
        binding=first.binding,
        arguments={
            "pump_id": "pump-b",
            "reason": "Try another check from the stale parent binding.",
        },
    )
    run.apply_v4_actor_action(first)
    selected = run.snapshot()

    with pytest.raises(PumpStationWorldRunError) as raised:
        run.apply_v4_actor_action(stale)

    assert raised.value.code == "actor-request-binding"
    assert run.snapshot() == selected
    assert len(run.repository.v4_steps()) == 1


def test_invalid_control_authority_leaves_the_selected_pointer_unchanged(
    tmp_path: Path,
) -> None:
    run = _start_reference_run(tmp_path / "run")
    opening = run.snapshot()
    invalid = _bound_control(
        run,
        PumpStationCommonBoundaryRequest(
            version=PUMP_STATION_COMMON_BOUNDARY_CONTROL_VERSION,
            request_id="invalid-power-control",
            authority_id="maintenance-controller",
            boundary_kind="power",
            available=False,
            base_state_id=run.state.state_id,
        ),
    )

    with pytest.raises(PumpStationWorldRunError) as raised:
        run.apply_v4_control(invalid)

    assert raised.value.code == "common-boundary-authority"
    assert run.snapshot() == opening
    assert run.repository.v4_steps() == ()


def test_changed_control_content_conflicts_before_stale_scope_evaluation(
    tmp_path: Path,
) -> None:
    run = _start_reference_run(tmp_path / "run")
    original = _bound_control(
        run,
        PumpStationCommonBoundaryRequest(
            version=PUMP_STATION_COMMON_BOUNDARY_CONTROL_VERSION,
            request_id="common-boundary-conflict",
            authority_id="operations-controller",
            boundary_kind="power",
            available=False,
            base_state_id=run.state.state_id,
        ),
    )
    run.apply_v4_control(original)
    changed = PumpStationBoundControlRequest(
        control_envelope_version=original.control_envelope_version,
        request_id=original.request_id,
        run_id=original.run_id,
        episode_id=original.episode_id,
        world_branch_id=original.world_branch_id,
        base_state_id=original.base_state_id,
        base_commit_id=original.base_commit_id,
        based_on_sequence=original.based_on_sequence,
        control=PumpStationCommonBoundaryRequest(
            version=PUMP_STATION_COMMON_BOUNDARY_CONTROL_VERSION,
            request_id=original.request_id,
            authority_id="operations-controller",
            boundary_kind="discharge",
            available=False,
            base_state_id=original.base_state_id,
        ),
    )

    with pytest.raises(PumpStationWorldRunError) as raised:
        run.apply_v4_control(changed)

    assert raised.value.code == "v4-command-id-conflict"
    assert run.snapshot().sequence == 1
    assert len(run.repository.v4_steps()) == 1


def test_root_host_controls_use_the_same_commit_chain_and_exact_retry(
    tmp_path: Path,
) -> None:
    run = _start_reference_run(tmp_path / "run")
    verification = _actor_request(
        run,
        request_id="verify-a-for-review",
        reason="Start the required independent Pump A verification.",
    )
    run.apply_v4_actor_action(verification)
    continuation = _actor_request(
        run,
        request_id="continue-to-verification",
        action_name="continue_operation",
        arguments={},
        reason="Continue to the verification completion event.",
    )
    run.apply_v4_actor_action(continuation)
    state = run.state
    review = _bound_control(
        run,
        PumpStationOperationsBoundaryReviewRequest(
            version=PUMP_STATION_OPERATIONS_REVIEW_VERSION,
            review_id="operations-review-a-registered",
            review_kind="post_verification_restriction",
            pump_id="pump-a",
            restriction_or_isolation_permit_id="restriction-a-run-in-001",
            accepted_evidence_id="evidence-pump-a-verification-pass-001",
            requested_outcome="release",
            base_state_id=state.state_id,
            operations_authority_id="operations-controller",
            reason="Release the matched boundary after accepted verification.",
        ),
    )

    transition = run.apply_v4_control(review)
    selected = run.snapshot()
    commits = run.repository.commits()

    assert not transition.receipt.actor_action
    assert transition.receipt.action_or_control_kind == "operations_boundary_review"
    assert isinstance(commits[-1], PumpStationWorldRunCommitV2)
    assert commits[-1].proposal_content_id is None
    assert commits[-1].information_set_content_id is None

    repeated = run.apply_v4_control(review)

    assert repeated == transition
    assert run.snapshot() == selected
    assert run.repository.commits() == commits


def test_process_outcome_and_common_boundary_controls_are_durable_root_transitions(
    tmp_path: Path,
) -> None:
    process_run = _start_reference_run(tmp_path / "process-run")
    process_run.apply_v4_actor_action(
        _actor_request(
            process_run,
            request_id="verify-a-for-failure",
            reason="Start the verification before recording its failed outcome.",
        )
    )
    active = process_run.state.processes[-1]
    process_control = _bound_control(
        process_run,
        PumpStationProcessOutcomeRequest(
            version=PUMP_STATION_PROCESS_OUTCOME_VERSION,
            request_id="verification-failed-001",
            authority_id="verification-engineer-01",
            process_id=active.process_id,
            outcome="failed",
            evidence_id="evidence-verification-failed-001",
            base_state_id=process_run.state.state_id,
        ),
    )

    process_transition = process_run.apply_v4_control(process_control)

    assert process_transition.receipt.action_or_control_kind == "process_outcome"
    assert process_transition.receipt.required_authorities == ("verification",)
    assert process_run.repository.v4_steps()[-1].command.kind == "process_outcome"

    boundary_run = _start_reference_run(tmp_path / "boundary-run")
    boundary_control = _bound_control(
        boundary_run,
        PumpStationCommonBoundaryRequest(
            version=PUMP_STATION_COMMON_BOUNDARY_CONTROL_VERSION,
            request_id="power-unavailable-001",
            authority_id="operations-controller",
            boundary_kind="power",
            available=False,
            base_state_id=boundary_run.state.state_id,
        ),
    )

    boundary_transition = boundary_run.apply_v4_control(boundary_control)

    assert boundary_transition.receipt.action_or_control_kind == "common_boundary_control"
    assert not boundary_transition.state.physical.common_boundary.power_available
    assert boundary_run.repository.v4_steps()[-1].command.kind == "common_boundary"


def test_registered_run_reopens_and_independently_replays_mixed_v4_history(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    run = _start_reference_run(root)
    actor_transition = run.apply_v4_actor_action(
        _actor_request(
            run,
            request_id="condition-check-a-001",
            action_name="request_condition_check",
            arguments={"pump_id": "pump-a"},
            reason="Record a current Pump A condition check.",
        )
    )
    control = _bound_control(
        run,
        PumpStationCommonBoundaryRequest(
            version=PUMP_STATION_COMMON_BOUNDARY_CONTROL_VERSION,
            request_id="discharge-unavailable-001",
            authority_id="operations-controller",
            boundary_kind="discharge",
            available=False,
            base_state_id=run.state.state_id,
        ),
    )
    control_transition = run.apply_v4_control(control)
    selected = run.snapshot()

    reopened = PumpStationWorldRun.resume_reference_system(
        repository=PumpStationWorldRunRepository(root),
        snapshot=selected,
    )
    report = reopened.verify_v4()

    assert reopened.state == control_transition.state
    assert report.valid
    assert report.issues == ()
    assert report.replayed_transition_ids == (
        actor_transition.receipt.transition_id,
        control_transition.receipt.transition_id,
    )
    assert report.final_state_id == selected.state_id


def test_interrupted_v4_publication_recovers_one_exact_actor_effect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = _start_reference_run(tmp_path / "run")
    request = _actor_request(
        run,
        request_id="condition-check-recovery",
        action_name="request_condition_check",
        arguments={"pump_id": "pump-a"},
        reason="Record one recoverable Pump A condition check.",
    )
    original_replace = run.repository._replace_current

    def interrupt_before_pointer(_pointer: object) -> None:
        raise OSError("injected interruption before current pointer replacement")

    monkeypatch.setattr(run.repository, "_replace_current", interrupt_before_pointer)
    with pytest.raises(OSError, match="before current pointer"):
        run.apply_v4_actor_action(request)

    assert run.snapshot().sequence == 0
    monkeypatch.setattr(run.repository, "_replace_current", original_replace)

    recovered = run.apply_v4_actor_action(request)

    assert run.snapshot().sequence == 1
    assert len(run.repository.v4_steps()) == 1
    assert sum(evidence.evidence_id == "condition-check-pump-a-1" for evidence in recovered.state.evidence) == 1


def test_unselected_exact_command_recovers_its_durable_transition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "run"
    run = _start_reference_run(root)
    request = _actor_request(
        run,
        request_id="condition-check-staged-recovery",
        action_name="request_condition_check",
        arguments={"pump_id": "pump-a"},
        reason="Recover the staged Pump A condition check.",
    )
    command = run._v4_actor_command(request)
    original_replace = run.repository._replace_current

    def interrupt_before_pointer(_pointer: object) -> None:
        raise OSError("interrupt before current pointer")

    monkeypatch.setattr(
        run.repository,
        "_replace_current",
        interrupt_before_pointer,
    )
    with pytest.raises(OSError, match="before current pointer"):
        run.apply_v4_actor_action(request)
    monkeypatch.setattr(run.repository, "_replace_current", original_replace)

    recovered = run.repository.recover_staged_v4_command(command)

    assert recovered is not None
    assert recovered.receipt.request_id == request.request_id
    assert run.snapshot().sequence == 1
    assert run.snapshot().commit_id in {path.stem for path in (root / "commits").glob("*.json")}
    assert len(run.repository.v4_steps()) == 1


def test_staged_v4_recovery_cannot_reselect_an_old_parent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = _start_reference_run(tmp_path / "run")
    opening = run.snapshot()
    orphan_request = _actor_request(
        run,
        request_id="condition-check-orphaned-parent",
        action_name="request_condition_check",
        arguments={"pump_id": "pump-a"},
        reason="Leave one Pump A condition check staged on the opening parent.",
    )
    staged = _stage_unselected_v4_actor_outcome(
        run,
        orphan_request,
        monkeypatch,
    )
    competing_request = _actor_request(
        run,
        request_id="condition-check-selected-parent",
        action_name="request_condition_check",
        arguments={"pump_id": "pump-b"},
        reason="Select a different Pump B condition check from the opening parent.",
    )
    run.apply_v4_actor_action(competing_request)
    selected = run.snapshot()

    with pytest.raises(PumpStationWorldRunError) as raised:
        run.repository.recover_staged_v4_command(staged.command)

    assert raised.value.code == "stale-publication"
    assert run.snapshot() == selected
    assert selected != opening
    assert selected.commit_id != staged.snapshot.commit_id
    assert tuple(step.command.request_id for step in run.repository.v4_steps()) == (competing_request.request_id,)


def test_staged_v4_recovery_rejects_multiple_durable_outcomes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = _start_reference_run(tmp_path / "run")
    opening = run.snapshot()
    request = _actor_request(
        run,
        request_id="condition-check-duplicate-outcome",
        action_name="request_condition_check",
        arguments={"pump_id": "pump-a"},
        reason="Leave one Pump A condition check with duplicate durable outcomes.",
    )
    staged = _stage_unselected_v4_actor_outcome(
        run,
        request,
        monkeypatch,
    )
    duplicate_commit_id = _publish_duplicate_v4_outcome(
        run.repository,
        staged,
    )

    with pytest.raises(PumpStationWorldRunError) as raised:
        run.repository.recover_staged_v4_command(staged.command)

    assert raised.value.code == "v4-command-id-conflict"
    assert run.snapshot() == opening
    assert duplicate_commit_id != staged.snapshot.commit_id
    assert run.repository.v4_steps() == ()


def test_restart_retry_after_pointer_selection_returns_the_selected_transition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "run"
    run = _start_reference_run(root)
    request = _actor_request(
        run,
        request_id="condition-check-after-pointer",
        action_name="request_condition_check",
        arguments={"pump_id": "pump-a"},
        reason="Record one Pump A condition check before response loss.",
    )
    original_publish = run.repository._publish_staged_v4_transition_under_lock

    def interrupt_after_pointer(staged: Any) -> Any:
        original_publish(staged)
        raise OSError("injected response loss after current pointer replacement")

    monkeypatch.setattr(
        run.repository,
        "_publish_staged_v4_transition_under_lock",
        interrupt_after_pointer,
    )
    with pytest.raises(OSError, match="after current pointer"):
        run.apply_v4_actor_action(request)

    selected = run.snapshot()
    assert selected.sequence == 1

    reopened = PumpStationWorldRun.resume_reference_system(
        repository=PumpStationWorldRunRepository(root),
        snapshot=selected,
    )
    recovered = reopened.apply_v4_actor_action(request)

    assert recovered.state.state_id == selected.state_id
    assert reopened.snapshot() == selected
    assert len(reopened.repository.v4_steps()) == 1


def test_two_processes_recover_one_exact_registered_actor_commit(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    run = _start_reference_run(root)
    request = _actor_request(
        run,
        request_id="condition-check-concurrent",
        action_name="request_condition_check",
        arguments={"pump_id": "pump-a"},
        reason="Record one concurrent Pump A condition check.",
    )
    opening = run.snapshot()
    context = multiprocessing.get_context("spawn")
    ready = (context.Event(), context.Event())
    start = context.Event()
    results = context.Queue()
    processes = tuple(
        context.Process(
            target=_apply_registered_actor_in_child,
            args=(
                root,
                opening,
                request.model_dump(mode="json"),
                ready[index],
                start,
                results,
            ),
        )
        for index in range(2)
    )

    for process in processes:
        process.start()
    try:
        assert all(signal.wait(10) for signal in ready)
        start.set()
        for process in processes:
            process.join(20)
            assert not process.is_alive()
            assert process.exitcode == 0
    finally:
        start.set()
        for process in processes:
            if process.is_alive():
                process.kill()
                process.join()

    outcomes = tuple(results.get(timeout=5) for _ in processes)
    assert {outcome[0] for outcome in outcomes} == {"applied"}
    assert len({outcome[1:] for outcome in outcomes}) == 1
    assert run.snapshot().sequence == 1
    assert len(run.repository.v4_steps()) == 1


def test_two_processes_select_only_one_of_two_effects_from_the_same_parent(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    run = _start_reference_run(root)
    requests = (
        _actor_request(
            run,
            request_id="condition-check-pump-a-concurrent",
            action_name="request_condition_check",
            arguments={"pump_id": "pump-a"},
            reason="Record the concurrent Pump A condition check.",
        ),
        _actor_request(
            run,
            request_id="condition-check-pump-b-concurrent",
            action_name="request_condition_check",
            arguments={"pump_id": "pump-b"},
            reason="Record the concurrent Pump B condition check.",
        ),
    )
    opening = run.snapshot()
    context = multiprocessing.get_context("spawn")
    ready = (context.Event(), context.Event())
    start = context.Event()
    results = context.Queue()
    processes = tuple(
        context.Process(
            target=_apply_registered_actor_in_child,
            args=(
                root,
                opening,
                request.model_dump(mode="json"),
                ready[index],
                start,
                results,
            ),
        )
        for index, request in enumerate(requests)
    )

    for process in processes:
        process.start()
    try:
        assert all(signal.wait(10) for signal in ready)
        start.set()
        for process in processes:
            process.join(20)
            assert not process.is_alive()
            assert process.exitcode == 0
    finally:
        start.set()
        for process in processes:
            if process.is_alive():
                process.kill()
                process.join()

    outcomes = tuple(results.get(timeout=5) for _ in processes)
    assert sum(outcome[0] == "applied" for outcome in outcomes) == 1
    assert sum(outcome == ("error", "actor-request-binding") for outcome in outcomes) == 1
    assert run.snapshot().sequence == 1
    assert len(run.repository.v4_steps()) == 1
