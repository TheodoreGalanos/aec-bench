# ABOUTME: Resolves task-owned lifecycle operations for runtime integration tests.
# ABOUTME: Keeps each test call explicit without importing concrete stormwater resolver classes.

from pathlib import Path

from aec_bench.lifecycles.catalogue import lifecycle_operation_resolver
from aec_bench.lifecycles.runtime.operation_protocol import LifecycleOperationResolver


def resolve_operation_runtime(package_dir: Path, run_dir: Path) -> LifecycleOperationResolver:
    resolver = lifecycle_operation_resolver(Path(package_dir), Path(run_dir))
    assert resolver is not None
    return resolver
