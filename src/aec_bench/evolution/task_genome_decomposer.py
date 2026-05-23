# ABOUTME: Runs LLM-driven semantic decomposition for task genome sidecars.
# ABOUTME: Converts bounded evidence packets into validated TaskGenomeManifest objects.

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import yaml

from aec_bench.contracts.task_genome import TaskGenomeEvidencePacket, TaskGenomeManifest

Reviewer = Callable[[str], TaskGenomeManifest | dict[str, Any]]

_DECOMPOSITION_SYSTEM = """You decompose AEC benchmark tasks into task genome manifests.

Use only the supplied evidence packet. Do not invent files, verifier behavior, or standards.
Improve the deterministic manifest semantically: identify pressure points, recombinable
parts, reasoning moves, difficulty controls, and trajectory affordances. Every pressure
point must include provenance. Mark uncertain semantic calls with confidence='low' or
status='needs_review'.
"""


def build_decomposition_prompt(packet: TaskGenomeEvidencePacket) -> str:
    """Build the bounded prompt handed to a lite decomposition reviewer."""
    evidence_yaml = yaml.safe_dump(
        packet.model_dump(mode="json", exclude_none=True),
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
        "Evidence packet:\n"
        f"{evidence_yaml}"
    )


def decompose_task_genome(
    packet: TaskGenomeEvidencePacket,
    *,
    model_name: str,
    reviewer: Reviewer | None = None,
) -> TaskGenomeManifest:
    """Run semantic decomposition with an injected or real PydanticAI reviewer."""
    prompt = build_decomposition_prompt(packet)
    if reviewer is not None:
        result = reviewer(prompt)
        if isinstance(result, TaskGenomeManifest):
            return result
        return TaskGenomeManifest.model_validate(result)

    from pydantic_ai import Agent

    from aec_bench.evolution.structured_evolver import _build_pydantic_model

    model = _build_pydantic_model(model_name)
    agent: Agent[None, TaskGenomeManifest] = Agent(
        model,
        system_prompt=_DECOMPOSITION_SYSTEM,
        output_type=TaskGenomeManifest,
        retries=2,
    )
    result = agent.run_sync(prompt)
    return result.output
