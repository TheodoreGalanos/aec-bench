# ABOUTME: Proves the versioned world actor endpoint delegates all action semantics to one authority.
# ABOUTME: Covers protocol rejection, framing, client staging, CLI use, redaction, and clean close.

from __future__ import annotations

import ast
import importlib
import json
import os
import socket
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from typing import Any, cast

import pytest

from aec_bench.contracts.world_interface import (
    WorldActorActionCapability,
    WorldActorActionRequest,
    WorldActorActionResult,
    WorldActorCapabilityCatalogue,
    WorldActorObservation,
    WorldInterfaceError,
)
from aec_bench.harness.world_actor import ActorInvocationAuthority, ActorInvocationAuthorityConfig
from aec_bench.harness.world_actor.client_bundle import (
    WorldActorClientInstallError,
    install_world_actor_client,
)
from aec_bench.harness.world_actor.endpoint import WorldActorEndpoint
from aec_bench.harness.world_actor.protocol import (
    WORLD_ACTOR_CAPABILITY_ENV,
    WORLD_ACTOR_PROTOCOL,
    WORLD_ACTOR_PROTOCOL_ENV,
    WORLD_ACTOR_SOCKET_ENV,
)


class _FakeHost:
    def __init__(self) -> None:
        self.calls: list[WorldActorActionRequest] = []

    def capabilities(self) -> WorldActorCapabilityCatalogue:
        return WorldActorCapabilityCatalogue(
            task_world_id="test-world",
            actions=(
                WorldActorActionCapability(
                    name="act",
                    description="Apply one deterministic action.",
                    input_schema={"type": "object"},
                ),
            ),
        )

    def observe(self) -> WorldActorObservation:
        return WorldActorObservation(decision_id=f"decision-{len(self.calls)}", view={"calls": len(self.calls)})

    def invoke(self, request: WorldActorActionRequest) -> WorldActorActionResult:
        if request.decision_id != f"decision-{len(self.calls)}":
            raise WorldInterfaceError("decision-stale", "The decision is stale.")
        self.calls.append(request)
        return WorldActorActionResult(
            request_id=request.request_id,
            action_name=request.action_name,
            status="applied",
            task_receipt={"receipt_id": f"receipt-{len(self.calls)}"},
            next_observation=self.observe(),
        )


class _LargeObservationHost(_FakeHost):
    def observe(self) -> WorldActorObservation:
        return WorldActorObservation(decision_id="large-decision", view={"large": "x" * 2_000})


def _endpoint(
    tmp_path: Path,
    host: _FakeHost,
    *,
    max_world_actions: int = 4,
    max_request_bytes: int = 1024 * 1024,
    max_response_bytes: int = 4 * 1024 * 1024,
) -> WorldActorEndpoint:
    actor_workspace = tmp_path / "actor"
    actor_workspace.mkdir(exist_ok=True)
    authority = ActorInvocationAuthority(
        host=host,
        config=ActorInvocationAuthorityConfig(
            actor_principal_id="actor.process-composite",
            max_world_actions=max_world_actions,
            evidence_path=tmp_path / "evidence" / "actor-authority.jsonl",
        ),
    )
    return WorldActorEndpoint(
        authority=authority,
        socket_directory=actor_workspace / ".world-endpoint",
        evidence_file=tmp_path / "evidence" / "actor-transport.jsonl",
        max_request_bytes=max_request_bytes,
        max_response_bytes=max_response_bytes,
    )


def _load_client(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    install_world_actor_client(workspace)
    monkeypatch.syspath_prepend(str(workspace))
    sys.modules.pop("aec_world", None)
    return importlib.import_module("aec_world")


def _request(
    environment: dict[str, str],
    request: dict[str, Any],
    *,
    transport_request_id: str,
    protocol: str = WORLD_ACTOR_PROTOCOL,
    capability: str | None = None,
) -> dict[str, Any]:
    return {
        "protocol": protocol,
        "transport_request_id": transport_request_id,
        "capability": capability or environment[WORLD_ACTOR_CAPABILITY_ENV],
        "request": request,
    }


def _raw_bytes(socket_path: str, payload: bytes, *, shutdown_write: bool = False) -> dict[str, Any]:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(3)
        client.connect(socket_path)
        client.sendall(payload)
        if shutdown_write:
            client.shutdown(socket.SHUT_WR)
        response = client.makefile("rb").readline()
    return cast(dict[str, Any], json.loads(response))


def _raw_call(socket_path: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _raw_bytes(socket_path, json.dumps(payload).encode("utf-8") + b"\n")


@pytest.mark.asyncio
async def test_endpoint_and_standalone_client_share_authority_semantics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "actor"
    workspace.mkdir()
    client = _load_client(workspace, monkeypatch)
    host = _FakeHost()
    endpoint = _endpoint(tmp_path, host, max_world_actions=1)

    with endpoint:
        environment = endpoint.connection_environment()
        for name, value in environment.items():
            monkeypatch.setenv(name, value)

        catalogue = await client.capabilities()
        observation = await client.observe()
        first = await client.invoke(
            "act",
            {"value": 1},
            decision_id=observation["decision_id"],
            request_id="action-1",
        )
        duplicate = await client.invoke(
            "act",
            {"value": 1},
            decision_id=observation["decision_id"],
            request_id="action-1",
        )
        with pytest.raises(client.ActorError) as conflict:
            await client.invoke(
                "act",
                {"value": 2},
                decision_id=observation["decision_id"],
                request_id="action-1",
            )
        with pytest.raises(client.ActorError) as exhausted:
            await client.invoke(
                "act",
                {},
                decision_id=first["next_observation"]["decision_id"],
                request_id="action-2",
            )

        assert environment[WORLD_ACTOR_PROTOCOL_ENV] == WORLD_ACTOR_PROTOCOL
        assert catalogue["task_world_id"] == "test-world"
        assert duplicate == first
        assert conflict.value.code == "request-id-conflict"
        assert conflict.value.outcome == "not-dispatched"
        assert exhausted.value.code == "world-action-budget-exhausted"
        assert host.calls[0].request_id == "action-1"
        assert len(host.calls) == 1
        assert endpoint.world_action_count == 1
        assert endpoint.world_action_limit_reached

    assert endpoint.lifecycle.value == "closed"
    assert not endpoint.socket_path.exists()
    assert not endpoint.socket_path.parent.exists()
    transport_evidence = (tmp_path / "evidence" / "actor-transport.jsonl").read_text(encoding="utf-8")
    authority_evidence = (tmp_path / "evidence" / "actor-authority.jsonl").read_text(encoding="utf-8")
    assert environment[WORLD_ACTOR_CAPABILITY_ENV] not in transport_evidence
    assert environment[WORLD_ACTOR_CAPABILITY_ENV] not in authority_evidence
    assert "request-conflict" in authority_evidence
    assert "request-duplicate" in authority_evidence


def test_endpoint_rejects_old_envelopes_versions_controls_and_bad_capabilities(tmp_path: Path) -> None:
    endpoint = _endpoint(tmp_path, _FakeHost())

    with endpoint:
        environment = endpoint.connection_environment()
        old = _raw_call(
            environment[WORLD_ACTOR_SOCKET_ENV],
            {
                "transport_request_id": "transport-old",
                "capability": environment[WORLD_ACTOR_CAPABILITY_ENV],
                "request": {"operation": "observe"},
            },
        )
        unsupported = _raw_call(
            environment[WORLD_ACTOR_SOCKET_ENV],
            _request(
                environment,
                {"operation": "observe"},
                transport_request_id="transport-version",
                protocol="aec-bench/world-actor/0",
            ),
        )
        control = _raw_call(
            environment[WORLD_ACTOR_SOCKET_ENV],
            _request(
                environment,
                {"operation": "execute", "authority_id": "host"},
                transport_request_id="transport-control",
            ),
        )
        selector = _raw_call(
            environment[WORLD_ACTOR_SOCKET_ENV],
            _request(
                environment,
                {"operation": "observe", "run_id": "private-run"},
                transport_request_id="transport-selector",
            ),
        )
        unauthorized = _raw_call(
            environment[WORLD_ACTOR_SOCKET_ENV],
            _request(
                environment,
                {"operation": "observe"},
                transport_request_id="transport-unauthorized",
                capability="wrong-capability",
            ),
        )

    assert old["transport_request_id"] == "transport-old"
    assert old["error"]["code"] == "actor-protocol-unsupported"
    assert unsupported["error"]["code"] == "actor-protocol-unsupported"
    assert control["error"]["code"] == "actor-request-invalid"
    assert selector["error"]["code"] == "actor-request-invalid"
    assert unauthorized["error"] == {
        "code": "actor-unauthorized",
        "detail": "The actor capability is invalid.",
        "outcome": "not-dispatched",
        "retryable": False,
    }
    evidence = (tmp_path / "evidence" / "actor-transport.jsonl").read_text(encoding="utf-8")
    assert "wrong-capability" not in evidence
    assert "private-run" not in evidence


@pytest.mark.parametrize(
    ("payload", "shutdown_write", "error_code"),
    [
        (b"\xff\n", False, "transport-invalid-utf8"),
        (b'{"protocol":"aec-bench/world-actor/1"}', True, "transport-incomplete"),
        (b'{"transport_request_id":"transport-json"\n', False, "transport-invalid-json"),
    ],
)
def test_endpoint_rejects_invalid_framing(
    tmp_path: Path,
    payload: bytes,
    shutdown_write: bool,
    error_code: str,
) -> None:
    endpoint = _endpoint(tmp_path, _FakeHost())
    with endpoint:
        response = _raw_bytes(
            endpoint.connection_environment()[WORLD_ACTOR_SOCKET_ENV],
            payload,
            shutdown_write=shutdown_write,
        )
    assert response["ok"] is False
    assert response["error"]["code"] == error_code


def test_endpoint_rejects_trailing_non_whitespace(tmp_path: Path) -> None:
    endpoint = _endpoint(tmp_path, _FakeHost())
    with endpoint:
        environment = endpoint.connection_environment()
        request = _request(environment, {"operation": "observe"}, transport_request_id="transport-trailing")
        response = _raw_bytes(
            environment[WORLD_ACTOR_SOCKET_ENV],
            json.dumps(request).encode("utf-8") + b"\nnot-another-request",
        )
    assert response["transport_request_id"] == "transport-trailing"
    assert response["error"]["code"] == "transport-trailing-data"


def test_endpoint_lifecycle_is_single_start_and_successful_close_is_idempotent(tmp_path: Path) -> None:
    endpoint = _endpoint(tmp_path, _FakeHost())
    endpoint.start()

    with pytest.raises(RuntimeError, match="can start only once"):
        endpoint.start()
    first = endpoint.close()
    second = endpoint.close()

    assert first.complete
    assert second == first
    assert endpoint.lifecycle.value == "closed"


def test_endpoint_rejects_a_symbolic_link_socket_directory(tmp_path: Path) -> None:
    endpoint = _endpoint(tmp_path, _FakeHost())
    target = tmp_path / "socket-target"
    target.mkdir()
    (tmp_path / "actor" / ".world-endpoint").symlink_to(target, target_is_directory=True)

    with pytest.raises(RuntimeError, match="socket directory already exists"):
        endpoint.start()

    assert not (tmp_path / "evidence" / "actor-transport.jsonl").exists()
    assert endpoint.lifecycle.value == "created"


def test_endpoint_bounds_requests_and_responses(tmp_path: Path) -> None:
    endpoint = _endpoint(tmp_path, _LargeObservationHost(), max_request_bytes=1024, max_response_bytes=1024)
    with endpoint:
        environment = endpoint.connection_environment()
        oversized_request = _raw_bytes(environment[WORLD_ACTOR_SOCKET_ENV], b"x" * 1026 + b"\n")
        observation_request = _request(
            environment,
            {"operation": "observe"},
            transport_request_id="transport-observe",
        )
        oversized_response = _raw_call(environment[WORLD_ACTOR_SOCKET_ENV], observation_request)

    assert oversized_request["error"]["code"] == "request-too-large"
    assert oversized_response["error"]["code"] == "response-too-large"


def test_client_install_is_content_addressed_idempotent_and_conflict_safe(tmp_path: Path) -> None:
    workspace = tmp_path / "actor"
    workspace.mkdir()
    first = install_world_actor_client(workspace)
    second = install_world_actor_client(workspace)

    assert first == second
    assert len(first.content_sha256) == 64
    assert (first.package_directory / "__main__.py").is_file()

    (first.package_directory / "extra.py").write_text("conflict", encoding="utf-8")
    with pytest.raises(WorldActorClientInstallError, match="different content"):
        install_world_actor_client(workspace)


def test_client_install_rejects_symbolic_link_destination(tmp_path: Path) -> None:
    workspace = tmp_path / "actor"
    workspace.mkdir()
    target = tmp_path / "target"
    target.mkdir()
    (workspace / "aec_world").symlink_to(target, target_is_directory=True)

    with pytest.raises(WorldActorClientInstallError, match="missing or unsafe"):
        install_world_actor_client(workspace)


def test_standalone_client_is_valid_for_prime_python_3_11(tmp_path: Path) -> None:
    workspace = tmp_path / "actor"
    workspace.mkdir()
    installed = install_world_actor_client(workspace)

    for source in installed.package_directory.glob("*.py"):
        ast.parse(
            source.read_text(encoding="utf-8"),
            filename=str(source),
            feature_version=(3, 11),
        )


def test_standalone_json_cli_runs_all_operations_without_aec_bench_on_its_python_path(tmp_path: Path) -> None:
    workspace = tmp_path / "actor"
    workspace.mkdir()
    install_world_actor_client(workspace)
    host = _FakeHost()
    endpoint = _endpoint(tmp_path, host)

    with endpoint:
        environment = {**os.environ, **endpoint.connection_environment(), "PYTHONPATH": ""}
        capabilities_call = subprocess.run(
            [sys.executable, "-m", "aec_world", "capabilities"],
            cwd=workspace,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        observe_call = subprocess.run(
            [sys.executable, "-m", "aec_world", "observe"],
            cwd=workspace,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        observation = json.loads(observe_call.stdout)
        invoke_call = subprocess.run(
            [
                sys.executable,
                "-m",
                "aec_world",
                "invoke",
                "--action",
                "act",
                "--decision-id",
                observation["decision_id"],
                "--arguments-json",
                json.dumps({"text": "$(not-a-shell); 'quoted'"}),
                "--request-id",
                "cli-action-1",
            ],
            cwd=workspace,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

    for completed in (capabilities_call, observe_call, invoke_call):
        assert completed.returncode == 0
        assert completed.stderr == ""
        assert completed.stdout.count("\n") == 1
    assert json.loads(capabilities_call.stdout)["task_world_id"] == "test-world"
    assert json.loads(invoke_call.stdout)["request_id"] == "cli-action-1"
    assert host.calls[0].arguments == {"text": "$(not-a-shell); 'quoted'"}


def test_standalone_json_cli_returns_one_structured_error_without_traceback(tmp_path: Path) -> None:
    workspace = tmp_path / "actor"
    workspace.mkdir()
    install_world_actor_client(workspace)

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "aec_world",
            "invoke",
            "--action",
            "act",
            "--decision-id",
            "decision-0",
            "--arguments-json",
            "not-json",
        ],
        cwd=workspace,
        env={**os.environ, "PYTHONPATH": ""},
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode != 0
    assert completed.stdout == ""
    assert completed.stderr.count("\n") == 1
    error = json.loads(completed.stderr)
    assert error["error"]["code"] == "cli-invalid"
    assert "Traceback" not in completed.stderr


@pytest.mark.asyncio
async def test_client_generates_request_identity_before_configuration_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "actor"
    workspace.mkdir()
    client = _load_client(workspace, monkeypatch)
    for name in (WORLD_ACTOR_SOCKET_ENV, WORLD_ACTOR_CAPABILITY_ENV, WORLD_ACTOR_PROTOCOL_ENV):
        monkeypatch.delenv(name, raising=False)
    secret = "must-not-appear-in-errors"
    monkeypatch.setenv(WORLD_ACTOR_CAPABILITY_ENV, secret)

    with pytest.raises(client.ActorError) as captured:
        await client.invoke("act", {}, decision_id="decision-0")

    assert captured.value.code == "actor-unavailable"
    assert captured.value.request_id
    assert captured.value.outcome == "not-dispatched"
    assert secret not in str(captured.value)
    assert secret not in repr(captured.value)


@pytest.mark.asyncio
async def test_client_surfaces_unknown_outcome_without_retrying_or_replacing_request_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "actor"
    workspace.mkdir()
    client = _load_client(workspace, monkeypatch)
    socket_path = Path("/tmp") / f"aec-world-{uuid.uuid4().hex}.sock"
    observed, thread = _serve_one_request(socket_path)
    monkeypatch.setenv(WORLD_ACTOR_SOCKET_ENV, str(socket_path))
    monkeypatch.setenv(WORLD_ACTOR_CAPABILITY_ENV, "test-capability")
    monkeypatch.setenv(WORLD_ACTOR_PROTOCOL_ENV, WORLD_ACTOR_PROTOCOL)

    with pytest.raises(client.ActorError) as captured:
        await client.invoke("act", {}, decision_id="decision-0")
    thread.join(timeout=3)

    sent_request_id = observed["request"]["request_id"]
    assert captured.value.code == "transport-malformed"
    assert captured.value.request_id == sent_request_id
    assert captured.value.outcome == "unknown"
    assert observed["connections"] == 1


@pytest.mark.asyncio
async def test_client_rejects_response_with_wrong_transport_correlation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "actor"
    workspace.mkdir()
    client = _load_client(workspace, monkeypatch)
    socket_path = Path("/tmp") / f"aec-world-{uuid.uuid4().hex}.sock"
    observed, thread = _serve_one_request(
        socket_path,
        response={
            "protocol": WORLD_ACTOR_PROTOCOL,
            "transport_request_id": "different-transport-request",
            "ok": True,
            "result": {},
        },
    )
    monkeypatch.setenv(WORLD_ACTOR_SOCKET_ENV, str(socket_path))
    monkeypatch.setenv(WORLD_ACTOR_CAPABILITY_ENV, "test-capability")
    monkeypatch.setenv(WORLD_ACTOR_PROTOCOL_ENV, WORLD_ACTOR_PROTOCOL)

    with pytest.raises(client.ActorError) as captured:
        await client.observe()
    thread.join(timeout=3)

    assert captured.value.code == "transport-malformed"
    assert captured.value.outcome == "not-dispatched"
    assert observed["connections"] == 1


def _serve_one_request(
    socket_path: Path, *, response: dict[str, Any] | None = None
) -> tuple[dict[str, Any], threading.Thread]:
    observed: dict[str, Any] = {"connections": 0}
    ready = threading.Event()

    def serve() -> None:
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                server.bind(str(socket_path))
                server.listen(1)
                ready.set()
                connection, _ = server.accept()
                with connection:
                    observed["connections"] += 1
                    line = connection.makefile("rb").readline()
                    observed.update(json.loads(line))
                    if response is not None:
                        connection.sendall(json.dumps(response).encode("utf-8") + b"\n")
        finally:
            socket_path.unlink(missing_ok=True)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    assert ready.wait(timeout=3)
    return observed, thread
