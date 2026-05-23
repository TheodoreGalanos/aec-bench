# ABOUTME: Tests for ExperimentManifest and related selection/configuration contracts.
# ABOUTME: These tests define the validated experiment-planning boundary for the harness.

import pytest
from pydantic import ValidationError

from aec_bench.contracts.experiment_manifest import (
    AgentConfig,
    ClientConfig,
    ComputeConfig,
    ExperimentManifest,
    TaskSelector,
)
from aec_bench.contracts.task_definition import Difficulty, Lifecycle


def _build_manifest(**overrides: object) -> ExperimentManifest:
    payload: dict = {
        "experiment_id": "experiment-001",
        "name": "Modal smoke run",
        "description": "Validate trustworthy-trial path.",
        "tasks": TaskSelector(domains=["electrical"], difficulties=[Difficulty.MEDIUM]),
        "agents": [
            AgentConfig(
                name="sonnet-tool-loop",
                adapter="tool_loop",
                model="anthropic:claude-sonnet-4-20250514",
            )
        ],
        "compute": ComputeConfig(backend="modal"),
    }
    payload.update(overrides)
    return ExperimentManifest.model_validate(payload)


# --- Valid construction ---


def test_experiment_manifest_accepts_valid_payload() -> None:
    manifest = _build_manifest(
        agents=[
            AgentConfig(
                name="sonnet-tool-loop",
                adapter="tool_loop",
                model="anthropic:claude-sonnet-4-20250514",
                client=ClientConfig(kind="replay"),
                parameters={"max_turns": 20},
                system_prompt_file="prompts/workflow-audit.md",
            )
        ],
        compute=ComputeConfig(backend="modal", resource_limits={"cpu": 2}, timeout_override=900),
    )

    assert manifest.repetitions == 1
    assert manifest.tasks.lifecycle_filter == [Lifecycle.ACTIVE]


def test_agent_config_accepts_explicit_client_config() -> None:
    config = AgentConfig(
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
    )

    assert config.client is not None
    assert config.client.kind == "anthropic_api"
    assert config.client.settings["api_key_env"] == "ANTHROPIC_API_KEY"


# --- Rejection tests ---


def test_experiment_manifest_rejects_non_positive_repetitions() -> None:
    with pytest.raises(ValidationError):
        _build_manifest(repetitions=0)


def test_experiment_manifest_rejects_empty_agents_list() -> None:
    with pytest.raises(ValidationError, match="at least one agent"):
        _build_manifest(agents=[])


def test_experiment_manifest_rejects_blank_experiment_id() -> None:
    with pytest.raises(ValidationError):
        _build_manifest(experiment_id="   ")


def test_experiment_manifest_rejects_blank_name() -> None:
    with pytest.raises(ValidationError):
        _build_manifest(name="  ")


def test_task_selector_rejects_proposed_in_lifecycle_filter() -> None:
    with pytest.raises(ValidationError, match="proposed or retired"):
        TaskSelector(lifecycle_filter=[Lifecycle.PROPOSED])


def test_task_selector_rejects_retired_in_lifecycle_filter() -> None:
    with pytest.raises(ValidationError, match="proposed or retired"):
        TaskSelector(lifecycle_filter=[Lifecycle.RETIRED])


def test_task_selector_accepts_deprecated_in_lifecycle_filter() -> None:
    selector = TaskSelector(lifecycle_filter=[Lifecycle.DEPRECATED])

    assert Lifecycle.DEPRECATED in selector.lifecycle_filter


def test_agent_config_accepts_harness_as_adapter_synonym() -> None:
    """Users can write 'harness' instead of 'adapter' in experiment YAML."""
    config = AgentConfig.model_validate({"name": "agent", "harness": "tool_loop", "model": "gpt-4"})
    assert config.adapter == "tool_loop"


def test_agent_config_rejects_both_adapter_and_harness() -> None:
    """Providing both 'adapter' and 'harness' is ambiguous — reject it."""
    with pytest.raises(ValidationError, match="[Aa]dapter.*[Hh]arness|[Hh]arness.*[Aa]dapter"):
        AgentConfig.model_validate({"name": "agent", "adapter": "rlm", "harness": "tool_loop", "model": "gpt-4"})


def test_agent_config_adapter_field_still_works() -> None:
    """Original 'adapter' field must keep working unchanged."""
    config = AgentConfig(name="agent", adapter="direct", model="gpt-4")
    assert config.adapter == "direct"


def test_experiment_manifest_accepts_harness_in_agent_config() -> None:
    """Full manifest round-trip with 'harness' synonym in YAML-style dict."""
    raw = {
        "experiment_id": "exp-harness-test",
        "name": "Harness synonym test",
        "tasks": {"domains": ["electrical"]},
        "agents": [{"name": "sonnet", "harness": "rlm", "model": "claude-sonnet-4"}],
        "compute": {"backend": "modal"},
    }
    manifest = ExperimentManifest.model_validate(raw)
    assert manifest.agents[0].adapter == "rlm"


def test_agent_config_rejects_blank_model() -> None:
    with pytest.raises(ValidationError):
        AgentConfig(name="agent", adapter="direct", model="   ")


def test_compute_config_rejects_blank_backend() -> None:
    with pytest.raises(ValidationError):
        ComputeConfig(backend="  ")


# --- Round-trip serialization ---


def test_task_selector_accepts_dataset_field() -> None:
    selector = TaskSelector(dataset="my-suite@1.0.0")

    assert selector.dataset == "my-suite@1.0.0"


def test_task_selector_accepts_dataset_name_without_version() -> None:
    selector = TaskSelector(dataset="my-suite")

    assert selector.dataset == "my-suite"


def test_task_selector_defaults_dataset_to_none() -> None:
    selector = TaskSelector()

    assert selector.dataset is None


def test_experiment_manifest_roundtrip_serialization() -> None:
    original = _build_manifest(
        agents=[
            AgentConfig(
                name="sonnet",
                adapter="tool_loop",
                model="anthropic:claude-sonnet-4-20250514",
                client=ClientConfig(kind="anthropic_api", settings={"max_tokens": 4096}),
                parameters={"max_turns": 20},
                system_prompt_file="prompts/workflow-audit.md",
            ),
        ],
        compute=ComputeConfig(
            backend="modal",
            resource_limits={"cpu": 4, "memory": "8Gi"},
            timeout_override=1200,
        ),
        repetitions=3,
    )

    serialized = original.model_dump(mode="json")
    restored = ExperimentManifest.model_validate(serialized)

    assert restored == original
    assert len(restored.agents) == 1
    assert restored.agents[0].client is not None
    assert restored.compute.timeout_override == 1200
