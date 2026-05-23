# ABOUTME: Tests for adapter construction from experiment agent configuration.
# ABOUTME: Covers direct provider client specs flowing from AgentConfig into
# ABOUTME: remote execution bundles.

from aec_bench.adapters.factory import build_remote_adapter
from aec_bench.contracts.experiment_manifest import AgentConfig, ClientConfig


def test_build_remote_adapter_from_anthropic_direct_config() -> None:
    adapter = build_remote_adapter(
        AgentConfig(
            name="direct-anthropic",
            adapter="direct",
            model="claude-sonnet-4-20250514",
            client=ClientConfig(
                kind="anthropic_api",
                settings={
                    "api_key_env": "ANTHROPIC_API_KEY",
                    "max_tokens": 4096,
                },
            ),
            parameters={"temperature": 0.1},
        )
    )

    execution = adapter.serialize_execution()

    assert adapter.adapter_name() == "direct-anthropic"
    assert adapter.resolved_model() == "claude-sonnet-4-20250514"
    assert execution.adapter_kind == "direct"
    assert execution.payload == {
        "client": {
            "client_kind": "anthropic_api",
            "payload": {
                "api_key_env": "ANTHROPIC_API_KEY",
                "max_tokens": 4096,
            },
        }
    }


def test_build_remote_adapter_from_azure_direct_config() -> None:
    adapter = build_remote_adapter(
        AgentConfig(
            name="direct-azure",
            adapter="direct",
            model="gpt-4.1-mini",
            client=ClientConfig(
                kind="azure_openai_chat",
                settings={
                    "api_key_env": "AZURE_OPENAI_API_KEY",
                    "endpoint_env": "AZURE_OPENAI_ENDPOINT",
                    "deployment": "gpt-4.1-mini",
                    "api_version": "2024-10-21",
                    "max_tokens": 2048,
                },
            ),
        )
    )

    execution = adapter.serialize_execution()

    assert execution.payload == {
        "client": {
            "client_kind": "azure_openai_chat",
            "payload": {
                "api_key_env": "AZURE_OPENAI_API_KEY",
                "endpoint_env": "AZURE_OPENAI_ENDPOINT",
                "deployment": "gpt-4.1-mini",
                "api_version": "2024-10-21",
                "max_tokens": 2048,
            },
        }
    }
