# ABOUTME: Tests the complete DeepSeek-native gateway path into a real pump-station world.
# ABOUTME: Proves socket identity, authority replay, one dispatch, and separate close evidence.

from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Any

from aec_bench.adapters.deepseek_harness.native_world_tools import (
    WORLD_OBSERVE_TOOL_NAME,
    compile_world_native_tools,
)
from aec_bench.adapters.deepseek_harness.tool_gateway import (
    TOOL_GATEWAY_PROTOCOL,
    TOOL_GATEWAY_SOCKET_ENV,
    TOOL_GATEWAY_TOKEN_ENV,
    ToolGatewayEndpoint,
)
from aec_bench.contracts.world_session import (
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
)
from aec_bench.harness.world_actor import ActorInvocationAuthority, ActorInvocationAuthorityConfig
from aec_bench.worlds.stewardship.wastewater_pump_station.episode_runtime import (
    PUMP_STATION_TASK_WORLD_ID,
    PumpStationEpisodeHost,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)


def test_socket_gateway_dispatches_one_exactly_replayed_action_to_real_pump_host(tmp_path: Path) -> None:
    world_root = tmp_path / "world-run"
    host = PumpStationEpisodeHost(world_root)
    host.open(
        WorldSessionRequest(
            execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
            open_mode=WorldSessionOpenMode.START,
            session_id="gateway-session",
            task_world_id=PUMP_STATION_TASK_WORLD_ID,
            agent_tenure_id="gateway-actor",
            run_id="gateway-run",
            episode_id="gateway-episode",
            world_branch_id="gateway-branch",
        )
    )
    actor_evidence_path = tmp_path / "actor-invocation-evidence.jsonl"
    authority = ActorInvocationAuthority(
        host=host,
        config=ActorInvocationAuthorityConfig(
            authority_id="gateway-authority",
            actor_principal_id="gateway-actor",
            max_world_actions=3,
            evidence_path=actor_evidence_path,
        ),
    )
    authority.start()
    native_tools = compile_world_native_tools(authority=authority, catalogue=host.capabilities())
    gateway_evidence_path = tmp_path / "tool-gateway-evidence.jsonl"
    endpoint = ToolGatewayEndpoint(
        tools=native_tools,
        evidence_path=gateway_evidence_path,
        capability_token="gateway-private-capability",
        generation_id="gateway-generation",
    )
    endpoint.start()
    connection = endpoint.connection_environment()
    payload = {
        "protocol": TOOL_GATEWAY_PROTOCOL,
        "capability": connection[TOOL_GATEWAY_TOKEN_ENV],
        "operation": "invoke",
        "tool": "continue_operation",
        "arguments": {"reason": "Advance once through the complete local gateway path."},
        "metadata": {
            "deepseek_session_id": "pump-e2e",
            "deepseek_tool_call_id": "continue-1",
            "aec_model_turn": 1,
        },
    }
    try:
        observed = _exchange(
            connection[TOOL_GATEWAY_SOCKET_ENV],
            {
                "protocol": TOOL_GATEWAY_PROTOCOL,
                "capability": connection[TOOL_GATEWAY_TOKEN_ENV],
                "operation": "invoke",
                "tool": WORLD_OBSERVE_TOOL_NAME,
                "arguments": {},
                "metadata": {
                    "deepseek_session_id": "pump-e2e",
                    "deepseek_tool_call_id": "observe-1",
                    "aec_model_turn": 1,
                },
            },
        )
        first = _exchange(connection[TOOL_GATEWAY_SOCKET_ENV], payload)
        replay = _exchange(connection[TOOL_GATEWAY_SOCKET_ENV], payload)
    finally:
        gateway_close = endpoint.close()
        authority_close = authority.close()

    assert observed["status"] == "ok"
    assert first == replay
    assert first["status"] == "ok"
    assert first["result"]["request_id"] == "dsh:pump-e2e:continue-1"
    assert first["result"]["status"] == "applied"
    assert authority.world_action_count == 1
    assert gateway_close.quiescent is True
    assert authority_close.complete is True

    repository = PumpStationWorldRunRepository(world_root)
    assert repository.current_snapshot().sequence == 1
    assert len(repository.command_steps()) == 1

    actor_evidence = _evidence(actor_evidence_path)
    assert len([record for record in actor_evidence if record["record_type"] == "dispatch"]) == 1
    assert len([record for record in actor_evidence if record["record_type"] == "request-duplicate"]) == 1
    gateway_evidence = _evidence(gateway_evidence_path)
    invocations = [record for record in gateway_evidence if record["record_type"] == "invocation"]
    assert len(invocations) == 3
    assert {record["request_semantics"] for record in invocations} == {"handler-authority"}
    assert "gateway-private-capability" not in json.dumps([*actor_evidence, *gateway_evidence])


def _exchange(socket_path: str, payload: dict[str, Any]) -> dict[str, Any]:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.connect(socket_path)
        client.sendall(json.dumps(payload).encode("utf-8") + b"\n")
        response = json.loads(client.makefile().readline())
    if not isinstance(response, dict):
        raise TypeError("tool gateway response must be an object")
    return response


def _evidence(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
