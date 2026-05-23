# ABOUTME: Builds normalized template decomposition sidecars from task genome manifests.
# ABOUTME: Produces recombinable task parts for crossover and population experiments.

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from aec_bench.contracts.task_decomposition import (
    TaskDecomposition,
    TaskDecompositionBatch,
    TaskPart,
)
from aec_bench.contracts.task_genome import TaskGenomeManifest

_DANGLING_TERMS = {
    "and",
    "or",
    "from",
    "with",
    "using",
    "then",
    "plus",
    "by",
    "for",
    "to",
    "of",
}


def load_template_genome(path: Path) -> TaskGenomeManifest:
    """Load a template genome sidecar from YAML."""
    return TaskGenomeManifest.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def build_template_decomposition(
    manifest: TaskGenomeManifest,
    *,
    source_genome_path: str,
) -> TaskDecomposition:
    """Build a normalized part decomposition from a template genome manifest."""
    parts = [
        TaskPart(
            id="domain_context",
            kind="context",
            summary=_summarise_context(manifest),
            depends_on=[],
            recombinable=True,
            crossover_role="engineering scenario frame",
        ),
        TaskPart(
            id="input_contract",
            kind="input",
            summary=_summarise_inputs(manifest),
            depends_on=["domain_context"],
            recombinable=True,
            crossover_role="parameter surface",
        ),
    ]

    if manifest.domain_frame.standards:
        parts.append(
            TaskPart(
                id="standards_context",
                kind="lookup",
                summary=_summarise_standards(manifest),
                depends_on=["domain_context"],
                recombinable=False,
                crossover_role="governing reference guard",
            )
        )

    formula_dependencies = ["input_contract"]
    if manifest.domain_frame.standards:
        formula_dependencies.append("standards_context")

    parts.append(
        TaskPart(
            id="calculation_chain",
            kind="formula",
            summary=_summarise_formula(manifest),
            depends_on=formula_dependencies,
            recombinable=True,
            crossover_role="computational kernel",
        )
    )

    if _has_pressure(manifest, "unit_conversion"):
        parts.append(
            TaskPart(
                id="unit_conversion",
                kind="intermediate",
                summary="Apply explicit unit conversions before comparing or reporting values.",
                depends_on=["calculation_chain"],
                recombinable=True,
                crossover_role="unit consistency adapter",
            )
        )

    intermediate_dependencies = ["calculation_chain"]
    if _has_pressure(manifest, "unit_conversion"):
        intermediate_dependencies.append("unit_conversion")

    parts.append(
        TaskPart(
            id="intermediate_outputs",
            kind="intermediate",
            summary=_summarise_intermediates(manifest),
            depends_on=intermediate_dependencies,
            recombinable=True,
            crossover_role="trajectory evidence",
        )
    )

    output_dependencies = ["intermediate_outputs"]
    if _has_threshold_pressure(manifest):
        parts.append(
            TaskPart(
                id="threshold_decision",
                kind="threshold",
                summary=_summarise_threshold(manifest),
                depends_on=["intermediate_outputs"],
                recombinable=False,
                crossover_role="branch or compliance gate",
            )
        )
        output_dependencies = ["threshold_decision"]

    parts.extend(
        [
            TaskPart(
                id="output_contract",
                kind="output",
                summary=_summarise_outputs(manifest),
                depends_on=output_dependencies,
                recombinable=True,
                crossover_role="answer schema",
            ),
            TaskPart(
                id="verifier_contract",
                kind="verifier",
                summary=_summarise_verifier(manifest),
                depends_on=["output_contract"],
                recombinable=False,
                crossover_role="scoring boundary",
            ),
            TaskPart(
                id="difficulty_profile",
                kind="difficulty",
                summary=_summarise_difficulty(manifest),
                depends_on=["domain_context", "input_contract"],
                recombinable=True,
                crossover_role="variant control surface",
            ),
        ]
    )

    return TaskDecomposition(
        task_id=manifest.task_id,
        source_genome_path=source_genome_path,
        parts=parts,
        trajectory_checks=_trajectory_checks(manifest),
        crossover_notes=_crossover_notes(manifest),
    )


def build_template_decomposition_batch(
    genome_paths: list[Path],
    *,
    output_root: Path,
    reviewer: str = "codex-spark-normalized",
    scope: str = "templates",
) -> TaskDecompositionBatch:
    """Build a validated batch from template genome paths."""
    decompositions = [
        build_template_decomposition(
            load_template_genome(path),
            source_genome_path=path.relative_to(output_root.parent).as_posix(),
        )
        for path in genome_paths
    ]
    return TaskDecompositionBatch(
        version=1,
        reviewer=reviewer,
        scope=scope,
        decompositions=decompositions,
    )


def task_decomposition_to_yaml(decomposition: TaskDecomposition) -> str:
    """Serialise a decomposition sidecar as stable YAML."""
    return yaml.safe_dump(
        decomposition.model_dump(mode="json", exclude_none=True),
        sort_keys=False,
        allow_unicode=False,
    )


def task_decomposition_batch_to_yaml(batch: TaskDecompositionBatch) -> str:
    """Serialise a decomposition batch as stable YAML."""
    return yaml.safe_dump(
        batch.model_dump(mode="json", exclude_none=True),
        sort_keys=False,
        allow_unicode=False,
    )


def _summarise_context(manifest: TaskGenomeManifest) -> str:
    subdomain = manifest.domain_frame.subdomain.replace("-", " ")
    return f"Frame {manifest.domain_frame.discipline} {subdomain} scenario and role."


def _summarise_inputs(manifest: TaskGenomeManifest) -> str:
    count = len(manifest.input_bundle.quantities)
    return f"Bind {count} input quantities: {_format_items(manifest.input_bundle.quantities)}."


def _summarise_standards(manifest: TaskGenomeManifest) -> str:
    standards = _format_items(manifest.domain_frame.standards)
    return f"Preserve governing references: {standards}."


def _summarise_formula(manifest: TaskGenomeManifest) -> str:
    return _complete_sentence(manifest.scenario.summary)


def _summarise_intermediates(manifest: TaskGenomeManifest) -> str:
    steps = _expected_steps(manifest)
    if not steps:
        return "Expose key derived quantities before final reporting."
    step_names = [step.removeprefix("compute_") for step in steps]
    return f"Track intermediate steps: {_format_items(step_names)}."


def _summarise_threshold(manifest: TaskGenomeManifest) -> str:
    point = next(
        (item for item in manifest.pressure_points if item.type == "threshold_decision"),
        None,
    )
    if point is None:
        return "Preserve explicit branch, range, or pass-fail decision."
    return _trim(point.description)


def _summarise_outputs(manifest: TaskGenomeManifest) -> str:
    fields = manifest.output_contract.required_fields
    return f"Emit {len(fields)} required fields: {_format_items(fields)}."


def _summarise_verifier(manifest: TaskGenomeManifest) -> str:
    return f"Score against {manifest.verifier_contract.mode} using fixed field tolerances."


def _summarise_difficulty(manifest: TaskGenomeManifest) -> str:
    controls: dict[str, Any] = manifest.difficulty_controls
    levels = controls.get("difficulty_levels", [])
    hidden = controls.get("hidden_parameter_count", 0)
    return f"Vary {levels or 'declared levels'} with {hidden} hidden parameters."


def _trajectory_checks(manifest: TaskGenomeManifest) -> list[str]:
    checks = [f"show {step}" for step in _expected_steps(manifest)]
    checks.extend(f"respect pressure point: {point.id}" for point in manifest.pressure_points)
    return checks


def _crossover_notes(manifest: TaskGenomeManifest) -> list[str]:
    notes = [
        "Keep verifier_contract coupled to output_contract during recombination.",
        "Do not swap standards_context across disciplines without human review.",
    ]
    for point in manifest.pressure_points:
        notes.append(f"{point.id}: {_trim(point.description)}")
    return notes


def _expected_steps(manifest: TaskGenomeManifest) -> list[str]:
    value = manifest.trajectory_affordances.get("expected_intermediate_steps", [])
    return [str(item) for item in value if str(item)]


def _has_pressure(manifest: TaskGenomeManifest, pressure_type: str) -> bool:
    return any(point.type == pressure_type or point.id == pressure_type for point in manifest.pressure_points)


def _has_threshold_pressure(manifest: TaskGenomeManifest) -> bool:
    return any(point.type == "threshold_decision" for point in manifest.pressure_points)


def _trim(value: str, limit: int = 96) -> str:
    value = " ".join(value.split())
    if len(value) <= limit:
        return value
    return _complete_sentence(value, limit=limit)


def _format_items(values: list[str]) -> str:
    if not values:
        return "none"
    if len(values) == 1:
        return values[0]
    return ", ".join(values[:-1]) + f", and {values[-1]}"


def _complete_sentence(value: str, limit: int = 160) -> str:
    value = " ".join(value.split())
    if not value:
        return "Execute the template calculation chain."
    if len(value) > limit:
        clauses = [item.strip() for item in value.split(".") if item.strip()]
        for clause in clauses:
            if 24 <= len(clause) <= limit:
                value = clause
                break
        else:
            words: list[str] = []
            for word in value.split():
                candidate = " ".join([*words, word])
                if len(candidate) > limit:
                    break
                words.append(word)
            value = " ".join(words)
    value = _remove_dangling_tail(value)
    value = value.rstrip()
    if value[-1] not in ".!?":
        value = f"{value}."
    return value


def _remove_dangling_tail(value: str) -> str:
    words = value.rstrip(" .,;:").split()
    while words and words[-1].lower() in _DANGLING_TERMS:
        words.pop()
    return " ".join(words).rstrip(",;:")
