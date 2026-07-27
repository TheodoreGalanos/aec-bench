# ABOUTME: Starts the credentialed proposal provider broker before child execution.
# ABOUTME: Replaces the bootstrap process with an uncredentialed RLM entrypoint on Linux.

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from aec_bench.adapters.rlm.providers import (
    detect_provider,
    make_rlm_client,
)
from aec_bench.contracts.provider_broker import ProviderBrokerPolicy
from aec_bench.harness.execution_payload import (
    execution_request_sha256,
    read_execution_bundle,
)
from aec_bench.harness.provider_broker import (
    ProviderBrokerError,
    build_broker_agent_environment,
    serve_provider_broker,
)

_SUPPORTED_PROVIDERS = frozenset(
    {
        "anthropic",
        "azure",
        "bedrock",
        "together",
    }
)
_SOCKET_READY_TIMEOUT_SECONDS = 5.0


def run_provider_broker_bootstrap(
    *,
    bundle_path: Path,
    result_path: Path,
    policy_path: Path,
    socket_path: Path,
    receipt_path: Path,
) -> None:
    """Fork the broker, then exec the exact entrypoint under a scrubbed env."""
    if not sys.platform.startswith("linux"):
        raise ProviderBrokerError(
            "proposal provider broker execution requires Linux SO_PEERCRED",
        )
    bundle = read_execution_bundle(bundle_path)
    policy = ProviderBrokerPolicy.model_validate_json(
        policy_path.read_text(encoding="utf-8"),
    )
    if bundle.execution.adapter_kind != policy.adapter_kind:
        raise ProviderBrokerError(
            "provider broker policy does not authorize this adapter",
        )
    if bundle.execution.resolved_model != policy.model:
        raise ProviderBrokerError(
            "provider broker policy does not authorize this model",
        )
    if execution_request_sha256(bundle) != policy.execution_request_sha256:
        raise ProviderBrokerError(
            "provider broker policy does not bind this execution request",
        )
    provider = detect_provider(policy.model)
    if provider not in _SUPPORTED_PROVIDERS:
        raise ProviderBrokerError(
            f"provider broker does not support provider routing {provider!r}",
        )
    broker_pid = os.fork()
    if broker_pid == 0:
        exit_code = 0
        try:
            prompt_cache = bundle.request.configuration.get(
                "prompt_cache",
                False,
            )
            if not isinstance(prompt_cache, bool):
                raise ProviderBrokerError("prompt_cache must be a boolean")
            client = make_rlm_client(
                policy.model,
                cache=prompt_cache,
                max_tokens=policy.max_total_tokens,
            )
            serve_provider_broker(
                socket_path=socket_path,
                expected_peer_pid=os.getppid(),
                policy=policy,
                client=client,
                receipt_path=receipt_path,
            )
        except BaseException:
            exit_code = 1
        finally:
            os._exit(exit_code)

    _wait_for_broker_socket(
        socket_path=socket_path,
        broker_pid=broker_pid,
    )
    child_environment = build_broker_agent_environment(
        inherited_environment=os.environ,
        provider_environment={},
        socket_path=socket_path,
        policy_sha256=policy.content_sha256,
    )
    argv = [
        sys.executable,
        "-m",
        "aec_bench.harness.execution_entrypoint",
        "--bundle",
        str(bundle_path),
        "--result",
        str(result_path),
    ]
    os.execvpe(sys.executable, argv, child_environment)


def _wait_for_broker_socket(
    *,
    socket_path: Path,
    broker_pid: int,
) -> None:
    deadline = time.monotonic() + _SOCKET_READY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if socket_path.exists():
            return
        exited_pid, status = os.waitpid(broker_pid, os.WNOHANG)
        if exited_pid == broker_pid:
            raise ProviderBrokerError(
                f"provider broker exited before its socket became ready (status={status})",
            )
        time.sleep(0.01)
    raise ProviderBrokerError("provider broker socket did not become ready")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--policy", required=True)
    parser.add_argument("--socket", required=True)
    parser.add_argument("--receipt", required=True)
    args = parser.parse_args()
    run_provider_broker_bootstrap(
        bundle_path=Path(args.bundle),
        result_path=Path(args.result),
        policy_path=Path(args.policy),
        socket_path=Path(args.socket),
        receipt_path=Path(args.receipt),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
