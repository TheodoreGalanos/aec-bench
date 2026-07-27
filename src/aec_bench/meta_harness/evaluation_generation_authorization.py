# ABOUTME: Replays evaluation dispatch authority in exact frozen assignment order.
# ABOUTME: Separates reusable authorization closure from experiment-specific error wording.

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from typing import Protocol


class EvaluationDispatch(Protocol):
    """Minimal exact-order identity exposed by an authorized dispatch."""

    assignment_sha256: str


class EvaluationGenerationAuthorizationCode(StrEnum):
    """Stable failure reason for one authority replay barrier."""

    CARDINALITY = "cardinality"
    ASSIGNMENT_ORDER = "assignment_order"
    REPLAY_DRIFT = "replay_drift"


class EvaluationGenerationAuthorizationError(ValueError):
    """Evaluation dispatch authority cannot close exactly."""

    def __init__(
        self,
        code: EvaluationGenerationAuthorizationCode,
    ) -> None:
        self.code = code
        super().__init__(code.value)


def replay_evaluation_dispatch_authorizations[
    AuthorizationT,
    DispatchT: EvaluationDispatch,
](
    *,
    expected_assignment_sha256s: tuple[str, ...],
    authorizations: tuple[AuthorizationT, ...],
    replay: Callable[[AuthorizationT], DispatchT],
) -> tuple[DispatchT, ...]:
    """Replay exactly one authority per frozen assignment in frozen order."""

    require_evaluation_dispatch_authorization_count(
        expected_assignment_sha256s=expected_assignment_sha256s,
        authorizations=authorizations,
    )
    dispatches = replay_evaluation_dispatches(
        authorizations=authorizations,
        replay=replay,
    )
    verify_evaluation_dispatch_assignment_order(
        expected_assignment_sha256s=expected_assignment_sha256s,
        dispatches=dispatches,
    )
    return dispatches


def require_evaluation_dispatch_authorization_count[AuthorizationT](
    *,
    expected_assignment_sha256s: tuple[str, ...],
    authorizations: tuple[AuthorizationT, ...],
) -> None:
    """Require exactly one authority input for each frozen assignment."""

    if len(authorizations) != len(expected_assignment_sha256s):
        raise EvaluationGenerationAuthorizationError(
            EvaluationGenerationAuthorizationCode.CARDINALITY,
        )


def replay_evaluation_dispatches[AuthorizationT, DispatchT](
    *,
    authorizations: tuple[AuthorizationT, ...],
    replay: Callable[[AuthorizationT], DispatchT],
) -> tuple[DispatchT, ...]:
    """Replay a previously cardinality-checked authority sequence."""

    return tuple(replay(authorization) for authorization in authorizations)


def verify_evaluation_dispatch_assignment_order[
    DispatchT: EvaluationDispatch,
](
    *,
    expected_assignment_sha256s: tuple[str, ...],
    dispatches: tuple[DispatchT, ...],
) -> None:
    """Require replayed dispatches to preserve frozen assignment order."""

    if tuple(item.assignment_sha256 for item in dispatches) != expected_assignment_sha256s:
        raise EvaluationGenerationAuthorizationError(
            EvaluationGenerationAuthorizationCode.ASSIGNMENT_ORDER,
        )


def replay_evaluation_dispatch_gate[
    AuthorizationT,
    DispatchT: EvaluationDispatch,
](
    *,
    expected_dispatches: tuple[DispatchT, ...],
    authorizations: tuple[AuthorizationT, ...],
    replay: Callable[[AuthorizationT], DispatchT],
) -> tuple[DispatchT, ...]:
    """Replay authority just in time and reject any dispatch identity drift."""

    replayed = replay_evaluation_dispatch_authorizations(
        expected_assignment_sha256s=tuple(item.assignment_sha256 for item in expected_dispatches),
        authorizations=authorizations,
        replay=replay,
    )
    if replayed != expected_dispatches:
        raise EvaluationGenerationAuthorizationError(
            EvaluationGenerationAuthorizationCode.REPLAY_DRIFT,
        )
    return replayed
