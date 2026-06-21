# ABOUTME: Tests the executable operation-orchestrator runner emitted in Harbor-shaped packages.
# ABOUTME: Verifies materialized task packages name an importable runner that writes expected artifacts.

from __future__ import annotations

import importlib
import json
from pathlib import Path

from aec_bench.meta_harness.harbor_task import materialize_harbor_task_package
from aec_bench.meta_harness.operation_model_runner import run_operation_model_package


def test_materialized_harbor_task_runner_imports_and_writes_artifacts(tmp_path: Path) -> None:
    output_dir = tmp_path / "operation-task"

    materialize_harbor_task_package(
        output_dir=output_dir,
        brief=_brief(),
        worlds=[_world()],
        task_id="operation.demo",
        operation_plan=_operation_plan(),
    )

    module = importlib.import_module("aec_bench.meta_harness.operation_model_runner")
    result = run_operation_model_package(input_path=output_dir / "agent" / "input.json")

    agent_input = json.loads((output_dir / "agent" / "input.json").read_text(encoding="utf-8"))
    agent_result = json.loads((output_dir / "agent_result.json").read_text(encoding="utf-8"))
    result_json = json.loads((output_dir / "result.json").read_text(encoding="utf-8"))

    assert module is not None
    assert agent_input["operation_plan"]["plan_id"] == "plan.artifact_projection"
    assert result["status"] == "complete"
    assert agent_result["execution"]["status"] == "complete"
    assert result_json["status"] == "complete"
    assert (
        (output_dir / "agent" / "output.md").read_text(encoding="utf-8").startswith("# Operation Orchestrator Output")
    )


def _brief() -> dict:
    return {
        "brief_id": "brief.demo",
        "objective": "Create diagnostic variants.",
        "task_request": "Create a diagnostic task.",
        "evidence_requirements": ["preserve verifier artifacts"],
    }


def _world() -> dict:
    return {
        "world_id": "world.base",
        "name": "Base World",
        "task_unit": "Complete a calculation.",
        "logic_profile": {
            "closure_gates": [],
            "construction_gates": [],
            "containment_gates": [],
            "agentic_review": {"required": True},
        },
        "operation_profile": {
            "projection_axes": ["artifact_evidence"],
            "difference_axes": ["artifact_evidence"],
        },
        "operation_handles": {"artifact_evidence": {"paths": ["evidence_profile.artifacts"]}},
        "evidence_profile": {"artifacts": ["logs/verifier/details.json"]},
    }


def _operation_plan() -> dict:
    return {
        "plan_id": "plan.artifact_projection",
        "objective": "Project artifact evidence.",
        "steps": [
            {
                "id": "project_artifacts",
                "kind": "deterministic_operation",
                "world_ref": "world.base",
                "operation": {"operation": "projection", "axis": "artifact_evidence"},
            }
        ],
        "acceptance_checks": ["projection completes"],
    }
