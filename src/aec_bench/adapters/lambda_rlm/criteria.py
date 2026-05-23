# ABOUTME: Per-section criteria assembly for the optional best-of-k tournament.
# ABOUTME: Bundles writing guidance + rubric criteria + expert persona for one section.

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from aec_bench.contracts.repl import DependencyTreeSchema, TreeSection
from aec_bench.contracts.rubric import Rubric, RubricCriterion


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
            for crit in self.rubric_criteria:
                marker = crit.category.upper()
                parts.append(f"- [{marker}] {crit.text}")
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
    summary = ""
    rules: tuple[str, ...] = tuple(section.writing_guidance or ())

    matching_dims: list[str] = []
    criteria: list[RubricCriterion] = []
    personas: list[str] = []
    eval_refs: list[str] = []

    if rubric is not None:
        for dim in rubric.dimensions:
            if section.id not in (dim.eval_sections or ()):
                continue
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
        eval_references=tuple(eval_refs),
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

    Mirrors verify.py's ``_focus_references``: each entry in ``eval_references``
    is matched as a substring against the full ref keys, returning matching
    docs. If no eval_references are specified or nothing matches, returns all
    refs (fall-through behaviour matching the rubric judge).
    """
    if not eval_references:
        return dict(all_refs)
    focused: dict[str, str] = {}
    for ref_key in eval_references:
        for full_key, content in all_refs.items():
            if ref_key in full_key:
                focused[full_key] = content
    return focused if focused else dict(all_refs)
