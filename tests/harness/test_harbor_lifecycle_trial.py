# ABOUTME: Exercises stormwater Harbor Trial orchestration through the production lifecycle bridge.
# ABOUTME: Proves integration phase ordering and verifier ownership without container claims.

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, cast

from harbor.models.trial.config import TrialConfig  # type: ignore[import-untyped]

from aec_bench.harness.harbor_task_export import (
    HARBOR_LIFECYCLE_BRIDGE_MODE,
    export_compiled_lifecycle_harbor_task,
)
from aec_bench.lifecycles.compiled import compile_lifecycle
from tests.support.harbor_local_environment import run_harbor_trial

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_ID = "hydraulic-interaction-lifecycle-review"


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def test_harbor_trial_orchestrates_public_bridge_then_independent_verifier(tmp_path: Path) -> None:
    compiled = compile_lifecycle(
        TEMPLATE_ID,
        tmp_path / "compiled",
        variant_id="administrative_no_op",
    )
    exported = export_compiled_lifecycle_harbor_task(
        compiled,
        tmp_path / "tasks" / "civil" / "stormwater-hydraulic-interaction",
        project_root=REPO_ROOT,
    )
    trial_name = "stormwater-public-bridge"
    config = TrialConfig.model_validate(
        {
            "task": {"path": str(exported.task_dir)},
            "trial_name": trial_name,
            "trials_dir": str(tmp_path / "trials"),
            "agent": {
                "import_path": ("tests.support.harbor_lifecycle_reference:PublicToolReferenceEntrypointAgent"),
                "model_name": "public-tool-reference",
                "kwargs": {
                    "lifecycle_bridge": HARBOR_LIFECYCLE_BRIDGE_MODE,
                    "adapter": "tool_loop",
                    "max_turns": 60,
                },
            },
            "environment": {
                "import_path": ("tests.support.harbor_local_environment:LocalFilesystemHarborEnvironment"),
                "delete": False,
            },
        }
    )

    result = asyncio.run(run_harbor_trial(config))

    assert result.exception_info is None
    assert result.agent_result is not None
    assert result.agent_result.metadata["bridge_mode"] == HARBOR_LIFECYCLE_BRIDGE_MODE
    assert result.agent_result.metadata["lifecycle_status"] == "complete"
    assert result.agent_result.metadata["reward_owner"] == "harbor_verifier"
    assert result.verifier_result is not None
    assert result.verifier_result.rewards == {"reward": 1.0}

    trial_dir = config.trials_dir / trial_name
    operations = [
        json.loads(line)
        for line in (trial_dir / "environment-operations.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    uploads = [event for event in operations if event["event"] == "upload_dir"]
    upload_targets = [event["target"] for event in uploads]
    assert upload_targets[0] == "/workspace/lifecycle-run"
    assert upload_targets[-1] == "/tests"
    assert upload_targets.count("/tests") == 1
    assert not any("/opt/aec_bench" in str(event) for event in operations)
    tests_upload_index = next(index for index, event in enumerate(operations) if event.get("target") == "/tests")
    run_upload_index = next(
        index for index, event in enumerate(operations) if event.get("target") == "/workspace/lifecycle-run"
    )
    assert run_upload_index < tests_upload_index

    sandbox = trial_dir / "local-environment"
    run_dir = sandbox / "workspace" / "lifecycle-run"
    lifecycle = _read_json(run_dir / "state.json")
    assert lifecycle["status"] == "complete"
    assert not list(run_dir.rglob("verification*.json"))
    assert not list(run_dir.rglob("reward*.json"))

    conversation = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(run_dir.glob("sessions/*/conversation.jsonl"))
    )
    assert "../tests/compiled-world/hidden/variant.json" in conversation
    assert "workspace path must stay inside the lifecycle workspace" in conversation
    assert "inbox/revision_analysis/notice.md" in conversation
    assert "workspace file not found" in conversation
    assert "Completed from staged public lifecycle tool outputs." in (
        run_dir / "sessions" / "session-001" / "raw_output.md"
    ).read_text(encoding="utf-8")

    details = _read_json(trial_dir / "verifier" / "details.json")
    assert details["reward_owner"] == "harbor_verifier"
    assert details["source_package_sha256"] == compiled.envelope.package_sha256
    assert details["verification"]["reward"] == 1.0

    dockerfile = (exported.task_dir / "environment" / "Dockerfile").read_text(encoding="utf-8")
    assert "FROM --platform=linux/amd64 python:3.13-slim-bookworm@sha256:" in dockerfile
    requirements = (
        "annotated-types==0.7.0",
        "pydantic-core==2.46.4",
        "pydantic==2.13.4",
        "typing-extensions==4.15.0",
        "typing-inspection==0.4.2",
    )
    for requirement in requirements:
        assert requirement in dockerfile
    manifest = _read_json(exported.manifest_path)
    assert "@sha256:" in manifest["agent_surface"]["base_image"]
    assert manifest["agent_surface"]["dependencies"] == list(requirements)
    reference_source = (REPO_ROOT / "tests" / "support" / "harbor_lifecycle_reference.py").read_text(encoding="utf-8")
    for forbidden_reference_capability in (
        "from pathlib",
        "import pathlib",
        ".__self__",
        "package_dir",
        "stormwater_hydraulic_interaction_smoke",
        "stormwater_hydraulic_interaction_verifier",
    ):
        assert forbidden_reference_capability not in reference_source
