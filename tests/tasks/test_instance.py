# ABOUTME: Tests for execution-ready task instance resolution in aec-bench Python.
# ABOUTME: Covers path normalization from TaskDefinition to harness-facing paths.

from pathlib import Path

from aec_bench.tasks.instance import ResolvedTaskInstance, resolve_instance_paths
from tests.support.task_factories import make_task_definition


def test_resolve_instance_paths_normalizes_relative_paths() -> None:
    project_root = Path("/tmp/aec-bench-python")
    instance_dir = project_root / "tasks" / "mechanical" / "heat-load" / "demo-instance"
    task = make_task_definition()

    resolved = resolve_instance_paths(task, instance_dir)

    assert isinstance(resolved, ResolvedTaskInstance)
    assert resolved.instance_dir == instance_dir
    assert resolved.environment_dockerfile == instance_dir / "environment/Dockerfile"
    assert resolved.verifier_script == instance_dir / "tests/test.sh"
