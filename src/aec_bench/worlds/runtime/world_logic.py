# ABOUTME: Defines the small accepted-transition and action-rejection values shared by real worlds.
# ABOUTME: Leaves initial state, observation, actions, effects, and evaluation with each task owner.

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Transition[StateT, OutputT]:
    state: StateT
    output: OutputT
    termination_reason: str | None = None

    @property
    def terminated(self) -> bool:
        return self.termination_reason is not None


@dataclass(frozen=True, slots=True)
class ActionRejected:
    code: str
    message: str


type TransitionResult[StateT, OutputT] = Transition[StateT, OutputT] | ActionRejected
