# ABOUTME: Tests the isolated DeepSeek worker-process boundary and whole-tree timeout cleanup.
# ABOUTME: Proves environment allowlisting and raw notification capture without a provider key.

from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
from pathlib import Path

import pytest

from aec_bench.adapters.base import AdapterRequest
from aec_bench.adapters.deepseek_harness import runtime as deepseek_runtime
from aec_bench.adapters.deepseek_harness.config import DeepSeekHarnessSettings
from aec_bench.adapters.deepseek_harness.evidence import (
    DeepSeekEvidenceManifest,
    verify_deepseek_evidence_manifest,
)
from aec_bench.adapters.deepseek_harness.native_world_tools import DeepSeekNativeWorldEvidence
from aec_bench.adapters.deepseek_harness.runtime import (
    DeepSeekHarnessProcessRuntime,
    DeepSeekHarnessRuntimeError,
    DeepSeekHarnessRuntimeTimeout,
    build_deepseek_worker_environment,
)
from aec_bench.adapters.deepseek_harness.tool_gateway import json_native_tool_definition, native_tool_manifest
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
    assert manifest["schema"] == "aec-bench/deepseek-evidence/2"
    assert manifest["trial_id"] == runtime.paths.root.name
    assert manifest["adapter"]["kind"] == "deepseek_harness"
    assert manifest["adapter"]["aec_bench_version"] == "0.1.0"
    assert manifest["adapter"]["python_sdk_version"] == "fake-sdk"
    assert manifest["adapter"]["runtime_distribution_version"] == "fake-runtime"
    assert manifest["adapter"]["runtime_reported_version"] is None
    assert (manifest["adapter"]["aec_bench_revision"] is None) != (
        manifest["adapter"]["aec_bench_revision_reason"] is None
    )
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
    assert manifest["attestation"]["declared"]["status"] == "complete"
    assert manifest["attestation"]["resolved_runtime"] == {
        "status": "unavailable",
        "artifacts": [],
        "reason": "deepseek-harness-sdk-does-not-expose-resolved-runtime-composition",
    }
    assert manifest["attestation"]["model_visible"]["status"] == "unavailable"
    assert manifest["qualification"] == {
        "matrix_id": "deepseek-harness-0.1.0rc6-initial",
        "matrix": {
            "path": "qualification-reference.json",
            "sha256": deepseek_runtime._file_sha256(runtime.paths.qualification_reference),
        },
        "provider_route": "azure",
        "status": "unqualified",
        "live_qualified": False,
        "qualified_features": [],
    }
    roles = {artifact["role"] for artifact in manifest["artifacts"]}
    assert {
        "all_session_notifications",
        "composition_identity",
        "qualification_matrix",
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
    assert composition["schema"] == "aec-bench/deepseek-declared-composition/1"
    assert "qualified_source_revision" not in composition
    assert "sdk_version" not in composition
    assert "schema_version" not in runtime_record
    assert composition["timeout_sec"] == 5
    assert composition["max_tokens"] == 17
    assert composition["aec_native_tool_manifest"] == []
    assert composition["environment"]["secret_names"] == ["DSH_API_KEY"]
    assert composition["environment"]["passthrough_names"]
    assert "DSH_API_KEY" not in composition["environment"]["passthrough_names"]
    assert composition["environment"]["provider_endpoint"] == "https://qualified.example.test/openai/v1"
    assert composition["plugins"] == []
    assert runtime_record["timeout_sec"] == 5
    assert runtime_record["max_tokens"] == 17
    assert result.evidence_manifest_sha256 is not None

    future_payload = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    future_payload["future_manifest_field"] = {"retained": True}
    future_payload["attestation"]["declared"]["future_level_field"] = "retained"
    imported = DeepSeekEvidenceManifest.model_validate(future_payload).model_dump(mode="json", by_alias=True)
    assert imported["future_manifest_field"] == {"retained": True}
    assert imported["attestation"]["declared"]["future_level_field"] == "retained"
    legacy_payload = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    legacy_payload["schema_version"] = "aecbench.deepseek-evidence-manifest.v1"
    del legacy_payload["schema"]
    with pytest.raises(ValueError, match="schema"):
        DeepSeekEvidenceManifest.model_validate(legacy_payload)

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
            "artifact_sha256": deepseek_runtime._file_sha256(runtime.paths.output_commit_plugin),
            "package_lock_path": "plugins/package-lock.json",
            "package_lock_sha256": deepseek_runtime._file_sha256(runtime.paths.plugin_package_lock),
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
    assert manifest["plugins"][0]["artifact_sha256"] == deepseek_runtime._file_sha256(
        runtime.paths.output_commit_plugin
    )
    assert manifest["plugins"][0]["package_lock_path"] == "plugins/package-lock.json"
    assert manifest["plugins"][0]["package_lock_sha256"] == deepseek_runtime._file_sha256(
        runtime.paths.plugin_package_lock
    )


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
    "protocol": "aec-bench/deepseek-tools/2",
    "capability": capability,
    "operation": "invoke",
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
    definition = json_native_tool_definition(
        name="list_workspace",
        description="List files",
        parameters_schema={
            "type": "object",
            "properties": {"path": {"type": "string", "default": ""}},
            "required": [],
            "additionalProperties": False,
        },
        function=list_workspace,
    )
    tool_manifest = native_tool_manifest((definition,))
    action_mapping = ({"catalogue_action": "list_workspace", "public_tool": "list_workspace"},)
    surface_identity = {"action_mapping": action_mapping, "tools": tool_manifest}
    public_surface_sha256 = hashlib.sha256(
        json.dumps(surface_identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    actor_evidence_path = tmp_path / "actor-invocation-evidence.jsonl"
    actor_evidence_path.write_text(
        json.dumps(
            {
                "sequence": 7,
                "record_type": "request-admitted",
                "request_id": "dsh:root:tool-1",
                "correlation": {
                    "transport_request_id": "dsh:root:tool-1",
                    "provider_session_id": "root",
                    "provider_tool_call_id": "tool-1",
                    "model_turn": 1,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    runtime = DeepSeekHarnessProcessRuntime(
        settings=_settings(tmp_path),
        workspace=tmp_path,
        worker_command=(sys.executable, str(worker)),
        native_tools=(definition,),
        native_world_evidence=DeepSeekNativeWorldEvidence(
            surface_record={
                "schema": "aec-bench/native-world-tool-surface/1",
                "task_world_id": "test/list-workspace",
                "catalogue_sha256": "a" * 64,
                "public_tool_surface_sha256": public_surface_sha256,
                "catalogue": {},
                "action_mapping": action_mapping,
                "tools": tool_manifest,
            },
            actor_authority_evidence_path=actor_evidence_path,
        ),
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
    invocation = next(
        json.loads(line) for line in evidence.splitlines() if json.loads(line)["record_type"] == "invocation"
    )
    assert invocation["tool"] == "list_workspace"
    assert invocation["request_id"] == "dsh:root:tool-1"
    composition = json.loads(runtime.paths.composition.read_text(encoding="utf-8"))
    assert composition["native_tools"] == ["list_workspace"]
    assert composition["environment"]["secret_names"] == ["DSH_API_KEY", "DSH_TOOLS_TOKEN"]
    manifest = json.loads(runtime.paths.manifest.read_text(encoding="utf-8"))
    assert manifest["composition"]["native_tools"] == ["list_workspace"]
    assert manifest["actor_native_tools"]["task_world_id"] == "test/list-workspace"
    assert manifest["actor_native_tools"]["actor_catalogue_sha256"] == "a" * 64
    assert manifest["actor_native_tools"]["public_native_tool_surface_sha256"] == public_surface_sha256
    assert manifest["actor_native_tools"]["presentation_mode"] == "deepseek-native"
    assert manifest["actor_native_tools"]["actor_authority_scope"] == "segment-snapshot"
    correlation = [json.loads(line) for line in runtime.paths.actor_correlation.read_text().splitlines()]
    assert correlation[0]["request_id"] == "dsh:root:tool-1"
    assert correlation[0]["actor_evidence_sequences"] == [7]
    assert len(manifest["plugins"]) == 1
    assert manifest["plugins"][0] == {
        "artifact_path": "plugins/tools/index.js",
        "artifact_sha256": deepseek_runtime._file_sha256(runtime.paths.tool_gateway_plugin),
        "package_lock_path": "plugins/package-lock.json",
        "package_lock_sha256": deepseek_runtime._file_sha256(runtime.paths.plugin_package_lock),
        "plugin_id": "@aec-bench/dsh-tools",
        "role": "native_tools",
        "version": "0.2.0",
    }
    assert {
        "actor_authority_evidence",
        "actor_correlation",
        "native_world_tool_surface",
        "tool_gateway_evidence",
        "optional_plugin",
        "plugin_package_lock",
    }.issubset({artifact["role"] for artifact in manifest["artifacts"]})


def test_runtime_rejects_completion_after_nonquiescent_tool_close(tmp_path: Path) -> None:
    started = threading.Event()
    release = threading.Event()

    def hang() -> str:
        started.set()
        release.wait(5)
        return json.dumps({"status": "late"})

    worker = _write_worker(
        tmp_path / "unsettled_tool_worker.py",
        """
payload = {
    "protocol": "aec-bench/deepseek-tools/2",
    "capability": os.environ["DSH_TOOLS_TOKEN"],
    "operation": "invoke",
    "tool": "hang",
    "arguments": {},
    "metadata": {
        "deepseek_session_id": "root",
        "deepseek_tool_call_id": "hanging-tool",
        "aec_model_turn": 1,
    },
}
client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
client.connect(os.environ["DSH_TOOLS_SOCKET"])
client.sendall(json.dumps(payload).encode() + b"\\n")
time.sleep(0.1)
client.close()
notifications = [
    {"method": "session.event", "params": {"sessionId": "root", "event": {
        "type": "step/start", "seq": 1, "time": 1, "data": {"turn": 1, "step": 1},
    }}},
    {"method": "session.event", "params": {"sessionId": "root", "event": {
        "type": "tool/call", "seq": 2, "time": 2,
        "data": {"callId": "hanging-tool", "name": "hang", "arguments": {}},
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
    "final_response": "claimed completion",
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
        native_tools=(
            json_native_tool_definition(
                name="hang",
                description="Hang",
                parameters_schema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False,
                },
                function=hang,
            ),
        ),
        tool_gateway_close_timeout_seconds=0.01,
    )

    try:
        with pytest.raises(DeepSeekHarnessRuntimeError, match="unsettled requests: dsh:root:hanging-tool"):
            runtime.run(
                AdapterRequest(
                    instruction="Call the hanging tool",
                    tools=[ToolSpec(name="hang", source="builtin", description="Hang")],
                    configuration={"timeout_sec": 5, "max_tokens": 512},
                )
            )
    finally:
        release.set()

    assert started.is_set()
    runtime_record = json.loads(runtime.paths.runtime_record.read_text(encoding="utf-8"))
    assert runtime_record["status"] == "failed"
    assert runtime_record["tool_gateway_close"]["quiescent"] is False
    assert runtime_record["tool_gateway_close"]["unknown_outcome_request_ids"] == ["dsh:root:hanging-tool"]
    verify_deepseek_evidence_manifest(runtime.paths.manifest)


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
