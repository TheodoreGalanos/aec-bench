# ABOUTME: Runs one-shot evolution variation against an isolated scratch workspace.
# ABOUTME: Keeps auto-seeding, mutation application, and child export outside canonical state.

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING

from aec_bench.contracts.evolution import (
    EvolutionObservation,
    MutationSummary,
    SkillEntry,
    WorkspaceSnapshot,
)
from aec_bench.evolution.core import VariationRequest, VariationResult, VariationStatus
from aec_bench.evolution.evolver_tools import build_evolver_toolset
from aec_bench.evolution.graveyard import MutationGraveyard
from aec_bench.evolution.mutation import ParsedMutationResponse, apply_mutations, parse_evolver_response
from aec_bench.evolution.prompts import (
    build_evolution_analysis_prompt,
    build_evolution_brief,
    build_evolver_system_prompt,
)
from aec_bench.evolution.seeding import compute_seed_skills
from aec_bench.evolution.workspace import Workspace, scratch_workspace_from

if TYPE_CHECKING:
    from aec_bench.evaluation.behavioral import BehavioralLLMClient

logger = logging.getLogger(__name__)


def run_structured_variation(
    request: VariationRequest,
    source: Workspace,
    child_candidate_id: str,
    *,
    evolver_model_name: str | None = None,
    evolver_llm: BehavioralLLMClient | None = None,
    compaction_llm: BehavioralLLMClient | None = None,
) -> VariationResult:
    """Run one structured variation request in scratch and return its child.

    The source workspace is never used as the mutation target. Auto-seeded
    skills and model actions are applied to scratch, and the submitted child
    is exported before the scratch directory is cleaned up. A request that
    makes no effective content change returns ``ABSTAINED``.
    """
    if request.scope.value == "skip":
        return VariationResult(
            status=VariationStatus.ABSTAINED,
            child=None,
            mutation=None,
            reasoning="Variation scope does not permit a mutation.",
            model_cost_usd=0.0,
        )
    if evolver_model_name is None and evolver_llm is None:
        raise ValueError("one evolver model or LLM client is required")

    with scratch_workspace_from(source, request.parent.snapshot, child_candidate_id) as scratch:
        before = scratch.export_snapshot(child_candidate_id)
        seeded_skills = _auto_seed(scratch, request)
        existing_skills = scratch.list_skills()
        current_prompt = scratch.read_prompt()
        system_prompt = build_evolver_system_prompt(scratch.manifest)
        inspiration_material = _render_inspiration_material(request.inspirations)
        parsed = _propose_mutations(
            request=request,
            scratch=scratch,
            system_prompt=system_prompt,
            current_prompt=current_prompt,
            current_skills=existing_skills,
            evolver_model_name=evolver_model_name,
            evolver_llm=evolver_llm,
            inspiration_material=inspiration_material,
        )

        evolver_mutation = apply_mutations(parsed.actions, scratch)
        mutation = _merge_mutation_summaries(seeded_skills, evolver_mutation, parsed.reasoning)

        after_mutation = scratch.export_snapshot(child_candidate_id)
        if not seeded_skills and _same_content(before, after_mutation):
            return VariationResult(
                status=VariationStatus.ABSTAINED,
                child=None,
                mutation=None,
                reasoning=parsed.reasoning or "No effective mutation was submitted.",
                model_cost_usd=0.0,
            )

        # Sanitisation is part of candidate construction and therefore also
        # runs in scratch. It cannot alter canonical source on a rejected run.
        from aec_bench.evolution.sanitiser import sanitise_workspace

        sanitise_workspace(scratch, compaction_llm=compaction_llm)
        child = scratch.export_snapshot(child_candidate_id)

        if _same_content(before, child):
            return VariationResult(
                status=VariationStatus.ABSTAINED,
                child=None,
                mutation=None,
                reasoning=parsed.reasoning or "No effective mutation was submitted.",
                model_cost_usd=0.0,
            )

        return VariationResult(
            status=VariationStatus.SUBMITTED,
            child=child,
            mutation=mutation,
            reasoning=parsed.reasoning,
            model_cost_usd=0.0,
        )


def _auto_seed(scratch: Workspace, request: VariationRequest) -> list[str]:
    """Apply deterministic pattern-based skills to scratch and return names."""
    existing_skills = scratch.list_skills()
    budget_remaining = scratch.manifest.skill_budget - len(existing_skills)
    seeds = compute_seed_skills(
        request.analysis.behavioral_patterns,
        {skill.name for skill in existing_skills},
        budget_remaining,
    )
    for skill in seeds:
        scratch.write_skill(skill)
    return [skill.name for skill in seeds]


def _propose_mutations(
    *,
    request: VariationRequest,
    scratch: Workspace,
    system_prompt: str,
    current_prompt: str,
    current_skills: Sequence[SkillEntry],
    evolver_model_name: str | None,
    evolver_llm: BehavioralLLMClient | None,
    inspiration_material: str,
) -> ParsedMutationResponse:
    """Preserve the existing investigation/proposal sequence on scratch."""
    field_failure_rates = _field_failure_rates(request.parent.observations)
    skill_entries = scratch.list_skills()
    if evolver_model_name is not None:
        from aec_bench.evolution.structured_evolver import call_structured_evolver_with_tools

        tool_graveyard = MutationGraveyard()
        for entry in request.graveyard:
            tool_graveyard.insert(entry)
        toolset = build_evolver_toolset(
            observations=request.parent.observations,
            workspace_root=scratch.root,
            history=request.history,
            current_prompt=current_prompt,
            current_skills=[(skill.name, skill.body) for skill in skill_entries],
            graveyard=tool_graveyard,
        )
        brief = build_evolution_brief(
            batch_score=request.parent.assessment.batch_score,
            discipline_scores=request.analysis.discipline_scores,
            patterns=request.analysis.behavioral_patterns,
            scope=request.scope,
            field_failure_rates=field_failure_rates,
            workspace_skill_count=len(skill_entries),
            workspace_prompt_length=len(current_prompt),
            skill_names=[skill.name for skill in skill_entries],
            trial_ids=[observation.trial.trial_id for observation in request.parent.observations],
            structural_score=request.parent.assessment.structural_score,
            graveyard_size=tool_graveyard.size,
        )
        brief = f"{brief}\n\n{inspiration_material}" if inspiration_material else brief
        return call_structured_evolver_with_tools(
            model_name=evolver_model_name,
            system_prompt=system_prompt,
            analysis_brief=brief,
            toolset=toolset,
            scope=request.scope.name,
            workspace_root=scratch.root,
        )

    assert evolver_llm is not None
    analysis_prompt = build_evolution_analysis_prompt(
        batch_score=request.parent.assessment.batch_score,
        discipline_scores=request.analysis.discipline_scores,
        patterns=request.analysis.behavioral_patterns,
        scope=request.scope,
        field_failure_rates=field_failure_rates,
        workspace_skill_count=len(current_skills),
        workspace_prompt_length=len(current_prompt),
        current_prompt=current_prompt,
        current_skills=[(skill.name, skill.body) for skill in scratch.list_skills()],
        task_instruction=_task_instruction(request.parent.observations),
        field_details_map=_field_details_map(request.parent.observations),
        structural_score=request.parent.assessment.structural_score,
    )
    if inspiration_material:
        analysis_prompt = f"{analysis_prompt}\n\n{inspiration_material}"
    response = evolver_llm.complete(system_prompt + "\n\n" + analysis_prompt, max_tokens=16384)
    return parse_evolver_response(response)


def _merge_mutation_summaries(
    seeded_names: list[str],
    mutation: MutationSummary,
    reasoning: str,
) -> MutationSummary:
    """Combine scratch auto-seeding and one-shot actions into one summary."""
    added = [*seeded_names, *mutation.skills_added]
    return mutation.model_copy(update={"skills_added": added, "evolver_reasoning": reasoning})


def _same_content(left: WorkspaceSnapshot, right: WorkspaceSnapshot) -> bool:
    """Compare snapshots without treating the candidate ID as workspace content."""
    return left.system_prompt == right.system_prompt and left.skills == right.skills


def _field_failure_rates(observations: Sequence[EvolutionObservation]) -> dict[str, float]:
    totals: dict[str, int] = {}
    failures: dict[str, int] = {}
    for observation in observations:
        for field_score in observation.enrichment.field_scores:
            totals[field_score.field_name] = totals.get(field_score.field_name, 0) + 1
            if field_score.reward < 1.0:
                failures[field_score.field_name] = failures.get(field_score.field_name, 0) + 1
    return {name: failures.get(name, 0) / total for name, total in totals.items()}


def _field_details_map(observations: Sequence[EvolutionObservation]) -> dict[str, tuple[str, str]]:
    details: dict[str, tuple[str, str]] = {}
    for observation in observations:
        for field_score in observation.enrichment.field_scores:
            if field_score.reward < 1.0 and field_score.expected and field_score.actual:
                details.setdefault(field_score.field_name, (field_score.expected, field_score.actual))
    return details


def _render_inspiration_material(inspirations: Sequence[WorkspaceSnapshot]) -> str:
    if not inspirations:
        return ""

    lines = [
        "## Selected Inspiration Material",
        "Use these exact candidate materials as optional inspiration. Do not treat them as evaluated evidence.",
    ]
    for snapshot in inspirations:
        lines.extend([f"\n### Candidate {snapshot.candidate_id}", "\n#### Prompt", snapshot.system_prompt])
        if snapshot.skills:
            lines.append("\n#### Skills")
            for skill in snapshot.skills:
                lines.extend(
                    [
                        f"\n##### {skill.name}",
                        f"Description: {skill.description}",
                        f"Body:\n{skill.body}",
                    ]
                )
        else:
            lines.append("\n#### Skills\nNo skills provided.")
    return "\n".join(lines)


def _task_instruction(observations: Sequence[EvolutionObservation]) -> str:
    for observation in observations:
        if observation.trial.inputs.instruction:
            return observation.trial.inputs.instruction
    return ""
