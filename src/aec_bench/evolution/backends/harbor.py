# ABOUTME: Harbor/Modal solve backend for the evolution orchestrator.
# ABOUTME: Wraps existing TrialRunner + ComputeBackend with workspace snapshot injection.

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from aec_bench.contracts.evolution import WorkspaceSnapshot
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.evolution.backends.local import SolveFn
from aec_bench.evolution.snapshot import serialise_snapshot

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def inject_snapshot_into_workspace(
    snapshot: WorkspaceSnapshot,
    workspace_dir: Path,
) -> None:
    """Write the serialised workspace snapshot as system_prompt.md.

    Overwrites any existing file at that path. The agent reads this file
    to obtain its system prompt and domain knowledge skills at runtime.
    """
    prompt_content = serialise_snapshot(snapshot)
    (workspace_dir / "system_prompt.md").write_text(prompt_content, encoding="utf-8")
    logger.debug(
        "Injected snapshot (version=%s) into %s",
        snapshot.workspace_version,
        workspace_dir,
    )


def make_harbor_solve_fn(
    *,
    trial_runner: object,
    backend: object,
    tasks: list[object],
    adapter: object,
    experiment_id: str,
    runtime_image: str = "evolution",
    adapter_revision: str | None = None,
) -> SolveFn:
    """Create a solve function that runs tasks via Harbor/Modal.

    Each invocation injects the current workspace snapshot into each task's
    instance directory as system_prompt.md, then delegates to TrialRunner.run()
    which handles environment build, container launch, agent execution,
    verifier running, and TrialRecord construction.

    Uses object types for heavy dependencies (Modal SDK, TrialRunner) to avoid
    importing them at module load time. TYPE_CHECKING imports provide IDE support.
    """
    call_count = [0]

    def solve(snapshot: WorkspaceSnapshot, batch_size: int) -> list[TrialRecord]:
        if not tasks:
            return []

        records: list[TrialRecord] = []
        batch = tasks[:batch_size]

        for i, task in enumerate(batch):
            trial_id = f"evo-{experiment_id}-c{call_count[0]}-t{i}"

            try:
                # Inject evolved prompt and skills into the task directory before
                # the runner picks it up. The runner reads system_prompt.md as
                # part of the container environment setup.
                inject_snapshot_into_workspace(snapshot, task.instance_dir)

                record = trial_runner.run(
                    trial_id=trial_id,
                    experiment_id=experiment_id,
                    task=task,
                    task_revision="evolution",
                    backend=backend,
                    adapter=adapter,
                    runtime_image=runtime_image,
                    adapter_revision=adapter_revision,
                )
                records.append(record)
            except Exception:
                logger.exception("Harbor task %d failed (trial_id=%s)", i, trial_id)

        call_count[0] += 1
        return records

    return solve
