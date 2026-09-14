# ABOUTME: Shared actor-visible rubric context for report drafting and review.
# ABOUTME: Preserves dimension identity and resolves reference scopes without broadening access.

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite

from aec_bench.contracts.repl import DependencyTreeSchema, TreeSection
from aec_bench.contracts.rubric import CATEGORY_WEIGHTS, Rubric, RubricCriterion, RubricDimension


@dataclass(frozen=True)
class CriteriaBundle:
    """All criteria available to a pairwise judge for a single section.

    Used by the experimental best-of-k generation path. Combines:
    - The section's writing guidance rules from the template
    - Criteria from every rubric dimension whose ``eval_sections`` includes
      this section
    - Expert persona from those dimensions (joined if multiple)
    - The union of ``eval_references`` keys those dimensions specify
    """

    section_id: str
    section_title: str
    summary: str
    writing_rules: tuple[str, ...]
    rubric_dimensions: tuple[str, ...]
    rubric_criteria: tuple[RubricCriterion, ...]
    expert_personas: tuple[str, ...]
    eval_references: tuple[str, ...]
    dimensions: tuple[RubricDimension, ...] = ()

    def format_for_judge(self) -> str:
        """Render this bundle as a prompt block the judge can read."""
        parts: list[str] = [
            f"SECTION: {self.section_title}",
        ]
        if self.summary:
            parts.append(f"OVERVIEW: {self.summary}")
        parts.append("")
        parts.append("SECTION WRITING RULES:")
        for rule in self.writing_rules:
            parts.append(f"- {rule}")
        if self.rubric_criteria:
            parts.append("")
            parts.append("EVALUATION CRITERIA (from rubric):")
            if self.dimensions:
                for dim in self.dimensions:
                    parts.append(f"Dimension {dim.id}: {dim.name} (weight {dim.weight}, maximum {dim.max_score})")
                    for crit in dim.criteria:
                        parts.append(f"- [{crit.category.upper()}] {crit.text}")
            else:
                for crit in self.rubric_criteria:
                    parts.append(f"- [{crit.category.upper()}] {crit.text}")
        if not self.dimensions and not self.rubric_criteria:
            parts.append("No public rubric dimensions apply to this section.")
        if self.expert_personas:
            parts.append("")
            parts.append("EVALUATOR CONTEXT:")
            for persona in self.expert_personas:
                parts.append(persona)
        return "\n".join(parts)


def build_criteria_bundle(
    *,
    section: TreeSection,
    rubric: Rubric | None,
) -> CriteriaBundle:
    """Build a CriteriaBundle for one section, combining writing guidance and rubric.

    If ``rubric`` is None, the bundle still contains the section's writing rules
    and summary — useful for sections with no rubric coverage.
    """
    summary = (
        "Output fields: " + ", ".join(f"{name} ({spec.dtype})" for name, spec in section.fields.items())
        if section.fields
        else ""
    )
    rules: tuple[str, ...] = tuple(section.writing_guidance or ())

    matching_dims: list[str] = []
    criteria: list[RubricCriterion] = []
    personas: list[str] = []
    eval_refs: list[str] = []
    dimensions: list[RubricDimension] = []

    if rubric is not None:
        for dim in rubric.dimensions:
            if dim.eval_sections and section.id not in dim.eval_sections:
                continue
            dimensions.append(dim)
            matching_dims.append(dim.id)
            criteria.extend(dim.criteria or ())
            persona = (dim.expert_persona or "").strip()
            if persona and persona not in personas:
                personas.append(persona)
            for ref in dim.eval_references or ():
                if ref not in eval_refs:
                    eval_refs.append(ref)

    return CriteriaBundle(
        section_id=section.id,
        section_title=section.title,
        summary=summary,
        writing_rules=rules,
        rubric_dimensions=tuple(matching_dims),
        rubric_criteria=tuple(criteria),
        expert_personas=tuple(personas),
        eval_references=() if any(not d.eval_references for d in dimensions) else tuple(eval_refs),
        dimensions=tuple(dimensions),
    )


def build_all_criteria_bundles(
    *,
    schema: DependencyTreeSchema,
    rubric: Rubric | None,
) -> dict[str, CriteriaBundle]:
    """Build CriteriaBundles for every section in the schema."""
    return {sec.id: build_criteria_bundle(section=sec, rubric=rubric) for sec in schema.sections}


def filter_references(
    all_refs: dict[str, str],
    eval_references: Sequence[str],
) -> dict[str, str]:
    """Filter reference materials by ``eval_references`` substring matching.

    Each non-empty selector must match a permitted source. An empty scope
    selects all references already permitted to the actor; it does not discover files.
    """
    if not eval_references:
        return dict(all_refs)
    focused: dict[str, str] = {}
    for ref_key in eval_references:
        matched = False
        for full_key, content in all_refs.items():
            if ref_key in full_key:
                focused[full_key] = content
                matched = True
        if not matched:
            raise ValueError(f"Unmatched rubric reference selector: {ref_key}")
    return focused


def validate_rubric(schema: DependencyTreeSchema, rubric: Rubric | None, sources: dict[str, str] | None = None) -> None:
    if rubric is None:
        return
    section_ids = {s.id for s in schema.sections}
    ids: set[str] = set()
    if rubric.rollup_strategy not in {"weighted_mean", "min"}:
        raise ValueError(f"Unsupported rubric rollup: {rubric.rollup_strategy}")
    for dim in rubric.dimensions:
        if not dim.id or dim.id in ids:
            raise ValueError(f"Invalid or duplicate rubric dimension: {dim.id}")
        ids.add(dim.id)
        if not isfinite(dim.weight) or dim.weight < 0 or not isfinite(dim.max_score) or dim.max_score <= 0:
            raise ValueError(f"Invalid rubric numeric bounds: {dim.id}")
        if dim.eval_method not in {"automated", "llm_judge"}:
            raise ValueError(f"Unsupported rubric method: {dim.eval_method}")
        if set(dim.eval_sections) - section_ids:
            raise ValueError(f"Unknown rubric sections in {dim.id}")
        for criterion in dim.criteria:
            if criterion.category not in CATEGORY_WEIGHTS or not criterion.text.strip():
                raise ValueError(f"Invalid rubric criterion in {dim.id}")
        if sources is not None:
            filter_references(sources, dim.eval_references)
