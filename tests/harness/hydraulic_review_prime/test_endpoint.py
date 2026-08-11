# ABOUTME: Proves the hydraulic-review Prime endpoint exposes only its six checkpoint operations.
# ABOUTME: Covers real operation semantics, file confinement, capability scope, and redacted evidence.

from __future__ import annotations

import importlib
import inspect
import json
import socket
import sys
import threading
from pathlib import Path
from typing import Any, cast

import pytest

from aec_bench.harness.hydraulic_review_prime.endpoint import (
    HYDRAULIC_REVIEW_CAPABILITY_ENV,
    HYDRAULIC_REVIEW_SOCKET_ENV,
)
from aec_bench.harness.hydraulic_review_prime.lifecycle import install_hydraulic_review_skill
from aec_bench.lifecycles.runtime.lifecycle import read_evidence_lifecycle_state
from aec_bench.lifecycles.stormwater_design.hydraulic_review_smoke import write_hydraulic_review_smoke_submission


def _load_client(case: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    install_hydraulic_review_skill(case.actor)
    monkeypatch.syspath_prepend(str(case.actor))
    sys.modules.pop("hydraulic_review", None)
    return importlib.import_module("hydraulic_review")


def _raw_call(socket_path: str, payload: object) -> dict[str, Any]:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.connect(socket_path)
        client.sendall(json.dumps(payload).encode("utf-8") + b"\n")
        response = client.makefile("rb").readline()
    return cast(dict[str, Any], json.loads(response))


@pytest.mark.asyncio
async def test_installed_client_uses_all_six_calls_and_preserves_operation_identity(
    active_checkpoint: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    case = active_checkpoint
    client = _load_client(case, monkeypatch)
    with case.endpoint:
        environment = case.endpoint.connection_environment()
        monkeypatch.setenv(HYDRAULIC_REVIEW_SOCKET_ENV, environment[HYDRAULIC_REVIEW_SOCKET_ENV])
        monkeypatch.setenv(HYDRAULIC_REVIEW_CAPABILITY_ENV, environment[HYDRAULIC_REVIEW_CAPABILITY_ENV])

        capabilities = await client.capabilities()
        observation = await client.observe()
        files = await client.list_files(".")
        instruction = await client.read_file("instruction.md")
        source_hash = observation["current_source"]["visible_source_state_sha256"]
        operation = await client.execute_operation(
            "hydrology.design-10yr",
            source_hash,
            "Calculate the declared design hydrology.",
        )
        artifact = await client.read_file(operation["artifacts"][0]["path"])

        candidate = tmp_path / "candidate.json"
        write_hydraulic_review_smoke_submission(
            case.package,
            case.run,
            case.request.checkpoint_id,
            case.request.session_id,
            candidate,
        )
        submission = json.loads(candidate.read_text(encoding="utf-8"))
        offer = await client.offer_submission(submission)
        retry = await client.offer_submission(submission)

        assert capabilities["operations"] == [
            "capabilities",
            "observe",
            "list_files",
            "read_file",
            "execute_operation",
            "offer_submission",
        ]
        assert observation["checkpoint_id"] == "baseline_analysis"
        assert {"checkpoints", "inbox", "instruction.md", "operations"}.issubset(files["entries"])
        assert instruction["content"] == case.request.instruction
        assert operation["operation_id"] == "hydrology.design-10yr"
        assert artifact["path"] == operation["artifacts"][0]["path"]
        assert offer == retry
        assert case.endpoint.offered_submission == submission
        assert not Path(case.request.submission_path).exists()

    assert not Path(environment[HYDRAULIC_REVIEW_SOCKET_ENV]).exists()
    state = read_evidence_lifecycle_state(case.package, case.run, operation_resolver=case.resolver)
    baseline = next(item for item in state["checkpoint_runs"] if item["checkpoint_id"] == "baseline_analysis")
    assert {item["session_id"] for item in baseline["operation_actions"]} == {case.request.session_id}
    assert all(
        name in dir(client)
        for name in ("capabilities", "observe", "list_files", "read_file", "execute_operation", "offer_submission")
    )
    assert tuple(inspect.signature(client.execute_operation).parameters) == (
        "operation_id",
        "visible_source_state_sha256",
        "reason",
    )


@pytest.mark.asyncio
async def test_endpoint_rejects_selectors_conflicts_and_private_paths_without_leaking_evidence(
    active_checkpoint: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    case = active_checkpoint
    client = _load_client(case, monkeypatch)
    private_file = case.package / "hidden" / "variant.json"
    symlink = case.run / "workspace" / "inbox" / "baseline_analysis" / "private-link.json"
    symlink.symlink_to(private_file)
    with case.endpoint:
        environment = case.endpoint.connection_environment()
        monkeypatch.setenv(HYDRAULIC_REVIEW_SOCKET_ENV, environment[HYDRAULIC_REVIEW_SOCKET_ENV])
        monkeypatch.setenv(HYDRAULIC_REVIEW_CAPABILITY_ENV, environment[HYDRAULIC_REVIEW_CAPABILITY_ENV])
        forbidden = _raw_call(
            environment[HYDRAULIC_REVIEW_SOCKET_ENV],
            {
                "capability": environment[HYDRAULIC_REVIEW_CAPABILITY_ENV],
                "request": {"operation": "observe", "run_id": str(case.run)},
            },
        )
        unauthorized = _raw_call(
            environment[HYDRAULIC_REVIEW_SOCKET_ENV],
            {"capability": "wrong-secret", "request": {"operation": "observe"}},
        )
        for path in (
            "../state.json",
            str(private_file),
            "inbox\\baseline_analysis\\notice.md",
            ".private",
            "inbox/revision_analysis/notice.md",
            "inbox/baseline_analysis/private-link.json",
        ):
            with pytest.raises(client.LifecycleError):
                await client.read_file(path)

        candidate = tmp_path / "candidate.json"
        write_hydraulic_review_smoke_submission(
            case.package,
            case.run,
            case.request.checkpoint_id,
            case.request.session_id,
            candidate,
        )
        submission = json.loads(candidate.read_text(encoding="utf-8"))
        await client.offer_submission(submission)
        changed = dict(submission)
        changed["readiness_decision"] = "changed"
        with pytest.raises(client.LifecycleError, match="different offered submission"):
            await client.offer_submission(changed)

    assert forbidden == {"error": {"code": "request-invalid", "detail": "request does not match the endpoint contract"}}
    assert unauthorized == {"error": {"code": "endpoint-unauthorized", "detail": "endpoint capability is invalid"}}
    evidence = (tmp_path / "endpoint-evidence.jsonl").read_text(encoding="utf-8")
    assert environment[HYDRAULIC_REVIEW_CAPABILITY_ENV] not in evidence
    assert "wrong-secret" not in evidence
    assert str(case.package) not in evidence
    assert str(case.run) not in evidence
    assert str(private_file) not in evidence
    assert '"run_id"' not in evidence
    assert '"hidden"' not in evidence


def test_endpoint_close_waits_for_an_active_actor_request(
    active_checkpoint: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = active_checkpoint
    entered = threading.Event()
    release = threading.Event()
    closed = threading.Event()
    results: list[dict[str, Any]] = []
    errors: list[BaseException] = []
    original_dispatch = case.endpoint._dispatch

    def blocked_dispatch(request: Any) -> dict[str, Any]:
        entered.set()
        if not release.wait(timeout=5):
            raise TimeoutError("test did not release the active endpoint request")
        return cast(dict[str, Any], original_dispatch(request))

    def call_endpoint(environment: dict[str, str]) -> None:
        try:
            results.append(
                _raw_call(
                    environment[HYDRAULIC_REVIEW_SOCKET_ENV],
                    {
                        "capability": environment[HYDRAULIC_REVIEW_CAPABILITY_ENV],
                        "request": {"operation": "observe"},
                    },
                )
            )
        except BaseException as exc:
            errors.append(exc)

    def close_endpoint() -> None:
        try:
            case.endpoint.close()
        except BaseException as exc:
            errors.append(exc)
        finally:
            closed.set()

    monkeypatch.setattr(case.endpoint, "_dispatch", blocked_dispatch)
    case.endpoint.start()
    environment = case.endpoint.connection_environment()
    caller = threading.Thread(target=call_endpoint, args=(environment,))
    closer = threading.Thread(target=close_endpoint)
    caller.start()
    assert entered.wait(timeout=2)
    closer.start()
    try:
        assert not closed.wait(timeout=0.75)
    finally:
        release.set()
        caller.join(timeout=3)
        closer.join(timeout=3)

    assert not caller.is_alive()
    assert not closer.is_alive()
    assert not errors
    assert results[0]["result"]["checkpoint_id"] == case.request.checkpoint_id
