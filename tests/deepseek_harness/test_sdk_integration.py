# ABOUTME: Runs the pinned DeepSeek Harness wheel against a local keyless model endpoint.
# ABOUTME: Proves the AEC profile, worker process, SDK protocol, and event reduction compose.

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, ClassVar

import pytest

from aec_bench.adapters.base import AdapterRequest, SerializedAdapterExecution
from aec_bench.adapters.deepseek_harness import DeepSeekHarnessAdapter
from aec_bench.adapters.deepseek_harness.config import DeepSeekHarnessSettings
from aec_bench.adapters.deepseek_harness.tool_gateway import (
    NativeToolDisposition,
    json_native_tool_definition,
)
from aec_bench.contracts.agent_output import AgentOutputStatus
from aec_bench.contracts.task_definition import ToolSpec
from aec_bench.harness.deepseek_harness_driver import DeepSeekHarnessExecutionDriver
from aec_bench.harness.execution_entrypoint import default_execution_driver_registry, run_execution_bundle
from aec_bench.harness.execution_payload import (
    AdapterRequestPayload,
    ExecutionBundle,
    build_entrypoint_execution_bundle,
    write_execution_bundle,
)


class _KeylessDeepSeekHandler(BaseHTTPRequestHandler):
    requests: ClassVar[list[dict[str, Any]]] = []
    mode: ClassVar[str] = "text"

    def do_POST(self) -> None:
        content_length = int(self.headers.get("content-length", "0"))
        body = json.loads(self.rfile.read(content_length).decode("utf-8"))
        self.requests.append(
            {
                "path": self.path,
                "authorization": self.headers.get("authorization"),
                "body": body,
            }
        )
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.end_headers()
        messages = body["messages"]
        request_number = len(self.requests)
        if self.mode == "max-tokens":
            chunks = _text_chunks("cut", finish_reason="length", completion_tokens=3)
        elif self.mode == "write" and messages[-1]["role"] != "tool":
            chunks = _tool_call_chunks(
                "write-output",
                "write",
                {"file_path": "output.md", "content": "# DeepSeek artifact\n\nCreated through the write tool.\n"},
            )
        elif self.mode == "commit" and request_number == 1:
            chunks = _tool_call_chunks("write-output", "write", _valid_output_write())
        elif self.mode == "commit" and request_number == 2:
            chunks = _tool_call_chunks("commit-output", "aec_commit_output", {})
        elif self.mode in {"repair-commit", "reject-stop"} and request_number == 1:
            chunks = _tool_call_chunks(
                "write-incomplete-output",
                "write",
                {"file_path": "output.md", "content": "Incomplete candidate\n"},
            )
        elif self.mode in {"repair-commit", "reject-stop"} and request_number == 2:
            chunks = _tool_call_chunks("commit-incomplete-output", "aec_commit_output", {})
        elif self.mode == "repair-commit" and request_number == 3:
            chunks = _tool_call_chunks("repair-output", "write", _valid_output_write())
        elif self.mode == "repair-commit" and request_number == 4:
            chunks = _tool_call_chunks("commit-repaired-output", "aec_commit_output", {})
        elif self.mode == "lifecycle" and request_number == 1:
            chunks = _tool_call_chunks(
                "submit-checkpoint",
                "submit_checkpoint",
                {"checkpoint_id": "closeout_review"},
            )
        else:
            chunks = _text_chunks("AEC-Bench DeepSeek SDK composition is active.")
        for chunk in chunks:
            self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")

    def log_message(self, _format: str, *_args: object) -> None:
        return


def _text_chunks(
    text: str,
    *,
    finish_reason: str = "stop",
    completion_tokens: int = 9,
) -> tuple[dict[str, object], ...]:
    return (
        {"choices": [{"delta": {"role": "assistant", "content": None, "reasoning_content": ""}}]},
        {"choices": [{"delta": {"content": text}}]},
        {
            "choices": [{"delta": {"content": ""}, "finish_reason": finish_reason}],
            "usage": {"prompt_tokens": 7, "completion_tokens": completion_tokens},
        },
    )


def _tool_call_chunks(call_id: str, name: str, arguments: dict[str, object]) -> tuple[dict[str, object], ...]:
    return (
        {"choices": [{"delta": {"role": "assistant", "content": None, "reasoning_content": ""}}]},
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": call_id,
                                "type": "function",
                                "function": {"name": name, "arguments": json.dumps(arguments)},
                            }
                        ]
                    }
                }
            ]
        },
        {
            "choices": [{"delta": {"content": ""}, "finish_reason": "tool_calls"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 4},
        },
    )


def _valid_output_write() -> dict[str, object]:
    return {
        "file_path": "output.md",
        "content": 'Report\n```json\n{"findings": [], "summary": {}}\n```\n',
    }


def _commit_configuration() -> dict[str, object]:
    return {
        "timeout_sec": 30,
        "output_completion_commit": True,
        "output_completion_contract": {
            "schema_version": "aecbench.output-completion-contract.v1",
            "output_path": "output.md",
            "format": "markdown_final_fenced_json",
            "required_top_level_keys": ["findings", "summary"],
            "require_single_final_json_block": True,
        },
    }


def _start_server(
    monkeypatch: pytest.MonkeyPatch,
    *,
    mode: str,
    provider: str = "azure",
) -> tuple[ThreadingHTTPServer, threading.Thread]:
    _KeylessDeepSeekHandler.requests = []
    _KeylessDeepSeekHandler.mode = mode
    server = ThreadingHTTPServer(("127.0.0.1", 0), _KeylessDeepSeekHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    endpoint = f"http://127.0.0.1:{server.server_address[1]}"
    if provider == "azure":
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", endpoint)
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "keyless-test-token")
    elif provider == "deepseek":
        monkeypatch.setenv("DEEPSEEK_BASE_URL", endpoint)
        monkeypatch.setenv("DEEPSEEK_API_KEY", "keyless-test-token")
    else:
        raise ValueError(f"unsupported keyless test provider: {provider}")
    return server, thread


def _azure_settings(model: str = "deepseek-v4-flash") -> DeepSeekHarnessSettings:
    return DeepSeekHarnessSettings.from_execution_payload(
        model_name=f"azure:{model}",
        payload={"provider": "azure"},
    )


def _deepseek_settings(model: str = "deepseek-v4-flash") -> DeepSeekHarnessSettings:
    return DeepSeekHarnessSettings.from_execution_payload(
        model_name=f"deepseek:{model}",
        payload={"provider": "deepseek"},
    )


def test_real_sdk_composition_reaches_keyless_model_endpoint(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pytest.importorskip("deepseek_harness")
    server, thread = _start_server(monkeypatch, mode="text")
    settings = _azure_settings()

    try:
        result = DeepSeekHarnessAdapter(settings=settings, workspace=tmp_path).execute(
            AdapterRequest(
                instruction="Reply with a short confirmation and do not call tools.",
                system_prompt="You are the environment-selected AEC test agent.",
                configuration={"timeout_sec": 30},
                output_path="output.md",
                output_format="markdown",
            )
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result.agent_output.status is AgentOutputStatus.COMPLETED
    assert result.raw_output_text == "AEC-Bench DeepSeek SDK composition is active."
    assert result.configuration_record["sdk_version"] == "0.1.0rc6"
    assert result.configuration_record["runtime_distribution_version"] == "0.1.0rc6"
    assert result.configuration_record["runtime_reported_version"] is None
    assert result.configuration_record["plugin_free_baseline"] is True
    assert result.usage_model_calls == 1
    assert result.usage_input_tokens == 7
    assert result.usage_output_tokens == 9
    assert len(_KeylessDeepSeekHandler.requests) == 1
    assert _KeylessDeepSeekHandler.requests[0]["path"] == "/openai/v1/chat/completions"
    assert _KeylessDeepSeekHandler.requests[0]["authorization"] == "Bearer keyless-test-token"
    assert _KeylessDeepSeekHandler.requests[0]["body"]["model"] == "deepseek-v4-flash"
    assert "reasoning_effort" not in _KeylessDeepSeekHandler.requests[0]["body"]
    assert "thinking" not in _KeylessDeepSeekHandler.requests[0]["body"]
    system_messages = [
        message["content"]
        for message in _KeylessDeepSeekHandler.requests[0]["body"]["messages"]
        if message["role"] == "system"
    ]
    assert any("environment-selected AEC test agent" in content for content in system_messages)
    assert Path(result.configuration_record["system_prompt_path"]).read_text(encoding="utf-8") == (
        "You are the environment-selected AEC test agent."
    )
    manifest_path = Path(result.configuration_record["manifest_path"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["model"]["harness_route"] == "azure"


def test_real_sdk_composition_uses_the_selected_deepseek_provider(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pytest.importorskip("deepseek_harness")
    server, thread = _start_server(monkeypatch, mode="text", provider="deepseek")

    try:
        result = DeepSeekHarnessAdapter(settings=_deepseek_settings(), workspace=tmp_path).execute(
            AdapterRequest(
                instruction="Reply with a short confirmation and do not call tools.",
                configuration={"timeout_sec": 30},
                output_path="output.md",
                output_format="markdown",
            )
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result.agent_output.status is AgentOutputStatus.COMPLETED
    assert len(_KeylessDeepSeekHandler.requests) == 1
    assert _KeylessDeepSeekHandler.requests[0]["path"] == "/chat/completions"
    assert _KeylessDeepSeekHandler.requests[0]["authorization"] == "Bearer keyless-test-token"
    manifest_path = Path(result.configuration_record["manifest_path"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["model"] == {
        "provider": "deepseek",
        "harness_route": "deepseek-official",
        "requested": "deepseek:deepseek-v4-flash",
        "resolved": "deepseek-v4-flash",
    }


def test_real_sdk_enforces_max_tokens_and_maps_truncation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pytest.importorskip("deepseek_harness")
    server, thread = _start_server(monkeypatch, mode="max-tokens")
    settings = _azure_settings()

    try:
        result = DeepSeekHarnessAdapter(settings=settings, workspace=tmp_path).execute(
            AdapterRequest(
                instruction="Produce more than three output tokens.",
                configuration={"timeout_sec": 30, "max_tokens": 3},
                output_path="output.md",
                output_format="markdown",
            )
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result.agent_output.status is AgentOutputStatus.PARTIAL
    assert result.failure_kind is not None
    assert result.failure_kind.value == "token_budget_reached"
    assert result.stop_reason is not None
    assert result.stop_reason.value == "token_budget"
    assert result.raw_output_text == "cut"
    assert result.usage_output_tokens == 3
    assert result.maximum_output_tokens_in_one_call == 3
    assert result.configuration_record["timeout_sec"] == 30
    assert result.configuration_record["max_tokens"] == 3
    assert len(_KeylessDeepSeekHandler.requests) == 1
    assert _KeylessDeepSeekHandler.requests[0]["body"]["max_completion_tokens"] == 3
    root_events_path = Path(result.configuration_record["root_events_path"])
    root_events = [json.loads(line) for line in root_events_path.read_text(encoding="utf-8").splitlines()]
    request_header = next(event for event in root_events if event["payload"]["event"]["type"] == "request/header")
    assert request_header["payload"]["event"]["data"]["header"]["config"]["maxTokens"] == 3


def test_real_sdk_composition_writes_the_requested_workspace_artifact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pytest.importorskip("deepseek_harness")
    server, thread = _start_server(monkeypatch, mode="write")
    driver = DeepSeekHarnessExecutionDriver(workspace_dir=tmp_path)
    bundle = ExecutionBundle(
        execution=SerializedAdapterExecution(
            adapter_kind="deepseek_harness",
            adapter_name="deepseek-keyless-integration",
            resolved_model="azure:deepseek-v4-flash",
            payload={"provider": "azure"},
        ),
        request=AdapterRequestPayload(
            instruction="Write the requested output file, then confirm completion.",
            system_prompt=None,
            tools=[],
            configuration={"timeout_sec": 30},
            output_path="output.md",
            output_format="markdown",
        ),
    )

    try:
        result = driver.execute(bundle)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result.agent_output.status is AgentOutputStatus.COMPLETED
    assert result.raw_output_text is None
    assert (tmp_path / "output.md").read_text(encoding="utf-8") == (
        "# DeepSeek artifact\n\nCreated through the write tool.\n"
    )
    assert result.configuration_record["tool_calls_started"] == 1
    assert result.configuration_record["tool_calls_completed"] == 1
    assert result.turns_used == 2
    assert result.usage_model_calls == 2
    assert result.usage_input_tokens == 12
    assert result.usage_output_tokens == 13
    assert len(_KeylessDeepSeekHandler.requests) == 2
    advertised_tools = {tool["function"]["name"] for tool in _KeylessDeepSeekHandler.requests[0]["body"]["tools"]}
    assert {"bash", "read", "write", "edit"}.issubset(advertised_tools)
    assert "aec_commit_output" not in advertised_tools
    root_events_path = Path(result.configuration_record["root_events_path"])
    root_events = [json.loads(line) for line in root_events_path.read_text(encoding="utf-8").splitlines()]
    assert root_events
    assert all(event["notification_method"] == "session.event" for event in root_events)
    assert all(event["payload"]["sessionId"] == result.configuration_record["root_session_id"] for event in root_events)

    sessions_path = Path(result.configuration_record["sessions_path"])
    assert list(sessions_path.rglob("*.jsonl"))
    manifest_path = Path(result.configuration_record["manifest_path"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert (
        result.configuration_record["evidence_manifest_sha256"]
        == hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    )
    assert result.configuration_record["optional_plugins"] == []
    composition = json.loads(Path(result.configuration_record["composition_path"]).read_text(encoding="utf-8"))
    assert composition["environment"]["provider_endpoint"].startswith("http://127.0.0.1:")
    evidence_root = manifest_path.parent
    roles = {artifact["role"] for artifact in manifest["artifacts"]}
    assert {
        "all_session_notifications",
        "composition_identity",
        "cordis_input",
        "deepseek_session_jsonl",
        "redaction_audit",
        "root_session_events",
        "runtime_identity",
        "system_prompt",
    }.issubset(roles)
    for artifact in manifest["artifacts"]:
        evidence_path = evidence_root / artifact["path"]
        assert hashlib.sha256(evidence_path.read_bytes()).hexdigest() == artifact["sha256"]
    exported_evidence = "".join(
        path.read_text(encoding="utf-8", errors="replace") for path in evidence_root.rglob("*") if path.is_file()
    )
    assert "keyless-test-token" not in exported_evidence


def test_real_sdk_lifecycle_composition_exposes_only_the_gateway_tools(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pytest.importorskip("deepseek_harness")
    server, thread = _start_server(monkeypatch, mode="lifecycle")
    calls: list[str] = []

    def submit_checkpoint(checkpoint_id: str) -> str:
        calls.append(checkpoint_id)
        return json.dumps({"status": "complete"})

    try:
        result = DeepSeekHarnessAdapter(
            settings=_azure_settings(),
            workspace=tmp_path,
            native_tools=(
                json_native_tool_definition(
                    name="submit_checkpoint",
                    description="Submit checkpoint",
                    parameters_schema={
                        "type": "object",
                        "properties": {"checkpoint_id": {"type": "string"}},
                        "required": ["checkpoint_id"],
                        "additionalProperties": False,
                    },
                    function=submit_checkpoint,
                    disposition=lambda result: (
                        NativeToolDisposition.CONCLUDE_TURN
                        if isinstance(result, dict) and result.get("status") == "complete"
                        else NativeToolDisposition.CONTINUE
                    ),
                ),
            ),
        ).execute(
            AdapterRequest(
                instruction="Submit the completed lifecycle checkpoint.",
                tools=[
                    ToolSpec(
                        name="submit_checkpoint",
                        source="builtin",
                        description="Submit checkpoint",
                    )
                ],
                configuration={"timeout_sec": 30, "max_tokens": 512},
                output_path="output.md",
                output_format="markdown",
            )
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result.agent_output.status is AgentOutputStatus.PARTIAL
    assert calls == ["closeout_review"]
    assert len(_KeylessDeepSeekHandler.requests) == 1
    advertised_tools = {tool["function"]["name"] for tool in _KeylessDeepSeekHandler.requests[0]["body"]["tools"]}
    assert advertised_tools == {"submit_checkpoint"}
    cordis = Path(result.configuration_record["cordis_path"]).read_text(encoding="utf-8")
    assert "@deepseek-ai/dsh-tool-fs" not in cordis
    assert "@deepseek-ai/dsh-tool-bash-persistent" not in cordis


def test_real_sdk_runs_through_the_serialized_harbor_entrypoint(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pytest.importorskip("deepseek_harness")
    server, thread = _start_server(monkeypatch, mode="write")
    bundle = build_entrypoint_execution_bundle(
        instruction="Write the requested output file, then confirm completion.",
        adapter_name="entrypoint",
        model_name="azure:deepseek-chat",
        harbor_kwargs={"adapter": "deepseek_harness", "timeout_sec": 30},
    )
    bundle_path = write_execution_bundle(path=tmp_path / "execution-bundle.json", bundle=bundle)
    result_path = tmp_path / "agent-result.json"

    try:
        run_execution_bundle(
            bundle_path=bundle_path,
            result_path=result_path,
            registry=default_execution_driver_registry(workspace_dir=tmp_path),
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert (tmp_path / "output.md").read_text(encoding="utf-8") == (
        "# DeepSeek artifact\n\nCreated through the write tool.\n"
    )
    assert payload["agent_output"]["status"] == "completed"
    assert payload["adapter_name"] == "entrypoint"
    assert payload["runtime_execution_attestation"]["adapter_kind"] == "deepseek_harness"
    assert (
        payload["runtime_execution_attestation"]["evidence_manifest_sha256"]
        == (payload["configuration_record"]["evidence_manifest_sha256"])
    )


def test_repeated_real_trials_retire_transient_state_and_keep_treatments_separate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pytest.importorskip("deepseek_harness")
    socket_directories_before = set(Path(tempfile.gettempdir()).glob("aec-dsh-commit-*"))
    settings = DeepSeekHarnessSettings(provider="azure", model="deepseek-chat")

    commit_server, commit_thread = _start_server(monkeypatch, mode="commit")
    try:
        committed = DeepSeekHarnessAdapter(settings=settings, workspace=tmp_path).execute(
            AdapterRequest(
                instruction="Write and commit the requested artifact.",
                configuration=_commit_configuration(),
                output_path="output.md",
                output_format="markdown",
            )
        )
    finally:
        commit_server.shutdown()
        commit_server.server_close()
        commit_thread.join(timeout=5)

    baseline_server, baseline_thread = _start_server(monkeypatch, mode="write")
    try:
        baseline = DeepSeekHarnessAdapter(settings=settings, workspace=tmp_path).execute(
            AdapterRequest(
                instruction="Write the requested artifact without an explicit commit.",
                configuration={"timeout_sec": 30},
                output_path="output.md",
                output_format="markdown",
            )
        )
    finally:
        baseline_server.shutdown()
        baseline_server.server_close()
        baseline_thread.join(timeout=5)

    committed_root = Path(committed.configuration_record["manifest_path"]).parent
    baseline_root = Path(baseline.configuration_record["manifest_path"]).parent
    assert committed_root != baseline_root
    assert committed.configuration_record["output_commit_mode"] == "required"
    assert baseline.configuration_record["output_commit_mode"] == "disabled"
    assert committed.configuration_record["optional_plugins"]
    assert baseline.configuration_record["optional_plugins"] == []
    assert "aec-output-commit" in (committed_root / "cordis.input.yml").read_text(encoding="utf-8")
    assert "aec-output-commit" not in (baseline_root / "cordis.input.yml").read_text(encoding="utf-8")
    for trial_root in (committed_root, baseline_root):
        assert not (trial_root / "runtime-home").exists()
        assert not (trial_root / "tmp").exists()
    assert set(Path(tempfile.gettempdir()).glob("aec-dsh-commit-*")) == socket_directories_before
    assert not any(thread.name == "aec-output-commit" for thread in threading.enumerate())
    assert "AEC_BENCH_COMMIT_SOCKET" not in os.environ
    assert "AEC_BENCH_COMMIT_TOKEN" not in os.environ


def test_real_sdk_output_commit_plugin_accepts_and_concludes_the_turn(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pytest.importorskip("deepseek_harness")
    server, thread = _start_server(monkeypatch, mode="commit")
    settings = _azure_settings()

    try:
        result = DeepSeekHarnessAdapter(settings=settings, workspace=tmp_path).execute(
            AdapterRequest(
                instruction="Write the requested output and commit it after review.",
                configuration=_commit_configuration(),
                output_path="output.md",
                output_format="markdown",
            )
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result.agent_output.status is AgentOutputStatus.COMPLETED
    assert result.completion_reason is not None
    assert result.completion_reason.value == "output_contract_committed"
    assert result.completion_commit is not None
    assert result.completion_commit.commit_turn == 2
    assert result.turns_used == 2
    assert len(_KeylessDeepSeekHandler.requests) == 2
    advertised_tools = {tool["function"]["name"] for tool in _KeylessDeepSeekHandler.requests[0]["body"]["tools"]}
    assert "aec_commit_output" in advertised_tools
    assert result.configuration_record["output_commit_mode"] == "required"
    assert result.configuration_record["plugin_free_baseline"] is False
    manifest_plugins = [
        {
            "artifact_path": "plugins/output-commit/index.js",
            "plugin_id": "@aec-bench/dsh-output-commit",
            "role": "output_commit",
            "version": "0.1.0",
        }
    ]
    assert result.configuration_record["optional_plugins"] == manifest_plugins
    manifest_path = Path(result.configuration_record["manifest_path"])
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["plugins"] == manifest_plugins
    commit_evidence = Path(result.configuration_record["commit_evidence_path"]).read_text(encoding="utf-8")
    assert "keyless-test-token" not in commit_evidence


def test_real_sdk_rejected_commit_can_be_repaired_and_committed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pytest.importorskip("deepseek_harness")
    server, thread = _start_server(monkeypatch, mode="repair-commit")
    settings = _azure_settings()

    try:
        result = DeepSeekHarnessAdapter(settings=settings, workspace=tmp_path).execute(
            AdapterRequest(
                instruction="Write the requested output, repair rejected structure, and commit it.",
                configuration=_commit_configuration(),
                output_path="output.md",
                output_format="markdown",
            )
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result.agent_output.status is AgentOutputStatus.COMPLETED
    assert result.completion_commit is not None
    assert result.completion_commit.commit_turn == 4
    assert result.turns_used == 4
    assert len(_KeylessDeepSeekHandler.requests) == 4
    evidence = [
        json.loads(line)
        for line in Path(result.configuration_record["commit_evidence_path"]).read_text(encoding="utf-8").splitlines()
    ]
    assert [record["response"]["status"] for record in evidence] == ["rejected", "accepted"]


def test_real_sdk_stop_after_rejected_commit_is_not_ordinary_completion(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pytest.importorskip("deepseek_harness")
    server, thread = _start_server(monkeypatch, mode="reject-stop")
    settings = _azure_settings()

    try:
        result = DeepSeekHarnessAdapter(settings=settings, workspace=tmp_path).execute(
            AdapterRequest(
                instruction="Write and commit the requested output.",
                configuration=_commit_configuration(),
                output_path="output.md",
                output_format="markdown",
            )
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result.agent_output.status is AgentOutputStatus.PARTIAL
    assert result.failure_kind is not None
    assert result.failure_kind.value == "missing_output"
    assert result.completion_reason is None
    assert result.completion_commit is None
    assert len(_KeylessDeepSeekHandler.requests) == 3
