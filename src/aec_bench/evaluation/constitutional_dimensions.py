# ABOUTME: Post-hoc constitutional evaluation dimensions computed from trajectory data.
# ABOUTME: Metrics: context efficiency, state utilisation, turns-to-first-output, and stall count.

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from aec_bench.contracts.trajectory import TrajectoryEntry

_METADATA_PATTERN = re.compile(r"Output:\s*[\d,]+\s*chars\.")


@dataclass(frozen=True)
class ConstitutionalDimensions:
    """Mechanical evaluation dimensions computed from a trajectory."""

    context_efficiency_ratio: float  # fraction of repl tool results that were metadata-only
    state_utilisation_ratio: float  # fraction of steps that created durable state
    turns_to_first_output: int | None  # None if no output produced
    stall_count: int  # number of times stall_threshold was crossed


def _is_metadata_stdout(stdout: str | None) -> bool:
    if not stdout:
        return False
    return bool(_METADATA_PATTERN.search(stdout))


def _step_created_state(entry: TrajectoryEntry) -> bool:
    meta = entry.metadata or {}
    if meta.get("new_vars"):
        return True
    if meta.get("scratchpad_writes", 0) > 0:
        return True
    return False


def _first_output_step(trajectory: Sequence[TrajectoryEntry]) -> int | None:
    for entry in trajectory:
        meta = entry.metadata or {}
        if meta.get("section_filled"):
            return entry.step
        if meta.get("sections_filled", 0) > 0:
            return entry.step
        cmd = entry.command or ""
        if cmd.startswith("FILL(") or cmd.startswith("FINAL_VAR("):
            return entry.step
    return None


def _count_stalls(trajectory: Sequence[TrajectoryEntry], *, stall_threshold: int) -> int:
    """Count number of times a no-progress run of length >= stall_threshold+1 occurred.

    A stall event is counted once at the moment its length crosses the threshold,
    and then not counted again until progress is made.
    """
    stalls = 0
    in_stall = False
    streak = 0
    last_sections_filled = 0
    for entry in trajectory:
        meta = entry.metadata or {}
        current = int(meta.get("sections_filled", last_sections_filled))
        if current > last_sections_filled:
            streak = 0
            in_stall = False
            last_sections_filled = current
        else:
            streak += 1
            if streak >= stall_threshold and not in_stall:
                stalls += 1
                in_stall = True
    return stalls


def compute_constitutional_dimensions(
    *,
    trajectory: Sequence[TrajectoryEntry],
    stall_threshold: int = 3,
) -> ConstitutionalDimensions:
    """Compute mechanical constitutional dimensions from a trajectory.

    stall_threshold matches ProgressObligationParams.stall_threshold_turns.
    """
    if not trajectory:
        return ConstitutionalDimensions(
            context_efficiency_ratio=0.0,
            state_utilisation_ratio=0.0,
            turns_to_first_output=None,
            stall_count=0,
        )

    # Context efficiency: fraction of repl-tool entries with metadata-only stdout
    repl_entries = [e for e in trajectory if e.tool_name == "repl" and e.stdout is not None]
    metadata_count = sum(1 for e in repl_entries if _is_metadata_stdout(e.stdout))
    context_efficiency = metadata_count / len(repl_entries) if repl_entries else 0.0

    # State utilisation: fraction of trajectory steps that created durable state
    state_count = sum(1 for e in trajectory if _step_created_state(e))
    state_ratio = state_count / len(trajectory)

    turns_to_first = _first_output_step(trajectory)
    stalls = _count_stalls(trajectory, stall_threshold=stall_threshold)

    return ConstitutionalDimensions(
        context_efficiency_ratio=context_efficiency,
        state_utilisation_ratio=state_ratio,
        turns_to_first_output=turns_to_first,
        stall_count=stalls,
    )
