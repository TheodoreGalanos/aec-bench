# ABOUTME: Tests the DeepSeek native presentation of shared world invocation authority.
# ABOUTME: Proves hidden correlation, exact retry, terminal disposition, and actor-visible errors.

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from aec_bench.adapters.deepseek_harness.native_world_tools import NativeWorldToolTransport
from aec_bench.adapters.deepseek_harness.tool_gateway import (
    NativeCancellation,
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
)
from aec_bench.harness.world_actor import ActorInvocationAuthority, ActorInvocationAuthorityConfig


class _WorldHost:
    def __init__(self) -> None:
        self.calls: list[WorldActorActionRequest] = []

    def capabilities(self) -> WorldActorCapabilityCatalogue:
        return WorldActorCapabilityCatalogue(
            task_world_id="native-world",
            actions=(
                WorldActorActionCapability(name="act", description="Act.", input_schema={"type": "object"}),
                WorldActorActionCapability(
                    name="terminate",
                    description="Terminate.",
                    input_schema={"type": "object"},
                ),
            ),
        )

    def observe(self) -> WorldActorObservation:
        return WorldActorObservation(decision_id=f"decision-{len(self.calls)}", view={"calls": len(self.calls)})

    def invoke(self, request: WorldActorActionRequest) -> WorldActorActionResult:
        self.calls.append(request)
        terminated = request.action_name == "terminate"
        return WorldActorActionResult(
            request_id=request.request_id,
            action_name=request.action_name,
            status="accepted",
            task_receipt={"transition_id": f"transition-{len(self.calls)}"},
            next_observation=None,
            terminated=terminated,
        )


def _authority(tmp_path: Path, host: _WorldHost) -> ActorInvocationAuthority:
    authority = ActorInvocationAuthority(
        host=host,
        config=ActorInvocationAuthorityConfig(
            authority_id="authority-native",
            actor_principal_id="actor-native",
            max_world_actions=5,
            evidence_path=tmp_path / "actor-invocations.jsonl",
        ),
    )
    authority.start()
    return authority


def _invocation(request_id: str, *, tool_name: str, tool_call_id: str) -> NativeToolInvocation:
    return NativeToolInvocation(
        request_id=request_id,
        deepseek_session_id="session-1",
        deepseek_tool_call_id=tool_call_id,
        model_turn=1,
        tool_name=tool_name,
        generation_id="generation-1",
        admitted_at=datetime.now(UTC),
        cancellation=NativeCancellation(),
    )


def _schema() -> dict[str, object]:
    return {
        "type": "object",
        "properties": {"value": {"type": "integer"}},
        "required": ["value"],
        "additionalProperties": False,
    }


def test_native_action_uses_authority_identity_and_replays_exact_retry(tmp_path: Path) -> None:
    host = _WorldHost()
    authority = _authority(tmp_path, host)
    transport = NativeWorldToolTransport(authority)
    definition = transport.action_definition(
        name="act",
        description="Act.",
        parameters_schema=_schema(),
    )
    invocation = _invocation("dsh:session-1:tool-1", tool_name="act", tool_call_id="tool-1")

    first = definition.handler(invocation, {"value": 1})
    replay = definition.handler(invocation, {"value": 1})

    assert definition.request_semantics is NativeToolRequestSemantics.HANDLER_AUTHORITY
    assert first == replay
    assert first.disposition is NativeToolDisposition.CONTINUE
    assert isinstance(first.result, dict)
    assert first.result["request_id"] == "dsh:session-1:tool-1"
    assert len(host.calls) == 1
    assert authority.world_action_count == 1
    assert authority.close().complete is True


def test_native_observation_and_terminal_errors_use_generic_dispositions(tmp_path: Path) -> None:
    host = _WorldHost()
    authority = _authority(tmp_path, host)
    transport = NativeWorldToolTransport(authority)
    observe = transport.observation_definition(
        name="observe_world",
        description="Observe.",
        parameters_schema={"type": "object", "properties": {}, "additionalProperties": False},
    )
    terminate = transport.action_definition(
        name="terminate",
        description="Terminate.",
        parameters_schema=_schema(),
    )
    act = transport.action_definition(name="act", description="Act.", parameters_schema=_schema())

    observation = observe.handler(
        _invocation("dsh:session-1:observe-1", tool_name="observe_world", tool_call_id="observe-1"),
        {},
    )
    terminal = terminate.handler(
        _invocation("dsh:session-1:terminate-1", tool_name="terminate", tool_call_id="terminate-1"),
        {"value": 1},
    )
    after_terminal = act.handler(
        _invocation("dsh:session-1:act-2", tool_name="act", tool_call_id="act-2"),
        {"value": 2},
    )

    assert observation.result == {"decision_id": "decision-0", "view": {"calls": 0}}
    assert terminal.disposition is NativeToolDisposition.CONCLUDE_TURN
    assert isinstance(terminal.result, dict)
    assert terminal.result["terminated"] is True
    assert after_terminal.disposition is NativeToolDisposition.CONCLUDE_TURN
    assert after_terminal.result == {
        "status": "error",
        "error": {
            "code": "episode-closed",
            "detail": "The world episode is closed.",
            "outcome": "not-dispatched",
            "action_sequence": None,
        },
    }
    assert len(host.calls) == 1
    assert authority.close().complete is True
