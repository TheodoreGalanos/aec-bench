# ABOUTME: Tests exact-order authorization replay for evaluation dispatches.
# ABOUTME: Covers cardinality, assignment order, and just-in-time authority drift.

from __future__ import annotations

from dataclasses import dataclass

import pytest

from aec_bench.harness.evaluation_dispatch_authorization import (
    EvaluationGenerationAuthorizationCode,
    EvaluationGenerationAuthorizationError,
    replay_evaluation_dispatch_authorizations,
    replay_evaluation_dispatch_gate,
)


@dataclass(frozen=True)
class _Authorization:
    assignment_sha256: str
    authority_sha256: str


@dataclass(frozen=True)
class _Dispatch:
    assignment_sha256: str
    authority_sha256: str


def _replay(authorization: _Authorization) -> _Dispatch:
    return _Dispatch(
        assignment_sha256=authorization.assignment_sha256,
        authority_sha256=authorization.authority_sha256,
    )


def test_authorization_replay_preserves_exact_assignment_order_and_jit_identity() -> None:
    expected = ("a", "b")
    authorizations = (
        _Authorization("a", "authority-a"),
        _Authorization("b", "authority-b"),
    )

    dispatches = replay_evaluation_dispatch_authorizations(
        expected_assignment_sha256s=expected,
        authorizations=authorizations,
        replay=_replay,
    )
    assert tuple(item.assignment_sha256 for item in dispatches) == expected
    assert (
        replay_evaluation_dispatch_gate(
            expected_dispatches=dispatches,
            authorizations=authorizations,
            replay=_replay,
        )
        == dispatches
    )


@pytest.mark.parametrize(
    ("authorizations", "code"),
    (
        (
            (_Authorization("a", "authority-a"),),
            EvaluationGenerationAuthorizationCode.CARDINALITY,
        ),
        (
            (
                _Authorization("b", "authority-b"),
                _Authorization("a", "authority-a"),
            ),
            EvaluationGenerationAuthorizationCode.ASSIGNMENT_ORDER,
        ),
    ),
)
def test_authorization_replay_fails_closed_on_cardinality_or_order(
    authorizations: tuple[_Authorization, ...],
    code: EvaluationGenerationAuthorizationCode,
) -> None:
    with pytest.raises(EvaluationGenerationAuthorizationError) as captured:
        replay_evaluation_dispatch_authorizations(
            expected_assignment_sha256s=("a", "b"),
            authorizations=authorizations,
            replay=_replay,
        )

    assert captured.value.code is code


def test_authorization_gate_rejects_replayed_authority_drift() -> None:
    expected = (
        _Dispatch("a", "authority-a"),
        _Dispatch("b", "authority-b"),
    )
    changed = (
        _Authorization("a", "changed"),
        _Authorization("b", "authority-b"),
    )

    with pytest.raises(EvaluationGenerationAuthorizationError) as captured:
        replay_evaluation_dispatch_gate(
            expected_dispatches=expected,
            authorizations=changed,
            replay=_replay,
        )

    assert captured.value.code is EvaluationGenerationAuthorizationCode.REPLAY_DRIFT
