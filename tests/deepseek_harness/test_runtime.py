# ABOUTME: Tests the isolated DeepSeek worker-process boundary and whole-tree timeout cleanup.
# ABOUTME: Proves environment allowlisting and raw notification capture without a provider key.

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from aec_bench.adapters.base import AdapterRequest
from aec_bench.adapters.deepseek_harness import runtime as deepseek_runtime
from aec_bench.adapters.deepseek_harness.config import DeepSeekHarnessSettings
from aec_bench.adapters.deepseek_harness.evidence import verify_deepseek_evidence_manifest
from aec_bench.adapters.deepseek_harness.runtime import (
    DeepSeekHarnessProcessRuntime,
    DeepSeekHarnessRuntimeError,
    DeepSeekHarnessRuntimeTimeout,
    build_deepseek_worker_environment,
)
from aec_bench.contracts.task_definition import ToolSpec


def _settings(workspace: Path) -> DeepSeekHarnessSettings:
    del workspace
    return DeepSeekHarnessSettings.from_execution_payload(
        model_name="azure:deepseek-v4-flash",
        payload={"provider": "azure"},
    )


@pytest.fixture(autouse=True)
def _azure_provider_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "keyless-test-token")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://qualified.example.test")


def _write_worker(path: Path, body: str) -> Path:
    path.write_text(
        "# ABOUTME: Generated test worker for the DeepSeek process boundary.\n"
        "# ABOUTME: Runs only inside one temporary pytest workspace.\n"
        "from __future__ import annotations\n"
        "import json, os, pathlib, socket, subprocess, sys, time\n"
        "request_path, result_path, notifications_path = map(pathlib.Path, sys.argv[1:4])\n"
        f"{body}\n",
        encoding="utf-8",
    )
    return path


def _commit_request() -> AdapterRequest:
    return AdapterRequest(
        instruction="Write and commit the output",
        output_path="output.md",
        output_format="markdown",
        configuration={
            "timeout_sec": 5,
            "output_completion_commit": True,
            "output_completion_contract": {
                "schema_version": "aecbench.output-completion-contract.v1",
                "output_path": "output.md",
                "format": "markdown_final_fenced_json",
                "required_top_level_keys": ["findings", "summary"],
                "require_single_final_json_block": True,
            },
        },
    )


def test_worker_environment_drops_ambient_credentials(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    del monkeypatch
    environment = build_deepseek_worker_environment(
        workspace=tmp_path,
        settings=_settings(tmp_path),
        source={
            "AZURE_OPENAI_API_KEY": "required-provider-key",
            "AZURE_OPENAI_ENDPOINT": "https://qualified.example.test",
            "PATH": "/qualified/bin",
            "PYTHONPATH": "/tmp/must-not-cross-pythonpath",
            "LANG": "en_AU.UTF-8",
            "AWS_SECRET_ACCESS_KEY": "must-not-cross",
            "SSH_AUTH_SOCK": "/tmp/agent.sock",
            "OPENAI_API_KEY": "must-not-cross",
            "DEEPSEEK_API_KEY": "must-not-cross",
            "DEEPSEEK_BASE_URL": "https://must-not-cross.example.test",
            "HTTP_PROXY": "http://must-not-cross",
            "NODE_OPTIONS": "--require /tmp/must-not-cross.js",
            "NPM_CONFIG_USERCONFIG": "/tmp/must-not-cross.npmrc",
            "HOME": "/tmp/must-not-cross-home",
            "DSH_CORDIS_CONFIG": "/tmp/must-not-cross.cordis.yml",
            "DSH_CONTEXT_WINDOW": "12",
            "DSH_MAX_TOKENS_AS_SUCCESS": "true",
            "DSH_MODEL": "must-not-cross-model",
            "DSH_SYSTEM_PROMPT": "must-not-cross-prompt",
        },
    )

    assert environment["DSH_API_KEY"] == "required-provider-key"
    assert environment["DSH_BASE_URL"] == "https://qualified.example.test/openai/v1"
    assert environment["PATH"] == "/qualified/bin"
    assert environment["PYTHONPATH"] == str(Path(deepseek_runtime.__file__).resolve().parents[3])
    assert environment["PYTHONPATH"] != "/tmp/must-not-cross-pythonpath"
    assert environment["LANG"] == "en_AU.UTF-8"
    assert "AZURE_OPENAI_API_KEY" not in environment
    assert "AZURE_OPENAI_ENDPOINT" not in environment
    assert "AWS_SECRET_ACCESS_KEY" not in environment
    assert "SSH_AUTH_SOCK" not in environment
    assert "OPENAI_API_KEY" not in environment
    assert "DEEPSEEK_API_KEY" not in environment
    assert "DEEPSEEK_BASE_URL" not in environment
    assert "HTTP_PROXY" not in environment
    assert "NODE_OPTIONS" not in environment
    assert "NPM_CONFIG_USERCONFIG" not in environment
    assert "DSH_MAX_TOKENS_AS_SUCCESS" not in environment
    assert environment["DSH_MODEL"] == "deepseek-v4-flash"
    assert "DSH_SYSTEM_PROMPT" not in environment
    assert "DSH_CONTEXT_WINDOW" not in environment
    assert environment["DSH_CORDIS_CONFIG"] != "/tmp/must-not-cross.cordis.yml"
    assert Path(environment["HOME"]).is_relative_to(tmp_path)
    assert Path(environment["TMPDIR"]).is_relative_to(tmp_path)


@pytest.mark.parametrize(
    ("configured", "expected"),
    [
        ("https://foundry.example.test", "https://foundry.example.test/openai/v1"),
        ("https://foundry.example.test/", "https://foundry.example.test/openai/v1"),
        ("https://foundry.example.test/openai/v1/", "https://foundry.example.test/openai/v1"),
    ],
)
def test_worker_environment_normalizes_the_azure_v1_endpoint(
    tmp_path: Path,
    configured: str,
    expected: str,
) -> None:
    environment = build_deepseek_worker_environment(
        workspace=tmp_path,
        settings=_settings(tmp_path),
        source={
            "AZURE_OPENAI_API_KEY": "provider-key",
            "AZURE_OPENAI_ENDPOINT": configured,
        },
    )

    assert environment["DSH_BASE_URL"] == expected


def test_worker_environment_normalizes_the_selected_deepseek_provider(tmp_path: Path) -> None:
    settings = DeepSeekHarnessSettings.from_execution_payload(
        model_name="deepseek:deepseek-v4-flash",
        payload={"provider": "deepseek"},
    )

    environment = build_deepseek_worker_environment(
        workspace=tmp_path,
        settings=settings,
        source={
            "DEEPSEEK_API_KEY": "deepseek-provider-key",
            "DEEPSEEK_BASE_URL": "https://gateway.example.test/deepseek/",
            "AZURE_OPENAI_API_KEY": "must-not-cross",
            "AZURE_OPENAI_ENDPOINT": "https://must-not-cross.example.test",
        },
    )

    assert environment["DSH_API_KEY"] == "deepseek-provider-key"
    assert environment["DSH_BASE_URL"] == "https://gateway.example.test/deepseek"
    assert environment["DSH_MODEL"] == "deepseek-v4-flash"
    assert "DEEPSEEK_API_KEY" not in environment
    assert "DEEPSEEK_BASE_URL" not in environment
    assert "AZURE_OPENAI_API_KEY" not in environment


def test_worker_environment_uses_the_public_deepseek_endpoint_by_default(tmp_path: Path) -> None:
    settings = DeepSeekHarnessSettings.from_execution_payload(
        model_name="deepseek:deepseek-v4-flash",
        payload={"provider": "deepseek"},
    )

    environment = build_deepseek_worker_environment(
        workspace=tmp_path,
        settings=settings,
        source={"DEEPSEEK_API_KEY": "deepseek-provider-key"},
    )

    assert environment["DSH_BASE_URL"] == "https://api.deepseek.com"


def test_worker_environment_requires_the_selected_deepseek_credential(tmp_path: Path) -> None:
    settings = DeepSeekHarnessSettings.from_execution_payload(
        model_name="deepseek:deepseek-v4-flash",
        payload={"provider": "deepseek"},
    )

    with pytest.raises(DeepSeekHarnessRuntimeError, match="DEEPSEEK_API_KEY"):
        build_deepseek_worker_environment(
            workspace=tmp_path,
            settings=settings,
            source={},
        )


@pytest.mark.parametrize("missing", ["AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT"])
def test_worker_environment_requires_the_azure_provider_configuration(tmp_path: Path, missing: str) -> None:
    source = {
        "AZURE_OPENAI_API_KEY": "provider-key",
        "AZURE_OPENAI_ENDPOINT": "https://foundry.example.test",
    }
    del source[missing]

    with pytest.raises(DeepSeekHarnessRuntimeError, match=missing):
        build_deepseek_worker_environment(
            workspace=tmp_path,
            settings=_settings(tmp_path),
            source=source,
        )


def test_process_runtime_collects_a_keyless_fake_worker_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "must-be-redacted")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://qualified.example.test")
    worker = _write_worker(
        tmp_path / "worker.py",
        """
request = json.loads(request_path.read_text())
assert "schema_version" not in request
assert "sdk_version" not in request
assert request["harness_route"] == "azure"
assert request["max_tokens"] == 17
print(os.environ["DSH_API_KEY"])
print(os.environ["DSH_BASE_URL"])
notification = {
    "method": "session.event",
    "params": {
        "sessionId": "root",
        "event": {"type": "step/start", "seq": 1, "time": 1, "data": {"turn": 1, "step": 1}},
    },
}
notifications_path.write_text(json.dumps(notification) + "\\n")
result_path.write_text(json.dumps({
    "session_id": "root",
    "final_response": "done",
    "finish_reason": "completed",
    "sdk_version": "fake-sdk",
    "runtime_distribution_version": "fake-runtime",
    "runtime_reported_version": None,
}))
""".strip(),
    )
    runtime = DeepSeekHarnessProcessRuntime(
        settings=_settings(tmp_path),
        workspace=tmp_path,
        worker_command=(sys.executable, str(worker)),
    )

    result = runtime.run(AdapterRequest(instruction="Do the work", configuration={"timeout_sec": 5, "max_tokens": 17}))

    assert result.session_id == "root"
    assert result.final_response == "done"
    assert result.projection.root_model_calls == 1
    assert result.timeout_seconds == 5
    assert result.max_tokens == 17
    assert result.notifications_path.read_text(encoding="utf-8").count("\n") == 1
    assert result.stderr_path.is_file()
    assert result.stderr_path.read_text(encoding="utf-8").splitlines() == [
        "[REDACTED]",
        "https://qualified.example.test/openai/v1",
    ]
    assert result.manifest_path is not None
    assert result.manifest_path.is_file()
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "aecbench.deepseek-evidence-manifest.v1"
    assert manifest["trial_id"] == runtime.paths.root.name
    assert manifest["adapter"] == {
        "kind": "deepseek_harness",
        "aec_bench_version": "0.1.0",
        "python_sdk_version": "fake-sdk",
        "runtime_distribution_version": "fake-runtime",
        "runtime_reported_version": None,
    }
    assert manifest["model"] == {
        "provider": "azure",
        "harness_route": "azure",
        "requested": "azure:deepseek-v4-flash",
        "resolved": "deepseek-v4-flash",
    }
    assert manifest["execution"]["status"] == "completed"
    assert manifest["execution"]["root_session_id"] == "root"
    assert manifest["execution"]["timeout_sec"] == 5
    assert manifest["execution"]["max_tokens"] == 17
    assert manifest["execution"]["process_group_retired"] is True
    assert manifest["plugins"] == []
    assert manifest["composition"]["resolved_composition_available"] is False
    assert manifest["composition"]["resolved_tool_surface_available"] is False
    roles = {artifact["role"] for artifact in manifest["artifacts"]}
    assert {
        "all_session_notifications",
        "composition_identity",
        "redaction_audit",
        "runtime_identity",
    }.issubset(roles)
    redaction = json.loads(runtime.paths.redaction_audit.read_text(encoding="utf-8"))
    assert redaction["schema_version"] == "aecbench.deepseek-redaction-audit.v1"
    assert redaction["replacement_count"] == 1
    assert redaction["files"] == [
        {
            "path": "stderr.log",
            "redaction_kinds": ["provider_api_key"],
            "replacement_count": 1,
        }
    ]
    redaction_text = runtime.paths.redaction_audit.read_text(encoding="utf-8")
    assert "must-be-redacted" not in redaction_text
    composition = json.loads(runtime.paths.composition.read_text(encoding="utf-8"))
    runtime_record = json.loads(runtime.paths.runtime_record.read_text(encoding="utf-8"))
    assert "schema_version" not in composition
    assert "qualified_source_revision" not in composition
    assert "sdk_version" not in composition
    assert "schema_version" not in runtime_record
    assert composition["timeout_sec"] == 5
    assert composition["max_tokens"] == 17
    assert composition["environment"]["secret_names"] == ["DSH_API_KEY"]
    assert composition["environment"]["passthrough_names"]
    assert "DSH_API_KEY" not in composition["environment"]["passthrough_names"]
    assert composition["environment"]["provider_endpoint"] == "https://qualified.example.test/openai/v1"
    assert composition["plugins"] == []
    assert runtime_record["timeout_sec"] == 5
    assert runtime_record["max_tokens"] == 17
    assert result.evidence_manifest_sha256 is not None

    with pytest.raises(DeepSeekHarnessRuntimeError, match="only one trial"):
        runtime.run(AdapterRequest(instruction="Do the work again", configuration={"timeout_sec": 5}))

    assert verify_deepseek_evidence_manifest(result.manifest_path).trial_id == runtime.paths.root.name
    runtime.paths.stderr.write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="does not match its receipt"):
        verify_deepseek_evidence_manifest(result.manifest_path)


def test_required_commit_runtime_binds_the_endpoint_and_records_secret_free_evidence(tmp_path: Path) -> None:
    worker = _write_worker(
        tmp_path / "commit_worker.py",
        """
request = json.loads(request_path.read_text())
cordis = pathlib.Path(request["cordis"])
assert cordis == request_path.parent / "cordis.input.yml"
assert "aec-output-commit" in cordis.read_text()
capability = os.environ["AEC_BENCH_COMMIT_TOKEN"]
print(f"capability={capability}")
session_root = pathlib.Path(request["session_root"])
session_root.mkdir(parents=True, exist_ok=True)
(session_root / "leak.jsonl").write_text(capability + "\\n")
output = pathlib.Path(request["workspace"]) / "output.md"
output.write_text('Report\\n```json\\n{"findings": [], "summary": {}}\\n```\\n')
socket_path = pathlib.Path(os.environ["AEC_BENCH_COMMIT_SOCKET"])
(request_path.parent / "socket.path").write_text(str(socket_path))
payload = {
    "protocol": "aec-bench/output-commit/1",
    "capability": capability,
    "request_id": "dsh:root:commit-1",
    "operation": "commit",
    "metadata": {
        "deepseek_session_id": "root",
        "deepseek_tool_call_id": "commit-1",
        "aec_model_turn": 1,
    },
}
with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
    client.connect(str(socket_path))
    client.sendall(json.dumps(payload).encode() + b"\\n")
    response = json.loads(client.makefile().readline())
assert response["status"] == "accepted"
notifications = [
    {"method": "session.event", "params": {"sessionId": "root", "event": {
        "type": "step/start", "seq": 1, "time": 1, "data": {"turn": 1, "step": 1},
    }}},
    {"method": "session.event", "params": {"sessionId": "root", "event": {
        "type": "tool/call", "seq": 2, "time": 2,
        "data": {"callId": "commit-1", "name": "aec_commit_output", "arguments": {}},
    }}},
    {"method": "session.event", "params": {"sessionId": "root", "event": {
        "type": "turn/end", "seq": 3, "time": 3,
        "data": {"turn": 1, "reason": {"kind": "completed"}},
    }}},
    {"method": "session.status", "params": {"sessionId": "root", "status": "idle"}},
]
notifications_path.write_text("".join(json.dumps(item) + "\\n" for item in notifications))
result_path.write_text(json.dumps({
    "session_id": "root",
    "final_response": capability,
    "finish_reason": "completed",
    "sdk_version": "fake-sdk",
    "runtime_distribution_version": "fake-runtime",
    "runtime_reported_version": None,
}))
""".strip(),
    )
    runtime = DeepSeekHarnessProcessRuntime(
        settings=_settings(tmp_path),
        workspace=tmp_path,
        worker_command=(sys.executable, str(worker)),
    )

    result = runtime.run(_commit_request())

    assert result.output_commit_mode == "required"
    assert result.completion_commit is not None
    assert result.completion_commit.commit_turn == 1
    assert result.commit_error is None
    assert result.final_response == "[REDACTED]"
    assert runtime.paths.stderr.read_text(encoding="utf-8").strip() == "capability=[REDACTED]"
    assert (runtime.paths.sessions / "leak.jsonl").read_text(encoding="utf-8").strip() == "[REDACTED]"
    assert result.commit_evidence_path == runtime.paths.commit_evidence
    evidence = runtime.paths.commit_evidence.read_text(encoding="utf-8")
    assert "AEC_BENCH_COMMIT_TOKEN" not in evidence
    assert not Path((runtime.paths.root / "socket.path").read_text(encoding="utf-8")).exists()
    composition = json.loads(runtime.paths.composition.read_text(encoding="utf-8"))
    assert composition["plugin_free_baseline"] is False
    assert composition["output_commit_mode"] == "required"
    assert composition["plugins"] == [
        {
            "artifact_path": "plugins/output-commit/index.js",
            "plugin_id": "@aec-bench/dsh-output-commit",
            "role": "output_commit",
            "version": "0.1.0",
        }
    ]
    manifest = json.loads(runtime.paths.manifest.read_text(encoding="utf-8"))
    assert {"optional_plugin", "output_commit_evidence"}.issubset(
        {artifact["role"] for artifact in manifest["artifacts"]}
    )
    assert manifest["plugins"] == composition["plugins"]


def test_runtime_binds_exact_native_tools_and_records_secret_free_evidence(tmp_path: Path) -> None:
    calls: list[str] = []

    def list_workspace(path: str = "") -> str:
        calls.append(path)
        return json.dumps({"status": "ok", "entries": ["inbox"]})

    worker = _write_worker(
        tmp_path / "lifecycle_worker.py",
        """
request = json.loads(request_path.read_text())
cordis = pathlib.Path(request["cordis"])
assert "aec-tools" in cordis.read_text()
manifest = json.loads(os.environ["DSH_TOOLS"])
assert [tool["name"] for tool in manifest] == ["list_workspace"]
capability = os.environ["DSH_TOOLS_TOKEN"]
print(f"capability={capability}")
payload = {
    "protocol": "aec-bench/deepseek-tools/1",
    "capability": capability,
    "request_id": "dsh:root:tool-1",
    "tool": "list_workspace",
    "arguments": {"path": "inbox"},
    "metadata": {
        "deepseek_session_id": "root",
        "deepseek_tool_call_id": "tool-1",
        "aec_model_turn": 1,
    },
}
with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
    client.connect(os.environ["DSH_TOOLS_SOCKET"])
    client.sendall(json.dumps(payload).encode() + b"\\n")
    response = json.loads(client.makefile().readline())
assert response["status"] == "ok"
assert response["result"]["entries"] == ["inbox"]
notifications = [
    {"method": "session.event", "params": {"sessionId": "root", "event": {
        "type": "step/start", "seq": 1, "time": 1, "data": {"turn": 1, "step": 1},
    }}},
    {"method": "session.event", "params": {"sessionId": "root", "event": {
        "type": "tool/call", "seq": 2, "time": 2,
        "data": {"callId": "tool-1", "name": "list_workspace", "arguments": {"path": "inbox"}},
    }}},
    {"method": "session.event", "params": {"sessionId": "root", "event": {
        "type": "turn/end", "seq": 3, "time": 3,
        "data": {"turn": 1, "reason": {"kind": "completed"}},
    }}},
    {"method": "session.status", "params": {"sessionId": "root", "status": "idle"}},
]
notifications_path.write_text("".join(json.dumps(item) + "\\n" for item in notifications))
result_path.write_text(json.dumps({
    "session_id": "root",
    "final_response": "",
    "finish_reason": "completed",
    "sdk_version": "fake-sdk",
    "runtime_distribution_version": "fake-runtime",
    "runtime_reported_version": None,
}))
""".strip(),
    )
    runtime = DeepSeekHarnessProcessRuntime(
        settings=_settings(tmp_path),
        workspace=tmp_path,
        worker_command=(sys.executable, str(worker)),
        native_tools={"list_workspace": list_workspace},
    )
    request = AdapterRequest(
        instruction="Review the lifecycle",
        tools=[ToolSpec(name="list_workspace", source="builtin", description="List files")],
        configuration={"timeout_sec": 5, "max_tokens": 512},
    )

    result = runtime.run(request)

    assert calls == ["inbox"]
    assert result.native_tools == ("list_workspace",)
    assert result.tool_gateway_evidence_path == runtime.paths.tool_gateway_evidence
    evidence = runtime.paths.tool_gateway_evidence.read_text(encoding="utf-8")
    assert "DSH_TOOLS_TOKEN" not in evidence
    assert "keyless-test-token" not in evidence
    assert json.loads(evidence)["tool"] == "list_workspace"
    composition = json.loads(runtime.paths.composition.read_text(encoding="utf-8"))
    assert composition["native_tools"] == ["list_workspace"]
    assert composition["environment"]["secret_names"] == ["DSH_API_KEY", "DSH_TOOLS_TOKEN"]
    manifest = json.loads(runtime.paths.manifest.read_text(encoding="utf-8"))
    assert manifest["composition"]["native_tools"] == ["list_workspace"]
    assert manifest["plugins"] == [
        {
            "artifact_path": "plugins/tools/index.js",
            "plugin_id": "@aec-bench/dsh-tools",
            "role": "native_tools",
            "version": "0.1.0",
        }
    ]
    assert {"tool_gateway_evidence", "optional_plugin"}.issubset(
        {artifact["role"] for artifact in manifest["artifacts"]}
    )


def test_runtime_invalidates_an_output_mutated_after_commit(tmp_path: Path) -> None:
    worker = _write_worker(
        tmp_path / "mutating_commit_worker.py",
        """
request = json.loads(request_path.read_text())
output = pathlib.Path(request["workspace"]) / "output.md"
output.write_text('Report\\n```json\\n{"findings": [], "summary": {}}\\n```\\n')
payload = {
    "protocol": "aec-bench/output-commit/1",
    "capability": os.environ["AEC_BENCH_COMMIT_TOKEN"],
    "request_id": "dsh:root:commit-1",
    "operation": "commit",
    "metadata": {"deepseek_session_id": "root", "deepseek_tool_call_id": "commit-1", "aec_model_turn": 1},
}
with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
    client.connect(os.environ["AEC_BENCH_COMMIT_SOCKET"])
    client.sendall(json.dumps(payload).encode() + b"\\n")
    assert json.loads(client.makefile().readline())["status"] == "accepted"
output.write_text('Changed\\n```json\\n{"findings": [], "summary": {}}\\n```\\n')
notifications = [
    {"method": "session.event", "params": {"sessionId": "root", "event": {
        "type": "step/start", "seq": 1, "time": 1, "data": {"turn": 1, "step": 1},
    }}},
    {"method": "session.event", "params": {"sessionId": "root", "event": {
        "type": "tool/call", "seq": 2, "time": 2,
        "data": {"callId": "commit-1", "name": "aec_commit_output", "arguments": {}},
    }}},
    {"method": "session.event", "params": {"sessionId": "root", "event": {
        "type": "turn/end", "seq": 3, "time": 3,
        "data": {"turn": 1, "reason": {"kind": "completed"}},
    }}},
    {"method": "session.status", "params": {"sessionId": "root", "status": "idle"}},
]
notifications_path.write_text("".join(json.dumps(item) + "\\n" for item in notifications))
result_path.write_text(json.dumps({
    "session_id": "root",
    "final_response": "",
    "finish_reason": "completed",
    "sdk_version": "fake-sdk",
    "runtime_distribution_version": "fake-runtime",
    "runtime_reported_version": None,
}))
""".strip(),
    )
    runtime = DeepSeekHarnessProcessRuntime(
        settings=_settings(tmp_path),
        workspace=tmp_path,
        worker_command=(sys.executable, str(worker)),
    )

    result = runtime.run(_commit_request())

    assert result.completion_commit is None
    assert result.commit_error == "artifact changed after the commit call."


@pytest.mark.skipif(not hasattr(os, "killpg"), reason="process-group cleanup requires POSIX")
def test_timeout_terminates_the_worker_process_group(tmp_path: Path) -> None:
    worker = _write_worker(
        tmp_path / "hung_worker.py",
        """
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
(request_path.parent / "child.pid").write_text(str(child.pid))
time.sleep(60)
""".strip(),
    )
    runtime = DeepSeekHarnessProcessRuntime(
        settings=_settings(tmp_path),
        workspace=tmp_path,
        worker_command=(sys.executable, str(worker)),
    )

    with pytest.raises(DeepSeekHarnessRuntimeTimeout):
        runtime.run(AdapterRequest(instruction="Hang", configuration={"timeout_sec": 1}))

    assert runtime.paths.manifest.is_file()
    runtime_record = json.loads(runtime.paths.runtime_record.read_text(encoding="utf-8"))
    assert runtime_record["status"] == "failed"
    assert runtime_record["process_group_retired"] is True
    assert runtime_record["timeout_sec"] == 1
    assert runtime_record["max_tokens"] is None
    child_pid = int((runtime.paths.root / "child.pid").read_text(encoding="utf-8"))
    with pytest.raises(ProcessLookupError):
        os.kill(child_pid, 0)
