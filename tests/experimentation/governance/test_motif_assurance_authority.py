# ABOUTME: Integrates motif assurance transitions with scoped events in the host authority ledger.
# ABOUTME: Proves retrievable or approval-shaped motifs cannot become active from an unresolvable event.

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from aec_bench.contracts.authority import AuthorityAction, AuthorityEvent, BasisKind
from aec_bench.experimentation.governance.authority_ledger import (
    AuthorityLedger,
    AuthorityLedgerIntegrityError,
)
from aec_bench.experimentation.governance.motif_assurance import (
    MotifAssuranceAuthorityError,
    MotifAssuranceLedger,
    MotifAssuranceState,
    MotifLifecycleEvent,
    append_authorized_motif_event,
    motif_subject_sha256,
)
from aec_bench.experimentation.governance.motifs import HarnessProgramMotif, MotifStatus
from aec_bench.experimentation.governance.standing_monitors import CycleMonitorReport
from tests.experimentation.governance.test_motif_library import _motif
from tests.support.governed_promotion import issue_test_governed_promotion


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _authority_ledger(tmp_path: Path) -> AuthorityLedger:
    candidate_root = tmp_path / "candidate"
    candidate_root.mkdir()
    return AuthorityLedger(
        tmp_path / "authority",
        candidate_roots=(candidate_root,),
        typed_basis_models={BasisKind.MONITOR_REPORT: CycleMonitorReport},
    )


def _promotion_event(
    ledger: AuthorityLedger,
    *,
    event_id: str,
    motif: HarnessProgramMotif,
) -> AuthorityEvent:
    return issue_test_governed_promotion(
        ledger=ledger,
        action=AuthorityAction.MOTIF_PROMOTION,
        event_id=event_id,
        subject_id="motif.review-first",
        subject_sha256=motif_subject_sha256(motif),
        kernel_sha256=motif.kernel_abi_sha256,
        motif=motif,
    ).promotion.event


def _lifecycle_event(
    *,
    motif_subject_sha256: str,
    authority_event_sha256: str,
    kernel_sha256: str = _sha("kernel"),
    critic_generation_sha256: str | None = _sha("critic-generation"),
) -> MotifLifecycleEvent:
    return MotifLifecycleEvent(
        event_id="motif-lifecycle.activate",
        motif_subject_sha256=motif_subject_sha256,
        state=MotifAssuranceState.ACTIVE,
        cause="governed_promotion",
        authority_event_sha256=authority_event_sha256,
        kernel_sha256=kernel_sha256,
        critic_generation_sha256=critic_generation_sha256,
        model_generation_sha256=_sha("model-generation"),
        tool_generation_sha256=_sha("tool-generation"),
        applicability_sha256=_sha("applicability"),
        revalidation_triggers=("critic_generation_change",),
    )


def test_motif_can_be_activated_only_from_a_resolvable_scoped_promotion(
    tmp_path: Path,
) -> None:
    authority = _authority_ledger(tmp_path)
    motif = _motif(status=MotifStatus.PROVISIONAL)
    subject_sha256 = motif_subject_sha256(motif)
    promotion = _promotion_event(
        authority,
        event_id="authority.motif-promotion",
        motif=motif,
    )
    lifecycle = _lifecycle_event(
        motif_subject_sha256=subject_sha256,
        authority_event_sha256=promotion.content_sha256,
        kernel_sha256=motif.kernel_abi_sha256,
        critic_generation_sha256=promotion.critic_generation_sha256,
    )

    assurance = append_authorized_motif_event(
        MotifAssuranceLedger.create(),
        lifecycle,
        authority_ledger=authority,
    )

    assert assurance.events == (lifecycle,)


def test_unresolvable_or_wrong_subject_authority_cannot_activate_a_motif(
    tmp_path: Path,
) -> None:
    authority = _authority_ledger(tmp_path)
    motif = _motif(status=MotifStatus.PROVISIONAL)
    subject_sha256 = motif_subject_sha256(motif)
    untrusted = _lifecycle_event(
        motif_subject_sha256=subject_sha256,
        authority_event_sha256=_sha("candidate-authored-approval-shaped-bytes"),
        kernel_sha256=motif.kernel_abi_sha256,
    )

    with pytest.raises(AuthorityLedgerIntegrityError, match="missing"):
        append_authorized_motif_event(
            MotifAssuranceLedger.create(),
            untrusted,
            authority_ledger=authority,
        )

    wrong_motif = _motif(
        status=MotifStatus.PROVISIONAL,
        template_label="different-subject",
    )
    wrong_subject = _promotion_event(
        authority,
        event_id="authority.wrong-subject-promotion",
        motif=wrong_motif,
    )
    mismatched = _lifecycle_event(
        motif_subject_sha256=subject_sha256,
        authority_event_sha256=wrong_subject.content_sha256,
        kernel_sha256=motif.kernel_abi_sha256,
        critic_generation_sha256=wrong_subject.critic_generation_sha256,
    )
    with pytest.raises(MotifAssuranceAuthorityError, match="subject"):
        append_authorized_motif_event(
            MotifAssuranceLedger.create(),
            mismatched,
            authority_ledger=authority,
        )
