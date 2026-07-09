# ABOUTME: Executes materialized operation-orchestrator task packages.
# ABOUTME: Reads Harbor-shaped agent input and writes output, agent result, and result artifacts.

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from aec_bench.meta_harness.harbor_task import HARBOR_REQUIRED_ARTIFACTS
from aec_bench.meta_harness.model_runner import endpoint_from_mapping, run_operation_models
from aec_bench.meta_harness.operation_orchestrator import run_operation_orchestrator


def run_operation_model_package(
    *,
    input_path: Path,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    resolved_input_path = Path(input_path)
    resolved_output_dir = output_dir or resolved_input_path.parent.parent
    payload = _read_json(resolved_input_path)
    operation_run = _run_operation(payload)
    agent_result = _agent_result(payload, operation_run)
    result = _result(payload, operation_run)

    _write_text(resolved_output_dir / "agent" / "output.md", _output_markdown(operation_run))
    _write_json(resolved_output_dir / "agent_result.json", agent_result)
    _write_json(resolved_output_dir / "result.json", result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a materialized meta-harness operation package.")
    parser.add_argument("--input", type=Path, default=Path("agent/input.json"))
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    result = run_operation_model_package(input_path=args.input, output_dir=args.output_dir)
    return 0 if result["status"] in {"complete", "needs_orchestration", "awaiting_agent_plan"} else 1


def _run_operation(payload: dict[str, Any]) -> dict[str, Any]:
    brief = payload["brief"]
    worlds = payload["worlds"]
    allowed_operations = payload.get("allowed_operations")
    operation_plan = payload.get("operation_plan")
    if isinstance(operation_plan, dict):
        return run_operation_orchestrator(
            brief=brief,
            worlds=worlds,
            allowed_operations=allowed_operations,
            operation_plan=operation_plan,
        ).to_dict()
    models = payload.get("models")
    if isinstance(models, list) and models:
        return _run_model_operation(
            brief=brief,
            worlds=worlds,
            allowed_operations=allowed_operations,
            models=models,
            request=payload.get("request"),
        )
    return run_operation_orchestrator(
        brief=brief,
        worlds=worlds,
        allowed_operations=allowed_operations,
    ).to_dict()


def _run_model_operation(
    *,
    brief: dict[str, Any],
    worlds: list[dict[str, Any]],
    allowed_operations: list[str] | None,
    models: list[Any],
    request: dict[str, Any] | None,
) -> dict[str, Any]:
    endpoints = [endpoint_from_mapping(_endpoint_mapping(model)) for model in models]
    model_run = run_operation_models(
        brief=brief,
        worlds=worlds,
        endpoints=endpoints,
        allowed_operations=allowed_operations,
    )
    model_result = _first_complete_result(model_run)
    if model_result is None:
        return {
            "status": "operation_model_error",
            "request": request,
            "execution": None,
            "model_run": model_run,
        }
    return {
        "status": model_result["status"],
        "request": request,
        "operation_plan": model_result.get("operation_plan"),
        "execution": model_result.get("execution"),
        "model_run": model_run,
    }


def _agent_result(payload: dict[str, Any], operation_run: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": payload.get("task_id"),
        "task_type": payload.get("task_type", "operation_orchestrator"),
        "status": operation_run["status"],
        "operation_plan": payload.get("operation_plan") or operation_run.get("operation_plan"),
        "execution": operation_run.get("execution"),
        "request": operation_run.get("request") or payload.get("request"),
        **({"model_run": operation_run["model_run"]} if "model_run" in operation_run else {}),
    }


def _result(payload: dict[str, Any], operation_run: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": payload.get("task_id"),
        "task_type": payload.get("task_type", "operation_orchestrator"),
        "status": operation_run["status"],
        "passed": operation_run["status"] == "complete",
        "required_artifacts": list(HARBOR_REQUIRED_ARTIFACTS),
        "agent_result_path": "agent_result.json",
        "agent_output_path": "agent/output.md",
    }


def _output_markdown(operation_run: dict[str, Any]) -> str:
    return (
        "# Operation Orchestrator Output\n\n"
        f"Status: `{operation_run['status']}`\n\n"
        "```json\n"
        f"{json.dumps(operation_run, indent=2, sort_keys=True)}\n"
        "```\n"
    )


def _first_complete_result(model_run: dict[str, Any]) -> dict[str, Any] | None:
    for result in model_run.get("results", []):
        if result.get("status") in {"complete", "certified"}:
            return result
    return None


def _endpoint_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("model entries must be objects")
    result = dict(value)
    result.pop("api_key_present", None)
    return result


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
