# ABOUTME: Tests the out-of-process provider boundary used by proposal-owned RLM execution.
# ABOUTME: Proves credential isolation, exact model and budget enforcement, and receipt closure.

from __future__ import annotations

import hashlib
import json
import os
import socket
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from aec_bench.adapters.base import AdapterRequest, SerializedAdapterExecution
from aec_bench.adapters.rlm.client import (
    ReplayRlmClient,
    RlmCompletionResponse,
    RlmMessage,
    ToolCall,
)
from aec_bench.contracts.agent_output import AgentOutputStatus
from aec_bench.contracts.provider_broker import (
    ProviderBrokerCallPlane,
    ProviderBrokerCallReceipt,
    ProviderBrokerEffectUnknownCallReceipt,
    ProviderBrokerPolicy,
    ProviderBrokerReceipt,
    ProviderBrokerStatus,
)
from aec_bench.harness.execution_payload import (
    build_execution_bundle,
    execution_request_sha256,
    read_execution_result,
    write_execution_bundle,
)
from aec_bench.harness.provider_broker import (
    BrokeredRlmClient,
    build_broker_agent_environment,
    disable_broker_process_dumpability,
    serve_provider_broker,
)
from aec_bench.harness.provider_broker_bootstrap import (
    run_provider_broker_bootstrap,
)


def test_provider_broker_facade_preserves_runtime_api_identity() -> None:
    from aec_bench.harness import provider_broker as facade
    from aec_bench.harness import provider_broker_runtime as runtime

    assert facade.ProviderBrokerError is runtime.ProviderBrokerError
    assert facade.ProviderBrokerReady is runtime.ProviderBrokerReady
    assert facade.disable_broker_process_dumpability is runtime.disable_broker_process_dumpability
    assert facade.serve_provider_broker is runtime.serve_provider_broker


def test_agent_environment_cannot_inherit_provider_credentials(
    tmp_path: Path,
) -> None:
    secret = "bedrock-secret-canary"
    inherited = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": "/opt/aec_bench",
        "AWS_BEARER_TOKEN_BEDROCK": secret,
        "AWS_REGION": "ap-southeast-2",
        "ANTHROPIC_API_KEY": "unrelated-secret",
    }

    sanitized = build_broker_agent_environment(
        inherited_environment=inherited,
        provider_environment={
            "AWS_BEARER_TOKEN_BEDROCK": secret,
            "AWS_REGION": "ap-southeast-2",
        },
        socket_path=tmp_path / "provider.sock",
        policy_sha256="a" * 64,
    )

    assert sanitized["PATH"] == inherited["PATH"]
    assert sanitized["PYTHONPATH"] == "/opt/aec_bench"
    assert sanitized["AEC_BENCH_PROVIDER_BROKER_SOCKET"] == str(
        tmp_path / "provider.sock",
    )
    assert sanitized["AEC_BENCH_PROVIDER_BROKER_POLICY_SHA256"] == "a" * 64
    assert "AWS_BEARER_TOKEN_BEDROCK" not in sanitized
    assert "AWS_REGION" not in sanitized
    assert "ANTHROPIC_API_KEY" not in sanitized
    assert secret not in "\n".join(f"{key}={value}" for key, value in sanitized.items())


def test_broker_process_disables_linux_dumpability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[int, int, int, int, int]] = []

    def _prctl(
        operation: int,
        argument_1: int,
        argument_2: int,
        argument_3: int,
        argument_4: int,
    ) -> int:
        calls.append(
            (
                operation,
                argument_1,
                argument_2,
                argument_3,
                argument_4,
            ),
        )
        return 0

    libc = SimpleNamespace(prctl=_prctl)
    monkeypatch.setattr(
        "aec_bench.harness.provider_broker_runtime.sys.platform",
        "linux",
    )
    monkeypatch.setattr(
        "aec_bench.harness.provider_broker_runtime.ctypes.CDLL",
        lambda *_args, **_kwargs: libc,
    )

    disable_broker_process_dumpability()

    assert calls == [(4, 0, 0, 0, 0)]


def test_broker_pins_model_and_budget_and_returns_content_addressed_receipt(
    tmp_path: Path,
) -> None:
    socket_path = Path("/tmp") / (
        "aec-broker-" + hashlib.sha256(str(tmp_path).encode("utf-8")).hexdigest()[:16] + ".sock"
    )
    policy = ProviderBrokerPolicy(
        broker_id="broker.node.1",
        execution_request_sha256="b" * 64,
        adapter_kind="rlm",
        model="bedrock:anthropic.claude-sonnet-test",
        max_main_calls=1,
        max_auxiliary_calls=0,
        max_calls=1,
        max_total_tokens=100,
        max_cost_usd=1.0,
        timeout_seconds=60,
    )
    upstream = ReplayRlmClient(
        [
            RlmCompletionResponse(
                output_text="first",
                input_tokens=12,
                output_tokens=7,
            ),
        ],
    )
    ready = threading.Event()
    server_result: dict[str, object] = {}

    def _serve() -> None:
        server_result["receipt"] = serve_provider_broker(
            socket_path=socket_path,
            expected_peer_pid=os.getpid(),
            policy=policy,
            client=upstream,
            ready=ready,
        )

    server = threading.Thread(target=_serve, daemon=True)
    server.start()
    assert ready.wait(timeout=5)
    client = BrokeredRlmClient(
        socket_path=socket_path,
        policy_sha256=policy.content_sha256,
    )

    response = client.generate(
        model=policy.model,
        messages=[RlmMessage(role="user", content="solve")],
        system_prompt="stay exact",
    )
    denied = client.generate(
        model=policy.model,
        messages=[RlmMessage(role="user", content="spend twice")],
        system_prompt=None,
    )
    drift = client.generate(
        model="bedrock:wrong-model",
        messages=[RlmMessage(role="user", content="drift")],
        system_prompt=None,
    )
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as direct:
        direct.connect(str(socket_path))
        direct.sendall(b"{}")
        direct.shutdown(socket.SHUT_WR)
        direct_response = json.loads(direct.recv(65_536))
    receipt = client.finalize()
    server.join(timeout=5)

    assert response.output_text == "first"
    assert response.input_tokens == 12
    assert response.output_tokens == 7
    assert denied.error_message == "provider broker call budget exhausted"
    assert drift.error_message == "provider broker model is not authorized"
    assert direct_response["response"]["error_message"] == "provider broker operation is not authorized"
    assert receipt == server_result["receipt"]
    assert receipt.policy_sha256 == policy.content_sha256
    assert receipt.status == "completed"
    assert receipt.total_calls == 1
    assert receipt.denied_calls == 3
    assert receipt.total_input_tokens == 12
    assert receipt.total_output_tokens == 7
    assert len(receipt.calls) == 1
    assert receipt.calls[0].call_plane is ProviderBrokerCallPlane.MAIN
    assert receipt.calls[0].model == policy.model
    assert receipt.calls[0].method == "generate"
    tampered_call = receipt.calls[0].model_dump(mode="json")
    tampered_call["call_plane"] = ProviderBrokerCallPlane.AUXILIARY.value
    with pytest.raises(
        ValidationError,
        match="content_sha256 does not match",
    ):
        ProviderBrokerCallReceipt.model_validate(tampered_call)
    serialized = receipt.model_dump_json()
    assert "bedrock-secret-canary" not in serialized
    assert "credential" not in serialized.lower()
    assert "effect_unknown_calls" not in serialized


@pytest.mark.parametrize(
    ("limited_plane", "max_main_calls", "max_auxiliary_calls"),
    (
        (ProviderBrokerCallPlane.MAIN, 1, 2),
        (ProviderBrokerCallPlane.AUXILIARY, 2, 1),
    ),
)
def test_broker_enforces_main_and_auxiliary_call_budgets_independently(
    tmp_path: Path,
    limited_plane: ProviderBrokerCallPlane,
    max_main_calls: int,
    max_auxiliary_calls: int,
) -> None:
    socket_path = Path("/tmp") / (
        "aec-broker-planes-"
        + hashlib.sha256(
            f"{tmp_path}:{limited_plane.value}".encode(),
        ).hexdigest()[:16]
        + ".sock"
    )
    policy = ProviderBrokerPolicy(
        broker_id="broker.planes",
        execution_request_sha256="c" * 64,
        adapter_kind="rlm",
        model="bedrock:anthropic.claude-sonnet-test",
        max_main_calls=max_main_calls,
        max_auxiliary_calls=max_auxiliary_calls,
        max_calls=max_main_calls + max_auxiliary_calls,
        max_total_tokens=100,
        max_cost_usd=1.0,
        timeout_seconds=60,
    )
    upstream = ReplayRlmClient(
        [
            RlmCompletionResponse(output_text="limited", input_tokens=5, output_tokens=3),
            RlmCompletionResponse(output_text="other", input_tokens=4, output_tokens=2),
        ],
    )
    ready = threading.Event()

    server = threading.Thread(
        target=serve_provider_broker,
        kwargs={
            "socket_path": socket_path,
            "expected_peer_pid": os.getpid(),
            "policy": policy,
            "client": upstream,
            "ready": ready,
        },
        daemon=True,
    )
    server.start()
    assert ready.wait(timeout=5)
    main_client = BrokeredRlmClient(
        socket_path=socket_path,
        policy_sha256=policy.content_sha256,
        call_plane=ProviderBrokerCallPlane.MAIN,
    )
    auxiliary_client = main_client.for_call_plane(
        ProviderBrokerCallPlane.AUXILIARY,
    )

    clients = {
        ProviderBrokerCallPlane.MAIN: main_client,
        ProviderBrokerCallPlane.AUXILIARY: auxiliary_client,
    }
    limited_client = clients[limited_plane]
    other_plane = (
        ProviderBrokerCallPlane.AUXILIARY
        if limited_plane is ProviderBrokerCallPlane.MAIN
        else ProviderBrokerCallPlane.MAIN
    )
    other_client = clients[other_plane]
    limited = limited_client.generate(
        model=policy.model,
        messages=[RlmMessage(role="user", content="limited")],
        system_prompt=None,
    )
    denied_limited = limited_client.generate(
        model=policy.model,
        messages=[RlmMessage(role="user", content="second limited")],
        system_prompt=None,
    )
    other = other_client.generate(
        model=policy.model,
        messages=[RlmMessage(role="user", content="other")],
        system_prompt=None,
    )
    receipt = main_client.finalize()
    server.join(timeout=5)

    assert limited.output_text == "limited"
    assert denied_limited.error_message == (f"provider broker {limited_plane.value} call budget exhausted")
    assert other.output_text == "other"
    assert [call.call_plane for call in receipt.calls] == [
        limited_plane,
        other_plane,
    ]
    assert receipt.total_calls == 2
    assert receipt.denied_calls == 1


def test_broker_rejects_unbound_call_plane_before_provider_effect(
    tmp_path: Path,
) -> None:
    socket_path = Path("/tmp") / (
        "aec-broker-plane-spoof-" + hashlib.sha256(str(tmp_path).encode("utf-8")).hexdigest()[:16] + ".sock"
    )
    policy = ProviderBrokerPolicy(
        broker_id="broker.plane-spoof",
        execution_request_sha256="d" * 64,
        adapter_kind="rlm",
        model="bedrock:anthropic.claude-sonnet-test",
        max_main_calls=1,
        max_auxiliary_calls=0,
        max_calls=1,
        max_total_tokens=100,
        max_cost_usd=1.0,
        timeout_seconds=60,
    )
    upstream = ReplayRlmClient(
        [
            RlmCompletionResponse(
                output_text="only authorized call",
                input_tokens=5,
                output_tokens=3,
            ),
        ],
    )
    ready = threading.Event()
    server = threading.Thread(
        target=serve_provider_broker,
        kwargs={
            "socket_path": socket_path,
            "expected_peer_pid": os.getpid(),
            "policy": policy,
            "client": upstream,
            "ready": ready,
        },
        daemon=True,
    )
    server.start()
    assert ready.wait(timeout=5)

    malformed_request = {
        "operation": "generate",
        "policy_sha256": policy.content_sha256,
        "model": policy.model,
        "messages": [{"role": "user", "content": "spoof"}],
        "system_prompt": None,
        "temperature": None,
    }
    denied_messages: list[str | None] = []
    for call_plane in (None, "side-channel", "auxiliary"):
        request = dict(malformed_request)
        if call_plane is not None:
            request["call_plane"] = call_plane
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as direct:
            direct.connect(str(socket_path))
            direct.sendall(json.dumps(request).encode("utf-8"))
            direct.shutdown(socket.SHUT_WR)
            denied_messages.append(
                json.loads(direct.recv(65_536))["response"]["error_message"],
            )

    client = BrokeredRlmClient(
        socket_path=socket_path,
        policy_sha256=policy.content_sha256,
    )
    authorized = client.generate(
        model=policy.model,
        messages=[RlmMessage(role="user", content="authorized")],
        system_prompt=None,
    )
    receipt = client.finalize()
    server.join(timeout=5)

    assert denied_messages == [
        "provider broker call plane is not authorized",
        "provider broker call plane is not authorized",
        "provider broker auxiliary call budget exhausted",
    ]
    assert authorized.output_text == "only authorized call"
    assert receipt.total_calls == 1
    assert receipt.calls[0].call_plane is ProviderBrokerCallPlane.MAIN
    assert receipt.denied_calls == 3


class _EffectUnknownReplayClient(ReplayRlmClient):
    """Provider test double that loses terminal evidence after an admitted effect."""

    def __init__(self) -> None:
        super().__init__([])
        self.invocation_count = 0

    def generate(
        self,
        *,
        model: str,
        messages: list[RlmMessage],
        system_prompt: str | None,
        temperature: float | None = None,
    ) -> RlmCompletionResponse:
        del model, messages, system_prompt, temperature
        self.invocation_count += 1
        raise TimeoutError("provider-private-timeout-detail")


def test_broker_closes_with_typed_effect_unknown_evidence_after_provider_exception(
    tmp_path: Path,
) -> None:
    socket_path = Path("/tmp") / (
        "aec-broker-effect-unknown-" + hashlib.sha256(str(tmp_path).encode("utf-8")).hexdigest()[:16] + ".sock"
    )
    receipt_path = tmp_path / "provider-broker-receipt.json"
    policy = ProviderBrokerPolicy(
        broker_id="broker.effect-unknown",
        execution_request_sha256="e" * 64,
        adapter_kind="rlm",
        model="bedrock:anthropic.claude-sonnet-test",
        max_main_calls=1,
        max_auxiliary_calls=0,
        max_calls=1,
        max_total_tokens=100,
        max_cost_usd=1.0,
        timeout_seconds=1,
    )
    upstream = _EffectUnknownReplayClient()
    ready = threading.Event()
    server_result: dict[str, object] = {}

    def _serve() -> None:
        server_result["receipt"] = serve_provider_broker(
            socket_path=socket_path,
            expected_peer_pid=os.getpid(),
            policy=policy,
            client=upstream,
            ready=ready,
            receipt_path=receipt_path,
        )

    server = threading.Thread(target=_serve, daemon=True)
    server.start()
    assert ready.wait(timeout=5)
    client = BrokeredRlmClient(
        socket_path=socket_path,
        policy_sha256=policy.content_sha256,
    )

    response = client.generate(
        model=policy.model,
        messages=[RlmMessage(role="user", content="admitted")],
        system_prompt=None,
    )
    server.join(timeout=2)

    assert not server.is_alive()
    assert upstream.invocation_count == 1
    assert response.error_message == "provider broker effect outcome is unknown"
    receipt = ProviderBrokerReceipt.model_validate_json(
        receipt_path.read_text(encoding="utf-8"),
    )
    assert receipt == server_result["receipt"]
    assert receipt.status is ProviderBrokerStatus.EFFECT_UNKNOWN
    assert receipt.failure_reason == "provider broker effect outcome is unknown"
    assert receipt.total_calls == 1
    assert receipt.denied_calls == 0
    assert receipt.calls == ()
    assert len(receipt.effect_unknown_calls) == 1
    unknown = receipt.effect_unknown_calls[0]
    assert isinstance(unknown, ProviderBrokerEffectUnknownCallReceipt)
    assert unknown.call_index == 1
    assert unknown.call_plane is ProviderBrokerCallPlane.MAIN
    assert unknown.method == "generate"
    assert unknown.model == policy.model
    assert unknown.failure_code == "provider_effect_outcome_unknown"
    assert "provider-private-timeout-detail" not in receipt.model_dump_json()


def test_broker_persists_known_call_before_post_effect_transport_failure(
    tmp_path: Path,
) -> None:
    socket_path = Path("/tmp") / (
        "aec-broker-transport-" + hashlib.sha256(str(tmp_path).encode("utf-8")).hexdigest()[:16] + ".sock"
    )
    receipt_path = tmp_path / "provider-broker-receipt.json"
    policy = ProviderBrokerPolicy(
        broker_id="broker.transport",
        execution_request_sha256="f" * 64,
        adapter_kind="rlm",
        model="bedrock:anthropic.claude-sonnet-test",
        max_main_calls=1,
        max_auxiliary_calls=0,
        max_calls=1,
        max_total_tokens=100,
        max_cost_usd=1.0,
        timeout_seconds=1,
    )
    upstream = ReplayRlmClient(
        [
            RlmCompletionResponse(
                output_text="known response",
                input_tokens=4,
                output_tokens=2,
            ),
        ],
    )
    ready = threading.Event()
    server_result: dict[str, object] = {}

    def _serve() -> None:
        try:
            server_result["receipt"] = serve_provider_broker(
                socket_path=socket_path,
                expected_peer_pid=os.getpid(),
                policy=policy,
                client=upstream,
                ready=ready,
                receipt_path=receipt_path,
            )
        except BaseException as error:
            server_result["error"] = error

    server = threading.Thread(target=_serve, daemon=True)
    server.start()
    assert ready.wait(timeout=5)
    request = {
        "operation": "generate",
        "policy_sha256": policy.content_sha256,
        "call_plane": ProviderBrokerCallPlane.MAIN.value,
        "model": policy.model,
        "messages": [{"role": "user", "content": "disconnect"}],
        "system_prompt": None,
        "temperature": None,
    }
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as direct:
        direct.connect(str(socket_path))
        direct.sendall(json.dumps(request).encode("utf-8"))
        direct.shutdown(socket.SHUT_RDWR)
    server.join(timeout=2)

    assert not server.is_alive()
    assert "error" not in server_result
    receipt = ProviderBrokerReceipt.model_validate_json(
        receipt_path.read_text(encoding="utf-8"),
    )
    assert receipt == server_result["receipt"]
    assert receipt.status is ProviderBrokerStatus.FAILED
    assert receipt.failure_reason == ("provider broker response transport failed after provider effect")
    assert receipt.total_calls == 1
    assert receipt.denied_calls == 0
    assert len(receipt.calls) == 1
    assert receipt.calls[0].response_sha256
    assert receipt.effect_unknown_calls == ()


def test_broker_preserves_admission_error_precedence_before_provider_effect(
    tmp_path: Path,
) -> None:
    socket_path = Path("/tmp") / (
        "aec-broker-precedence-" + hashlib.sha256(str(tmp_path).encode("utf-8")).hexdigest()[:16] + ".sock"
    )
    policy = ProviderBrokerPolicy(
        broker_id="broker.precedence",
        execution_request_sha256="1" * 64,
        adapter_kind="rlm",
        model="bedrock:anthropic.claude-sonnet-test",
        max_main_calls=1,
        max_auxiliary_calls=0,
        max_calls=1,
        timeout_seconds=60,
    )
    upstream = ReplayRlmClient(
        [RlmCompletionResponse(output_text="first", input_tokens=1, output_tokens=1)],
    )
    ready = threading.Event()
    server = threading.Thread(
        target=serve_provider_broker,
        kwargs={
            "socket_path": socket_path,
            "expected_peer_pid": os.getpid(),
            "policy": policy,
            "client": upstream,
            "ready": ready,
        },
        daemon=True,
    )
    server.start()
    assert ready.wait(timeout=5)
    client = BrokeredRlmClient(
        socket_path=socket_path,
        policy_sha256=policy.content_sha256,
    )
    first = client.generate(
        model=policy.model,
        messages=[RlmMessage(role="user", content="first")],
        system_prompt=None,
    )
    malformed_after_exhaustion = {
        "operation": "generate",
        "policy_sha256": policy.content_sha256,
        "call_plane": ProviderBrokerCallPlane.MAIN.value,
        "model": policy.model,
        "messages": "not-a-message-list",
        "system_prompt": None,
        "temperature": {"not": "numeric"},
    }
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as direct:
        direct.connect(str(socket_path))
        direct.sendall(json.dumps(malformed_after_exhaustion).encode("utf-8"))
        direct.shutdown(socket.SHUT_WR)
        denied = json.loads(direct.recv(65_536))
    receipt = client.finalize()
    server.join(timeout=5)

    assert first.output_text == "first"
    assert denied["response"]["error_message"] == ("provider broker call budget exhausted")
    assert receipt.total_calls == 1
    assert receipt.denied_calls == 1


def test_broker_denies_decoding_failure_without_closing_provider_authority(
    tmp_path: Path,
) -> None:
    socket_path = Path("/tmp") / (
        "aec-broker-decode-" + hashlib.sha256(str(tmp_path).encode("utf-8")).hexdigest()[:16] + ".sock"
    )
    policy = ProviderBrokerPolicy(
        broker_id="broker.decode",
        execution_request_sha256="2" * 64,
        adapter_kind="rlm",
        model="bedrock:anthropic.claude-sonnet-test",
        max_main_calls=1,
        max_auxiliary_calls=0,
        max_calls=1,
        timeout_seconds=60,
    )
    upstream = ReplayRlmClient(
        [RlmCompletionResponse(output_text="authorized", input_tokens=1, output_tokens=1)],
    )
    ready = threading.Event()
    server = threading.Thread(
        target=serve_provider_broker,
        kwargs={
            "socket_path": socket_path,
            "expected_peer_pid": os.getpid(),
            "policy": policy,
            "client": upstream,
            "ready": ready,
        },
        daemon=True,
    )
    server.start()
    assert ready.wait(timeout=5)
    malformed = {
        "operation": "generate",
        "policy_sha256": policy.content_sha256,
        "call_plane": ProviderBrokerCallPlane.MAIN.value,
        "model": policy.model,
        "messages": "not-a-message-list",
        "system_prompt": None,
        "temperature": None,
    }
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as direct:
        direct.connect(str(socket_path))
        direct.sendall(json.dumps(malformed).encode("utf-8"))
        direct.shutdown(socket.SHUT_WR)
        denied = json.loads(direct.recv(65_536))
    client = BrokeredRlmClient(
        socket_path=socket_path,
        policy_sha256=policy.content_sha256,
    )
    authorized = client.generate(
        model=policy.model,
        messages=[RlmMessage(role="user", content="authorized")],
        system_prompt=None,
    )
    receipt = client.finalize()
    server.join(timeout=5)

    assert denied["response"]["error_message"] == ("provider broker denied malformed request")
    assert denied["broker_error"] == "messages must be a list"
    assert authorized.output_text == "authorized"
    assert receipt.status is ProviderBrokerStatus.COMPLETED
    assert receipt.total_calls == 1
    assert receipt.denied_calls == 1


@pytest.mark.skipif(
    not sys.platform.startswith("linux"),
    reason="production broker identity and dumpability controls are Linux-only",
)
def test_bootstrap_executes_model_authored_env_canary_without_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = "bedrock:us.anthropic.claude-sonnet-4-6"
    bundle = build_execution_bundle(
        execution=SerializedAdapterExecution(
            adapter_kind="rlm",
            adapter_name="proposal-node",
            resolved_model=model,
        ),
        request=AdapterRequest(
            instruction="Check your process environment, then finish.",
            configuration={
                "max_turns": 2,
                "prompt_cache": False,
            },
            output_path=str(tmp_path / "output.md"),
            output_format="markdown",
        ),
    )
    bundle_path = write_execution_bundle(
        path=tmp_path / "bundle.json",
        bundle=bundle,
    )
    result_path = tmp_path / "result.json"
    policy = ProviderBrokerPolicy(
        broker_id="broker.env-canary",
        execution_request_sha256=execution_request_sha256(bundle),
        adapter_kind="rlm",
        model=model,
        max_main_calls=2,
        max_auxiliary_calls=2,
        max_calls=4,
        max_total_tokens=100,
        max_cost_usd=1.0,
        timeout_seconds=30,
    )
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(policy.model_dump_json(), encoding="utf-8")
    socket_path = Path("/tmp") / f"aec-broker-e2e-{os.getpid()}.sock"
    receipt_path = tmp_path / "broker-receipt.json"
    upstream = ReplayRlmClient(
        [
            RlmCompletionResponse(
                input_tokens=10,
                output_tokens=8,
                tool_call=ToolCall(
                    name="repl",
                    code=(
                        "import os\n"
                        "assert os.environ.get("
                        "'AWS_BEARER_TOKEN_BEDROCK') is None\n"
                        "assert 'provider-secret-canary' not in "
                        "'\\n'.join(os.environ.values())\n"
                        "FINAL_VAR('credentials absent')"
                    ),
                    call_id="call.env-canary",
                ),
            ),
        ],
    )
    monkeypatch.setattr(
        "aec_bench.harness.provider_broker_bootstrap.make_rlm_client",
        lambda *_args, **_kwargs: upstream,
    )
    monkeypatch.setenv(
        "AWS_BEARER_TOKEN_BEDROCK",
        "provider-secret-canary",
    )
    monkeypatch.setenv("AWS_REGION", "ap-southeast-2")

    child_pid = os.fork()
    if child_pid == 0:
        try:
            run_provider_broker_bootstrap(
                bundle_path=bundle_path,
                result_path=result_path,
                policy_path=policy_path,
                socket_path=socket_path,
                receipt_path=receipt_path,
            )
        except BaseException:
            os._exit(1)
        os._exit(2)
    waited_pid, status = os.waitpid(child_pid, 0)

    assert waited_pid == child_pid
    assert os.waitstatus_to_exitcode(status) == 0
    result = read_execution_result(result_path)
    assert result.agent_output.status is AgentOutputStatus.COMPLETED
    broker_evidence = result.configuration_record["provider_broker"]
    assert broker_evidence["policy_sha256"] == policy.content_sha256
    receipt = broker_evidence["receipt"]
    assert receipt["total_calls"] == 1
    assert receipt["calls"][0]["call_plane"] == "main"
    assert receipt["total_input_tokens"] == 10
    assert receipt["total_output_tokens"] == 8
    persisted = result_path.read_bytes() + receipt_path.read_bytes()
    assert b"provider-secret-canary" not in persisted
