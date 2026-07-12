# ABOUTME: Tests model-facing lifecycle operation tools against the real SSC-03 hydraulic package.
# ABOUTME: Keeps host transaction identity private while exposing source-bound operation evidence.

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from aec_bench.meta_harness.evidence_lifecycle import (
    load_evidence_lifecycle_spec,
    open_checkpoint_attempt,
    prepare_evidence_checkpoint,
    read_evidence_lifecycle_state,
)
from aec_bench.meta_harness.evidence_lifecycle_episode import LifecycleVisibilityPolicy
from aec_bench.meta_harness.evidence_lifecycle_local import (
    EvidenceLifecycleControlTool,
    EvidenceLifecycleWorkspaceTool,
    _lifecycle_tool_schema,
    run_local_evidence_lifecycle_fresh_context,
    run_local_evidence_lifecycle_session,
)
from aec_bench.task_world_templates.catalogue import get_template
from aec_bench.task_world_templates.lifecycles import materialize_lifecycle_template

TEMPLATE_ID = "hydraulic-interaction-lifecycle-review"


def _interaction_package(path: Path) -> Path:
    return materialize_lifecycle_template(
        get_template(TEMPLATE_ID),
        path,
        variant_id="tailwater_revision",
    )


def _completed_runtime_verification(package: Path, run_dir: Path) -> dict[str, Any]:
    lifecycle = read_evidence_lifecycle_state(package, run_dir)
    complete = lifecycle["status"] == "complete"
    return {
        "lifecycle_id": lifecycle["lifecycle_id"],
        "overall": "pass" if complete else "incomplete",
        "passed": complete,
        "reward": 1.0 if complete else 0.0,
        "gates": {
            "runtime_completion": {
                "passed": complete,
                "score": 1.0 if complete else 0.0,
                "failures": [] if complete else ["lifecycle_incomplete"],
            }
        },
    }


def test_control_tool_executes_one_source_bound_operation_without_host_identity_leakage(
    tmp_path: Path,
) -> None:
    package = _interaction_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    prepare_evidence_checkpoint(package, run_dir)
    open_checkpoint_attempt(
        package,
        run_dir,
        session_id="runtime-tools.session-001",
        execution_mode="persistent_context",
    )
    workspace = EvidenceLifecycleWorkspaceTool(
        package_dir=package,
        run_dir=run_dir,
        visibility_policy=LifecycleVisibilityPolicy.PERSISTENT_CONTEXT,
    )
    control = EvidenceLifecycleControlTool(
        package_dir=package,
        run_dir=run_dir,
        session_id="runtime-tools.session-001",
    )

    root = json.loads(workspace.list_workspace("."))
    hydraulics = json.loads(workspace.list_workspace("hydraulics"))
    source = json.loads(workspace.read_workspace_file("hydraulics/current-source.json"))
    source_payload = json.loads(source["content"])

    assert "hydraulics" in root["entries"]
    assert hydraulics == {
        "status": "ok",
        "path": "hydraulics",
        "entries": ["current-source.json"],
    }
    assert source["status"] == "ok"
    assert source_payload["revision_id"] == "baseline"
    undisclosed = json.loads(workspace.read_workspace_file("hydraulics/not-model-visible.json"))
    assert undisclosed == {
        "status": "rejected",
        "error": "workspace path is not agent-readable: hydraulics/not-model-visible.json",
    }

    blank = json.loads(
        control.execute_operation(
            "baseline_analysis",
            "hydrology.design-10yr",
            source_payload["visible_source_state_sha256"],
            " ",
        )
    )
    assert blank == {
        "status": "rejected",
        "error": "operation arguments must not be blank",
    }
    assert read_evidence_lifecycle_state(package, run_dir)["checkpoint_runs"][0]["operation_actions"] == []

    response = json.loads(
        control.execute_operation(
            "baseline_analysis",
            "hydrology.design-10yr",
            source_payload["visible_source_state_sha256"],
            "Calculate the declared baseline design hydrology.",
        )
    )

    assert set(response) == {
        "status",
        "action_id",
        "checkpoint_id",
        "operation_id",
        "operation_kind",
        "disposition",
        "visible_source_state_sha256",
        "input_projection_sha256",
        "prerequisite_action_ids",
        "retained_from_action_id",
        "budget_consumed",
        "remaining_budget",
        "artifacts",
    }
    assert response["status"] == "completed"
    assert response["action_id"] == "operation-000001"
    assert response["checkpoint_id"] == "baseline_analysis"
    assert response["operation_id"] == "hydrology.design-10yr"
    assert response["disposition"] == "computed"
    assert response["visible_source_state_sha256"] == source_payload["visible_source_state_sha256"]
    assert response["remaining_budget"] == 5
    assert response["artifacts"] == [
        {
            "path": "inbox/baseline_analysis/operations/operation-000001/hydrology.json",
            "sha256": response["artifacts"][0]["sha256"],
        }
    ]
    assert json.loads(workspace.read_workspace_file(response["artifacts"][0]["path"]))["status"] == "ok"
    encoded = json.dumps(response)
    for host_only in (
        "session_id",
        "attempt_id",
        "physical_source_state",
        "lifecycle_operations/",
        "request_sha256",
        "pre_action_state_sha256",
        "post_action_state_sha256",
    ):
        assert host_only not in encoded

    reused = json.loads(
        control.execute_operation(
            "baseline_analysis",
            "hydrology.design-10yr",
            source_payload["visible_source_state_sha256"],
            "Reuse the current design hydrology if its source projection still matches.",
        )
    )
    assert reused["status"] == "already_current"
    assert reused["action_id"] == "operation-000002"
    assert reused["retained_from_action_id"] == "operation-000001"
    assert reused["budget_consumed"] == 0
    assert reused["remaining_budget"] == 5
    assert reused["artifacts"] == response["artifacts"]

    stale = json.loads(
        control.execute_operation(
            "baseline_analysis",
            "hydrology.design-10yr",
            "f" * 64,
            "Calculate using this supplied visible source identity.",
        )
    )
    assert stale["status"] == "rejected"
    assert stale["action_id"] == "operation-000003"
    assert stale["rejection"] == "stale_visible_source"
    assert stale["budget_consumed"] == 0
    assert stale["remaining_budget"] == 5
    assert stale["artifacts"] == []
    assert "session_id" not in json.dumps(stale)
    assert "attempt_id" not in json.dumps(stale)


def test_workspace_tool_rejects_undeclared_hydraulic_submission_fields(tmp_path: Path) -> None:
    package = _interaction_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    prepare_evidence_checkpoint(package, run_dir)
    workspace = EvidenceLifecycleWorkspaceTool(
        package_dir=package,
        run_dir=run_dir,
        visibility_policy=LifecycleVisibilityPolicy.PERSISTENT_CONTEXT,
    )
    checkpoint = load_evidence_lifecycle_spec(package).checkpoints[0]
    submission: dict[str, Any] = {field: {} for field in checkpoint.required_submission_fields}
    submission["checkpoint_id"] = checkpoint.checkpoint_id
    submission["memo"] = {}

    response = json.loads(
        workspace.write_checkpoint_submission(
            checkpoint.checkpoint_id,
            json.dumps(submission),
        )
    )

    assert response == {
        "status": "rejected",
        "error": "checkpoint submission contains undeclared fields: memo",
    }
    assert not (run_dir / "workspace" / checkpoint.submission_path).exists()


def test_local_tool_schema_captures_operation_capability_in_both_execution_modes() -> None:
    persistent = _lifecycle_tool_schema(
        "persistent_context",
        supports_evidence_requests=False,
        supports_lifecycle_operations=True,
    )
    fresh = _lifecycle_tool_schema(
        "fresh_context",
        supports_evidence_requests=False,
        supports_lifecycle_operations=True,
    )

    assert [tool["name"] for tool in persistent] == [
        "list_workspace",
        "read_workspace_file",
        "write_checkpoint_submission",
        "execute_operation",
        "submit_checkpoint",
        "revisit_checkpoint",
    ]
    assert [tool["name"] for tool in fresh] == [
        "list_workspace",
        "read_workspace_file",
        "write_checkpoint_submission",
        "execute_operation",
    ]
    operation = next(tool for tool in persistent if tool["name"] == "execute_operation")
    assert "checkpoint_id" in operation["signature"]
    assert "operation_id" in operation["signature"]
    assert "visible_source_state_sha256" in operation["signature"]
    assert "reason" in operation["signature"]
    assert "session_id" not in operation["signature"]


@pytest.mark.parametrize("execution_mode", ["persistent_context", "fresh_context"])
def test_local_runner_assemblies_expose_and_execute_operation_tool(
    tmp_path: Path,
    execution_mode: str,
) -> None:
    package = _interaction_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    registry = _OperationExercisingRegistry(package, run_dir)
    common: dict[str, Any] = {
        "package_dir": package,
        "run_dir": run_dir,
        "model": "deterministic-operation-probe",
        "registry": registry,
        "verifier": _completed_runtime_verification,
    }

    if execution_mode == "persistent_context":
        result = run_local_evidence_lifecycle_session(**common)
    else:
        result = run_local_evidence_lifecycle_fresh_context(**common)

    assert result["evidence"]["lifecycle"]["status"] == "complete"
    assert registry.operation_response is not None
    assert registry.operation_response["status"] == "completed"
    assert all("execute_operation" in names for names in registry.native_tool_names)
    assert all("execute_operation" in names for names in registry.request_tool_names)
    actions = result["evidence"]["lifecycle"]["checkpoint_runs"][0]["operation_actions"]
    assert len(actions) == 1
    assert actions[0]["operation_id"] == "hydrology.design-10yr"
    manifest = json.loads((run_dir / "experiment-manifest.json").read_text(encoding="utf-8"))
    schema_names = [item["name"] for item in manifest["interaction"]["tool_schema"]]
    assert "execute_operation" in schema_names


class _OperationExercisingRegistry:
    """Drive the real lifecycle tools through both local adapter assembly paths."""

    def __init__(self, package: Path, run_dir: Path) -> None:
        self.package = package
        self.run_dir = run_dir
        self.native_tool_names: list[list[str]] = []
        self.request_tool_names: list[list[str]] = []
        self.operation_response: dict[str, Any] | None = None

    def build(self, *, native_tools: list[Any], **_kwargs: Any) -> Any:
        tool_map = {tool.__name__: tool for tool in native_tools}
        self.native_tool_names.append(list(tool_map))
        registry = self

        class _OperationExercisingAdapter:
            def execute(self, request: Any) -> SimpleNamespace:
                registry.request_tool_names.append([tool.name for tool in request.tools])
                checkpoint_id = Path(request.output_path).stem
                if checkpoint_id == "output":
                    lifecycle = read_evidence_lifecycle_state(registry.package, registry.run_dir)
                    checkpoint_id = str(lifecycle["active_checkpoint_id"])
                if registry.operation_response is None:
                    source_response = json.loads(tool_map["read_workspace_file"]("hydraulics/current-source.json"))
                    source = json.loads(source_response["content"])
                    registry.operation_response = json.loads(
                        tool_map["execute_operation"](
                            checkpoint_id,
                            "hydrology.design-10yr",
                            source["visible_source_state_sha256"],
                            "Calculate the declared baseline design hydrology.",
                        )
                    )
                spec = load_evidence_lifecycle_spec(registry.package)
                checkpoint = next(item for item in spec.checkpoints if item.checkpoint_id == checkpoint_id)
                submission: dict[str, Any] = {"checkpoint_id": checkpoint_id}
                submission.update(
                    {field: {} for field in checkpoint.required_submission_fields if field != "checkpoint_id"}
                )
                written = json.loads(
                    tool_map["write_checkpoint_submission"](
                        checkpoint_id,
                        json.dumps(submission),
                    )
                )
                assert written["status"] == "written"
                if "submit_checkpoint" in tool_map:
                    while True:
                        submitted = json.loads(tool_map["submit_checkpoint"](checkpoint_id))
                        if submitted["status"] == "complete":
                            break
                        checkpoint_id = submitted["checkpoint_id"]
                        checkpoint = next(item for item in spec.checkpoints if item.checkpoint_id == checkpoint_id)
                        submission = {"checkpoint_id": checkpoint_id}
                        submission.update(
                            {field: {} for field in checkpoint.required_submission_fields if field != "checkpoint_id"}
                        )
                        tool_map["write_checkpoint_submission"](
                            checkpoint_id,
                            json.dumps(submission),
                        )
                return SimpleNamespace(
                    agent_output=SimpleNamespace(status=SimpleNamespace(value="completed")),
                    transcript=[],
                    raw_output_text=None,
                    provider_error=None,
                    failure_kind=None,
                    usage_input_tokens=1,
                    usage_output_tokens=1,
                    usage_cache_read_tokens=0,
                    usage_cache_write_tokens=0,
                )

        return _OperationExercisingAdapter()
