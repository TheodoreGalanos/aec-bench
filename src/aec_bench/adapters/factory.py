# ABOUTME: Agent-config-driven adapter factory for remote execution in aec-bench Python.
# ABOUTME: Builds serializable remote adapters from experiment manifest
# ABOUTME: agent configuration.

from dataclasses import dataclass

from aec_bench.adapters.base import (
    RemoteExecutableAdapter,
    SerializedAdapterExecution,
)
from aec_bench.contracts.experiment_manifest import AgentConfig


@dataclass(frozen=True)
class ConfiguredRemoteAdapter:
    name: str
    adapter_kind: str
    model: str
    client_kind: str
    client_settings: dict[str, object]

    def serialize_execution(self) -> SerializedAdapterExecution:
        return SerializedAdapterExecution(
            adapter_kind=self.adapter_kind,
            adapter_name=self.name,
            resolved_model=self.model,
            payload={
                "client": {
                    "client_kind": self.client_kind,
                    "payload": dict(self.client_settings),
                }
            },
        )

    def adapter_name(self) -> str:
        return self.name

    def resolved_model(self) -> str:
        return self.model


def build_remote_adapter(agent: AgentConfig) -> RemoteExecutableAdapter:
    if agent.client is None:
        msg = f"agent config missing client definition: {agent.name}"
        raise ValueError(msg)
    return ConfiguredRemoteAdapter(
        name=agent.name,
        adapter_kind=agent.adapter,
        model=agent.model,
        client_kind=agent.client.kind,
        client_settings=agent.client.settings,
    )
