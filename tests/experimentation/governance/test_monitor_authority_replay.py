# ABOUTME: Integrates scheduled standing-monitor replay with the host-confined authority ledger.
# ABOUTME: Proves replay results come from resolving real immutable basis chains rather than caller claims.

from __future__ import annotations

import hashlib
from pathlib import Path

from aec_bench.contracts.authority import (
    AuthorityAction,
    AuthorityDecision,
    AuthorityEvent,
    AuthorityPrincipal,
    AuthorityPrincipalKind,
    BasisKind,
    TaintLabel,
)
from aec_bench.experimentation.governance.authority_ledger import AuthorityLedger
from aec_bench.experimentation.governance.standing_monitors import (
    replay_scheduled_basis,
    schedule_basis_replay,
)


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _host() -> AuthorityPrincipal:
    return AuthorityPrincipal(
        principal_id="host.runtime",
        kind=AuthorityPrincipalKind.HOST_RUNTIME,
    )


def _ledger_with_import_event(tmp_path: Path) -> tuple[AuthorityLedger, AuthorityEvent, Path]:
    candidate_root = tmp_path / "candidate"
    candidate_root.mkdir()
    ledger = AuthorityLedger(
        tmp_path / "authority",
        candidate_roots=(candidate_root,),
    )
    imported = ledger.observe_basis(
        kind=BasisKind.EVIDENCE,
        artifact_id="trial-record.imported-001",
        content=b'{"trial_id":"imported-001"}\n',
        producer=AuthorityPrincipal(
            principal_id="model.candidate",
            kind=AuthorityPrincipalKind.MODEL,
        ),
        producer_process_id="harbor.job-001",
        observed_by=_host(),
        channel="harbor-import",
        operation_id="scored-import",
        invocation_id="invocation-001",
        operation_taint=(
            TaintLabel.MODEL_REPORTED,
            TaintLabel.RUNTIME_OBSERVED,
        ),
    )
    event = AuthorityEvent(
        event_id="authority.import-001",
        principal=_host(),
        action=AuthorityAction.SCORED_EVIDENCE_IMPORT,
        decision=AuthorityDecision.GRANTED,
        subject_id="trial-record.imported-001",
        subject_sha256=imported.reference.artifact_sha256,
        basis=(imported.reference,),
        kernel_sha256=_sha("kernel"),
        reasons=("host imported exact scored evidence",),
        revalidation_triggers=("basis_replay_due",),
    )
    ledger.issue_authority_event(event)
    return ledger, event, imported.origin_path


def test_scheduled_replay_resolves_the_real_authority_basis_chain(tmp_path: Path) -> None:
    ledger, event, _ = _ledger_with_import_event(tmp_path)
    requirement = schedule_basis_replay(
        ledger=ledger,
        replay_id="replay.import-001",
        authority_event_id=event.event_id,
        authority_event_sha256=event.content_sha256,
        due_cycle_index=3,
    )

    observation = replay_scheduled_basis(
        ledger=ledger,
        requirement=requirement,
    )

    assert observation.replayed is True
    assert observation.closure_complete is True
    assert observation.observed_basis_closure_sha256 == requirement.basis_closure_sha256
    assert observation.evidence_sha256 is not None


def test_scheduled_replay_fails_when_a_previously_accepted_origin_disappears(
    tmp_path: Path,
) -> None:
    ledger, event, origin_path = _ledger_with_import_event(tmp_path)
    requirement = schedule_basis_replay(
        ledger=ledger,
        replay_id="replay.import-001",
        authority_event_id=event.event_id,
        authority_event_sha256=event.content_sha256,
        due_cycle_index=3,
    )
    origin_path.unlink()

    observation = replay_scheduled_basis(
        ledger=ledger,
        requirement=requirement,
    )

    assert observation.replayed is True
    assert observation.closure_complete is False
    assert observation.observed_basis_closure_sha256 is None
    assert observation.evidence_sha256 is not None
