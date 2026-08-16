# ABOUTME: Tests fail-closed DeepSeek Harness treatment and request configuration.
# ABOUTME: Keeps unsupported tools, limits, and optional commit behavior out of model execution.

import pytest

from aec_bench.adapters.base import AdapterRequest
from aec_bench.adapters.deepseek_harness.config import (
    DeepSeekHarnessConfigurationError,
    DeepSeekHarnessSettings,
    baseline_cordis_template,
    harness_provider_route,
    tool_gateway_cordis_template,
    validate_deepseek_request,
)


@pytest.mark.parametrize(
    ("model_name", "provider", "resolved_model"),
    [
        ("azure:deepseek-v4-flash", "azure", "deepseek-v4-flash"),
        ("deepseek:deepseek-v4-flash", "deepseek", "deepseek-v4-flash"),
    ],
)
def test_settings_accept_the_bundle_provider_and_model(
    model_name: str,
    provider: str,
    resolved_model: str,
) -> None:
    settings = DeepSeekHarnessSettings.from_execution_payload(
        model_name=model_name,
        payload={"provider": provider},
    )

    assert settings.provider == provider
    assert settings.model == resolved_model
    assert settings.requested_model == model_name


@pytest.mark.parametrize(
    ("provider", "route", "plugin", "excluded_plugin"),
    [
        ("azure", "azure", "@deepseek-ai/dsh-llm-pi-ai", "@deepseek-ai/dsh-llm-deepseek"),
        ("deepseek", "deepseek-official", "@deepseek-ai/dsh-llm-deepseek", "@deepseek-ai/dsh-llm-pi-ai"),
    ],
)
def test_baseline_profile_uses_the_selected_provider_wire_route(
    provider: str,
    route: str,
    plugin: str,
    excluded_plugin: str,
) -> None:
    profile = baseline_cordis_template(provider).read_text(encoding="utf-8")

    assert "apiKeyEnv: DSH_API_KEY" in profile
    assert "baseURL: !!js process.env.DSH_BASE_URL" in profile
    assert plugin in profile
    assert excluded_plugin not in profile
    assert harness_provider_route(provider) == route
    assert "AZURE_OPENAI_API_KEY" not in profile
    assert "DEEPSEEK_API_KEY" not in profile


@pytest.mark.parametrize("provider", ["azure", "deepseek"])
def test_lifecycle_profile_leaves_the_model_tool_surface_to_the_aec_plugin(provider: str) -> None:
    profile = tool_gateway_cordis_template(provider).read_text(encoding="utf-8")

    assert "@deepseek-ai/dsh-sdk-jsonrpc-server" in profile
    assert "@deepseek-ai/dsh-agent-spine-demo" in profile
    assert "@deepseek-ai/dsh-session-persistence-jsonl" in profile
    assert "@deepseek-ai/dsh-tool-fs" not in profile
    assert "@deepseek-ai/dsh-tool-bash-persistent" not in profile
    assert "@deepseek-ai/dsh-terminal-bash" not in profile


def test_settings_reject_execution_payload_model_drift() -> None:
    with pytest.raises(DeepSeekHarnessConfigurationError, match="model is owned by the execution bundle"):
        DeepSeekHarnessSettings.from_execution_payload(
            model_name="deepseek:deepseek-v4-flash",
            payload={"provider": "deepseek", "model": "other-model"},
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"sdk_version": "0.1.0rc6"},
        {"runtime_bin": "/tmp/deepseek-harness"},
        {"cordis_template": "/tmp/custom.cordis.yml"},
        {"tool_profile": "coding"},
        {"tool_presentation": "native"},
        {"sandbox_mode": "workspace-write"},
        {"require_full_sandbox_enforcement": True},
        {"allow_subagents": True},
        {"allow_workflows": True},
        {"allow_code_mode": True},
        {"retain_all_notifications": False},
        {"retain_session_jsonl": False},
        {"output_commit_mode": "required"},
    ],
)
def test_settings_reject_fixed_treatment_overrides(payload: dict[str, object]) -> None:
    with pytest.raises(DeepSeekHarnessConfigurationError, match="Extra inputs are not permitted"):
        DeepSeekHarnessSettings.from_execution_payload(
            model_name="deepseek:deepseek-v4-flash",
            payload={"provider": "deepseek", **payload},
        )


def test_settings_reject_an_unsupported_provider() -> None:
    with pytest.raises(DeepSeekHarnessConfigurationError, match="unsupported DeepSeek Harness provider"):
        DeepSeekHarnessSettings.from_execution_payload(
            model_name="bedrock:deepseek-v4-flash",
            payload={"provider": "bedrock"},
        )


@pytest.mark.parametrize(
    ("configuration", "message"),
    [
        ({"max_turns": 2}, "max_turns"),
        ({"max_tool_calls": 2}, "max_tool_calls"),
        ({"max_context_tokens": 8_000}, "max_context_tokens"),
    ],
)
def test_request_rejects_limits_without_typed_terminal_enforcement(
    configuration: dict[str, int],
    message: str,
) -> None:
    with pytest.raises(DeepSeekHarnessConfigurationError, match=message):
        validate_deepseek_request(AdapterRequest(instruction="Work", configuration=configuration))


def test_request_accepts_positive_safe_max_tokens() -> None:
    validate_deepseek_request(AdapterRequest(instruction="Work", configuration={"max_tokens": 512}))


@pytest.mark.parametrize("value", [True, 0, -1, 1.5, "512", 2**53])
def test_request_rejects_invalid_max_tokens(value: object) -> None:
    with pytest.raises(DeepSeekHarnessConfigurationError, match="max_tokens must be a positive safe integer"):
        validate_deepseek_request(AdapterRequest(instruction="Work", configuration={"max_tokens": value}))


def test_request_rejects_task_tools_before_runtime_start() -> None:
    from aec_bench.contracts.task_definition import ToolSpec

    request = AdapterRequest(
        instruction="Work",
        tools=[ToolSpec(name="custom", source="builtin", description="Unsupported bridge")],
    )

    with pytest.raises(DeepSeekHarnessConfigurationError, match="must match its configured native tool gateway"):
        validate_deepseek_request(request)


def test_request_accepts_only_the_exact_configured_native_tools() -> None:
    from aec_bench.contracts.task_definition import ToolSpec

    request = AdapterRequest(
        instruction="Work",
        tools=[
            ToolSpec(name="list_workspace", source="builtin", description="List files"),
            ToolSpec(name="submit_checkpoint", source="builtin", description="Submit checkpoint"),
        ],
        configuration={"max_tokens": 512, "timeout_sec": 30},
    )

    validate_deepseek_request(
        request,
        native_tool_names=frozenset({"list_workspace", "submit_checkpoint"}),
    )

    with pytest.raises(DeepSeekHarnessConfigurationError, match="requested: list_workspace, submit_checkpoint"):
        validate_deepseek_request(request, native_tool_names=frozenset({"list_workspace"}))


def test_request_rejects_output_commit_with_native_tools() -> None:
    from aec_bench.contracts.task_definition import ToolSpec

    request = AdapterRequest(
        instruction="Work",
        output_path="output.md",
        tools=[ToolSpec(name="submit_checkpoint", source="builtin", description="Submit checkpoint")],
        configuration={
            "output_completion_commit": True,
            "output_completion_contract": {
                "schema_version": "aecbench.output-completion-contract.v1",
                "output_path": "output.md",
                "format": "markdown_final_fenced_json",
                "required_top_level_keys": ["summary"],
                "require_single_final_json_block": True,
            },
        },
    )

    with pytest.raises(DeepSeekHarnessConfigurationError, match="cannot be combined"):
        validate_deepseek_request(request, native_tool_names=frozenset({"submit_checkpoint"}))


def test_request_accepts_shared_required_output_commit_configuration() -> None:
    request = AdapterRequest(
        instruction="Work",
        output_path="output.md",
        configuration={
            "output_completion_commit": True,
            "output_completion_contract": {
                "schema_version": "aecbench.output-completion-contract.v1",
                "output_path": "output.md",
                "format": "markdown_final_fenced_json",
                "required_top_level_keys": ["summary"],
                "require_single_final_json_block": True,
            },
        },
    )

    validate_deepseek_request(request)


def test_request_rejects_required_output_commit_without_contract() -> None:
    request = AdapterRequest(
        instruction="Work",
        configuration={"output_completion_commit": True},
    )

    with pytest.raises(DeepSeekHarnessConfigurationError, match="requires an output completion contract"):
        validate_deepseek_request(request)
