# ABOUTME: Builds and runs Harbor jobs for the wastewater pump-station world.
# ABOUTME: Applies task-specific backend checks before a provider execution starts.

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from harbor.models.job.config import JobConfig  # type: ignore[import-untyped]

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_export import (
    load_pump_station_harbor_bridge,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_session import (
    PUMP_STATION_MODEL_CONTROLLER_MODE,
    PUMP_STATION_MODEL_MAX_TURNS,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_controller import (
    PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID,
)

_ENTRYPOINT_IMPORT_PATH = "agents.entrypoint_agent:EntrypointAgent"
_MORPH_ENVIRONMENT_IMPORT_PATH = "aec_bench.providers.morph_harbor:MorphHarborEnvironment"
PUMP_STATION_HARBOR_BACKENDS = ("docker", "modal", "morph")


@dataclass(frozen=True)
class PumpStationHarborJobResult:
    """Local paths and process result for one Harbor job request."""

    config_path: Path
    command: tuple[str, ...]
    exit_code: int | None


def build_pump_station_harbor_job_config(
    *,
    task_dir: Path,
    jobs_dir: Path,
    backend: str = "docker",
    model_name: str = PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID,
    max_turns: int = PUMP_STATION_MODEL_MAX_TURNS,
) -> dict[str, Any]:
    """Build one validated local Harbor configuration for the exported task."""

    task_root = Path(task_dir).resolve(strict=True)
    bridge = load_pump_station_harbor_bridge(task_root / "environment")
    environment = _harbor_environment(backend)
    model = model_name.strip()
    if not model:
        raise ValueError("pump-station Harbor model name is required")
    if max_turns < 1:
        raise ValueError("pump-station Harbor max turns must be positive")
    reference_controller = model == PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID
    world_session = {"bridge_mode": bridge.bridge_mode}
    agent_kwargs: dict[str, Any] = {
        "adapter": "tool_loop",
        "execution_kind": bridge.execution_kind,
        "world_session": world_session,
    }
    agent_name = "pump-station-reference-controller"
    if not reference_controller:
        agent_name = "pump-station-model-controller"
        agent_kwargs["max_turns"] = max_turns
        world_session["controller"] = PUMP_STATION_MODEL_CONTROLLER_MODE
    config: dict[str, Any] = {
        "job_name": (f"wastewater-pump-station-{'reference' if reference_controller else 'model'}-{backend}"),
        "jobs_dir": str(Path(jobs_dir).resolve()),
        "n_attempts": 1,
        "timeout_multiplier": 1.0,
        "orchestrator": {
            "type": "local",
            "n_concurrent_trials": 1,
            "quiet": False,
        },
        "environment": environment,
        "agents": [
            {
                "name": agent_name,
                "import_path": _ENTRYPOINT_IMPORT_PATH,
                "model_name": model,
                "kwargs": agent_kwargs,
            }
        ],
        "datasets": [],
        "tasks": [{"path": str(task_root)}],
        "artifacts": [
            {
                "source": "/workspace/world-session",
                "destination": "agent/world-session",
            },
            {
                "source": "/workspace/output.md",
                "destination": "agent/output.md",
            },
        ],
    }
    JobConfig.model_validate(config)
    return config


def run_pump_station_harbor_job(
    *,
    task_dir: Path,
    project_root: Path,
    jobs_dir: Path,
    config_path: Path,
    backend: str = "docker",
    model_name: str = PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID,
    max_turns: int = PUMP_STATION_MODEL_MAX_TURNS,
    execute: bool = True,
) -> PumpStationHarborJobResult:
    """Write the exact job config and optionally execute local Harbor."""

    root = Path(project_root).resolve(strict=True)
    if not (root / "agents" / "entrypoint_agent.py").is_file():
        raise ValueError("project root lacks the Harbor entrypoint agent")
    if execute:
        validate_pump_station_harbor_backend_for_execution(backend)
    config = build_pump_station_harbor_job_config(
        task_dir=task_dir,
        jobs_dir=jobs_dir,
        backend=backend,
        model_name=model_name,
        max_turns=max_turns,
    )
    destination = Path(config_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        yaml.safe_dump(config, sort_keys=False),
        encoding="utf-8",
    )
    command = ("uv", "run", "harbor", "run", "-c", str(destination))
    exit_code: int | None = None
    if execute:
        environment = dict(os.environ)
        existing_pythonpath = environment.get("PYTHONPATH", "")
        environment["PYTHONPATH"] = str(root) if not existing_pythonpath else f"{root}{os.pathsep}{existing_pythonpath}"
        completed = subprocess.run(
            command,
            cwd=root,
            check=False,
            env=environment,
        )
        exit_code = int(completed.returncode)
    return PumpStationHarborJobResult(
        config_path=destination,
        command=command,
        exit_code=exit_code,
    )


def validate_pump_station_harbor_backend_for_execution(backend: str) -> None:
    """Reject a backend that cannot enforce the pump-station network rule."""

    if backend not in PUMP_STATION_HARBOR_BACKENDS:
        raise ValueError("unsupported pump-station Harbor backend: " + backend)


def _harbor_environment(backend: str) -> dict[str, Any]:
    if backend not in PUMP_STATION_HARBOR_BACKENDS:
        raise ValueError("unsupported pump-station Harbor backend: " + backend)
    if backend == "morph":
        return {
            "import_path": _MORPH_ENVIRONMENT_IMPORT_PATH,
            "force_build": False,
            "delete": True,
            "kwargs": {"compute_backend": "morph"},
        }
    return {
        "type": backend,
        "force_build": False,
        "delete": True,
    }


__all__ = (
    "PumpStationHarborJobResult",
    "PUMP_STATION_HARBOR_BACKENDS",
    "PUMP_STATION_MODEL_CONTROLLER_MODE",
    "build_pump_station_harbor_job_config",
    "run_pump_station_harbor_job",
    "validate_pump_station_harbor_backend_for_execution",
)
