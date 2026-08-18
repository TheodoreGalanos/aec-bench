# ABOUTME: Runs one deterministic actor script through Prime and DeepSeek world transports.
# ABOUTME: Proves provider changes do not change catalogue, cursor, replay, receipt, or terminal semantics.

from __future__ import annotations

import json
import socket
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from aec_bench.adapters.deepseek_harness.native_world_tools import (
    WORLD_OBSERVE_TOOL_NAME,
    compile_world_native_tools,
)
from aec_bench.adapters.deepseek_harness.tool_gateway import (
    NativeCancellation,
    NativeToolDefinition,
    NativeToolDisposition,
    NativeToolInvocation,
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
    WORLD_ACTOR_CAPABILITY_ENV,
    WORLD_ACTOR_PROTOCOL,
    WORLD_ACTOR_SOCKET_ENV,
    ActorInvocationAuthority,
    ActorInvocationAuthorityConfig,
    WorldActorEndpoint,
    actor_catalogue_sha256,
)
from aec_bench.ledger.artifact_repository import ArtifactRepository


class _ConformanceHost:
    def __init__(self) -> None:
        self.catalogue = WorldActorCapabilityCatalogue(
            task_world_id="provider-conformance-world",
            actions=(
                WorldActorActionCapability(
                    name="terminate",
                    description="Finish the deterministic episode.",
                    input_schema={
                        "type": "object",
                        "properties": {"reason": {"type": "string"}},
                        "required": ["reason"],
                        "additionalProperties": False,
                    },
                ),
                WorldActorActionCapability(
                    name="act",
                    description="Apply one deterministic value.",
                    input_schema={
                        "type": "object",
                        "properties": {"value": {"type": "integer"}},
                        "required": ["value"],
                        "additionalProperties": False,
                    },
                ),
            ),
        )
        self.decision_generation = 0
        self.attempts: list[WorldActorActionRequest] = []
        self.calls: list[WorldActorActionRequest] = []
        self.terminated = False

    def capabilities(self) -> WorldActorCapabilityCatalogue:
        return self.catalogue

    def observe(self) -> WorldActorObservation:
        return WorldActorObservation(
            decision_id=f"decision-{self.decision_generation}-{len(self.calls)}",
            view={"accepted_actions": len(self.calls), "terminated": self.terminated},
        )

    def advance_decision(self) -> None:
        self.decision_generation += 1

    def invoke(self, request: WorldActorActionRequest) -> WorldActorActionResult:
        self.attempts.append(request)
        if request.decision_id != self.observe().decision_id:
            raise WorldInterfaceError("decision-stale", "The decision is stale.")
        self.calls.append(request)
        self.terminated = request.action_name == "terminate"
        return WorldActorActionResult(
            request_id=request.request_id,
            action_name=request.action_name,
            status="applied",
            task_receipt={"receipt_id": f"receipt-{len(self.calls)}"},
            next_observation=None if self.terminated else self.observe(),
            terminated=self.terminated,
        )

    def verify(self) -> dict[str, Any]:
        return {
            "valid": self.terminated and [call.action_name for call in self.calls] == ["act", "terminate"],
            "receipts": [f"receipt-{index}" for index in range(1, len(self.calls) + 1)],
        }


def _authority(tmp_path: Path, host: _ConformanceHost, name: str) -> ActorInvocationAuthority:
    return ActorInvocationAuthority(
        host=host,
        config=ActorInvocationAuthorityConfig(
            authority_id="provider-conformance-authority",
            actor_principal_id="provider-conformance-actor",
            max_world_actions=8,
            evidence_path=tmp_path / name / "actor-authority.jsonl",
        ),
    )


def _prime_call(environment: dict[str, str], request: dict[str, Any], sequence: int) -> dict[str, Any]:
    payload = {
        "protocol": WORLD_ACTOR_PROTOCOL,
        "transport_request_id": f"prime-transport-{sequence}",
        "capability": environment[WORLD_ACTOR_CAPABILITY_ENV],
        "request": request,
    }
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(3)
        client.connect(environment[WORLD_ACTOR_SOCKET_ENV])
        client.sendall(json.dumps(payload).encode("utf-8") + b"\n")
        response = client.makefile("rb").readline()
    return cast(dict[str, Any], json.loads(response))


def _invocation(request_id: str, tool_name: str) -> NativeToolInvocation:
    return NativeToolInvocation(
        request_id=request_id,
        deepseek_session_id="deepseek-conformance-session",
        deepseek_tool_call_id=request_id,
        model_turn=1,
        tool_name=tool_name,
        generation_id="deepseek-conformance-generation",
        admitted_at=datetime.now(UTC),
        cancellation=NativeCancellation(),
    )


def _prime_script(tmp_path: Path) -> dict[str, Any]:
    host = _ConformanceHost()
    (tmp_path / "prime").mkdir()
    authority = _authority(tmp_path, host, "prime")
    endpoint = WorldActorEndpoint(
        authority=authority,
        socket_directory=tmp_path / "prime" / "socket",
        evidence_file=tmp_path / "prime" / "actor-transport.jsonl",
    )
    with endpoint:
        environment = endpoint.connection_environment()
        catalogue = _prime_call(environment, {"operation": "capabilities"}, 1)["result"]
        first_observation = _prime_call(environment, {"operation": "observe"}, 2)["result"]
        host.advance_decision()
        stale = _prime_call(
            environment,
            {
                "operation": "invoke",
                "request_id": "stale-1",
                "decision_id": first_observation["decision_id"],
                "action_name": "act",
                "arguments": {"value": 0},
            },
            3,
        )
        fresh_observation = _prime_call(environment, {"operation": "observe"}, 4)["result"]
        action_request = {
            "operation": "invoke",
            "request_id": "action-1",
            "decision_id": fresh_observation["decision_id"],
            "action_name": "act",
            "arguments": {"value": 1},
        }
        accepted = _prime_call(environment, action_request, 5)["result"]
        duplicate = _prime_call(environment, action_request, 6)["result"]
        conflict = _prime_call(
            environment,
            {**action_request, "arguments": {"value": 2}},
            7,
        )
        terminal = _prime_call(
            environment,
            {
                "operation": "invoke",
                "request_id": "terminal-1",
                "decision_id": accepted["next_observation"]["decision_id"],
                "action_name": "terminate",
                "arguments": {"reason": "Complete conformance script."},
            },
            8,
        )["result"]
    close_report = endpoint.close().authority
    assert close_report.evidence_ref is not None
    assert (
        ArtifactRepository(authority.config.evidence_path.parent).read_bytes(close_report.evidence_ref.artifact)
        == authority.config.evidence_path.read_bytes()
    )
    return _script_result(
        catalogue=catalogue,
        first_observation=first_observation,
        stale=stale["error"],
        fresh_observation=fresh_observation,
        accepted=accepted,
        duplicate=duplicate,
        conflict=conflict["error"],
        terminal=terminal,
        host=host,
        authority=authority,
        evidence_path=authority.config.evidence_path,
    )


def _deepseek_script(tmp_path: Path) -> dict[str, Any]:
    host = _ConformanceHost()
    authority = _authority(tmp_path, host, "deepseek")
    authority.start()
    definitions = {
        definition.name: definition
        for definition in compile_world_native_tools(authority=authority, catalogue=host.catalogue)
    }
    first_observation = _native_result(definitions[WORLD_OBSERVE_TOOL_NAME], "observe-1", {})
    host.advance_decision()
    stale = _native_result(definitions["act"], "stale-1", {"value": 0})
    fresh_observation = _native_result(definitions[WORLD_OBSERVE_TOOL_NAME], "observe-2", {})
    accepted = _native_result(definitions["act"], "action-1", {"value": 1})
    duplicate = _native_result(definitions["act"], "action-1", {"value": 1})
    conflict = _native_result(definitions["act"], "action-1", {"value": 2})
    terminal_response = definitions["terminate"].handler(
        _invocation("terminal-1", "terminate"),
        {"reason": "Complete conformance script."},
    )
    assert terminal_response.disposition is NativeToolDisposition.CONCLUDE_TURN
    terminal = cast(dict[str, Any], terminal_response.result)
    close_report = authority.close()
    assert close_report.complete is True
    assert close_report.evidence_ref is not None
    assert (
        ArtifactRepository(authority.config.evidence_path.parent).read_bytes(close_report.evidence_ref.artifact)
        == authority.config.evidence_path.read_bytes()
    )
    return _script_result(
        catalogue=host.catalogue.model_dump(mode="json"),
        first_observation=first_observation,
        stale=stale["error"],
        fresh_observation=fresh_observation,
        accepted=accepted,
        duplicate=duplicate,
        conflict=conflict["error"],
        terminal=terminal,
        host=host,
        authority=authority,
        evidence_path=authority.config.evidence_path,
    )


def _native_result(definition: NativeToolDefinition, request_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
    response = definition.handler(_invocation(request_id, definition.name), arguments)
    return cast(dict[str, Any], response.result)


def _script_result(
    *,
    catalogue: dict[str, Any],
    first_observation: dict[str, Any],
    stale: dict[str, Any],
    fresh_observation: dict[str, Any],
    accepted: dict[str, Any],
    duplicate: dict[str, Any],
    conflict: dict[str, Any],
    terminal: dict[str, Any],
    host: _ConformanceHost,
    authority: ActorInvocationAuthority,
    evidence_path: Path,
) -> dict[str, Any]:
    return {
        "catalogue_sha256": actor_catalogue_sha256(WorldActorCapabilityCatalogue.model_validate(catalogue)),
        "first_observation": first_observation,
        "stale": {"code": stale["code"], "outcome": stale["outcome"]},
        "fresh_observation": fresh_observation,
        "accepted": accepted,
        "duplicate": duplicate,
        "conflict": {"code": conflict["code"], "outcome": conflict["outcome"]},
        "terminal": terminal,
        "attempts": [request.model_dump(mode="json") for request in host.attempts],
        "calls": [request.model_dump(mode="json") for request in host.calls],
        "world_action_count": authority.world_action_count,
        "terminal_latched": authority.terminal,
        "verification": host.verify(),
        "authority_evidence": _semantic_evidence(evidence_path),
    }


def _semantic_evidence(path: Path) -> list[dict[str, Any]]:
    excluded = {
        "admitted_at",
        "closed_at",
        "completed_at",
        "correlation",
        "dispatched_at",
        "observed_at",
        "occurred_at",
        "started_at",
        "transport",
    }
    return [
        {key: value for key, value in json.loads(line).items() if key not in excluded}
        for line in path.read_text(encoding="utf-8").splitlines()
    ]


def test_prime_and_deepseek_share_one_world_action_contract(tmp_path: Path) -> None:
    prime = _prime_script(tmp_path)
    deepseek = _deepseek_script(tmp_path)

    assert deepseek == prime
    assert deepseek["stale"] == {"code": "decision-stale", "outcome": "completed"}
    assert deepseek["conflict"] == {"code": "request-id-conflict", "outcome": "not-dispatched"}
    assert [attempt["request_id"] for attempt in deepseek["attempts"]] == ["stale-1", "action-1", "terminal-1"]
    assert deepseek["accepted"] == deepseek["duplicate"]
    assert deepseek["world_action_count"] == 3
    assert deepseek["terminal_latched"] is True
    assert deepseek["verification"]["valid"] is True
    deepseek_evidence = [
        json.loads(line)
        for line in (tmp_path / "deepseek" / "actor-authority.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    deepseek_action = next(
        record
        for record in deepseek_evidence
        if record["record_type"] == "request-admitted" and record["request_id"] == "action-1"
    )
    deepseek_completion = next(
        record
        for record in deepseek_evidence
        if record["record_type"] == "completion" and record["request_id"] == "action-1"
    )
    assert deepseek_action["transport"] == "deepseek-native-world"
    assert deepseek_action["correlation"] == {
        "transport_request_id": "action-1",
        "provider_session_id": "deepseek-conformance-session",
        "provider_tool_call_id": "action-1",
        "model_turn": 1,
    }
    assert deepseek_completion["task_receipt_identity"] == "receipt-1"
    assert len(deepseek_completion["task_receipt_sha256"]) == 64
    prime_evidence = [
        json.loads(line)
        for line in (tmp_path / "prime" / "actor-authority.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    prime_action = next(
        record
        for record in prime_evidence
        if record["record_type"] == "request-admitted" and record["request_id"] == "action-1"
    )
    assert prime_action["transport"] == "world-actor-endpoint"
    assert prime_action["correlation"]["transport_request_id"] == "prime-transport-5"
