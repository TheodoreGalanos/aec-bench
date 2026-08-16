# ABOUTME: Tests shared provider selection and credential allowlisting for adapter execution.
# ABOUTME: Proves provider identity is stable while unselected host credentials stay outside the runtime.

import pytest

from aec_bench.adapters.provider_routing import provider_environment, provider_for_execution


@pytest.mark.parametrize(
    ("adapter_kind", "model_name", "client_payload", "expected"),
    [
        ("direct", "gpt-4.1-mini", None, "azure"),
        ("rlm", "deepseek:deepseek-chat", None, "deepseek"),
        ("tool_loop", "openai:gpt-5.4", None, "openai"),
        ("direct", "ignored", {"client_kind": "replay", "payload": {}}, None),
    ],
)
def test_provider_selection_aligns_existing_adapter_routes(
    adapter_kind: str,
    model_name: str,
    client_payload: object,
    expected: str | None,
) -> None:
    assert (
        provider_for_execution(
            adapter_kind=adapter_kind,
            model_name=model_name,
            client_payload=client_payload,
        )
        == expected
    )


def test_provider_environment_returns_only_the_selected_deepseek_route() -> None:
    environment = provider_environment(
        "deepseek",
        host_environment={
            "DEEPSEEK_API_KEY": "selected-key",
            "DEEPSEEK_BASE_URL": "https://gateway.example/deepseek",
            "AZURE_OPENAI_API_KEY": "unselected-key",
            "AZURE_OPENAI_ENDPOINT": "https://unselected.example",
        },
    )

    assert environment == {
        "DEEPSEEK_API_KEY": "selected-key",
        "DEEPSEEK_BASE_URL": "https://gateway.example/deepseek",
    }
