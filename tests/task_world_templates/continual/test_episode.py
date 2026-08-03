# ABOUTME: Tests the shared episode owner for decisions, limits, recording, and lifecycle semantics.
# ABOUTME: Proves rejected actions and recorder failures cannot advance live episode state.

from collections.abc import Iterator
from decimal import Decimal

import pytest

from aec_bench.task_world_templates.continual.episode import (
    ActionSubmission,
    Episode,
    EpisodeFinishedError,
    EpisodeFunctions,
    EpisodeLimits,
    EpisodeStatus,
    MemoryEpisodeRecorder,
)
from aec_bench.task_world_templates.continual.world_logic import ActionRejected, Transition


def _episode(
    *,
    limits: EpisodeLimits | None = None,
    recorder: MemoryEpisodeRecorder[int, str, int, str] | None = None,
    clock: Iterator[float] | None = None,
) -> tuple[Episode[int, str, int, str, tuple[str, ...]], MemoryEpisodeRecorder[int, str, int, str]]:
    selected = recorder or MemoryEpisodeRecorder()
    times = iter((0.0, 0.0)) if clock is None else clock
    return (
        Episode(
            episode_id="episode",
            actor_id="actor",
            state=0,
            functions=EpisodeFunctions(
                observe=lambda state: f"state:{state}",
                transition=lambda state, action: (
                    ActionRejected("negative", "actions must be non-negative")
                    if action < 0
                    else Transition(
                        state=state + action,
                        output=f"accepted:{action}",
                        termination_reason="world complete" if state + action >= 3 else None,
                    )
                ),
                available_actions=lambda _state: ("advance",),
            ),
            recorder=selected,
            limits=limits,
            decision_id_factory=lambda state, step: f"decision:{state}:{step}",
            clock=lambda: next(times),
        ),
        selected,
    )


def test_episode_accepts_once_and_rejects_the_stale_decision() -> None:
    episode, recorder = _episode()
    first = episode.current_decision()

    accepted = episode.submit(ActionSubmission(first.decision_id, 1))
    stale = episode.submit(ActionSubmission(first.decision_id, 1))

    assert accepted.accepted
    assert accepted.decision is not None
    assert accepted.decision.decision_id == "decision:1:1"
    assert episode.state == 1
    assert episode.step_index == 1
    assert not stale.accepted
    assert stale.rejection == ActionRejected("decision-stale", "decision is unknown or no longer current")
    assert episode.state == 1
    assert episode.step_index == 1
    assert len(recorder.steps) == 1


def test_domain_rejection_leaves_state_step_and_decision_unchanged() -> None:
    episode, recorder = _episode()
    decision = episode.current_decision()

    reply = episode.submit(ActionSubmission(decision.decision_id, -1))

    assert reply.rejection == ActionRejected("negative", "actions must be non-negative")
    assert episode.current_decision() == decision
    assert episode.state == 0
    assert episode.step_index == 0
    assert recorder.steps == []


def test_world_termination_and_host_truncation_are_distinct() -> None:
    terminated, terminated_recorder = _episode()
    decision = terminated.current_decision()
    terminal = terminated.submit(ActionSubmission(decision.decision_id, 3))

    truncated, truncated_recorder = _episode(limits=EpisodeLimits(max_steps=1))
    decision = truncated.current_decision()
    limited = truncated.submit(ActionSubmission(decision.decision_id, 1))

    assert terminal.terminated and not terminal.truncated
    assert terminated.status is EpisodeStatus.TERMINATED
    assert terminated_recorder.finished is not None
    assert terminated_recorder.finished.status is EpisodeStatus.TERMINATED
    assert limited.truncated and not limited.terminated
    assert truncated.status is EpisodeStatus.TRUNCATED
    assert truncated_recorder.finished is not None
    assert truncated_recorder.finished.status is EpisodeStatus.TRUNCATED
    with pytest.raises(EpisodeFinishedError):
        terminated.current_decision()
    with pytest.raises(EpisodeFinishedError):
        truncated.current_decision()


@pytest.mark.parametrize(
    ("limits", "usage", "reason"),
    (
        (EpisodeLimits(max_tokens=10), {"tokens": 10}, "token limit reached"),
        (EpisodeLimits(max_cost=Decimal("1.5")), {"cost": Decimal("1.5")}, "cost limit reached"),
    ),
)
def test_reported_usage_truncates_at_the_configured_limit(
    limits: EpisodeLimits,
    usage: dict[str, object],
    reason: str,
) -> None:
    episode, _ = _episode(limits=limits)
    episode.current_decision()

    reply = episode.add_usage(**usage)  # type: ignore[arg-type]

    assert reply is not None
    assert reply.truncated
    assert reply.reason == reason


def test_wall_clock_limit_is_checked_before_exposing_a_decision() -> None:
    episode, recorder = _episode(
        limits=EpisodeLimits(max_wall_seconds=1),
        clock=iter((0.0, 1.0)),
    )

    with pytest.raises(EpisodeFinishedError, match="wall-clock limit reached"):
        episode.current_decision()

    assert recorder.opened is None
    assert recorder.finished is not None
    assert recorder.finished.status is EpisodeStatus.TRUNCATED


def test_recorder_failure_prevents_live_state_advance() -> None:
    class FailingRecorder(MemoryEpisodeRecorder[int, str, int, str]):
        def record_step(self, event: object) -> None:
            del event
            raise OSError("durable publication failed")

    recorder = FailingRecorder()
    episode, _ = _episode(recorder=recorder)
    decision = episode.current_decision()

    with pytest.raises(OSError, match="durable publication failed"):
        episode.submit(ActionSubmission(decision.decision_id, 1))

    assert episode.state == 0
    assert episode.step_index == 0
    assert episode.current_decision() == decision


def test_finished_recorder_failure_prevents_terminal_state_advance() -> None:
    class FailingRecorder(MemoryEpisodeRecorder[int, str, int, str]):
        def record_finished(self, event: object) -> None:
            del event
            raise OSError("durable finalization failed")

    recorder = FailingRecorder()
    episode, _ = _episode(recorder=recorder)
    decision = episode.current_decision()

    with pytest.raises(OSError, match="durable finalization failed"):
        episode.submit(ActionSubmission(decision.decision_id, 3))

    assert episode.state == 0
    assert episode.step_index == 0
    assert episode.status is EpisodeStatus.ACTIVE
    assert episode.current_decision() == decision


def test_cancel_and_close_are_idempotent_truncations() -> None:
    episode, recorder = _episode()
    episode.current_decision()

    first = episode.cancel("operator cancelled")
    second = episode.cancel("ignored replacement")
    episode.close()

    assert first.truncated and second.truncated
    assert first.reason == second.reason == "operator cancelled"
    assert recorder.finished is not None
    assert recorder.finished.reason == "operator cancelled"
