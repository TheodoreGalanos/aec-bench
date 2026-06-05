# ABOUTME: Configuration model for multi-agent swarm runs.
# ABOUTME: Loaded from standalone swarm.yaml files via load_swarm_config().

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml  # type: ignore[import-untyped]
from pydantic import PositiveInt

from aec_bench.contracts.validators import NonEmptyStr, StrictModel


class SwarmTaskConfig(StrictModel):
    """Task and workspace references for a swarm run."""

    workspace: NonEmptyStr
    task_path: NonEmptyStr


class SwarmAgentConfig(StrictModel):
    """Agent pool configuration."""

    count: PositiveInt = 4
    default_model: NonEmptyStr
    models: list[str] = []
    specialisation: Literal["homogeneous", "nudged"] = "homogeneous"
    nudges: list[str] = []
    max_restarts: PositiveInt = 3


class SwarmBudgetConfig(StrictModel):
    """Shared budget pool configuration."""

    max_cost_usd: float
    eval_budget_usd: float
    wind_down_threshold: float = 0.8
    final_threshold: float = 0.95
    pool: Literal["shared", "per_agent"] = "shared"


class SwarmHeartbeatConfig(StrictModel):
    """Heartbeat interval configuration (fast-follow, schema reserved)."""

    reflect_every: PositiveInt = 1
    consolidate_every: PositiveInt = 10
    pivot_after: PositiveInt = 5


class SwarmArchiveConfig(StrictModel):
    """QD archive configuration."""

    n_centroids: PositiveInt = 512


class SwarmChannelsConfig(StrictModel):
    """Communication channel toggles."""

    graveyard: Literal["archive-indexed"] = "archive-indexed"
    notes: bool = False
    lineage: bool = True


class SwarmEvalConfig(StrictModel):
    """Evaluation configuration."""

    parallel: bool = True
    timeout: PositiveInt = 300
    backend: Literal["local", "modal", "e2b", "morph"] = "local"


class SwarmEvolutionConfig(StrictModel):
    """Per-agent evolution settings."""

    batch_size: PositiveInt = 1
    improvement_threshold: float = 0.01
    structural_weight: float = 0.3


class SwarmRunConfig(StrictModel):
    """Run-level options."""

    verbose: bool = False
    ui: bool = False


class SwarmConfig(StrictModel):
    """Top-level configuration for a multi-agent swarm run."""

    task: SwarmTaskConfig
    agents: SwarmAgentConfig
    budget: SwarmBudgetConfig
    heartbeat: SwarmHeartbeatConfig = SwarmHeartbeatConfig()
    archive: SwarmArchiveConfig = SwarmArchiveConfig()
    channels: SwarmChannelsConfig = SwarmChannelsConfig()
    evaluation: SwarmEvalConfig = SwarmEvalConfig()
    evolution: SwarmEvolutionConfig = SwarmEvolutionConfig()
    run: SwarmRunConfig = SwarmRunConfig()


def load_swarm_config(path: Path) -> SwarmConfig:
    """Load a SwarmConfig from a YAML file."""
    if not path.exists():
        msg = f"Swarm config not found: {path}"
        raise FileNotFoundError(msg)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return SwarmConfig.model_validate(data)
