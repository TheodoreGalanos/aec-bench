# ABOUTME: Exposes the uncredentialed client and stable provider-broker boundary.
# ABOUTME: Scrubs child environments while delegating effect handling to the broker runtime.

from __future__ import annotations

import os
import socket
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from aec_bench.adapters.rlm.client import (
    RlmCompletionResponse,
    RlmMessage,
)
from aec_bench.contracts.provider_broker import (
    ProviderBrokerCallPlane,
    ProviderBrokerReceipt,
)
from aec_bench.harness.provider_broker_runtime import (
    ProviderBrokerError as ProviderBrokerError,
)
from aec_bench.harness.provider_broker_runtime import (
    ProviderBrokerReady as ProviderBrokerReady,
)
from aec_bench.harness.provider_broker_runtime import (
    _encode_payload,
    _message_payload,
    _receive_payload,
    _response_from_payload,
)
from aec_bench.harness.provider_broker_runtime import (
    disable_broker_process_dumpability as disable_broker_process_dumpability,
)
from aec_bench.harness.provider_broker_runtime import (
    serve_provider_broker as serve_provider_broker,
)

_SOCKET_CONNECT_TIMEOUT_SECONDS = 5.0
_SAFE_CHILD_ENVIRONMENT_KEYS = frozenset(
    {
        "HOME",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "PATH",
        "PYTHONPATH",
        "SSL_CERT_DIR",
        "SSL_CERT_FILE",
        "TZ",
    },
)
_BROKER_SOCKET_ENV = "AEC_BENCH_PROVIDER_BROKER_SOCKET"
_BROKER_POLICY_ENV = "AEC_BENCH_PROVIDER_BROKER_POLICY_SHA256"


class BrokeredRlmClient:
    """RLM client that can reach a provider only through a local policy broker."""

    def __init__(
        self,
        *,
        socket_path: Path,
        policy_sha256: str,
        call_plane: ProviderBrokerCallPlane = ProviderBrokerCallPlane.MAIN,
    ) -> None:
        self._socket_path = Path(socket_path)
        self._policy_sha256 = policy_sha256
        self._call_plane = ProviderBrokerCallPlane(call_plane)
        self._receipt: ProviderBrokerReceipt | None = None

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
        *,
        call_plane: ProviderBrokerCallPlane = ProviderBrokerCallPlane.MAIN,
    ) -> BrokeredRlmClient | None:
        """Build the broker client only when both pinned environment fields exist."""
        values = environment if environment is not None else os.environ
        socket_value = values.get(_BROKER_SOCKET_ENV)
        policy_sha256 = values.get(_BROKER_POLICY_ENV)
        if socket_value is None and policy_sha256 is None:
            return None
        if not socket_value or not policy_sha256:
            raise ProviderBrokerError(
                "provider broker socket and policy digest must be configured together",
            )
        return cls(
            socket_path=Path(socket_value),
            policy_sha256=policy_sha256,
            call_plane=call_plane,
        )

    @property
    def call_plane(self) -> ProviderBrokerCallPlane:
        """Return the immutable metering plane attached to this client."""
        return self._call_plane

    def for_call_plane(
        self,
        call_plane: ProviderBrokerCallPlane,
    ) -> BrokeredRlmClient:
        """Build a sibling client whose requests use one explicit metering plane."""
        return type(self)(
            socket_path=self._socket_path,
            policy_sha256=self._policy_sha256,
            call_plane=call_plane,
        )

    def generate(
        self,
        *,
        model: str,
        messages: list[RlmMessage],
        system_prompt: str | None,
        temperature: float | None = None,
    ) -> RlmCompletionResponse:
        payload: dict[str, Any] = {
            "operation": "generate",
            "policy_sha256": self._policy_sha256,
            "call_plane": self._call_plane.value,
            "model": model,
            "messages": [_message_payload(message) for message in messages],
            "system_prompt": system_prompt,
            "temperature": temperature,
        }
        return _response_from_payload(self._request(payload))

    def generate_with_tools(
        self,
        *,
        model: str,
        messages: list[RlmMessage],
        system_prompt: str | None,
        tool_name: str,
        tool_description: str,
        tool_parameters_schema: dict[str, Any],
    ) -> RlmCompletionResponse:
        payload: dict[str, Any] = {
            "operation": "generate_with_tools",
            "policy_sha256": self._policy_sha256,
            "call_plane": self._call_plane.value,
            "model": model,
            "messages": [_message_payload(message) for message in messages],
            "system_prompt": system_prompt,
            "tool_name": tool_name,
            "tool_description": tool_description,
            "tool_parameters_schema": tool_parameters_schema,
        }
        return _response_from_payload(self._request(payload))

    def finalize(self) -> ProviderBrokerReceipt:
        """Close broker authority and return its immutable metering receipt."""
        if self._receipt is not None:
            return self._receipt
        payload = self._request(
            {
                "operation": "finalize",
                "policy_sha256": self._policy_sha256,
            },
        )
        try:
            receipt = ProviderBrokerReceipt.model_validate(payload["receipt"])
        except (KeyError, TypeError, ValueError) as error:
            raise ProviderBrokerError(
                f"provider broker returned malformed final evidence: {error}",
            ) from error
        self._receipt = receipt
        return receipt

    def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        encoded = _encode_payload(payload)
        deadline = time.monotonic() + _SOCKET_CONNECT_TIMEOUT_SECONDS
        connection = _connect_to_broker(
            socket_path=self._socket_path,
            deadline=deadline,
        )
        try:
            connection.sendall(encoded)
            connection.shutdown(socket.SHUT_WR)
            response = _receive_payload(connection)
        finally:
            connection.close()
        if not isinstance(response, dict):
            raise ProviderBrokerError("provider broker response must be an object")
        return cast(dict[str, Any], response)


def _connect_to_broker(
    *,
    socket_path: Path,
    deadline: float,
) -> socket.socket:
    while True:
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            connection.connect(str(socket_path))
        except (FileNotFoundError, ConnectionRefusedError) as error:
            connection.close()
            if time.monotonic() >= deadline:
                raise ProviderBrokerError(
                    "provider broker socket did not become ready",
                ) from error
            time.sleep(0.01)
        else:
            return connection


def build_broker_agent_environment(
    *,
    inherited_environment: Mapping[str, str],
    provider_environment: Mapping[str, str],
    socket_path: Path,
    policy_sha256: str,
) -> dict[str, str]:
    """Build an allowlisted environment for the uncredentialed RLM process."""
    environment = {
        key: value
        for key, value in inherited_environment.items()
        if key in _SAFE_CHILD_ENVIRONMENT_KEYS or key.startswith("LC_")
    }
    provider_values = frozenset(value for value in provider_environment.values() if value)
    for key, value in tuple(environment.items()):
        if key in provider_environment or value in provider_values:
            environment.pop(key, None)
    environment[_BROKER_SOCKET_ENV] = str(socket_path)
    environment[_BROKER_POLICY_ENV] = policy_sha256
    return environment
