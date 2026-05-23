# ABOUTME: Harbor dispatch boundary for manifest-driven experiment execution.
# ABOUTME: Builds precise Harbor configs and can execute the Harbor CLI via an injected executor.

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import yaml

from aec_bench.contracts.experiment_manifest import AgentConfig, ExperimentManifest
from aec_bench.contracts.task_definition import TaskDefinition
from aec_bench.harness.scheduler import build_trial_plan


class HarborDispatchError(Exception):
    pass


@dataclass(frozen=True)
class HarborDispatchResult:
    config_path: Path
    command: list[str]
    selected_task_count: int
    planned_trial_count: int
    exit_code: int | None = None


class HarborCommandExecutor(Protocol):
    def execute(self, *, command: list[str], cwd: Path) -> int: ...


class SubprocessHarborExecutor:
    def execute(self, *, command: list[str], cwd: Path) -> int:
        completed = subprocess.run(command, cwd=cwd, check=False)
        return int(completed.returncode)


@dataclass(frozen=True)
class HarborExperimentDispatcher:
    project_root: Path

    def dispatch(
        self,
        *,
        manifest: ExperimentManifest,
        tasks: list[TaskDefinition],
        config_path: Path,
        executor: HarborCommandExecutor | None = None,
        execute: bool = True,
    ) -> HarborDispatchResult:
        if not tasks:
            raise HarborDispatchError("manifest did not select any tasks for Harbor dispatch")

        job_config = build_harbor_job_config(manifest=manifest, tasks=tasks)
        config_path.write_text(yaml.safe_dump(job_config, sort_keys=False), encoding="utf-8")

        planned_trials = build_trial_plan(manifest, tasks)
        command = ["uv", "run", "harbor", "run", "-c", str(config_path)]
        exit_code: int | None = None
        if execute:
            resolved_executor = executor or SubprocessHarborExecutor()
            exit_code = resolved_executor.execute(command=command, cwd=self.project_root)

        return HarborDispatchResult(
            config_path=config_path,
            command=command,
            selected_task_count=len(tasks),
            planned_trial_count=len(planned_trials),
            exit_code=exit_code,
        )


def build_harbor_job_config(
    *,
    manifest: ExperimentManifest,
    tasks: list[TaskDefinition],
) -> dict[str, Any]:
    config: dict[str, Any] = {
        "jobs_dir": "jobs",
        "n_attempts": 1,
        "timeout_multiplier": 1.0,
        "metrics": [{"type": "mean"}, {"type": "min"}, {"type": "max"}],
        "orchestrator": {
            "type": "local",
            "n_concurrent_trials": int(manifest.compute.resource_limits.get("n_concurrent_trials", 1)),
            "quiet": False,
        },
        "environment": {
            "type": manifest.compute.backend,
            "force_build": False,
            "delete": True,
            "kwargs": {},
        },
        "agents": [_harbor_agent_config(agent) for agent in manifest.agents],
        "datasets": [],
        "tasks": [{"path": f"tasks/{task.task_id}"} for task in tasks],
        "artifacts": [
            {"source": "/workspace/output.md", "destination": "agent/output.md"},
            {"source": "/workspace/agent_result.json", "destination": "agent/agent_result.json"},
            {"source": "/workspace/conversation.jsonl", "destination": "agent/conversation.jsonl"},
            {"source": "/workspace/trajectory.jsonl", "destination": "agent/trajectory.jsonl"},
            {"source": "/workspace/symbolic_state.json", "destination": "agent/symbolic_state.json"},
            {"source": "/workspace/model_reasoning.jsonl", "destination": "agent/model_reasoning.jsonl"},
            {"source": "/workspace/.scratchpad.json", "destination": "agent/scratchpad.json"},
        ],
    }
    if manifest.disable_verification:
        config["verifier"] = {"disable": True}
    return config


ENTRYPOINT_AGENT_IMPORT_PATH = "agents.entrypoint_agent:EntrypointAgent"

# Kept for reference during deprecation — no longer used for routing.
_LEGACY_HARBOR_IMPORT_PATH_TABLE: dict[tuple[str, str], str] = {
    # Tool-loop agents
    ("tool_loop", "anthropic"): "agents.tool_loop_anthropic:ToolLoopAnthropicAgent",
    ("tool-loop-anthropic", "anthropic"): "agents.tool_loop_anthropic:ToolLoopAnthropicAgent",
    ("tool_loop", "azure_openai"): "agents.tool_loop_azure_openai:ToolLoopAzureOpenAIAgent",
    # Script agents (single-turn)
    ("direct", "anthropic"): "agents.script_anthropic:ScriptAnthropicAgent",
    ("direct-anthropic", "anthropic"): "agents.script_anthropic:ScriptAnthropicAgent",
    ("direct", "azure_openai"): "agents.script_azure_openai:ScriptAzureOpenAIAgent",
    # PydanticAI agent (provider-agnostic)
    ("pydantic_ai", "anthropic"): "agents.pydantic_ai_agent:PydanticAIBenchAgent",
    ("pydantic_ai", "azure_openai"): "agents.pydantic_ai_agent:PydanticAIBenchAgent",
    # RLM REPL agent (provider-agnostic via PydanticAI)
    ("rlm", "anthropic"): "agents.rlm_agent:RlmAgent",
    ("rlm", "azure_openai"): "agents.rlm_agent:RlmAgent",
    ("rlm-anthropic", "anthropic"): "agents.rlm_agent:RlmAgent",
}


def _harbor_agent_config(agent: AgentConfig) -> dict[str, Any]:
    kwargs = dict(agent.parameters)
    kwargs["adapter"] = agent.adapter
    return {
        "name": agent.name,
        "import_path": _resolve_import_path(agent),
        "model_name": agent.model,
        "kwargs": kwargs,
    }


def _resolve_import_path(agent: AgentConfig) -> str:
    return ENTRYPOINT_AGENT_IMPORT_PATH
