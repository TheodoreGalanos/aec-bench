# ABOUTME: Tests the authenticated DeepSeek gateway to exact AEC-owned native tools.
# ABOUTME: Proves exact allowlists, bounded requests, idempotency, and secret-free evidence.

from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Any

from aec_bench.adapters.deepseek_harness.tool_gateway import (
    TOOL_GATEWAY_PROTOCOL,
    ToolGatewayEndpoint,
)


def test_endpoint_executes_one_allowed_tool_and_replays_the_identical_request(tmp_path: Path) -> None:
    calls: list[dict[str, str]] = []

    def read_workspace_file(path: str) -> str:
        calls.append({"path": path})
        return json.dumps({"status": "ok", "path": path, "content": "released evidence"})

    evidence_path = tmp_path / "lifecycle-tool-evidence.jsonl"
    endpoint = ToolGatewayEndpoint(
        tools={"read_workspace_file": read_workspace_file},
        evidence_path=evidence_path,
        capability_token="private-capability",
    )
    endpoint.start()
    try:
        payload = _request(
            endpoint,
            request_id="dsh:root:tool-1",
            tool_name="read_workspace_file",
            arguments={"path": "inbox/checkpoint/evidence.md"},
        )
        first = _exchange(endpoint, payload)
        second = _exchange(endpoint, payload)
    finally:
        endpoint.close()

    assert first == {
        "protocol": TOOL_GATEWAY_PROTOCOL,
        "status": "ok",
        "result": {
            "status": "ok",
            "path": "inbox/checkpoint/evidence.md",
            "content": "released evidence",
        },
    }
    assert second == first
    assert calls == [{"path": "inbox/checkpoint/evidence.md"}]
    evidence = [json.loads(line) for line in evidence_path.read_text(encoding="utf-8").splitlines()]
    assert [item["idempotent_replay"] for item in evidence] == [False, True]
    assert all("private-capability" not in json.dumps(item) for item in evidence)


def test_endpoint_rejects_unauthorised_unknown_invalid_and_conflicting_requests(tmp_path: Path) -> None:
    def submit_checkpoint(checkpoint_id: str) -> str:
        return json.dumps({"status": "complete", "checkpoint_id": checkpoint_id})

    endpoint = ToolGatewayEndpoint(
        tools={"submit_checkpoint": submit_checkpoint},
        evidence_path=tmp_path / "tool-gateway-evidence.jsonl",
        capability_token="private-capability",
    )
    endpoint.start()
    try:
        unauthorized = _request(
            endpoint,
            request_id="request-unauthorized",
            tool_name="submit_checkpoint",
            arguments={"checkpoint_id": "review"},
        )
        unauthorized["capability"] = "wrong"
        assert _exchange(endpoint, unauthorized)["error"]["code"] == "unauthorized"

        unknown = _request(
            endpoint,
            request_id="request-unknown",
            tool_name="read_workspace_file",
            arguments={"path": "instruction.md"},
        )
        assert _exchange(endpoint, unknown)["error"]["code"] == "tool_not_allowed"

        invalid = _request(
            endpoint,
            request_id="request-invalid",
            tool_name="submit_checkpoint",
            arguments={"checkpoint_id": 3},
        )
        assert _exchange(endpoint, invalid)["error"]["code"] == "invalid_arguments"

        accepted = _request(
            endpoint,
            request_id="request-conflict",
            tool_name="submit_checkpoint",
            arguments={"checkpoint_id": "review"},
        )
        assert _exchange(endpoint, accepted)["status"] == "ok"
        conflicting = {**accepted, "arguments": {"checkpoint_id": "decision"}}
        assert _exchange(endpoint, conflicting)["error"]["code"] == "request_id_conflict"
    finally:
        endpoint.close()


def test_endpoint_derives_array_and_integer_schema_from_a_world_tool(tmp_path: Path) -> None:
    calls: list[tuple[tuple[str, ...], int]] = []

    def request_duty_assignment(ordered_pump_ids: tuple[str, ...], limit: int = 3) -> str:
        calls.append((ordered_pump_ids, limit))
        return json.dumps({"status": "accepted", "ordered_pump_ids": ordered_pump_ids, "limit": limit})

    endpoint = ToolGatewayEndpoint(
        tools={"request_duty_assignment": request_duty_assignment},
        evidence_path=tmp_path / "tool-gateway-evidence.jsonl",
        capability_token="private-capability",
    )
    endpoint.start()
    try:
        manifest = json.loads(endpoint.connection_environment()["DSH_TOOLS"])
        parameters = manifest[0]["parameters"]
        ordered_ids = parameters["properties"]["ordered_pump_ids"]
        assert ordered_ids["type"] == "array"
        assert ordered_ids["items"] == {"type": "string"}
        assert parameters["properties"]["limit"]["default"] == 3
        assert parameters["properties"]["limit"]["type"] == "integer"
        assert parameters["required"] == ["ordered_pump_ids"]
        response = _exchange(
            endpoint,
            _request(
                endpoint,
                request_id="world-action-1",
                tool_name="request_duty_assignment",
                arguments={"ordered_pump_ids": ["P-101", "P-102"], "limit": 2},
            ),
        )
    finally:
        endpoint.close()

    assert response["status"] == "ok"
    assert calls == [(("P-101", "P-102"), 2)]


def _request(
    endpoint: ToolGatewayEndpoint,
    *,
    request_id: str,
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    connection = endpoint.connection_environment()
    return {
        "protocol": TOOL_GATEWAY_PROTOCOL,
        "capability": connection["DSH_TOOLS_TOKEN"],
        "request_id": request_id,
        "tool": tool_name,
        "arguments": arguments,
        "metadata": {
            "deepseek_session_id": "root",
            "deepseek_tool_call_id": request_id,
            "aec_model_turn": 1,
        },
    }


def _exchange(endpoint: ToolGatewayEndpoint, payload: dict[str, Any]) -> dict[str, Any]:
    socket_path = endpoint.connection_environment()["DSH_TOOLS_SOCKET"]
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.connect(socket_path)
        client.sendall(json.dumps(payload).encode("utf-8") + b"\n")
        response = json.loads(client.makefile().readline())
    assert isinstance(response, dict)
    return response
