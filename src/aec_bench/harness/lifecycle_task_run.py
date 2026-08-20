# ABOUTME: Adapts one complete lifecycle run to the existing harness task-run result boundary.
# ABOUTME: Keeps task execution composition outside lifecycle progression and persistence.

from __future__ import annotations

import copy
from collections.abc import Callable
from pathlib import Path
from typing import Any

from aec_bench.lifecycles.runtime.episode import LifecycleEpisodeEnvironment
from aec_bench.lifecycles.runtime.lifecycle import (
    LifecycleVerifier,
    load_evidence_lifecycle_spec,
    run_lifecycle,
    validate_lifecycle_verification,
)
from aec_bench.lifecycles.runtime.operation_protocol import LifecycleOperationResolver
from aec_bench.lifecycles.runtime.request_store import lifecycle_ledger_path


def build_evidence_lifecycle_task_run_resolver(
    *,
    package_dir: Path,
    run_dir: Path,
    episode_environment: LifecycleEpisodeEnvironment,
    verifier: LifecycleVerifier,
    operation_resolver: LifecycleOperationResolver | None = None,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Wrap a complete lifecycle as one existing harness task-run."""

    def resolve(runtime_result: dict[str, Any]) -> dict[str, Any]:
        lifecycle = run_lifecycle(
            package_dir,
            run_dir,
            episode_environment=episode_environment,
            operation_resolver=operation_resolver,
        )
        verification = validate_lifecycle_verification(verifier(Path(package_dir), Path(run_dir)))
        reward = float(verification["reward"])
        passed = bool(verification["passed"])
        process_id = runtime_result.get("process_id") or "process"
        spec = load_evidence_lifecycle_spec(Path(package_dir))
        return {
            "run_id": f"{process_id}.{spec.lifecycle_id}",
            "evidence": {
                "score": {"reward": reward, "passed": passed},
                "gates": copy.deepcopy(verification.get("gates", {})),
                "lifecycle": lifecycle,
                "verification": verification,
                "artifacts": {
                    "run_dir": str(Path(run_dir)),
                    "ledger": str(lifecycle_ledger_path(Path(run_dir))),
                },
            },
        }

    return resolve
