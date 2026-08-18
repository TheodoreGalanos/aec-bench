# ABOUTME: Tests experiment configuration composed from exact dataset references.
# ABOUTME: Ensures generated YAML persists immutable references and never human selectors.

from pathlib import Path

import yaml

from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.dataset import BundleDatasetRef
from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.dataset.experiment import build_experiment_config, write_experiment_yaml


def _reference() -> BundleDatasetRef:
    return BundleDatasetRef(
        dataset_id="electrical-only",
        artifact=ArtifactRef(
            artifact_id="sha256:" + "a" * 64,
            sha256="a" * 64,
            size_bytes=100,
            media_type="application/vnd.aec-bench.dataset-bundle+tar+gzip",
        ),
    )


def test_build_experiment_config_uses_stable_dataset_id_for_defaults() -> None:
    manifest = build_experiment_config(
        dataset=_reference(),
        agents=[AgentConfig(name="test-agent", adapter="tool_loop", model="gpt-41-mini")],
        compute=ComputeConfig(backend="modal"),
    )

    assert manifest.tasks.dataset == _reference()
    assert manifest.experiment_id == "electrical-only-gpt41mini"
    assert manifest.name == "Evaluate on electrical-only"


def test_write_experiment_yaml_persists_exact_reference(tmp_path: Path) -> None:
    manifest = build_experiment_config(
        dataset=_reference(),
        agents=[AgentConfig(name="test-agent", adapter="tool_loop", model="gpt-41-mini")],
        compute=ComputeConfig(backend="modal", resource_limits={"n_concurrent_trials": 2}),
        repetitions=3,
    )
    output = tmp_path / "experiment.yaml"

    yaml_text = write_experiment_yaml(manifest, output_path=str(output))
    parsed = yaml.safe_load(yaml_text)

    assert parsed["tasks"]["dataset"] == _reference().model_dump(mode="json")
    assert yaml.safe_load(output.read_text(encoding="utf-8")) == parsed
    assert "latest" not in yaml_text
