# ABOUTME: Tests catalogue-compiled DeepSeek world tools and their private decision cursor.
# ABOUTME: Proves exact schemas, trusted identity, retry, stale recovery, terminal close, and unknown freeze.

from __future__ import annotations

import threading
from datetime import UTC, datetime
from pathlib import Path

import pytest

from aec_bench.adapters.deepseek_harness.native_world_tools import (
    WORLD_OBSERVE_TOOL_NAME,
    compile_world_native_tools,
    native_world_tool_surface_record,
)
from aec_bench.adapters.deepseek_harness.tool_gateway import (
    NativeCancellation,
    NativeToolDefinition,
    NativeToolDisposition,
    NativeToolInvocation,
    NativeToolRequestSemantics,
)
from aec_bench.contracts.world_interface import (
    WorldActorActionCapability,
    WorldActorActionRequest,
    WorldActorActionResult,
    WorldActorCapabilityCatalogue,
    WorldActorObservation,
    WorldInterfaceError,
)
from aec_bench.harness.world_actor import (
    ActorInvocationAuthority,
    ActorInvocationAuthorityConfig,
    ActorInvocationError,
    actor_catalogue_sha256,
)


class _WorldHost:
    def __init__(self, catalogue: WorldActorCapabilityCatalogue | None = None) -> None:
        self.calls: list[WorldActorActionRequest] = []
        self.decision_generation = 0
        self.unknown_outcome = False
        self.catalogue = catalogue or _catalogue()

    def capabilities(self) -> WorldActorCapabilityCatalogue:
        return self.catalogue

    def observe(self) -> WorldActorObservation:
        return WorldActorObservation(
            decision_id=f"decision-{self.decision_generation}-{len(self.calls)}",
            view={"calls": len(self.calls)},
        )

    def invoke(self, request: WorldActorActionRequest) -> WorldActorActionResult:
        if self.unknown_outcome:
            raise RuntimeError("unknown external outcome")
        if request.decision_id != self.observe().decision_id:
            raise WorldInterfaceError("decision-stale", "The decision is stale.")
        self.calls.append(request)
        terminated = request.action_name == "terminate"
        return WorldActorActionResult(
            request_id=request.request_id,
            action_name=request.action_name,
            status="accepted",
            task_receipt={"transition_id": f"transition-{len(self.calls)}"},
            next_observation=None if terminated else self.observe(),
            terminated=terminated,
        )


def _catalogue(*, action_names: tuple[str, ...] = ("terminate", "act")) -> WorldActorCapabilityCatalogue:
    schemas = {
        "act": {
            "type": "object",
            "properties": {
                "value": {"type": "integer", "minimum": 0},
                "note": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
            },
            "required": ["value"],
            "additionalProperties": False,
        },
        "terminate": {
            "type": "object",
            "properties": {"reason": {"type": "string"}},
            "required": ["reason"],
            "additionalProperties": False,
        },
    }
    return WorldActorCapabilityCatalogue(
        task_world_id="native-world",
        actions=tuple(
            WorldActorActionCapability(
                name=name,
                description=f"{name.title()} through the task catalogue.",
                input_schema=schemas.get(name, {"type": "object", "properties": {}}),
            )
            for name in action_names
        ),
    )


def _authority(tmp_path: Path, host: _WorldHost) -> ActorInvocationAuthority:
    authority = ActorInvocationAuthority(
        host=host,
        config=ActorInvocationAuthorityConfig(
            authority_id="authority-native",
            actor_principal_id="actor-native",
            max_world_actions=8,
            evidence_path=tmp_path / "actor-invocations.jsonl",
        ),
    )
    authority.start()
    return authority


def _invocation(request_id: str, *, tool_name: str) -> NativeToolInvocation:
    return NativeToolInvocation(
        request_id=request_id,
        deepseek_session_id="session-1",
        deepseek_tool_call_id=request_id,
        model_turn=1,
        tool_name=tool_name,
        generation_id="generation-1",
        admitted_at=datetime.now(UTC),
        cancellation=NativeCancellation(),
    )


def _definitions(
    tmp_path: Path,
    host: _WorldHost,
) -> tuple[ActorInvocationAuthority, dict[str, NativeToolDefinition]]:
    authority = _authority(tmp_path, host)
    definitions = compile_world_native_tools(authority=authority, catalogue=host.catalogue)
    return authority, {definition.name: definition for definition in definitions}


def _error_code(result: object) -> str:
    assert isinstance(result, dict)
    error = result["error"]
    assert isinstance(error, dict)
    return str(error["code"])


def test_compiler_uses_only_the_canonical_catalogue_and_records_exact_hashes(tmp_path: Path) -> None:
    host = _WorldHost()
    authority = _authority(tmp_path, host)

    definitions = compile_world_native_tools(authority=authority, catalogue=host.catalogue)
    surface = native_world_tool_surface_record(catalogue=host.catalogue, definitions=definitions)

    assert tuple(definition.name for definition in definitions) == (WORLD_OBSERVE_TOOL_NAME, "act", "terminate")
    assert definitions[1].description == host.catalogue.actions[1].description
    assert definitions[1].parameters_schema == host.catalogue.actions[1].input_schema
    assert all(
        definition.request_semantics is NativeToolRequestSemantics.HANDLER_AUTHORITY for definition in definitions
    )
    assert all(
        "request_id" not in definition.parameters_schema.get("properties", {})
        and "decision_id" not in definition.parameters_schema.get("properties", {})
        for definition in definitions
    )
    reordered = _catalogue(action_names=("act", "terminate"))
    assert actor_catalogue_sha256(reordered) == authority.catalogue_hash
    assert surface["catalogue_sha256"] == authority.catalogue_hash
    assert len(str(surface["public_tool_surface_sha256"])) == 64
    assert surface["action_mapping"] == (
        {"catalogue_action": "act", "public_tool": "act"},
        {"catalogue_action": "terminate", "public_tool": "terminate"},
    )
    assert authority.close().complete is True


@pytest.mark.parametrize(
    ("capability", "message"),
    [
        (
            WorldActorActionCapability(
                name=WORLD_OBSERVE_TOOL_NAME,
                description="Collision.",
                input_schema={"type": "object", "properties": {}},
            ),
            "reserved tool name",
        ),
        (
            WorldActorActionCapability(
                name="exposes_identity",
                description="Bad identity.",
                input_schema={"type": "object", "properties": {"request_id": {"type": "string"}}},
            ),
            "exposes infrastructure fields",
        ),
        (
            WorldActorActionCapability(
                name="unsupported_schema",
                description="Unsupported schema.",
                input_schema={"type": "object", "properties": {"value": {"oneOf": [{"type": "string"}]}}},
            ),
            "unsupported JSON Schema keywords",
        ),
        (
            WorldActorActionCapability(
                name="invalid-name",
                description="Invalid provider name.",
                input_schema={"type": "object", "properties": {}},
            ),
            "invalid native tool name",
        ),
    ],
)
def test_compiler_fails_closed_for_invalid_catalogues(
    tmp_path: Path,
    capability: WorldActorActionCapability,
    message: str,
) -> None:
    catalogue = WorldActorCapabilityCatalogue(task_world_id="invalid-world", actions=(capability,))
    host = _WorldHost(catalogue)
    authority = _authority(tmp_path, host)

    with pytest.raises(ValueError, match=message):
        compile_world_native_tools(authority=authority, catalogue=catalogue)

    assert authority.close().complete is True


def test_compiler_rejects_catalogue_drift_before_model_execution(tmp_path: Path) -> None:
    host = _WorldHost()
    frozen_catalogue = host.catalogue
    authority = _authority(tmp_path, host)
    host.catalogue = _catalogue(action_names=("act",))

    with pytest.raises(ActorInvocationError, match="actor-catalogue-drift"):
        compile_world_native_tools(authority=authority, catalogue=frozen_catalogue)

    assert authority.close().complete is True


def test_native_cursor_requires_visible_observation_and_preserves_exact_retry(tmp_path: Path) -> None:
    host = _WorldHost()
    authority, definitions = _definitions(tmp_path, host)
    act = definitions["act"]
    terminate = definitions["terminate"]

    before_observe = act.handler(_invocation("action-before-observe", tool_name="act"), {"value": 1})
    observation = definitions[WORLD_OBSERVE_TOOL_NAME].handler(
        _invocation("observe-1", tool_name=WORLD_OBSERVE_TOOL_NAME),
        {},
    )
    invocation = _invocation("action-1", tool_name="act")
    first = act.handler(invocation, {"value": 1})
    duplicate = act.handler(invocation, {"value": 1})
    terminal = terminate.handler(_invocation("terminal-1", tool_name="terminate"), {"reason": "done"})
    after_terminal = act.handler(_invocation("action-after-terminal", tool_name="act"), {"value": 2})

    assert _error_code(before_observe.result) == "world-observation-required"
    assert observation.result == {"decision_id": "decision-0-0", "view": {"calls": 0}}
    assert first == duplicate
    assert first.disposition is NativeToolDisposition.CONTINUE
    assert terminal.disposition is NativeToolDisposition.CONCLUDE_TURN
    assert _error_code(after_terminal.result) == "episode-closed"
    assert [request.request_id for request in host.calls] == ["action-1", "terminal-1"]
    assert host.calls[0].decision_id == "decision-0-0"
    assert authority.world_action_count == 2
    assert authority.close().complete is True


def test_native_cursor_allows_only_one_concurrent_action_to_consume_an_observation(tmp_path: Path) -> None:
    dispatch_started = threading.Event()
    release_dispatch = threading.Event()

    class BlockingHost(_WorldHost):
        def invoke(self, request: WorldActorActionRequest) -> WorldActorActionResult:
            dispatch_started.set()
            assert release_dispatch.wait(timeout=3)
            return super().invoke(request)

    host = BlockingHost()
    authority, definitions = _definitions(tmp_path, host)
    definitions[WORLD_OBSERVE_TOOL_NAME].handler(
        _invocation("observe-1", tool_name=WORLD_OBSERVE_TOOL_NAME),
        {},
    )
    first_result: list[object] = []
    first = threading.Thread(
        target=lambda: first_result.append(
            definitions["act"].handler(_invocation("action-1", tool_name="act"), {"value": 1}).result
        )
    )
    first.start()
    assert dispatch_started.wait(timeout=3)
    competing = definitions["act"].handler(_invocation("action-2", tool_name="act"), {"value": 2})
    release_dispatch.set()
    first.join(timeout=3)

    assert not first.is_alive()
    assert _error_code(competing.result) == "world-observation-required"
    assert len(first_result) == 1
    assert len(host.calls) == 1
    assert authority.world_action_count == 1
    assert authority.close().complete is True


def test_stale_decision_clears_cursor_until_the_model_observes_again(tmp_path: Path) -> None:
    host = _WorldHost()
    authority, definitions = _definitions(tmp_path, host)
    observe = definitions[WORLD_OBSERVE_TOOL_NAME]
    act = definitions["act"]

    observe.handler(_invocation("observe-1", tool_name=WORLD_OBSERVE_TOOL_NAME), {})
    host.decision_generation += 1
    stale = act.handler(_invocation("stale-action", tool_name="act"), {"value": 1})
    blocked = act.handler(_invocation("blocked-action", tool_name="act"), {"value": 2})
    refreshed = observe.handler(_invocation("observe-2", tool_name=WORLD_OBSERVE_TOOL_NAME), {})
    accepted = act.handler(_invocation("accepted-action", tool_name="act"), {"value": 3})

    assert _error_code(stale.result) == "decision-stale"
    assert _error_code(blocked.result) == "world-observation-required"
    assert refreshed.result == {"decision_id": "decision-1-0", "view": {"calls": 0}}
    assert isinstance(accepted.result, dict)
    assert accepted.result["status"] == "accepted"
    assert [request.request_id for request in host.calls] == ["accepted-action"]
    assert authority.close().complete is True


def test_unknown_outcome_freezes_new_native_calls_and_requires_exact_reconciliation(tmp_path: Path) -> None:
    host = _WorldHost()
    authority, definitions = _definitions(tmp_path, host)
    observe = definitions[WORLD_OBSERVE_TOOL_NAME]
    act = definitions["act"]

    observe.handler(_invocation("observe-1", tool_name=WORLD_OBSERVE_TOOL_NAME), {})
    host.unknown_outcome = True
    invocation = _invocation("unknown-action", tool_name="act")
    unknown = act.handler(invocation, {"value": 1})
    blocked_action = act.handler(_invocation("new-action", tool_name="act"), {"value": 2})
    blocked_observe = observe.handler(_invocation("observe-2", tool_name=WORLD_OBSERVE_TOOL_NAME), {})
    exact_retry = act.handler(invocation, {"value": 1})

    for response in (unknown, blocked_action, blocked_observe, exact_retry):
        assert _error_code(response.result) in {
            "actor-invocation-outcome-unknown",
            "world-action-outcome-unknown",
        }
        assert response.disposition is NativeToolDisposition.CONCLUDE_TURN
    assert authority.world_action_count == 1
    assert authority.close().complete is False
