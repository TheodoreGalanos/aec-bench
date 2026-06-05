# ABOUTME: Tests for SwarmConfig loading from YAML files.
# ABOUTME: Verifies defaults, validation, and the load_swarm_config function.

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]
from pydantic import ValidationError

from aec_bench.evolution.swarm.config import SwarmConfig, load_swarm_config

MINIMAL_YAML: dict[str, Any] = {
    "task": {
        "workspace": "./workspaces/test",
        "task_path": "tasks/electrical/voltage-drop",
    },
    "agents": {
        "default_model": "anthropic.claude-sonnet-4-20250514",
    },
    "budget": {
        "max_cost_usd": 50.0,
        "eval_budget_usd": 10.0,
    },
}


def test_minimal_config_loads() -> None:
    config = SwarmConfig.model_validate(MINIMAL_YAML)
    assert config.agents.count == 4
    assert config.agents.default_model == "anthropic.claude-sonnet-4-20250514"
    assert config.budget.max_cost_usd == 50.0
    assert config.budget.wind_down_threshold == 0.8
    assert config.agents.max_restarts == 3


def test_config_defaults() -> None:
    config = SwarmConfig.model_validate(MINIMAL_YAML)
    assert config.agents.specialisation == "homogeneous"
    assert config.channels.lineage is True
    assert config.channels.notes is False
    assert config.evaluation.parallel is True
    assert config.evaluation.backend == "local"
    assert config.evolution.batch_size == 1
    assert config.heartbeat.pivot_after == 5


def test_config_accepts_morph_backend_name() -> None:
    data = {
        **MINIMAL_YAML,
        "evaluation": {
            "backend": "morph",
        },
    }
    config = SwarmConfig.model_validate(data)
    assert config.evaluation.backend == "morph"


def test_config_rejects_missing_budget() -> None:
    invalid = {"task": MINIMAL_YAML["task"], "agents": MINIMAL_YAML["agents"]}
    with pytest.raises(ValidationError):
        SwarmConfig.model_validate(invalid)


def test_config_rejects_missing_task() -> None:
    invalid = {"agents": MINIMAL_YAML["agents"], "budget": MINIMAL_YAML["budget"]}
    with pytest.raises(ValidationError):
        SwarmConfig.model_validate(invalid)


def test_load_swarm_config_from_file(tmp_path: Path) -> None:
    config_path = tmp_path / "swarm.yaml"
    config_path.write_text(yaml.dump(MINIMAL_YAML))
    config = load_swarm_config(config_path)
    assert config.task.workspace == "./workspaces/test"
    assert config.agents.count == 4


def test_load_swarm_config_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_swarm_config(tmp_path / "missing.yaml")


def test_config_custom_agent_count() -> None:
    data = {**MINIMAL_YAML, "agents": {**MINIMAL_YAML["agents"], "count": 8}}
    config = SwarmConfig.model_validate(data)
    assert config.agents.count == 8


def test_config_per_agent_models() -> None:
    data = {
        **MINIMAL_YAML,
        "agents": {
            **MINIMAL_YAML["agents"],
            "count": 3,
            "models": ["sonnet", "opus", "haiku"],
        },
    }
    config = SwarmConfig.model_validate(data)
    assert len(config.agents.models) == 3
