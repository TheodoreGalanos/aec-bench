# ABOUTME: Tests for experiment config composition from dataset references.
# ABOUTME: Pure function tests — ExperimentManifest in, YAML string out.

import yaml

from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.dataset.experiment import build_experiment_config, write_experiment_yaml


def test_build_experiment_config_basic() -> None:
    agents = [AgentConfig(name="test-agent", adapter="tool_loop", model="gpt-41-mini")]
    compute = ComputeConfig(backend="modal")

    manifest = build_experiment_config(
        dataset="electrical-only@1.0.0",
        agents=agents,
        compute=compute,
    )
    assert manifest.tasks.dataset == "electrical-only@1.0.0"
    assert manifest.experiment_id == "electrical-only-gpt41mini"
    assert manifest.name == "Evaluate on electrical-only@1.0.0"
    assert len(manifest.agents) == 1


def test_build_experiment_config_custom_id() -> None:
    agents = [AgentConfig(name="a", adapter="tool_loop", model="m")]
    compute = ComputeConfig(backend="modal")

    manifest = build_experiment_config(
        dataset="ds@1.0.0",
        agents=agents,
        compute=compute,
        experiment_id="my-custom-id",
        name="My experiment",
    )
    assert manifest.experiment_id == "my-custom-id"
    assert manifest.name == "My experiment"


def test_write_experiment_yaml_produces_valid_yaml() -> None:
    agents = [AgentConfig(name="test-agent", adapter="tool_loop", model="gpt-41-mini")]
    compute = ComputeConfig(backend="modal", resource_limits={"n_concurrent_trials": 2})

    manifest = build_experiment_config(
        dataset="electrical-only@1.0.0",
        agents=agents,
        compute=compute,
        repetitions=3,
    )

    yaml_str = write_experiment_yaml(manifest)
    parsed = yaml.safe_load(yaml_str)

    assert parsed["tasks"]["dataset"] == "electrical-only@1.0.0"
    assert parsed["agents"][0]["model"] == "gpt-41-mini"
    assert parsed["compute"]["backend"] == "modal"
    assert parsed["repetitions"] == 3


def test_write_experiment_yaml_to_file(tmp_path) -> None:
    agents = [AgentConfig(name="a", adapter="tool_loop", model="m")]
    compute = ComputeConfig(backend="modal")
    manifest = build_experiment_config(dataset="ds@1.0.0", agents=agents, compute=compute)

    output = tmp_path / "experiment.yaml"
    write_experiment_yaml(manifest, output_path=str(output))

    assert output.exists()
    parsed = yaml.safe_load(output.read_text())
    assert parsed["tasks"]["dataset"] == "ds@1.0.0"
