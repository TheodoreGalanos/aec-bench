# ABOUTME: Tests the authenticated trial-local output commit authority for DeepSeek Harness.
# ABOUTME: Proves fixed-path validation, idempotency, secret safety, permissions, repair, and shutdown.

from __future__ import annotations

import json
import socket
import stat
import threading
from pathlib import Path
from typing import Any

from aec_bench.adapters.deepseek_harness.commit_endpoint import (
    OUTPUT_COMMIT_PROTOCOL,
    OutputCommitEndpoint,
)
from aec_bench.contracts.output_completion import OutputCompletionContract


def _contract(output_path: str = "output.md") -> OutputCompletionContract:
    return OutputCompletionContract.model_validate(
        {
            "schema_version": "aecbench.output-completion-contract.v1",
            "output_path": output_path,
            "format": "markdown_final_fenced_json",
            "required_top_level_keys": ["findings", "summary"],
            "require_single_final_json_block": True,
        }
    )


def _request(token: str, request_id: str, *, turn: int = 1, tool_call_id: str = "commit-1") -> dict[str, object]:
    return {
        "protocol": OUTPUT_COMMIT_PROTOCOL,
        "capability": token,
        "request_id": request_id,
        "operation": "commit",
        "metadata": {
            "deepseek_session_id": "root-session",
            "deepseek_tool_call_id": tool_call_id,
            "aec_model_turn": turn,
        },
    }


def _send(socket_path: Path, payload: dict[str, object]) -> dict[str, Any]:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.connect(str(socket_path))
        client.sendall(json.dumps(payload).encode("utf-8") + b"\n")
        response = b""
        while not response.endswith(b"\n"):
            response += client.recv(65536)
    value = json.loads(response)
    assert isinstance(value, dict)
    return value


def test_endpoint_accepts_exact_bytes_and_replays_an_identical_request(tmp_path: Path) -> None:
    output = 'Report\n```json\n{"findings": [], "summary": {}}\n```\n'
    (tmp_path / "output.md").write_text(output, encoding="utf-8")
    evidence_path = tmp_path / "commit-evidence.jsonl"
    endpoint = OutputCommitEndpoint(
        workspace=tmp_path,
        contract=_contract(),
        initial_content=None,
        evidence_path=evidence_path,
    )
    endpoint.start()
    environment = endpoint.connection_environment()
    socket_path = Path(environment["AEC_BENCH_COMMIT_SOCKET"])
    token = environment["AEC_BENCH_COMMIT_TOKEN"]
    request = _request(token, "dsh:root-session:commit-1", turn=2)

    try:
        first = _send(socket_path, request)
        repeated = _send(socket_path, request)

        assert first == repeated
        assert first["status"] == "accepted"
        assert first["attestation"]["commit_turn"] == 2
        assert endpoint.accepted_attestation is not None
        assert endpoint.accepted_attestation.output_sha256 == first["attestation"]["output_sha256"]
        assert stat.S_IMODE(socket_path.parent.stat().st_mode) == 0o700
        assert stat.S_IMODE(socket_path.stat().st_mode) == 0o600
    finally:
        endpoint.close()

    records = [json.loads(line) for line in evidence_path.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 2
    assert records[0]["idempotent_replay"] is False
    assert records[1]["idempotent_replay"] is True
    assert token not in evidence_path.read_text(encoding="utf-8")
    assert not socket_path.exists()
    assert not socket_path.parent.exists()


def test_rejected_commit_is_repairable_and_does_not_select_an_output_path(tmp_path: Path) -> None:
    output_path = tmp_path / "output.md"
    output_path.write_text("Incomplete report\n", encoding="utf-8")
    endpoint = OutputCommitEndpoint(
        workspace=tmp_path,
        contract=_contract(),
        initial_content=None,
        evidence_path=tmp_path / "commit-evidence.jsonl",
    )
    endpoint.start()
    environment = endpoint.connection_environment()
    socket_path = Path(environment["AEC_BENCH_COMMIT_SOCKET"])
    token = environment["AEC_BENCH_COMMIT_TOKEN"]

    try:
        rejected = _send(socket_path, _request(token, "dsh:root-session:commit-1"))
        assert rejected["status"] == "rejected"
        assert rejected["completion_evaluation"]["reason"] == "final_json_block_missing"
        assert endpoint.accepted_attestation is None

        output_path.write_text(
            'Repaired\n```json\n{"findings": [], "summary": {}}\n```\n',
            encoding="utf-8",
        )
        accepted = _send(
            socket_path,
            _request(token, "dsh:root-session:commit-2", turn=2, tool_call_id="commit-2"),
        )
        assert accepted["status"] == "accepted"
        assert endpoint.accepted_attestation is not None
        assert endpoint.accepted_attestation.commit_turn == 2
    finally:
        endpoint.close()


def test_endpoint_rejects_bad_capability_and_conflicting_request_id(tmp_path: Path) -> None:
    (tmp_path / "output.md").write_text(
        'Report\n```json\n{"findings": [], "summary": {}}\n```\n',
        encoding="utf-8",
    )
    endpoint = OutputCommitEndpoint(
        workspace=tmp_path,
        contract=_contract(),
        initial_content=None,
        evidence_path=tmp_path / "commit-evidence.jsonl",
    )
    endpoint.start()
    environment = endpoint.connection_environment()
    socket_path = Path(environment["AEC_BENCH_COMMIT_SOCKET"])
    token = environment["AEC_BENCH_COMMIT_TOKEN"]
    request = _request(token, "dsh:root-session:commit-1")

    try:
        unauthorized = _send(socket_path, {**request, "capability": "wrong-token"})
        assert unauthorized == {
            "protocol": OUTPUT_COMMIT_PROTOCOL,
            "status": "error",
            "diagnostics": [{"code": "unauthorized", "message": "Output commit authorization failed."}],
        }

        accepted = _send(socket_path, request)
        assert accepted["status"] == "accepted"

        conflict = _send(
            socket_path,
            _request(token, "dsh:root-session:commit-1", turn=2, tool_call_id="different-call"),
        )
        assert conflict["status"] == "error"
        assert conflict["diagnostics"][0]["code"] == "request_id_conflict"
    finally:
        endpoint.close()


def test_close_waits_for_an_open_request_and_removes_the_socket(tmp_path: Path) -> None:
    endpoint = OutputCommitEndpoint(
        workspace=tmp_path,
        contract=_contract(),
        initial_content=None,
        evidence_path=tmp_path / "commit-evidence.jsonl",
        client_timeout_seconds=0.1,
    )
    endpoint.start()
    socket_path = Path(endpoint.connection_environment()["AEC_BENCH_COMMIT_SOCKET"])
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.connect(str(socket_path))
    client.sendall(b'{"protocol":')

    closer = threading.Thread(target=endpoint.close)
    closer.start()
    closer.join(timeout=2)
    client.close()

    assert not closer.is_alive()
    assert not socket_path.exists()
    assert not socket_path.parent.exists()
