# ABOUTME: Shared trajectory reading and step grouping utilities for viewers.
# ABOUTME: Provides step grouping, status computation, and adapter type detection.

from __future__ import annotations

from collections import defaultdict

from aec_bench.contracts.trajectory import TrajectoryEntry


def group_by_step(
    entries: list[TrajectoryEntry],
) -> dict[int, list[TrajectoryEntry]]:
    """Group trajectory entries by step number."""
    groups: dict[int, list[TrajectoryEntry]] = defaultdict(list)
    for entry in entries:
        groups[entry.step].append(entry)
    return dict(sorted(groups.items()))


def compute_step_status(entries: list[TrajectoryEntry]) -> str:
    """Derive a step status from its trajectory entries."""
    has_error = any(e.exit_code is not None and e.exit_code != 0 for e in entries)
    if has_error:
        return "fail"
    has_incomplete = any(e.exit_code is None and e.role == "tool" for e in entries)
    if has_incomplete:
        return "incomplete"
    return "success"


def detect_rlm_trial(entries: list[TrajectoryEntry]) -> bool:
    """Check if a trial is an RLM trial by looking for RLM-specific metadata."""
    return any(
        e.metadata is not None and ("template_progress" in e.metadata or "tokens" in e.metadata) for e in entries
    )


def detect_adapter_type(entries: list[TrajectoryEntry]) -> str:
    """Detect adapter type from trajectory metadata.

    Lambda-RLM entries carry 'phase' and 'plan_state' in metadata.
    RLM entries carry 'template_progress' or 'tokens'.
    """
    for e in entries:
        if e.metadata and "phase" in e.metadata and "plan_state" in e.metadata:
            return "lambda-rlm"
    for e in entries:
        if e.metadata and ("template_progress" in e.metadata or "tokens" in e.metadata):
            return "rlm"
    return "other"
