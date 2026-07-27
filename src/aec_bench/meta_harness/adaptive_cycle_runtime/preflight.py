# ABOUTME: Revalidates adaptive-cycle archives, task surfaces, and split visibility before dispatch.
# ABOUTME: Keeps all no-side-effect preflight gates ahead of external execution.

from __future__ import annotations

from pathlib import Path

from aec_bench.contracts.task_definition import Visibility
from aec_bench.meta_harness.adaptive_cycle_runtime.contracts import (
    AdaptiveCycleSpec,
)
from aec_bench.meta_harness.applicability import profile_task_applicability
from aec_bench.meta_harness.kernel_catalogue import KernelRuntimeRegistry
from aec_bench.meta_harness.motif_library import (
    MotifLibrary,
    load_pinned_motif_library,
)
from aec_bench.tasks.registry import TaskRegistry


def preflight_cycle_inputs(
    *,
    spec: AdaptiveCycleSpec,
    registry: KernelRuntimeRegistry,
    tasks_root: Path,
) -> MotifLibrary:
    """Recompute every split boundary and archive pin before external dispatch."""

    library = load_pinned_motif_library(spec.input_motif_library)
    if spec.source_stage.candidate_requests[0].kernel_ref != registry.manifest.ref:
        raise ValueError("adaptive cycle spec does not target the installed fixed kernel")
    child = profile_task_applicability(
        task_refs=spec.child_calibration.instantiation.task_refs,
        tasks_root=tasks_root,
        registry=registry,
    )
    transfer = profile_task_applicability(
        task_refs=spec.transfer.instantiation.task_refs,
        tasks_root=tasks_root,
        registry=registry,
    )
    if child != spec.child_calibration.applicability:
        raise ValueError("adaptive cycle child calibration applicability changed after preregistration")
    if transfer != spec.transfer.applicability:
        raise ValueError("adaptive cycle transfer applicability changed after preregistration")
    _validate_task_split_visibility(
        spec=spec,
        tasks_root=tasks_root,
    )
    return library


def _validate_task_split_visibility(
    *,
    spec: AdaptiveCycleSpec,
    tasks_root: Path,
) -> None:
    registry_tasks = TaskRegistry(tasks_root=Path(tasks_root))
    registry_tasks.reload()
    expected_visibility = {
        Visibility.PUBLIC: tuple(
            sorted(
                {task_ref for request in spec.source_stage.candidate_requests for task_ref in request.task_refs}
                | set(spec.repair_request.pairing.task_ids)
                | set(spec.child_calibration.instantiation.task_refs)
            )
        ),
        Visibility.HOLDOUT: spec.transfer.instantiation.task_refs,
    }
    for visibility, task_refs in expected_visibility.items():
        invalid = tuple(
            task_ref
            for task_ref in task_refs
            if (task := registry_tasks.get(task_ref)) is None or task.visibility is not visibility
        )
        if invalid:
            raise ValueError(
                f"adaptive cycle {visibility.value} split contains invalid task visibility: " + ", ".join(invalid)
            )
