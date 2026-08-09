# ABOUTME: Exercises assurance-bound motif selection and the governed transfer-plan boundary.
# ABOUTME: Proves dispatch and promotion fail closed on changed pins, motifs, snapshots, or authority.

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from aec_bench.contracts.authority import (
    AuthorityAction,
    BasisKind,
)
from aec_bench.contracts.evaluation_outcome import CriticEvaluationOutcome
from aec_bench.contracts.execution_program import ProgramLimits
from aec_bench.contracts.harness_instance import HarnessBudget
from aec_bench.experimentation.governance.applicability import profile_task_applicability
from aec_bench.experimentation.governance.authority_ledger import AuthorityLedger
from aec_bench.experimentation.governance.motif_assurance import (
    AssuredMotifSelectionRecord,
    MotifAssuranceAuthorityError,
    MotifAssuranceBoundary,
    MotifAssuranceDriftError,
    MotifAssuranceLedger,
    MotifAssuranceState,
    MotifLifecycleEvent,
    append_authorized_motif_event,
    apply_governed_motif_promotion,
    derive_motif_assurance_snapshot,
    motif_subject_sha256,
)
from aec_bench.experimentation.governance.motifs import (
    HarnessProgramMotif,
    MotifLibrary,
    MotifSelectionRequest,
    MotifStatus,
    decide_motif_promotion,
)
from aec_bench.experimentation.governance.standing_monitors import CycleMonitorReport
from aec_bench.experimentation.qualification.motif_learning import (
    GovernedMotifTransferPlan,
    release_governed_motif_transfer_plan,
    select_and_materialize_assured_motif,
    select_and_materialize_motif,
)
from aec_bench.experimentation.qualification.motif_materialization import (
    MotifHarnessProgramInstantiationRequest,
    encode_harness_motif_template,
    encode_program_motif_template,
)
from aec_bench.harness.kernel_catalogue import default_kernel_registry
from tests.experimentation.governance.test_motif_library import _motif, _policy, _transfer
from tests.experimentation.qualification.test_motif_materialization import (
    _descriptor,
    _fanout_program,
    _monolithic_program,
    _recipe,
)
from tests.support.adaptive_harness import write_adaptive_task
from tests.support.governed_promotion import issue_test_governed_promotion


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _active_assurance(
    tmp_path: Path,
    motif: HarnessProgramMotif,
) -> tuple[AuthorityLedger, MotifAssuranceLedger]:
    candidate_root = tmp_path / "candidate"
    candidate_root.mkdir()
    authority = AuthorityLedger(
        tmp_path / "authority",
        candidate_roots=(candidate_root,),
        typed_basis_models={BasisKind.MONITOR_REPORT: CycleMonitorReport},
    )
    subject_sha256 = motif_subject_sha256(motif)
    provisional = HarnessProgramMotif.create(
        status=MotifStatus.PROVISIONAL,
        kernel_abi_sha256=motif.kernel_abi_sha256,
        hx_template=motif.hx_template,
        px_template=motif.px_template,
        applicability=motif.applicability,
        descriptor=motif.descriptor,
        accepted_repair_refs=motif.accepted_repair_refs,
        harness_program_evidence_refs=motif.harness_program_evidence_refs,
        quality_evidence_refs=motif.quality_evidence_refs,
        transfer_evidence_refs=motif.transfer_evidence_refs,
        parent_motif_sha256=motif.parent_motif_sha256,
    )
    authority_event = issue_test_governed_promotion(
        ledger=authority,
        action=AuthorityAction.MOTIF_PROMOTION,
        event_id="authority.motif-selection",
        subject_id="motif.selection-subject",
        subject_sha256=subject_sha256,
        kernel_sha256=motif.kernel_abi_sha256,
        motif=provisional,
    ).promotion.event
    lifecycle = MotifLifecycleEvent(
        event_id="motif-lifecycle.activate-selection",
        motif_subject_sha256=subject_sha256,
        state=MotifAssuranceState.ACTIVE,
        cause="governed_promotion",
        authority_event_sha256=authority_event.content_sha256,
        kernel_sha256=motif.kernel_abi_sha256,
        critic_generation_sha256=authority_event.critic_generation_sha256,
        model_generation_sha256=_sha("model-generation"),
        tool_generation_sha256=_sha("tool-generation"),
        applicability_sha256=_sha("applicability-generation"),
        revalidation_triggers=("critic_generation_change",),
    )
    assurance = append_authorized_motif_event(
        MotifAssuranceLedger.create(),
        lifecycle,
        authority_ledger=authority,
    )
    return authority, assurance


def _governed_plan(
    tmp_path: Path,
) -> tuple[
    GovernedMotifTransferPlan,
    MotifLibrary,
    HarnessProgramMotif,
    AuthorityLedger,
    MotifAssuranceLedger,
]:
    registry = default_kernel_registry()
    task_ref = "civil/calculation/assured-motif-target"
    tasks_root = tmp_path / "tasks"
    write_adaptive_task(tasks_root, task_id=task_ref)
    applicability = profile_task_applicability(
        task_refs=(task_ref,),
        tasks_root=tasks_root,
        registry=registry,
    )
    budget = HarnessBudget(max_parallelism=2)
    limits = ProgramLimits(max_parallelism=2)
    source_recipe = _recipe(
        registry,
        recipe_id="assured-source-hx",
        task_refs=(task_ref,),
        model="claude-sonnet-4-6",
        adapter_capability="aecbench.adapter.rlm",
        budget=budget,
    )
    source_program = _fanout_program("assured-source-px", limits)
    motif = HarnessProgramMotif.create(
        status=MotifStatus.REUSABLE,
        kernel_abi_sha256=registry.manifest.content_sha256,
        hx_template=encode_harness_motif_template(source_recipe),
        px_template=encode_program_motif_template(source_program),
        applicability=applicability.descriptor,
        descriptor=_descriptor(),
    )
    library = MotifLibrary.create((motif,))
    authority, assurance = _active_assurance(tmp_path, motif)
    governed = select_and_materialize_assured_motif(
        library=library,
        applicability=applicability,
        selection_split="calibration",
        request=MotifHarnessProgramInstantiationRequest(
            candidate_set_id="assured-transfer",
            world_id="assured-world",
            experiment_id="assured-experiment",
            kernel_ref=registry.manifest.ref,
            task_refs=(task_ref,),
            model="claude-sonnet-4-6",
            harness_budget=budget,
            program_limits=limits,
            seeds=(17,),
            repetitions=1,
            fixed_harness_recipe=_recipe(
                registry,
                recipe_id="assured-target-h0",
                task_refs=(task_ref,),
                model="claude-sonnet-4-6",
                adapter_capability="aecbench.adapter.tool-loop",
                budget=budget,
            ),
            fixed_program=_monolithic_program("assured-target-p0", limits),
        ),
        assurance_snapshot=derive_motif_assurance_snapshot(assurance),
    )
    return governed, library, motif, authority, assurance


@pytest.mark.parametrize(
    "boundary",
    [MotifAssuranceBoundary.DISPATCH, MotifAssuranceBoundary.PROMOTION],
)
def test_governed_transfer_rechecks_the_exact_selection_at_each_boundary(
    tmp_path: Path,
    boundary: MotifAssuranceBoundary,
) -> None:
    governed, library, motif, authority, assurance = _governed_plan(tmp_path)
    snapshot = derive_motif_assurance_snapshot(assurance)

    legacy_plan = release_governed_motif_transfer_plan(
        plan=governed,
        frozen_library=library,
        current_snapshot=snapshot,
        authority_ledger=authority,
        boundary=boundary,
    )

    assert legacy_plan == governed.transfer_plan
    assert governed.assured_selection.selection_request == legacy_plan.selection_request
    assert governed.assured_selection.selection_decision == legacy_plan.selection_decision
    assert governed.assured_selection.selected_motif_sha256 == motif.motif_sha256
    assert governed.assured_selection.motif_subject_sha256 == motif_subject_sha256(motif)
    assert governed.assured_selection.assurance_pin.assurance_snapshot_sha256 == snapshot.content_sha256


def test_unassured_reusable_motif_cannot_be_materialized_for_dispatch(
    tmp_path: Path,
) -> None:
    governed, library, _, _, _ = _governed_plan(tmp_path)
    legacy = governed.transfer_plan

    with pytest.raises(MotifAssuranceAuthorityError, match="governed assurance"):
        select_and_materialize_motif(
            library=library,
            applicability=legacy.target_applicability,
            selection_split="calibration",
            request=cast(
                MotifHarnessProgramInstantiationRequest,
                legacy.instantiation.harness_program_request,
            ),
        )


def test_governed_transfer_validation_requires_exact_state_change_authority_and_selection(
    tmp_path: Path,
) -> None:
    governed, _, selected, authority, assurance = _governed_plan(tmp_path)
    snapshot = derive_motif_assurance_snapshot(assurance)
    enriched = HarnessProgramMotif.create(
        status=MotifStatus.REUSABLE,
        kernel_abi_sha256=selected.kernel_abi_sha256,
        hx_template=selected.hx_template,
        px_template=selected.px_template,
        applicability=selected.applicability,
        descriptor=selected.descriptor,
        transfer_evidence_refs=(_transfer(),),
        parent_motif_sha256=selected.motif_sha256,
    )
    policy = _policy()
    decision = decide_motif_promotion(
        enriched,
        MotifStatus.TRANSFER_VALIDATED,
        policy,
    )
    assert decision.accepted is True
    promotion_authority = authority.resolve_authority_event_by_content(
        governed.assured_selection.assurance_authority_event_sha256
    ).event

    with pytest.raises(MotifAssuranceAuthorityError, match="motif_state_change"):
        apply_governed_motif_promotion(
            enriched,
            decision,
            policy,
            authority_ledger=authority,
            authority_event_sha256=promotion_authority.content_sha256,
            assured_selection=governed.assured_selection,
            selected_motif=selected,
            current_snapshot=snapshot,
        )

    outcome_reference = next(
        reference for reference in promotion_authority.basis if reference.kind is BasisKind.CRITIC_EVALUATION_OUTCOME
    )
    _, first_outcome = authority.resolve_model_basis(
        outcome_reference,
        CriticEvaluationOutcome,
    )
    critic_release = authority.resolve_authority_event(
        event_id=first_outcome.critic_release_authority_event_id,
        content_sha256=first_outcome.critic_release_authority_event_sha256,
    )
    state_change = issue_test_governed_promotion(
        ledger=authority,
        action=AuthorityAction.MOTIF_STATE_CHANGE,
        event_id="authority.motif-transfer-validated",
        subject_id="motif.selection-subject",
        subject_sha256=motif_subject_sha256(selected),
        kernel_sha256=selected.kernel_abi_sha256,
        critic=first_outcome.critic,
        critic_execution_principal_id=first_outcome.execution_principal_id,
        critic_release=critic_release,
        motif=enriched,
        motif_assurance_snapshot=snapshot,
        motif_assurance_pin=governed.assured_selection.assurance_pin,
    )
    promoted = apply_governed_motif_promotion(
        enriched,
        decision,
        policy,
        authority_ledger=authority,
        authority_event_sha256=state_change.promotion.event.content_sha256,
        assured_selection=governed.assured_selection,
        selected_motif=selected,
        current_snapshot=snapshot,
    )

    assert promoted.status is MotifStatus.TRANSFER_VALIDATED
    assert promoted.parent_motif_sha256 == enriched.motif_sha256


def test_reusable_promotion_rejects_qualification_for_a_different_provisional_motif(
    tmp_path: Path,
) -> None:
    governed, _, _, authority, _ = _governed_plan(tmp_path)
    motif = _motif(status=MotifStatus.PROVISIONAL)
    policy = _policy()
    decision = decide_motif_promotion(motif, MotifStatus.REUSABLE, policy)

    assert decision.accepted is True
    with pytest.raises(
        MotifAssuranceAuthorityError,
        match="exact qualified provisional motif",
    ):
        apply_governed_motif_promotion(
            motif,
            decision,
            policy,
            authority_ledger=authority,
            authority_event_sha256=governed.assured_selection.assurance_authority_event_sha256,
        )


def test_assured_selection_rejects_request_decision_mismatch_and_wrong_motif(
    tmp_path: Path,
) -> None:
    governed, library, motif, _, assurance = _governed_plan(tmp_path)
    record_payload = governed.assured_selection.model_dump(
        mode="python",
        exclude={"content_sha256"},
    )
    record_payload["selection_request"] = MotifSelectionRequest.create(
        archive_sha256=library.archive_sha256,
        archive_frozen=True,
        kernel_abi_sha256=motif.kernel_abi_sha256,
        applicability=motif.applicability,
        selection_split="discovery",
    )
    with pytest.raises(ValidationError, match="decision does not bind"):
        AssuredMotifSelectionRecord.model_validate(record_payload)

    wrong_motif = HarnessProgramMotif.create(
        status=motif.status,
        kernel_abi_sha256=motif.kernel_abi_sha256,
        hx_template=motif.hx_template,
        px_template=motif.px_template,
        applicability=motif.applicability,
        descriptor=motif.descriptor,
        parent_motif_sha256=motif.motif_sha256,
    )
    with pytest.raises(ValueError, match="supplied selected motif"):
        AssuredMotifSelectionRecord.create(
            selection_request=governed.assured_selection.selection_request,
            selection_decision=governed.assured_selection.selection_decision,
            selected_motif=wrong_motif,
            snapshot=derive_motif_assurance_snapshot(assurance),
        )


def test_governed_transfer_rejects_missing_or_changed_assurance_pin(
    tmp_path: Path,
) -> None:
    governed, _, _, _, _ = _governed_plan(tmp_path)
    plan_payload = governed.model_dump(mode="python", exclude={"content_sha256"})
    plan_payload.pop("assured_selection")
    with pytest.raises(ValidationError, match="assured_selection"):
        GovernedMotifTransferPlan.model_validate(plan_payload)

    record_payload = governed.assured_selection.model_dump(
        mode="python",
        exclude={"content_sha256"},
    )
    pin_payload = governed.assured_selection.assurance_pin.model_dump(
        mode="python",
        exclude={"content_sha256"},
    )
    pin_payload["selection_id"] = "selection.changed"
    record_payload["assurance_pin"] = pin_payload
    with pytest.raises(ValidationError, match="pin does not bind"):
        AssuredMotifSelectionRecord.model_validate(record_payload)


def test_governed_transfer_rejects_snapshot_drift_and_stale_authority_basis(
    tmp_path: Path,
) -> None:
    governed, library, _, authority, assurance = _governed_plan(tmp_path)
    extra_subject = _sha("unrelated-subject")
    drifted = derive_motif_assurance_snapshot(
        assurance.append(
            MotifLifecycleEvent(
                event_id="motif-lifecycle.unrelated",
                motif_subject_sha256=extra_subject,
                state=MotifAssuranceState.ACTIVE,
                cause="unrelated_activation",
                authority_event_sha256=_sha("unrelated-authority"),
                kernel_sha256=_sha("kernel-generation"),
                applicability_sha256=_sha("unrelated-applicability"),
            )
        )
    )
    with pytest.raises(MotifAssuranceDriftError, match="snapshot drift"):
        release_governed_motif_transfer_plan(
            plan=governed,
            frozen_library=library,
            current_snapshot=drifted,
            authority_ledger=authority,
            boundary=MotifAssuranceBoundary.DISPATCH,
        )

    empty_authority_root = tmp_path / "empty-authority"
    stale_authority = AuthorityLedger(
        empty_authority_root,
        candidate_roots=(tmp_path / "other-candidate",),
    )
    with pytest.raises(MotifAssuranceAuthorityError, match="stale authority basis"):
        release_governed_motif_transfer_plan(
            plan=governed,
            frozen_library=library,
            current_snapshot=derive_motif_assurance_snapshot(assurance),
            authority_ledger=stale_authority,
            boundary=MotifAssuranceBoundary.PROMOTION,
        )
