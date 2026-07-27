# ABOUTME: Defines lifecycle ports used by the cardinality-neutral governed batch engine.
# ABOUTME: Keeps phase-specific authority, persistence, effects, and payload types outside the engine.

from __future__ import annotations

from typing import Protocol

from .contracts import (
    GovernedBatchAssignment,
    GovernedBatchAssignmentTerminal,
    GovernedBatchDesign,
    GovernedBatchTerminal,
)


class GovernedBatchExecutionPort[
    EffectAuthorizationT,
    ResultT,
    PayloadT,
    ClosureT,
](Protocol):
    """Required phase adapter for the single governed batch lifecycle."""

    def replay_authorization_barrier(
        self,
        design: GovernedBatchDesign,
    ) -> None:
        """Replay all authority before any execution state can be opened."""

    def open_execution_state(
        self,
        design: GovernedBatchDesign,
    ) -> None:
        """Open or replay state bound to the exact authorized design."""

    def load_terminal(self) -> ClosureT | None:
        """Load an existing terminal closure, if one is durable."""

    def load_results(self) -> tuple[ResultT, ...]:
        """Load the only permitted durable assignment-result prefix."""

    def project_result(
        self,
        result: ResultT,
    ) -> GovernedBatchAssignmentTerminal:
        """Project a phase result into the normalized evidence contract."""

    def replay_result(
        self,
        *,
        assignment: GovernedBatchAssignment,
        ordinal: int,
        expected: ResultT,
    ) -> tuple[ResultT, PayloadT]:
        """Replay one durable result and return its phase payload."""

    def authorize_effect(
        self,
        *,
        assignment: GovernedBatchAssignment,
        ordinal: int,
    ) -> EffectAuthorizationT:
        """Persist exact pre-effect authorization for one assignment."""

    def effect_authorization_sha256(
        self,
        authorization: EffectAuthorizationT,
    ) -> str:
        """Return the immutable identity of one effect authorization."""

    def execute_assignment(
        self,
        *,
        assignment: GovernedBatchAssignment,
        ordinal: int,
        effect_authorization: EffectAuthorizationT,
    ) -> tuple[ResultT, PayloadT]:
        """Execute or recover one assignment under its exact authorization."""

    def record_result(self, result: ResultT) -> ResultT:
        """Persist and replay one exact next assignment result."""

    def close_terminal(
        self,
        *,
        incomplete_reason: str | None,
    ) -> ClosureT:
        """Close standing monitors and persist one terminal batch variant."""

    def project_terminal(
        self,
        closure: ClosureT,
    ) -> GovernedBatchTerminal:
        """Project a phase closure into the normalized terminal contract."""
