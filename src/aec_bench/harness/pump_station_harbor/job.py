# ABOUTME: Builds the concrete Harbor job for the wastewater pump-station world.
# ABOUTME: Delegates config execution to the one current Harbor dispatcher.

from __future__ import annotations

from pathlib import Path
from typing import Any

from aec_bench.contracts.execution_environment import HarborEnvironmentBinding
from aec_bench.harness.harbor_dispatch import (
    HarborCommandExecutor,
    HarborDispatchResult,
    dispatch_harbor_config,
    harbor_environment_config,
    validate_harbor_job_config,
)
from aec_bench.harness.pump_station_harbor.export import (
    load_pump_station_harbor_bridge,
)
from aec_bench.harness.pump_station_harbor.session import (
    PUMP_STATION_MODEL_CONTROLLER_MODE,
    PUMP_STATION_MODEL_MAX_TOKENS,
    PUMP_STATION_MODEL_MAX_TURNS,
    PUMP_STATION_MODEL_MAX_WORLD_ACTIONS,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.reference_controller import (
    PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID,
)

_ENTRYPOINT_IMPORT_PATH = "agents.entrypoint_agent:EntrypointAgent"
PUMP_STATION_HARBOR_BACKENDS = ("docker", "modal", "morph")


def build_pump_station_harbor_job_config(
    *,
    task_dir: Path,
    jobs_dir: Path,
    backend: str = "docker",
    model_name: str = PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID,
    adapter: str = "tool_loop",
    max_turns: int = PUMP_STATION_MODEL_MAX_TURNS,
    max_world_actions: int = PUMP_STATION_MODEL_MAX_WORLD_ACTIONS,
    max_tokens: int | None = None,
    timeout_sec: int | None = None,
    environment_binding: HarborEnvironmentBinding | None = None,
) -> dict[str, Any]:
    """Build one validated local Harbor configuration for the exported task."""

    task_root = Path(task_dir).resolve(strict=True)
    bridge = load_pump_station_harbor_bridge(task_root / "environment")
    validate_pump_station_harbor_backend(backend)
    environment = harbor_environment_config(backend, environment_binding=environment_binding)
    model = model_name.strip()
    if not model:
        raise ValueError("pump-station Harbor model name is required")
    if max_turns < 1:
        raise ValueError("pump-station Harbor max turns must be positive")
    if isinstance(max_world_actions, bool) or max_world_actions < 1:
        raise ValueError("pump-station Harbor world action budget must be positive")
    reference_controller = model == PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID
    adapter_kind = "tool_loop" if reference_controller else adapter.strip()
    if adapter_kind not in {"deepseek_harness", "tool_loop"}:
        raise ValueError(f"unsupported pump-station Harbor adapter: {adapter_kind}")
    world_session = {"bridge_mode": bridge.bridge_mode}
    agent_kwargs: dict[str, Any] = {
        "adapter": adapter_kind,
        "execution_kind": bridge.execution_kind,
        "world_session": world_session,
    }
    agent_name = "pump-station-reference-controller"
    if not reference_controller:
        agent_name = "pump-station-model-controller"
        agent_kwargs["max_world_actions"] = max_world_actions
        if adapter_kind == "deepseek_harness":
            resolved_max_tokens = PUMP_STATION_MODEL_MAX_TOKENS if max_tokens is None else max_tokens
            if isinstance(resolved_max_tokens, bool) or resolved_max_tokens <= 0:
                raise ValueError("pump-station Harbor max tokens must be positive")
            agent_kwargs["max_tokens"] = resolved_max_tokens
            if timeout_sec is not None:
                if isinstance(timeout_sec, bool) or timeout_sec <= 0:
                    raise ValueError("pump-station Harbor timeout must be positive")
                agent_kwargs["timeout_sec"] = timeout_sec
        else:
            if max_tokens is not None or timeout_sec is not None:
                raise ValueError("max_tokens and timeout_sec require the deepseek_harness adapter")
            agent_kwargs["max_turns"] = max_turns
        world_session["controller"] = PUMP_STATION_MODEL_CONTROLLER_MODE
    config: dict[str, Any] = {
        "job_name": (f"wastewater-pump-station-{'reference' if reference_controller else 'model'}-{backend}"),
        "jobs_dir": str(Path(jobs_dir).resolve()),
        "n_attempts": 1,
        "timeout_multiplier": 1.0,
        "n_concurrent_trials": 1,
        "quiet": False,
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
    return validate_harbor_job_config(config)


def run_pump_station_harbor_job(
    *,
    task_dir: Path,
    project_root: Path,
    jobs_dir: Path,
    config_path: Path,
    backend: str = "docker",
    model_name: str = PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID,
    adapter: str = "tool_loop",
    max_turns: int = PUMP_STATION_MODEL_MAX_TURNS,
    max_world_actions: int = PUMP_STATION_MODEL_MAX_WORLD_ACTIONS,
    max_tokens: int | None = None,
    timeout_sec: int | None = None,
    environment_binding: HarborEnvironmentBinding | None = None,
    execute: bool = True,
    executor: HarborCommandExecutor | None = None,
) -> HarborDispatchResult:
    """Write the exact job config and optionally execute local Harbor."""

    root = Path(project_root).resolve(strict=True)
    if not (root / "agents" / "entrypoint_agent.py").is_file():
        raise ValueError("project root lacks the Harbor entrypoint agent")
    validate_pump_station_harbor_backend(backend)
    config = build_pump_station_harbor_job_config(
        task_dir=task_dir,
        jobs_dir=jobs_dir,
        backend=backend,
        model_name=model_name,
        adapter=adapter,
        max_turns=max_turns,
        max_world_actions=max_world_actions,
        max_tokens=max_tokens,
        timeout_sec=timeout_sec,
        environment_binding=environment_binding,
    )
    return dispatch_harbor_config(
        config=config,
        config_path=config_path,
        project_root=root,
        selected_task_count=1,
        planned_trial_count=1,
        executor=executor,
        execute=execute,
    )


def validate_pump_station_harbor_backend(backend: str) -> None:
    """Reject a backend that cannot enforce the pump-station network rule."""

    if backend not in PUMP_STATION_HARBOR_BACKENDS:
        raise ValueError("unsupported pump-station Harbor backend: " + backend)
