# ABOUTME: Tests the plain run plan and its one versioned publication envelope.
# ABOUTME: Verifies relationship validation without bundle hashes or provider-owned task identity.

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from aec_bench.contracts.run_bundle import PublishedRunPackage, RunPlan
from aec_bench.contracts.task_snapshot import ArtifactTaskSnapshotRef
from aec_bench.ledger.artifact_repository import ArtifactRepository
from tests.support.adaptive_harness import build_adaptive_bundle, write_adaptive_task


def test_run_plan_embeds_ordinary_configuration_without_parallel_identity(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    write_adaptive_task(tasks_root)
    plan = build_adaptive_bundle(
        tasks_root=tasks_root,
        artifact_repository=ArtifactRepository(tmp_path / "artifacts"),
    )

    payload = plan.model_dump(mode="json")
    assert set(payload) == {
        "run_manifest",
        "task_snapshots",
        "harness",
        "execution_program",
        "review",
    }
    assert "bundle_id" not in payload
    assert "kernel_ref" not in payload
    assert "harbor" not in payload
    assert "repetitions" not in payload
    assert isinstance(plan.task_snapshots[0], ArtifactTaskSnapshotRef)
    task_payload = payload["task_snapshots"][0]
    assert set(task_payload) == {"kind", "task_id", "task_identity", "artifact"}
    assert "provider" not in task_payload
    assert "definition_sha256" not in task_payload
    assert "package_sha256" not in task_payload


def test_run_plan_validates_program_to_harness_relationship(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    write_adaptive_task(tasks_root)
    plan = build_adaptive_bundle(tasks_root=tasks_root)
    payload = plan.model_dump(mode="python")
    program = plan.execution_program.model_copy(
        update={"harness_ref": plan.harness.ref.model_copy(update={"instance_id": "different-harness"})}
    )
    payload["execution_program"] = program

    with pytest.raises(ValidationError, match="does not target the embedded harness"):
        RunPlan.model_validate(payload)


def test_run_plan_requires_exact_task_binding_order(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    write_adaptive_task(tasks_root, task_id="civil/calculation/alpha")
    write_adaptive_task(tasks_root, task_id="civil/calculation/beta")
    plan = build_adaptive_bundle(
        tasks_root=tasks_root,
        task_ids=("civil/calculation/alpha", "civil/calculation/beta"),
    )
    payload = plan.model_dump(mode="python")
    payload["task_snapshots"] = tuple(reversed(plan.task_snapshots))

    with pytest.raises(ValidationError, match="exactly match"):
        RunPlan.model_validate(payload)


def test_published_run_package_has_one_schema_and_unique_trial_references(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    write_adaptive_task(tasks_root)
    repository = ArtifactRepository(tmp_path / "artifacts")
    plan = build_adaptive_bundle(tasks_root=tasks_root, artifact_repository=repository)
    trial_ref = repository.publish_bytes(data=b"{}\n", media_type="application/json")

    package = PublishedRunPackage(run_plan=plan, trial_refs=(trial_ref,))
    assert package.schema_version == 1
    assert set(package.model_dump(mode="json")) == {"schema_version", "run_plan", "trial_refs"}
    with pytest.raises(ValidationError, match="must be unique"):
        PublishedRunPackage(run_plan=plan, trial_refs=(trial_ref, trial_ref))
