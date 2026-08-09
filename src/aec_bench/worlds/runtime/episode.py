# ABOUTME: Owns one live continual-world state, decision sequence, limits, and recorder calls.
# ABOUTME: Keeps task transition meaning, persistence layout, evaluation, and provider behavior outside the shell.

from __future__ import annotations

import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from aec_bench.worlds.runtime.world_logic import ActionRejected, Transition, TransitionResult


class EpisodeStatus(StrEnum):
    ACTIVE = "active"
    TERMINATED = "terminated"
    TRUNCATED = "truncated"


class EpisodeFinishedError(RuntimeError):
    """Raised when a caller requests a decision from a finished episode."""


@dataclass(frozen=True, slots=True)
class EpisodeLimits:
    max_steps: int | None = None
    max_wall_seconds: float | None = None
    max_tokens: int | None = None
    max_cost: Decimal | None = None

    def __post_init__(self) -> None:
        if self.max_steps is not None and self.max_steps < 1:
            raise ValueError("episode max_steps must be positive")
        if self.max_wall_seconds is not None and self.max_wall_seconds <= 0:
            raise ValueError("episode max_wall_seconds must be positive")
        if self.max_tokens is not None and self.max_tokens < 1:
            raise ValueError("episode max_tokens must be positive")
        if self.max_cost is not None and self.max_cost <= 0:
            raise ValueError("episode max_cost must be positive")


@dataclass(frozen=True, slots=True)
class EpisodeUsage:
    tokens: int = 0
    cost: Decimal = Decimal(0)

    def __post_init__(self) -> None:
        if self.tokens < 0 or self.cost < 0:
            raise ValueError("episode usage must be non-negative")


@dataclass(frozen=True, slots=True)
class Decision[ObservationT, ActionsT]:
    decision_id: str
    observation: ObservationT
    available_actions: ActionsT | None = None

    def __post_init__(self) -> None:
        if not self.decision_id.strip():
            raise ValueError("decision_id must not be empty")


@dataclass(frozen=True, slots=True)
class ActionSubmission[ActionT]:
    decision_id: str
    action: ActionT


@dataclass(frozen=True, slots=True)
class StepReply[ObservationT, ActionsT, OutputT]:
    accepted: bool
    decision: Decision[ObservationT, ActionsT] | None
    rejection: ActionRejected | None
    output: OutputT | None
    terminated: bool
    truncated: bool
    reason: str | None


@dataclass(frozen=True, slots=True)
class EpisodeOpened[StateT, ObservationT]:
    episode_id: str
    actor_id: str
    step_index: int
    decision_id: str
    state: StateT
    observation: ObservationT


@dataclass(frozen=True, slots=True)
class EpisodeStepRecorded[StateT, ObservationT, ActionT, OutputT]:
    episode_id: str
    actor_id: str
    step_index: int
    decision_id: str
    action: ActionT
    observation: ObservationT
    prior_state: StateT
    next_state: StateT
    output: OutputT
    next_decision_id: str | None
    next_observation: ObservationT | None
    terminated: bool
    termination_reason: str | None


@dataclass(frozen=True, slots=True)
class EpisodeFinished:
    episode_id: str
    actor_id: str
    step_index: int
    status: EpisodeStatus
    reason: str


class EpisodeRecorder[StateT, ObservationT, ActionT, OutputT](Protocol):
    """Persist typed episode facts without interpreting world behavior."""

    def record_opened(self, event: EpisodeOpened[StateT, ObservationT]) -> None: ...

    def record_step(
        self,
        event: EpisodeStepRecorded[StateT, ObservationT, ActionT, OutputT],
    ) -> None: ...

    def record_finished(self, event: EpisodeFinished) -> None: ...


@dataclass(slots=True)
class MemoryEpisodeRecorder[StateT, ObservationT, ActionT, OutputT]:
    opened: EpisodeOpened[StateT, ObservationT] | None = None
    steps: list[EpisodeStepRecorded[StateT, ObservationT, ActionT, OutputT]] = field(default_factory=list)
    finished: EpisodeFinished | None = None

    def record_opened(self, event: EpisodeOpened[StateT, ObservationT]) -> None:
        if self.opened is not None and self.opened != event:
            raise RuntimeError("episode opened record conflicts with existing content")
        self.opened = event

    def record_step(
        self,
        event: EpisodeStepRecorded[StateT, ObservationT, ActionT, OutputT],
    ) -> None:
        if len(self.steps) > event.step_index:
            if self.steps[event.step_index] != event:
                raise RuntimeError("episode step record conflicts with existing content")
            return
        if len(self.steps) != event.step_index:
            raise RuntimeError("episode step records must be contiguous")
        self.steps.append(event)

    def record_finished(self, event: EpisodeFinished) -> None:
        if self.finished is not None and self.finished != event:
            raise RuntimeError("episode finished record conflicts with existing content")
        self.finished = event


@dataclass(frozen=True, slots=True)
class EpisodeFunctions[StateT, ObservationT, ActionT, OutputT, ActionsT]:
    """Private world composition supplied by one registered execution owner."""

    observe: Callable[[StateT], ObservationT]
    transition: Callable[[StateT, ActionT], TransitionResult[StateT, OutputT]]
    available_actions: Callable[[StateT], ActionsT] | None = None


class Episode[StateT, ObservationT, ActionT, OutputT, ActionsT]:
    """Imperative owner of one live state and its current actor decision."""

    def __init__(
        self,
        *,
        episode_id: str,
        actor_id: str,
        state: StateT,
        functions: EpisodeFunctions[StateT, ObservationT, ActionT, OutputT, ActionsT],
        recorder: EpisodeRecorder[StateT, ObservationT, ActionT, OutputT],
        limits: EpisodeLimits | None = None,
        step_index: int = 0,
        decision_id: str | None = None,
        usage: EpisodeUsage | None = None,
        decision_id_factory: Callable[[StateT, int], str] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not episode_id.strip() or not actor_id.strip():
            raise ValueError("episode and actor identities must not be empty")
        if step_index < 0:
            raise ValueError("episode step_index must be non-negative")
        self._episode_id = episode_id
        self._actor_id = actor_id
        self._state = state
        self._functions = functions
        self._recorder = recorder
        self._limits = limits or EpisodeLimits()
        self._step_index = step_index
        self._usage = usage or EpisodeUsage()
        self._decision_id_factory = decision_id_factory or (lambda _state, _step: secrets.token_urlsafe(24))
        self._decision_id = decision_id or self._next_decision_id(state, step_index)
        self._decision: Decision[ObservationT, ActionsT] | None = None
        self._status = EpisodeStatus.ACTIVE
        self._reason: str | None = None
        self._opened_recorded = False
        self._clock = clock
        self._opened_at = clock()
        self._lock = threading.Lock()

    @property
    def state(self) -> StateT:
        return self._state

    @property
    def step_index(self) -> int:
        return self._step_index

    @property
    def status(self) -> EpisodeStatus:
        return self._status

    @property
    def usage(self) -> EpisodeUsage:
        return self._usage

    def current_decision(self) -> Decision[ObservationT, ActionsT]:
        with self._lock:
            limited = self._limit_reason()
            if limited is not None:
                self._finish(EpisodeStatus.TRUNCATED, limited)
            if self._status is not EpisodeStatus.ACTIVE:
                raise EpisodeFinishedError(f"episode is {self._status.value}: {self._reason}")
            if self._decision is None:
                observation = self._functions.observe(self._state)
                actions = (
                    None
                    if self._functions.available_actions is None
                    else self._functions.available_actions(self._state)
                )
                decision = Decision(
                    decision_id=self._decision_id,
                    observation=observation,
                    available_actions=actions,
                )
                if not self._opened_recorded:
                    self._recorder.record_opened(
                        EpisodeOpened(
                            episode_id=self._episode_id,
                            actor_id=self._actor_id,
                            step_index=self._step_index,
                            decision_id=decision.decision_id,
                            state=self._state,
                            observation=observation,
                        )
                    )
                    self._opened_recorded = True
                self._decision = decision
            return self._decision

    def submit(
        self,
        submission: ActionSubmission[ActionT],
    ) -> StepReply[ObservationT, ActionsT, OutputT]:
        with self._lock:
            limited = self._limit_reason()
            if limited is not None:
                self._finish(EpisodeStatus.TRUNCATED, limited)
                return self._reply(reason=limited)
            if self._status is not EpisodeStatus.ACTIVE:
                return self._reply(reason=self._reason)
            decision = self._decision
            if decision is None:
                raise RuntimeError("current_decision must be observed before submitting an action")
            if submission.decision_id != decision.decision_id:
                return StepReply(
                    accepted=False,
                    decision=decision,
                    rejection=ActionRejected("decision-stale", "decision is unknown or no longer current"),
                    output=None,
                    terminated=False,
                    truncated=False,
                    reason=None,
                )
            transition = self._functions.transition(self._state, submission.action)
            if isinstance(transition, ActionRejected):
                return StepReply(
                    accepted=False,
                    decision=decision,
                    rejection=transition,
                    output=None,
                    terminated=False,
                    truncated=False,
                    reason=None,
                )
            return self._accept(decision, submission.action, transition)

    def add_usage(
        self,
        *,
        tokens: int = 0,
        cost: Decimal = Decimal(0),
    ) -> StepReply[ObservationT, ActionsT, OutputT] | None:
        with self._lock:
            self._usage = EpisodeUsage(
                tokens=self._usage.tokens + tokens,
                cost=self._usage.cost + cost,
            )
            limited = self._limit_reason()
            if limited is None:
                return None
            self._finish(EpisodeStatus.TRUNCATED, limited)
            return self._reply(reason=limited)

    def cancel(self, reason: str) -> StepReply[ObservationT, ActionsT, OutputT]:
        with self._lock:
            if self._status is EpisodeStatus.ACTIVE:
                self._finish(EpisodeStatus.TRUNCATED, self._require_reason(reason))
            return self._reply(reason=self._reason)

    def close(self) -> None:
        with self._lock:
            if self._status is EpisodeStatus.ACTIVE:
                self._finish(EpisodeStatus.TRUNCATED, "episode closed by host")

    def _accept(
        self,
        decision: Decision[ObservationT, ActionsT],
        action: ActionT,
        transition: Transition[StateT, OutputT],
    ) -> StepReply[ObservationT, ActionsT, OutputT]:
        next_step = self._step_index + 1
        terminated = transition.terminated
        post_limit = None if terminated else self._limit_reason(step_index=next_step)
        finished_status = (
            EpisodeStatus.TERMINATED if terminated else EpisodeStatus.TRUNCATED if post_limit is not None else None
        )
        finished_reason = transition.termination_reason if terminated else post_limit
        next_decision_id = None if finished_status is not None else self._next_decision_id(transition.state, next_step)
        next_observation = None if finished_status is not None else self._functions.observe(transition.state)
        self._recorder.record_step(
            EpisodeStepRecorded(
                episode_id=self._episode_id,
                actor_id=self._actor_id,
                step_index=self._step_index,
                decision_id=decision.decision_id,
                action=action,
                observation=decision.observation,
                prior_state=self._state,
                next_state=transition.state,
                output=transition.output,
                next_decision_id=next_decision_id,
                next_observation=next_observation,
                terminated=terminated,
                termination_reason=transition.termination_reason,
            )
        )
        if finished_status is not None:
            self._recorder.record_finished(
                EpisodeFinished(
                    episode_id=self._episode_id,
                    actor_id=self._actor_id,
                    step_index=next_step,
                    status=finished_status,
                    reason=finished_reason or ("world terminated" if terminated else "runtime limit reached"),
                )
            )
        self._state = transition.state
        self._step_index = next_step
        self._decision_id = next_decision_id or decision.decision_id
        if finished_status is not None:
            self._status = finished_status
            self._reason = finished_reason
            self._decision = None
            return StepReply(
                True,
                None,
                None,
                transition.output,
                terminated,
                not terminated,
                self._reason,
            )
        actions = None if self._functions.available_actions is None else self._functions.available_actions(self._state)
        assert next_observation is not None
        self._decision = Decision(
            decision_id=self._decision_id,
            observation=next_observation,
            available_actions=actions,
        )
        return StepReply(True, self._decision, None, transition.output, False, False, None)

    def _finish(self, status: EpisodeStatus, reason: str) -> None:
        self._recorder.record_finished(
            EpisodeFinished(
                episode_id=self._episode_id,
                actor_id=self._actor_id,
                step_index=self._step_index,
                status=status,
                reason=reason,
            )
        )
        self._status = status
        self._reason = reason
        self._decision = None

    def _limit_reason(self, *, step_index: int | None = None) -> str | None:
        selected_step = self._step_index if step_index is None else step_index
        if self._limits.max_steps is not None and selected_step >= self._limits.max_steps:
            return "step limit reached"
        if (
            self._limits.max_wall_seconds is not None
            and self._clock() - self._opened_at >= self._limits.max_wall_seconds
        ):
            return "wall-clock limit reached"
        if self._limits.max_tokens is not None and self._usage.tokens >= self._limits.max_tokens:
            return "token limit reached"
        if self._limits.max_cost is not None and self._usage.cost >= self._limits.max_cost:
            return "cost limit reached"
        return None

    def _reply(self, *, reason: str | None) -> StepReply[ObservationT, ActionsT, OutputT]:
        return StepReply(
            accepted=False,
            decision=None,
            rejection=None,
            output=None,
            terminated=self._status is EpisodeStatus.TERMINATED,
            truncated=self._status is EpisodeStatus.TRUNCATED,
            reason=reason,
        )

    def _next_decision_id(self, state: StateT, step_index: int) -> str:
        value = self._decision_id_factory(state, step_index)
        if not value.strip():
            raise ValueError("decision ID factory returned an empty value")
        return value

    @staticmethod
    def _require_reason(reason: str) -> str:
        value = reason.strip()
        if not value:
            raise ValueError("episode cancellation reason must not be empty")
        return value
