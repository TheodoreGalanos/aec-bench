# ABOUTME: Compose experiment configs from dataset references.
# ABOUTME: Pure function that builds ExperimentManifest YAML from a dataset + agent + compute.

from __future__ import annotations

from typing import Any

import yaml

from aec_bench.contracts.experiment_manifest import (
    AgentConfig,
    ComputeConfig,
    ExperimentManifest,
    TaskSelector,
)


def build_experiment_config(
    *,
    dataset: str,
    agents: list[AgentConfig],
    compute: ComputeConfig,
    experiment_id: str | None = None,
    name: str | None = None,
    repetitions: int = 1,
    difficulties: list[str] | None = None,
    include_patterns: list[str] | None = None,
) -> ExperimentManifest:
    """Build an ExperimentManifest from a dataset reference and agent/compute config.

    Pure function — no I/O, no side effects. The returned manifest can be
    serialised to YAML with write_experiment_yaml().
    """
    # Derive experiment_id from dataset if not provided
    if experiment_id is None:
        ds_name = dataset.split("@")[0]
        agent_slug = agents[0].model.replace(".", "").replace("-", "") if agents else "agent"
        experiment_id = f"{ds_name}-{agent_slug}"

    if name is None:
        name = f"Evaluate on {dataset}"

    selector = TaskSelector(
        dataset=dataset,
        difficulties=difficulties or [],
        include_patterns=include_patterns or [],
    )

    return ExperimentManifest(
        experiment_id=experiment_id,
        name=name,
        tasks=selector,
        agents=agents,
        compute=compute,
        repetitions=repetitions,
    )


def write_experiment_yaml(manifest: ExperimentManifest, output_path: str | None = None) -> str:
    """Serialise an ExperimentManifest to YAML.

    Returns the YAML string. If output_path is provided, also writes to disk.
    """
    data: dict[str, Any] = {
        "experiment_id": manifest.experiment_id,
        "name": manifest.name,
        "tasks": {},
        "agents": [],
        "compute": {
            "backend": manifest.compute.backend,
        },
        "repetitions": manifest.repetitions,
    }

    # Tasks section
    if manifest.tasks.dataset:
        data["tasks"]["dataset"] = manifest.tasks.dataset
    if manifest.tasks.include_patterns:
        data["tasks"]["include_patterns"] = manifest.tasks.include_patterns
    if manifest.tasks.domains:
        data["tasks"]["domains"] = manifest.tasks.domains
    if manifest.tasks.difficulties:
        data["tasks"]["difficulties"] = [d.value for d in manifest.tasks.difficulties]

    # Compute resource limits
    if manifest.compute.resource_limits:
        data["compute"]["resource_limits"] = dict(manifest.compute.resource_limits)

    # Agents
    for agent in manifest.agents:
        agent_data: dict[str, Any] = {
            "name": agent.name,
            "adapter": agent.adapter,
            "model": agent.model,
        }
        if agent.parameters:
            agent_data["parameters"] = dict(agent.parameters)
        if agent.system_prompt_file:
            agent_data["system_prompt_file"] = agent.system_prompt_file
        data["agents"].append(agent_data)

    yaml_str = yaml.safe_dump(data, sort_keys=False, default_flow_style=False)

    if output_path is not None:
        from pathlib import Path

        Path(output_path).write_text(yaml_str, encoding="utf-8")

    return yaml_str
