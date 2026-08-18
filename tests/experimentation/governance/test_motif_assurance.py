# ABOUTME: Exercises append-only motif assurance state, stable subjects, and frozen selection pins.
# ABOUTME: Proves assurance drift blocks dispatch and promotion without rewriting immutable motif evidence.

from __future__ import annotations

import hashlib

import pytest

from aec_bench.contracts.evaluation_refs import CriticRef
from aec_bench.contracts.harness_kernel import KernelRef
from aec_bench.experimentation.governance.motif_assurance import (
    MotifAssuranceBoundary,
    MotifAssuranceDriftError,
    MotifAssuranceLedger,
    MotifAssurancePin,
    MotifAssuranceState,
    MotifLifecycleEvent,
    assert_motif_assurance_current,
    derive_motif_assurance_snapshot,
    motif_subject_sha256,
)
from aec_bench.experimentation.governance.motifs import (
    HarnessProgramMotif,
    MotifApplicabilityDescriptor,
    MotifPromotionPolicy,
    MotifStatus,
    MotifStructuralDescriptor,
    MotifTemplate,
    apply_motif_promotion,
    decide_motif_promotion,
)
from tests.support.evaluation_regimes import fake_regime_ref


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _candidate() -> HarnessProgramMotif:
    return HarnessProgramMotif.create(
        status=MotifStatus.CANDIDATE,
        kernel_abi_sha256=_sha("kernel-abi"),
        hx_template=MotifTemplate.create(kind="hx", payload={"recipe": "review-first"}),
        px_template=MotifTemplate.create(kind="px", payload={"program": "fanout-join"}),
        applicability=MotifApplicabilityDescriptor(
            task_pattern="review_first",
            stage_pattern="evidence_then_decision",
            stage_count=3,
            fanout_characteristic="bounded",
            branching_characteristic="conditional",
            evidence_surfaces=("source_pack", "verifier_gates"),
            state_mode="ephemeral",
        ),
        descriptor=MotifStructuralDescriptor(
            decomposition_pattern="evidence_fanout",
            orchestration_pattern="verified_join",
            decomposition_depth=2,
            maximum_parallelism=2,
            tool_surface=("artifact.read", "verifier.check"),
            state_mode="ephemeral",
        ),
    )


def _event(
    *,
    subject_sha256: str,
    state: MotifAssuranceState,
    label: str,
    parent_event_sha256: str | None = None,
    revalidation_basis_sha256: str | None = None,
) -> MotifLifecycleEvent:
    return MotifLifecycleEvent(
        event_id=f"motif-event.{label}",
        motif_subject_sha256=subject_sha256,
        state=state,
        cause=f"cause.{label}",
        parent_event_sha256=parent_event_sha256,
        authority_event_sha256=_sha(f"authority.{label}"),
        revalidation_basis_sha256=revalidation_basis_sha256,
        kernel_ref=KernelRef(kernel_id="test-kernel", version="1.0.0"),
        kernel_abi_sha256=_sha("kernel-generation"),
        critic=CriticRef(
            regime=fake_regime_ref(),
            critic_id="critic.acceptance",
            role="acceptance",
        ),
        model_generation_sha256=_sha("model-generation"),
        tool_generation_sha256=_sha("tool-generation"),
        applicability_sha256=_sha("applicability-generation"),
        revalidation_triggers=("critic_change",),
    )


def test_append_only_lifecycle_revokes_every_immutable_record_for_one_stable_subject() -> None:
    candidate = _candidate()
    retire_decision = decide_motif_promotion(candidate, MotifStatus.RETIRED, MotifPromotionPolicy())
    retired_child = apply_motif_promotion(candidate, retire_decision, MotifPromotionPolicy())
    subject_sha256 = motif_subject_sha256(candidate)

    assert motif_subject_sha256(retired_child) == subject_sha256

    active = _event(
        subject_sha256=subject_sha256,
        state=MotifAssuranceState.ACTIVE,
        label="active",
    )
    active_ledger = MotifAssuranceLedger.create().append(active)
    active_snapshot = derive_motif_assurance_snapshot(active_ledger)

    assert active_snapshot.require(subject_sha256).state is MotifAssuranceState.ACTIVE
    assert active_snapshot.require(subject_sha256).eligible is True

    revoked = _event(
        subject_sha256=subject_sha256,
        state=MotifAssuranceState.REVOKED,
        label="revoked",
        parent_event_sha256=active.content_sha256,
    )
    revoked_ledger = active_ledger.append(revoked)
    revoked_snapshot = derive_motif_assurance_snapshot(revoked_ledger)

    assert active_snapshot.require(subject_sha256).state is MotifAssuranceState.ACTIVE
    assert revoked_snapshot.require(subject_sha256).state is MotifAssuranceState.REVOKED
    assert revoked_snapshot.require(subject_sha256).eligible is False
    assert revoked_snapshot.content_sha256 != active_snapshot.content_sha256

    forked = _event(
        subject_sha256=subject_sha256,
        state=MotifAssuranceState.SUSPENDED,
        label="forked",
        parent_event_sha256=active.content_sha256,
    )
    with pytest.raises(ValueError, match="current subject head"):
        revoked_ledger.append(forked)


@pytest.mark.parametrize(
    "boundary",
    [MotifAssuranceBoundary.DISPATCH, MotifAssuranceBoundary.PROMOTION],
)
def test_snapshot_pin_blocks_dispatch_and_promotion_after_revocation(
    boundary: MotifAssuranceBoundary,
) -> None:
    candidate = _candidate()
    subject_sha256 = motif_subject_sha256(candidate)
    active = _event(
        subject_sha256=subject_sha256,
        state=MotifAssuranceState.ACTIVE,
        label="active",
    )
    active_ledger = MotifAssuranceLedger.create().append(active)
    active_snapshot = derive_motif_assurance_snapshot(active_ledger)
    pin = MotifAssurancePin.create(
        selection_id="selection.001",
        selected_motif_sha256=candidate.motif_sha256,
        motif_subject_sha256=subject_sha256,
        snapshot=active_snapshot,
    )

    assert_motif_assurance_current(pin, active_snapshot, boundary=boundary)

    revoked = _event(
        subject_sha256=subject_sha256,
        state=MotifAssuranceState.REVOKED,
        label="revoked",
        parent_event_sha256=active.content_sha256,
    )
    revoked_snapshot = derive_motif_assurance_snapshot(active_ledger.append(revoked))

    with pytest.raises(MotifAssuranceDriftError, match=f"{boundary.value}.*snapshot drift"):
        assert_motif_assurance_current(pin, revoked_snapshot, boundary=boundary)


def test_reactivation_requires_explicit_revalidation_basis() -> None:
    subject_sha256 = motif_subject_sha256(_candidate())
    active = _event(
        subject_sha256=subject_sha256,
        state=MotifAssuranceState.ACTIVE,
        label="active",
    )
    stale = _event(
        subject_sha256=subject_sha256,
        state=MotifAssuranceState.STALE,
        label="stale",
        parent_event_sha256=active.content_sha256,
    )
    ledger = MotifAssuranceLedger.create().append(active).append(stale)
    ungrounded_reactivation = _event(
        subject_sha256=subject_sha256,
        state=MotifAssuranceState.ACTIVE,
        label="reactivate-without-basis",
        parent_event_sha256=stale.content_sha256,
    )

    with pytest.raises(ValueError, match="revalidation basis"):
        ledger.append(ungrounded_reactivation)

    grounded_reactivation = _event(
        subject_sha256=subject_sha256,
        state=MotifAssuranceState.ACTIVE,
        label="reactivate-with-basis",
        parent_event_sha256=stale.content_sha256,
        revalidation_basis_sha256=_sha("revalidation-evidence"),
    )
    reactivated = derive_motif_assurance_snapshot(ledger.append(grounded_reactivation))

    assert reactivated.require(subject_sha256).eligible is True
