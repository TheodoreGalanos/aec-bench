# ABOUTME: Runs LLM-driven semantic decomposition for task genome sidecars.
# ABOUTME: Reviews snapshot-resolved source spans without persisting copied task source.

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from aec_bench.contracts.task_genome import TaskGenomeManifest, TaskGenomeReview
from aec_bench.contracts.task_snapshot import TaskSnapshotRef
from aec_bench.tasks.genome import resolve_task_genome_evidence

Reviewer = Callable[[str], TaskGenomeManifest | dict[str, Any]]

_DECOMPOSITION_SYSTEM = """You decompose AEC benchmark tasks into task genome manifests.

Use only the supplied review artifact and snapshot-resolved excerpts. Do not invent files,
verifier behavior, or standards.
Improve the deterministic manifest semantically: identify pressure points, recombinable
parts, reasoning moves, difficulty controls, and trajectory affordances. Every pressure
point must be supported by the supplied evidence map. Mark uncertain semantic calls with
confidence='low'.
"""


def build_decomposition_prompt(
    review: TaskGenomeReview,
    *,
    task_dir: Path,
    current_task: TaskSnapshotRef,
) -> str:
    """Build a prompt from one review and its verified snapshot-resolved excerpts."""
    review_yaml = yaml.safe_dump(
        review.model_dump(mode="json", exclude_none=True),
        sort_keys=False,
        allow_unicode=False,
    )
    excerpts_yaml = yaml.safe_dump(
        resolve_task_genome_evidence(review, task_dir=task_dir, current_task=current_task),
        sort_keys=False,
        allow_unicode=False,
    )
    return (
        f"{_DECOMPOSITION_SYSTEM}\n\n"
        "Output schema: TaskGenomeManifest. Preserve valid deterministic fields when the "
        "evidence supports them, but improve semantic fields where the evidence is richer.\n\n"
        "Required review focus:\n"
        "- pressure_points: identify traps, formula choices, omitted terms, audit errors, "
        "unit conversions, lookup pressure, and verifier-sensitive distinctions.\n"
        "- reasoning_moves: name the operations the solver must perform.\n"
        "- difficulty_controls: explain knobs that would make variants easier or harder.\n"
        "- trajectory_affordances: list intermediate evidence a good trajectory should show.\n"
        "- extraction: record which fields still need human review.\n\n"
        "Review artifact:\n"
        f"{review_yaml}\n"
        "Snapshot-resolved evidence excerpts:\n"
        f"{excerpts_yaml}"
    )


def decompose_task_genome(
    review: TaskGenomeReview,
    *,
    task_dir: Path,
    current_task: TaskSnapshotRef,
    model_name: str,
    reviewer: Reviewer | None = None,
) -> TaskGenomeReview:
    """Run semantic decomposition and return a new review of the same task snapshot."""
    prompt = build_decomposition_prompt(review, task_dir=task_dir, current_task=current_task)
    if reviewer is not None:
        reviewer_result = reviewer(prompt)
        if isinstance(reviewer_result, TaskGenomeManifest):
            genome = reviewer_result
        else:
            genome = TaskGenomeManifest.model_validate(reviewer_result)
        return _with_reviewed_genome(review, genome=genome, reviewer=model_name)

    from pydantic_ai import Agent

    from aec_bench.evolution.structured_evolver import _build_pydantic_model

    model = _build_pydantic_model(model_name)
    agent: Agent[None, TaskGenomeManifest] = Agent(
        model,
        system_prompt=_DECOMPOSITION_SYSTEM,
        output_type=TaskGenomeManifest,
        retries=2,
    )
    run_result = agent.run_sync(prompt)
    return _with_reviewed_genome(review, genome=run_result.output, reviewer=model_name)


def _with_reviewed_genome(
    review: TaskGenomeReview,
    *,
    genome: TaskGenomeManifest,
    reviewer: str,
) -> TaskGenomeReview:
    payload = review.model_dump(mode="python")
    payload.update(status="needs_review", reviewer=reviewer, genome=genome)
    return TaskGenomeReview.model_validate(payload)
