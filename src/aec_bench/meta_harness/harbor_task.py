# ABOUTME: Materializes Harbor-shaped task packages for operation orchestrator runs.
# ABOUTME: Keeps task artifacts compatible with external runners and import boundaries.

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from aec_bench.meta_harness.operation_orchestrator import run_operation_orchestrator

HARBOR_REQUIRED_ARTIFACTS = [
    "job.yaml",
    "agent/input.json",
    "agent/output.md",
    "agent_result.json",
    "result.json",
]


def build_harbor_task_package(
    *,
    brief: dict[str, Any],
    worlds: list[dict[str, Any]],
    task_id: str | None = None,
    allowed_operations: list[str] | None = None,
    operation_plan: dict[str, Any] | None = None,
    model_endpoints: list[Any] | None = None,
) -> dict[str, Any]:
    resolved_task_id = task_id or _default_task_id(brief)
    run = run_operation_orchestrator(
        brief=brief,
        worlds=worlds,
        allowed_operations=allowed_operations,
        operation_plan=operation_plan,
    ).to_dict()
    public_models = [_public_endpoint(endpoint) for endpoint in model_endpoints or []]
    allowed = run["request"]["payload"]["allowed_operations"]
    agent_input = {
        "task_id": resolved_task_id,
        "task_type": "operation_orchestrator",
        "brief": brief,
        "worlds": worlds,
        "allowed_operations": allowed,
        "request": run["request"],
        "operation_plan": operation_plan,
        "models": public_models,
    }
    agent_result = {
        "task_id": resolved_task_id,
        "task_type": "operation_orchestrator",
        "status": run["status"],
        "operation_plan": operation_plan,
        "execution": run["execution"],
        "request": run["request"],
    }
    result = {
        "task_id": resolved_task_id,
        "task_type": "operation_orchestrator",
        "status": run["status"],
        "required_artifacts": list(HARBOR_REQUIRED_ARTIFACTS),
        "agent_result_path": "agent_result.json",
        "agent_output_path": "agent/output.md",
    }
    return {
        "task_id": resolved_task_id,
        "task_type": "operation_orchestrator",
        "harbor_import_contract": {
            "required_artifacts": list(HARBOR_REQUIRED_ARTIFACTS),
            "status_source": "result.json",
            "agent_output_source": "agent/output.md",
            "agent_result_source": "agent_result.json",
        },
        "job": _job_manifest(task_id=resolved_task_id, allowed_operations=allowed),
        "files": {
            "job.yaml": _job_yaml(task_id=resolved_task_id, allowed_operations=allowed),
            "agent/input.json": agent_input,
            "agent/output.md": _agent_output_markdown(run, operation_plan),
            "agent_result.json": agent_result,
            "result.json": result,
        },
    }


def materialize_harbor_task_package(
    *,
    output_dir: Path,
    brief: dict[str, Any],
    worlds: list[dict[str, Any]],
    task_id: str | None = None,
    allowed_operations: list[str] | None = None,
    operation_plan: dict[str, Any] | None = None,
    model_endpoints: list[Any] | None = None,
) -> dict[str, Any]:
    package = build_harbor_task_package(
        brief=brief,
        worlds=worlds,
        task_id=task_id,
        allowed_operations=allowed_operations,
        operation_plan=operation_plan,
        model_endpoints=model_endpoints,
    )
    for relative_path, content in package["files"].items():
        path = output_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if relative_path.endswith(".json"):
            path.write_text(json.dumps(content, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        else:
            path.write_text(str(content), encoding="utf-8")
    return {
        "task_id": package["task_id"],
        "task_type": package["task_type"],
        "output_dir": str(output_dir),
        "required_artifacts": package["harbor_import_contract"]["required_artifacts"],
        "status": package["files"]["result.json"]["status"],
    }


def _job_manifest(
    *,
    task_id: str,
    allowed_operations: list[str],
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "task_type": "operation_orchestrator",
        "runner": {
            "module": "aec_bench.meta_harness.operation_model_runner",
            "input": "agent/input.json",
        },
        "allowed_operations": list(allowed_operations),
        "expected_artifacts": list(HARBOR_REQUIRED_ARTIFACTS),
    }


def _job_yaml(
    *,
    task_id: str,
    allowed_operations: list[str],
) -> str:
    operation_lines = "\n".join(f"  - {operation}" for operation in allowed_operations)
    artifact_lines = "\n".join(f"  - {artifact}" for artifact in HARBOR_REQUIRED_ARTIFACTS)
    return (
        f"task_id: {task_id}\n"
        "task_type: operation_orchestrator\n"
        "runner:\n"
        "  module: aec_bench.meta_harness.operation_model_runner\n"
        "  input: agent/input.json\n"
        "allowed_operations:\n"
        f"{operation_lines}\n"
        "expected_artifacts:\n"
        f"{artifact_lines}\n"
    )


def _agent_output_markdown(
    run: dict[str, Any],
    operation_plan: dict[str, Any] | None,
) -> str:
    if operation_plan is None:
        operation_plan_schema = run["request"]["response_schema"]["properties"]["operation_plan"]
        return (
            "# Operation Orchestrator Output\n\n"
            "Awaiting an `operation_plan` matching the response schema in `agent/input.json`.\n\n"
            "```json\n"
            f"{json.dumps({'operation_plan': operation_plan_schema}, indent=2, sort_keys=True)}\n"
            "```\n"
        )
    return (
        "# Operation Orchestrator Output\n\n"
        "Completed operation plan:\n\n"
        "```json\n"
        f"{json.dumps({'operation_plan': operation_plan}, indent=2, sort_keys=True)}\n"
        "```\n"
    )


def _default_task_id(brief: dict[str, Any]) -> str:
    seed = str(brief.get("brief_id") or brief.get("objective") or "operation-orchestrator")
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "-", seed.strip()).strip("-").lower()
    return f"operation-{slug or 'task'}"


def _public_endpoint(endpoint: Any) -> dict[str, Any]:
    if hasattr(endpoint, "to_public_dict"):
        return endpoint.to_public_dict()
    if hasattr(endpoint, "public_dict"):
        return endpoint.public_dict()
    if hasattr(endpoint, "model_dump"):
        return endpoint.model_dump(mode="json", exclude_none=True)
    return dict(endpoint) if isinstance(endpoint, dict) else {"name": str(endpoint)}
