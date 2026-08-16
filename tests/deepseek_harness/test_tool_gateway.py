# ABOUTME: Tests the authenticated DeepSeek gateway to exact AEC-owned native tools.
# ABOUTME: Proves trusted identity, explicit schemas, cancellation, dispositions, and bounded close evidence.

from __future__ import annotations

import json
import socket
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import JsonValue

from aec_bench.adapters.deepseek_harness.tool_gateway import (
    TOOL_GATEWAY_PROTOCOL,
    NativeToolDefinition,
    NativeToolDisposition,
    NativeToolInvocation,
    NativeToolResponse,
    ToolGatewayEndpoint,
)


def test_endpoint_uses_explicit_schema_hidden_identity_and_exact_replay(tmp_path: Path) -> None:
    calls: list[tuple[str, str]] = []

    def read_workspace_file(
        invocation: NativeToolInvocation,
        arguments: Mapping[str, JsonValue],
    ) -> NativeToolResponse:
        path = str(arguments["path"])
        calls.append((invocation.request_id, path))
        return NativeToolResponse(
            result={"status": "ok", "path": path, "content": "released evidence"},
            disposition=NativeToolDisposition.CONTINUE,
        )

    evidence_path = tmp_path / "lifecycle-tool-evidence.jsonl"
    endpoint = ToolGatewayEndpoint(
        tools=(
            _definition(
                "read_workspace_file",
                read_workspace_file,
                properties={"path": {"type": "string"}},
                required=("path",),
            ),
        ),
        evidence_path=evidence_path,
        capability_token="private-capability",
        generation_id="generation-1",
    )
    endpoint.start()
    try:
        payload = _request(
            endpoint, tool_call_id="tool-1", tool_name="read_workspace_file", arguments={"path": "inbox/evidence.md"}
        )
        first = _exchange(endpoint, payload)
        second = _exchange(endpoint, payload)
        manifest = json.loads(endpoint.connection_environment()["DSH_TOOLS"])
    finally:
        close_report = endpoint.close()

    assert first == {
        "protocol": TOOL_GATEWAY_PROTOCOL,
        "status": "ok",
        "result": {"status": "ok", "path": "inbox/evidence.md", "content": "released evidence"},
        "disposition": "continue",
    }
    assert second == first
    assert calls == [("dsh:root:tool-1", "inbox/evidence.md")]
    assert "request_id" not in payload
    assert manifest == [
        {
            "name": "read_workspace_file",
            "description": "read workspace file",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
                "additionalProperties": False,
            },
        }
    ]
    assert close_report.quiescent is True
    evidence = _evidence(evidence_path)
    invocation = next(item for item in evidence if item["record_type"] == "invocation")
    duplicate = next(item for item in evidence if item["record_type"] == "duplicate")
    assert invocation["request_id"] == "dsh:root:tool-1"
    assert invocation["generation_id"] == "generation-1"
    assert invocation["outcome"] == "completed"
    assert invocation["disposition"] == "continue"
    assert invocation["result_sha256"] is not None
    assert duplicate["duplicate_of"] == "dsh:root:tool-1"
    assert all("private-capability" not in json.dumps(item) for item in evidence)


def test_endpoint_rejects_unauthorised_unknown_invalid_and_conflicting_requests(tmp_path: Path) -> None:
    def submit_checkpoint(
        _invocation: NativeToolInvocation,
        arguments: Mapping[str, JsonValue],
    ) -> NativeToolResponse:
        return NativeToolResponse(
            result={"status": "complete", "checkpoint_id": arguments["checkpoint_id"]},
            disposition=NativeToolDisposition.CONCLUDE_TURN,
        )

    endpoint = ToolGatewayEndpoint(
        tools=(
            _definition(
                "submit_checkpoint",
                submit_checkpoint,
                properties={"checkpoint_id": {"type": "string"}},
                required=("checkpoint_id",),
            ),
        ),
        evidence_path=tmp_path / "tool-gateway-evidence.jsonl",
        capability_token="private-capability",
    )
    endpoint.start()
    try:
        unauthorized = _request(
            endpoint,
            tool_call_id="unauthorized",
            tool_name="submit_checkpoint",
            arguments={"checkpoint_id": "review"},
        )
        unauthorized["capability"] = "wrong"
        assert _exchange(endpoint, unauthorized)["error"]["code"] == "unauthorized"

        unknown = _request(
            endpoint,
            tool_call_id="unknown",
            tool_name="read_workspace_file",
            arguments={"path": "instruction.md"},
        )
        assert _exchange(endpoint, unknown)["error"]["code"] == "tool_not_allowed"

        invalid = _request(
            endpoint,
            tool_call_id="invalid",
            tool_name="submit_checkpoint",
            arguments={"checkpoint_id": 3},
        )
        assert _exchange(endpoint, invalid)["error"]["code"] == "invalid_arguments"

        model_chosen_identity = _request(
            endpoint,
            tool_call_id="model-chosen-identity",
            tool_name="submit_checkpoint",
            arguments={"checkpoint_id": "review", "request_id": "model-choice"},
        )
        assert _exchange(endpoint, model_chosen_identity)["error"]["code"] == "invalid_arguments"

        accepted = _request(
            endpoint,
            tool_call_id="conflict",
            tool_name="submit_checkpoint",
            arguments={"checkpoint_id": "review"},
        )
        assert _exchange(endpoint, accepted)["disposition"] == "conclude-turn"
        conflicting = {**accepted, "arguments": {"checkpoint_id": "decision"}}
        assert _exchange(endpoint, conflicting)["error"]["code"] == "request_id_conflict"
    finally:
        endpoint.close()


def test_cancellation_reaches_a_cooperative_handler_and_pre_dispatch_cancel_is_retained(tmp_path: Path) -> None:
    started = threading.Event()

    def wait_for_cancel(
        invocation: NativeToolInvocation,
        _arguments: Mapping[str, JsonValue],
    ) -> NativeToolResponse:
        started.set()
        assert invocation.cancellation.wait(2)
        return NativeToolResponse(result={"status": "cancelled"})

    evidence_path = tmp_path / "tool-gateway-evidence.jsonl"
    endpoint = ToolGatewayEndpoint(
        tools=(_definition("wait_for_cancel", wait_for_cancel),),
        evidence_path=evidence_path,
        capability_token="private-capability",
    )
    endpoint.start()
    response: dict[str, Any] = {}
    invocation = _request(endpoint, tool_call_id="active", tool_name="wait_for_cancel", arguments={})
    thread = threading.Thread(target=lambda: response.update(_exchange(endpoint, invocation)))
    thread.start()
    assert started.wait(2)

    cancellation = _exchange(endpoint, _cancel_request(endpoint, tool_call_id="active"))
    thread.join(timeout=2)
    assert not thread.is_alive()

    early_cancel = _exchange(endpoint, _cancel_request(endpoint, tool_call_id="early"))
    cancelled_request = _request(endpoint, tool_call_id="early", tool_name="wait_for_cancel", arguments={})
    rejected = _exchange(endpoint, cancelled_request)
    close_report = endpoint.close()

    assert cancellation["result"]["outcome"] == "unknown"
    assert response["result"] == {"status": "cancelled"}
    assert early_cancel["result"]["outcome"] == "not-dispatched"
    assert rejected["error"]["code"] == "request_cancelled"
    assert close_report.quiescent is True
    evidence = _evidence(evidence_path)
    completed = next(
        item for item in evidence if item.get("request_id") == "dsh:root:active" and item["record_type"] == "invocation"
    )
    not_dispatched = next(
        item for item in evidence if item.get("request_id") == "dsh:root:early" and item["record_type"] == "invocation"
    )
    assert completed["cancellation_requested_at"] is not None
    assert completed["outcome"] == "completed"
    assert not_dispatched["outcome"] == "not-dispatched"


def test_close_reports_unsettled_work_and_late_result_is_stale(tmp_path: Path) -> None:
    started = threading.Event()
    release = threading.Event()

    def hang(
        _invocation: NativeToolInvocation,
        _arguments: Mapping[str, JsonValue],
    ) -> NativeToolResponse:
        started.set()
        release.wait(2)
        return NativeToolResponse(result={"status": "late"})

    evidence_path = tmp_path / "tool-gateway-evidence.jsonl"
    endpoint = ToolGatewayEndpoint(
        tools=(_definition("hang", hang),),
        evidence_path=evidence_path,
        capability_token="private-capability",
        close_timeout_seconds=0.01,
    )
    endpoint.start()
    response: dict[str, Any] = {}
    thread = threading.Thread(
        target=lambda: response.update(
            _exchange(endpoint, _request(endpoint, tool_call_id="hanging", tool_name="hang", arguments={}))
        )
    )
    thread.start()
    assert started.wait(2)

    close_report = endpoint.close()
    assert close_report.quiescent is False
    assert close_report.unsettled_request_ids == ("dsh:root:hanging",)
    assert close_report.unknown_outcome_request_ids == ("dsh:root:hanging",)

    release.set()
    thread.join(timeout=2)
    assert not thread.is_alive()
    assert response["error"]["code"] == "generation_finalized"
    evidence = _evidence(evidence_path)
    assert not any(item["record_type"] == "invocation" for item in evidence)
    close_evidence = next(item for item in evidence if item["record_type"] == "close")
    assert close_evidence["late_results_after_close_are_ignored"] is True


def _definition(
    name: str,
    handler: Any,
    *,
    properties: dict[str, Any] | None = None,
    required: tuple[str, ...] = (),
) -> NativeToolDefinition:
    return NativeToolDefinition(
        name=name,
        description=name.replace("_", " "),
        parameters_schema={
            "type": "object",
            "properties": properties or {},
            "required": list(required),
            "additionalProperties": False,
        },
        handler=handler,
    )


def _request(
    endpoint: ToolGatewayEndpoint,
    *,
    tool_call_id: str,
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    connection = endpoint.connection_environment()
    return {
        "protocol": TOOL_GATEWAY_PROTOCOL,
        "capability": connection["DSH_TOOLS_TOKEN"],
        "operation": "invoke",
        "tool": tool_name,
        "arguments": arguments,
        "metadata": {
            "deepseek_session_id": "root",
            "deepseek_tool_call_id": tool_call_id,
            "aec_model_turn": 1,
        },
    }


def _cancel_request(endpoint: ToolGatewayEndpoint, *, tool_call_id: str) -> dict[str, Any]:
    connection = endpoint.connection_environment()
    return {
        "protocol": TOOL_GATEWAY_PROTOCOL,
        "capability": connection["DSH_TOOLS_TOKEN"],
        "operation": "cancel",
        "metadata": {
            "deepseek_session_id": "root",
            "deepseek_tool_call_id": tool_call_id,
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


def _evidence(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
