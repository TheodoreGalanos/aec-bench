# ABOUTME: Tests the shared trial-wide authority for actor world actions.
# ABOUTME: Proves exact retry, causal order, budget, terminal latch, evidence, and close semantics.

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import JsonValue, ValidationError

from aec_bench.contracts.world_interface import (
    WorldActorActionCapability,
    WorldActorActionRequest,
    WorldActorActionResult,
    WorldActorCapabilityCatalogue,
    WorldActorObservation,
    WorldInterfaceError,
)
from aec_bench.harness.world_actor import (
    ACTOR_INVOCATION_EVIDENCE_SCHEMA,
    ActorCorrelation,
    ActorInvocationAuthority,
    ActorInvocationAuthorityConfig,
    ActorInvocationError,
    ActorInvocationLifecycle,
    ActorInvocationOutcome,
    ActorInvocationOutcomeClass,
    ActorInvocationRequest,
    ActorTurnDisposition,
)


def _catalogue(*names: str) -> WorldActorCapabilityCatalogue:
    return WorldActorCapabilityCatalogue(
        task_world_id="test-world",
        actions=tuple(
            WorldActorActionCapability(
                name=name,
                description=f"Run {name}.",
                input_schema={"type": "object"},
            )
            for name in names
        ),
    )


def _result(
    request: WorldActorActionRequest,
    *,
    status: str = "accepted",
    terminated: bool = False,
    truncated: bool = False,
    task_receipt: dict[str, JsonValue] | None = None,
) -> WorldActorActionResult:
    return WorldActorActionResult(
        request_id=request.request_id,
        action_name=request.action_name,
        status=status,
        task_receipt=task_receipt or {"transition_id": f"transition-{request.request_id}"},
        next_observation=None,
        terminated=terminated,
        truncated=truncated,
    )


class _FakeWorldHost:
    def __init__(
        self,
        *,
        invoke: Callable[[WorldActorActionRequest], WorldActorActionResult] | None = None,
        catalogue: WorldActorCapabilityCatalogue | None = None,
    ) -> None:
        self.catalogue = catalogue or _catalogue("act")
        self.calls: list[WorldActorActionRequest] = []
        self.observe_calls = 0
        self._invoke = invoke
        self._lock = threading.Lock()

    def capabilities(self) -> WorldActorCapabilityCatalogue:
        return self.catalogue

    def observe(self) -> WorldActorObservation:
        with self._lock:
            self.observe_calls += 1
            call_count = len(self.calls)
        return WorldActorObservation(decision_id=f"decision-{call_count}", view={"call_count": call_count})

    def invoke(self, request: WorldActorActionRequest) -> WorldActorActionResult:
        with self._lock:
            self.calls.append(request)
        if self._invoke is not None:
            return self._invoke(request)
        return _result(request)


def _authority(
    tmp_path: Path,
    host: _FakeWorldHost,
    *,
    max_world_actions: int = 10,
    close_timeout_sec: float = 0.1,
    max_result_bytes: int = 4_194_304,
) -> ActorInvocationAuthority:
    authority = ActorInvocationAuthority(
        host=host,
        config=ActorInvocationAuthorityConfig(
            authority_id="authority-1",
            actor_principal_id="actor-1",
            max_world_actions=max_world_actions,
            evidence_path=tmp_path / "actor-invocations.jsonl",
            close_timeout_sec=close_timeout_sec,
            max_result_bytes=max_result_bytes,
        ),
    )
    authority.start()
    return authority


def _request(
    request_id: str,
    *,
    decision_id: str = "decision-0",
    action_name: str = "act",
    arguments: dict[str, JsonValue] | None = None,
) -> ActorInvocationRequest:
    return ActorInvocationRequest(
        request_id=request_id,
        decision_id=decision_id,
        action_name=action_name,
        arguments=arguments or {},
        transport="test",
        correlation=ActorCorrelation(transport_request_id=f"transport-{request_id}"),
    )


def _invoke_thread(
    authority: ActorInvocationAuthority,
    request: ActorInvocationRequest,
    outcomes: list[ActorInvocationOutcome],
    errors: list[ActorInvocationError],
) -> None:
    try:
        outcomes.append(authority.invoke(request))
    except ActorInvocationError as exc:
        errors.append(exc)


def _evidence(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_start_freezes_and_hashes_catalogue_and_rejects_drift(tmp_path: Path) -> None:
    host = _FakeWorldHost()
    authority = _authority(tmp_path, host)

    frozen = authority.capabilities(correlation=ActorCorrelation(transport_request_id="catalogue-1"))
    original_hash = authority.catalogue_hash
    host.catalogue = _catalogue("act", "drifted-action")

    with pytest.raises(ActorInvocationError) as error:
        authority.capabilities(correlation=ActorCorrelation(transport_request_id="catalogue-2"))

    assert frozen == _catalogue("act")
    assert original_hash is not None
    assert error.value.code == "actor-catalogue-drift"
    assert error.value.outcome is ActorInvocationOutcomeClass.NOT_DISPATCHED
    assert authority.world_action_count == 0
    assert authority.close().complete is True


def test_completed_duplicate_replays_and_conflict_fails_without_dispatch(tmp_path: Path) -> None:
    host = _FakeWorldHost()
    authority = _authority(tmp_path, host)
    request = _request("request-1", arguments={"value": 1})

    first = authority.invoke(request)
    replay = authority.invoke(request)
    with pytest.raises(ActorInvocationError) as conflict:
        authority.invoke(_request("request-1", arguments={"value": 2}))

    assert first.action_sequence == 1
    assert first.duplicate is False
    assert replay.result == first.result
    assert replay.action_sequence == first.action_sequence
    assert replay.duplicate is True
    assert conflict.value.code == "request-id-conflict"
    assert conflict.value.outcome is ActorInvocationOutcomeClass.NOT_DISPATCHED
    assert len(host.calls) == 1
    assert authority.world_action_count == 1
    assert authority.close().complete is True


def test_invoke_current_retains_the_original_hidden_decision_for_retry(tmp_path: Path) -> None:
    host = _FakeWorldHost()
    authority = _authority(tmp_path, host)
    correlation = ActorCorrelation(transport_request_id="native-1")

    first = authority.invoke_current(
        request_id="native-request",
        action_name="act",
        arguments={"value": 1},
        transport="native",
        correlation=correlation,
    )
    replay = authority.invoke_current(
        request_id="native-request",
        action_name="act",
        arguments={"value": 1},
        transport="native",
        correlation=correlation,
    )
    with pytest.raises(ActorInvocationError) as conflict:
        authority.invoke_current(
            request_id="native-request",
            action_name="act",
            arguments={"value": 2},
            transport="native",
            correlation=correlation,
        )

    assert first.result == replay.result
    assert replay.duplicate is True
    assert conflict.value.code == "request-id-conflict"
    assert host.observe_calls == 1
    assert len(host.calls) == 1
    assert authority.close().complete is True


def test_hidden_decision_capture_and_admission_precede_explicit_request(tmp_path: Path) -> None:
    observe_started = threading.Event()
    release_observe = threading.Event()

    class BlockingObserveHost(_FakeWorldHost):
        def observe(self) -> WorldActorObservation:
            observe_started.set()
            assert release_observe.wait(2)
            return super().observe()

    host = BlockingObserveHost()
    authority = _authority(tmp_path, host)
    outcomes: list[ActorInvocationOutcome] = []
    errors: list[ActorInvocationError] = []

    def invoke_hidden() -> None:
        try:
            outcomes.append(
                authority.invoke_current(
                    request_id="hidden",
                    action_name="act",
                    arguments={},
                    transport="native",
                    correlation=ActorCorrelation(transport_request_id="native-hidden"),
                )
            )
        except ActorInvocationError as exc:
            errors.append(exc)

    hidden = threading.Thread(target=invoke_hidden)
    explicit = threading.Thread(
        target=_invoke_thread,
        args=(authority, _request("explicit"), outcomes, errors),
    )
    hidden.start()
    assert observe_started.wait(2)
    explicit.start()
    time.sleep(0.02)
    assert not host.calls
    release_observe.set()
    hidden.join(timeout=2)
    explicit.join(timeout=2)

    assert not errors
    assert [request.request_id for request in host.calls] == ["hidden", "explicit"]
    assert sorted(outcome.action_sequence for outcome in outcomes) == [1, 2]
    assert authority.close().complete is True


def test_in_flight_duplicate_waits_and_dispatches_once(tmp_path: Path) -> None:
    started = threading.Event()
    release = threading.Event()

    def invoke(request: WorldActorActionRequest) -> WorldActorActionResult:
        started.set()
        assert release.wait(2)
        return _result(request)

    host = _FakeWorldHost(invoke=invoke)
    authority = _authority(tmp_path, host)
    request = _request("same-request")
    outcomes: list[ActorInvocationOutcome] = []
    errors: list[ActorInvocationError] = []
    owner = threading.Thread(target=_invoke_thread, args=(authority, request, outcomes, errors))
    duplicate = threading.Thread(target=_invoke_thread, args=(authority, request, outcomes, errors))

    owner.start()
    assert started.wait(2)
    duplicate.start()
    time.sleep(0.02)
    assert duplicate.is_alive()
    release.set()
    owner.join(timeout=2)
    duplicate.join(timeout=2)

    assert not errors
    assert not owner.is_alive()
    assert not duplicate.is_alive()
    assert len(host.calls) == 1
    assert authority.world_action_count == 1
    assert sorted(outcome.duplicate for outcome in outcomes) == [False, True]
    assert {outcome.action_sequence for outcome in outcomes} == {1}
    assert authority.close().complete is True


def test_budget_charges_dispatched_rejection_and_not_rejected_new_request(tmp_path: Path) -> None:
    host = _FakeWorldHost(invoke=lambda request: _result(request, status="rejected", task_receipt={"code": "stale"}))
    authority = _authority(tmp_path, host, max_world_actions=1)

    rejected_by_world = authority.invoke(_request("world-rejection"))
    with pytest.raises(ActorInvocationError) as exhausted:
        authority.invoke(_request("over-budget"))

    assert rejected_by_world.result.status == "rejected"
    assert authority.world_action_count == 1
    assert authority.world_action_limit_reached is True
    assert exhausted.value.code == "world-action-budget-exhausted"
    assert exhausted.value.outcome is ActorInvocationOutcomeClass.NOT_DISPATCHED
    assert len(host.calls) == 1
    assert authority.close().complete is True


def test_terminal_latch_replays_duplicates_and_rejects_queued_and_new_actions(tmp_path: Path) -> None:
    started = threading.Event()
    release = threading.Event()

    def invoke(request: WorldActorActionRequest) -> WorldActorActionResult:
        if request.request_id == "terminal":
            started.set()
            assert release.wait(2)
            return _result(request, terminated=True)
        return _result(request)

    host = _FakeWorldHost(invoke=invoke)
    authority = _authority(tmp_path, host, max_world_actions=2)
    outcomes: list[ActorInvocationOutcome] = []
    errors: list[ActorInvocationError] = []
    terminal_request = _request("terminal")
    terminal_thread = threading.Thread(
        target=_invoke_thread,
        args=(authority, terminal_request, outcomes, errors),
    )
    queued_thread = threading.Thread(
        target=_invoke_thread,
        args=(authority, _request("queued"), outcomes, errors),
    )

    terminal_thread.start()
    assert started.wait(2)
    queued_thread.start()
    for _ in range(100):
        if authority.world_action_limit_reached:
            break
        time.sleep(0.005)
    assert authority.world_action_limit_reached
    release.set()
    terminal_thread.join(timeout=2)
    queued_thread.join(timeout=2)

    replay = authority.invoke(terminal_request)
    with pytest.raises(ActorInvocationError) as after_terminal:
        authority.invoke(_request("new-after-terminal"))

    assert authority.terminal is True
    assert authority.world_action_count == 1
    assert len(host.calls) == 1
    assert replay.duplicate is True
    assert replay.disposition is ActorTurnDisposition.CONCLUDE_TURN
    assert {error.code for error in errors} == {"episode-closed"}
    assert after_terminal.value.code == "episode-closed"
    assert after_terminal.value.disposition is ActorTurnDisposition.CONCLUDE_TURN
    assert authority.close().complete is True


def test_concurrent_unique_actions_have_one_dispatch_order(tmp_path: Path) -> None:
    active = 0
    maximum_active = 0
    state_lock = threading.Lock()

    def invoke(request: WorldActorActionRequest) -> WorldActorActionResult:
        nonlocal active, maximum_active
        with state_lock:
            active += 1
            maximum_active = max(maximum_active, active)
        time.sleep(0.01)
        with state_lock:
            active -= 1
        return _result(request)

    host = _FakeWorldHost(invoke=invoke)
    authority = _authority(tmp_path, host)
    outcomes: list[ActorInvocationOutcome] = []
    errors: list[ActorInvocationError] = []
    threads = [
        threading.Thread(
            target=_invoke_thread,
            args=(authority, _request(f"request-{index}", arguments={"index": index}), outcomes, errors),
        )
        for index in range(6)
    ]

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=2)

    assert not errors
    assert all(not thread.is_alive() for thread in threads)
    assert maximum_active == 1
    assert sorted(outcome.action_sequence for outcome in outcomes) == list(range(1, 7))
    assert authority.world_action_count == 6
    assert authority.close().complete is True


def test_observe_waits_for_an_earlier_admitted_action(tmp_path: Path) -> None:
    started = threading.Event()
    release = threading.Event()
    observed = threading.Event()

    def invoke(request: WorldActorActionRequest) -> WorldActorActionResult:
        started.set()
        assert release.wait(2)
        return _result(request)

    host = _FakeWorldHost(invoke=invoke)
    authority = _authority(tmp_path, host)
    outcomes: list[ActorInvocationOutcome] = []
    errors: list[ActorInvocationError] = []
    action_thread = threading.Thread(
        target=_invoke_thread,
        args=(authority, _request("blocking"), outcomes, errors),
    )

    def observe() -> None:
        authority.observe(correlation=ActorCorrelation(transport_request_id="observe-1"))
        observed.set()

    observe_thread = threading.Thread(target=observe)
    action_thread.start()
    assert started.wait(2)
    observe_thread.start()
    time.sleep(0.02)
    assert not observed.is_set()
    release.set()
    action_thread.join(timeout=2)
    observe_thread.join(timeout=2)

    assert observed.is_set()
    assert not errors
    assert host.observe_calls == 1
    assert authority.close().complete is True


def test_world_error_and_oversized_result_are_cached_after_one_dispatch(tmp_path: Path) -> None:
    def world_error(_request: WorldActorActionRequest) -> WorldActorActionResult:
        raise WorldInterfaceError("decision-stale", "The actor decision is stale.")

    error_host = _FakeWorldHost(invoke=world_error)
    error_authority = _authority(tmp_path / "error", error_host)
    request = _request("world-error")
    for duplicate in (False, True):
        with pytest.raises(ActorInvocationError) as error:
            error_authority.invoke(request)
        assert error.value.code == "decision-stale"
        assert error.value.outcome is ActorInvocationOutcomeClass.COMPLETED
        assert error.value.duplicate is duplicate
    assert len(error_host.calls) == 1
    assert error_authority.close().complete is True

    large_host = _FakeWorldHost(
        invoke=lambda action: _result(action, terminated=True, task_receipt={"payload": "x" * 1_000}),
    )
    large_authority = _authority(tmp_path / "large", large_host, max_result_bytes=128)
    large_request = _request("large-result")
    for duplicate in (False, True):
        with pytest.raises(ActorInvocationError) as error:
            large_authority.invoke(large_request)
        assert error.value.code == "world-action-result-too-large"
        assert error.value.outcome is ActorInvocationOutcomeClass.COMPLETED
        assert error.value.duplicate is duplicate
        assert error.value.disposition is ActorTurnDisposition.CONCLUDE_TURN
    with pytest.raises(ActorInvocationError) as after_terminal:
        large_authority.invoke(_request("after-large-terminal"))
    assert len(large_host.calls) == 1
    assert large_authority.terminal is True
    assert after_terminal.value.code == "episode-closed"
    assert large_authority.close().complete is True


def test_invalid_world_outcome_is_unknown_and_does_not_break_authority_state(tmp_path: Path) -> None:
    host = _FakeWorldHost(invoke=lambda _request: cast(Any, {"not": "a world result"}))
    authority = _authority(tmp_path, host)
    request = _request("invalid-result")

    for duplicate in (False, True):
        with pytest.raises(ActorInvocationError) as error:
            authority.invoke(request)
        assert error.value.code == "world-action-outcome-invalid"
        assert error.value.outcome is ActorInvocationOutcomeClass.UNKNOWN
        assert error.value.duplicate is duplicate

    close_report = authority.close()
    assert len(host.calls) == 1
    assert close_report.quiescent is True
    assert close_report.complete is False
    assert close_report.unknown_outcome_request_ids == ("invalid-result",)


def test_incomplete_close_retains_unknown_identity_and_ignores_late_result(tmp_path: Path) -> None:
    started = threading.Event()
    release = threading.Event()

    def invoke(request: WorldActorActionRequest) -> WorldActorActionResult:
        started.set()
        assert release.wait(2)
        return _result(request)

    host = _FakeWorldHost(invoke=invoke)
    authority = _authority(tmp_path, host, close_timeout_sec=0.01)
    request = _request("unsettled")
    outcomes: list[ActorInvocationOutcome] = []
    errors: list[ActorInvocationError] = []
    thread = threading.Thread(target=_invoke_thread, args=(authority, request, outcomes, errors))
    thread.start()
    assert started.wait(2)

    incomplete = authority.close()
    with pytest.raises(ActorInvocationError) as retry:
        authority.invoke(request)
    release.set()
    thread.join(timeout=2)
    settled = authority.close()

    assert incomplete.quiescent is False
    assert incomplete.complete is False
    assert incomplete.lifecycle is ActorInvocationLifecycle.CLOSING
    assert incomplete.unsettled_request_ids == ("unsettled",)
    assert incomplete.unknown_outcome_request_ids == ("unsettled",)
    assert retry.value.code == "actor-invocation-outcome-unknown"
    assert retry.value.duplicate is True
    assert not outcomes
    assert len(errors) == 1
    assert errors[0].outcome is ActorInvocationOutcomeClass.UNKNOWN
    assert settled.quiescent is True
    assert settled.complete is False
    assert settled.lifecycle is ActorInvocationLifecycle.CLOSED
    assert settled.unknown_outcome_request_ids == ("unsettled",)
    completion = next(item for item in _evidence(authority.config.evidence_path) if item["record_type"] == "completion")
    assert completion["late_ignored"] is True
    assert completion["error_code"] == "actor-invocation-outcome-unknown"


def test_evidence_is_monotonic_content_bound_and_token_free(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        ActorCorrelation.model_validate({"transport_request_id": "request", "capability_token": "secret"})

    host = _FakeWorldHost()
    authority = _authority(tmp_path, host)
    authority.observe(correlation=ActorCorrelation(transport_request_id="observe-1"))
    authority.invoke(_request("request-1", arguments={"private": "value"}))
    authority.close()

    evidence = _evidence(authority.config.evidence_path)
    assert [item["sequence"] for item in evidence] == list(range(1, len(evidence) + 1))
    assert evidence[0]["record_type"] == "header"
    assert evidence[0]["schema"] == ACTOR_INVOCATION_EVIDENCE_SCHEMA
    assert evidence[0]["catalogue_sha256"] == authority.catalogue_hash
    assert evidence[-1]["record_type"] == "close"
    serialized = json.dumps(evidence)
    assert "capability_token" not in serialized
    assert '"arguments"' not in serialized
    assert '"decision_id"' not in serialized
