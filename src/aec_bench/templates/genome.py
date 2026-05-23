# ABOUTME: Extracts task genome sidecars from generation templates.
# ABOUTME: Converts params.toml and instruction.md into family-level manifests.

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

import yaml

from aec_bench.contracts.task_genome import (
    DomainFrame,
    ExtractionSummary,
    InputBundle,
    OutputContract,
    PressurePoint,
    ProvenanceRef,
    Scenario,
    TaskGenomeManifest,
    VerifierContract,
)

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


def extract_template_genome(template_dir: Path, repo_root: Path) -> TaskGenomeManifest:
    """Extract a heuristic task genome for a generation template."""
    template_dir = template_dir.resolve()
    repo_root = repo_root.resolve()
    raw_params = tomllib.loads((template_dir / "params.toml").read_text(encoding="utf-8"))
    instruction = (template_dir / "instruction.md").read_text(encoding="utf-8")
    sections = _parse_markdown_sections(instruction)

    meta = raw_params.get("meta", {})
    params = raw_params.get("params", {})
    outputs = raw_params.get("outputs", {})
    difficulty = raw_params.get("difficulty", {})
    constraints = raw_params.get("constraints", [])

    discipline = str(meta.get("discipline", template_dir.parent.name))
    name = str(meta.get("name", template_dir.name.replace("_", "-")))
    task_id = f"{discipline}/{name}"

    return TaskGenomeManifest(
        task_id=task_id,
        source_task_path=_relative_to_repo(template_dir, repo_root),
        status="extracted",
        domain_frame=DomainFrame(
            discipline=discipline,
            subdomain=str(meta.get("category", name)),
            role=_extract_role(instruction),
            standards=list(meta.get("standards", [])),
        ),
        scenario=Scenario(summary=_extract_template_summary(meta, sections)),
        input_bundle=InputBundle(
            quantities=list(params.keys()),
            artifacts=[
                _relative_to_repo(template_dir / "params.toml", repo_root),
                _relative_to_repo(template_dir / "instruction.md", repo_root),
                _relative_to_repo(template_dir / "engine.py", repo_root),
            ],
            assumptions=_extract_template_assumptions(instruction, meta),
        ),
        reasoning_moves=_extract_template_reasoning_moves(instruction, outputs, meta),
        pressure_points=_extract_template_pressure_points(
            params=params,
            outputs=outputs,
            difficulty=difficulty,
            constraints=constraints,
            instruction=instruction,
        ),
        output_contract=OutputContract(
            format="markdown_with_json_block",
            required_fields=list(outputs.keys()),
            output_path="/workspace/output.md",
        ),
        verifier_contract=VerifierContract(
            mode="template_engine",
            script=_relative_to_repo(template_dir / "engine.py", repo_root),
            field_scores={key: f"tolerance_{value.get('tolerance', 0.03)}" for key, value in outputs.items()},
        ),
        difficulty_controls=_extract_template_difficulty_controls(
            params=params,
            outputs=outputs,
            difficulty=difficulty,
            archetypes=raw_params.get("archetypes", {}),
            constraints=constraints,
        ),
        trajectory_affordances={
            "expected_intermediate_steps": [f"compute_{key}" for key in outputs.keys()],
            "template_archetypes": list(raw_params.get("archetypes", {}).keys()),
        },
        extraction=ExtractionSummary(
            deterministic_fields=[
                "domain_frame",
                "input_bundle",
                "output_contract",
                "verifier_contract",
                "difficulty_controls",
            ],
            reasoning_review_fields=["scenario", "reasoning_moves", "pressure_points"],
            missing_fields=[],
            notes=[
                ("Template-level heuristic extraction; review semantic pressure labels before crossover."),
            ],
        ),
    )


def template_genome_to_yaml(manifest: TaskGenomeManifest) -> str:
    """Serialise a template genome manifest as stable YAML."""
    return yaml.safe_dump(
        manifest.model_dump(mode="json", exclude_none=True),
        sort_keys=False,
        allow_unicode=False,
    )


def iter_template_dirs(templates_root: Path) -> list[Path]:
    """Return built template directories under a templates root."""
    return sorted(
        params_path.parent
        for params_path in templates_root.rglob("params.toml")
        if (params_path.parent / "engine.py").exists() and (params_path.parent / "instruction.md").exists()
    )


def _parse_markdown_sections(text: str) -> dict[str, str]:
    matches = list(_HEADING_RE.finditer(text))
    if not matches:
        return {"body": text.strip()}
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        title = _normalise_key(match.group(2))
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[title] = text[start:end].strip()
    return sections


def _normalise_key(value: str) -> str:
    key = re.sub(r"[^A-Za-z0-9]+", "_", value.strip().lower())
    return key.strip("_")


def _relative_to_repo(path: Path, repo_root: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def _extract_role(instruction: str) -> str | None:
    first_line = instruction.strip().splitlines()[0] if instruction.strip() else ""
    if first_line.lower().startswith("you are "):
        return first_line.rstrip(".")
    return None


def _extract_template_summary(meta: dict[str, Any], sections: dict[str, str]) -> str:
    long_description = str(meta.get("long_description", "")).strip()
    if long_description:
        return long_description
    description = str(meta.get("description", "")).strip()
    if description:
        return description
    problem = sections.get("problem", "").strip()
    return " ".join(problem.split()) if problem else "Template task family."


def _extract_template_assumptions(instruction: str, meta: dict[str, Any]) -> list[str]:
    assumptions: list[str] = []
    lowered = instruction.lower()
    if "no internet" in lowered:
        assumptions.append("no_internet_access")
    tool_mode = str(meta.get("tool_mode", ""))
    if tool_mode:
        assumptions.append(f"tool_mode:{tool_mode}")
    return assumptions


def _extract_template_reasoning_moves(
    instruction: str,
    outputs: dict[str, Any],
    meta: dict[str, Any],
) -> list[str]:
    lowered = instruction.lower()
    moves: list[str] = []
    if any(token in lowered for token in ("calculate", "compute", "calculation")):
        moves.append("calculation")
    if any(token in lowered for token in ("check", "range", "compliance", "criterion")):
        moves.append("threshold_compliance")
    if outputs:
        moves.append("structured_output")
    if str(meta.get("tool_mode", "")) == "with-tool":
        moves.append("tool_assisted_verification")
    return _dedupe(moves)


def _extract_template_pressure_points(
    *,
    params: dict[str, Any],
    outputs: dict[str, Any],
    difficulty: dict[str, Any],
    constraints: list[str],
    instruction: str,
) -> list[PressurePoint]:
    points: list[PressurePoint] = []
    if any("convert" in line.lower() for line in instruction.splitlines()):
        points.append(
            PressurePoint(
                id="unit_conversion",
                type="unit_conversion",
                description=("Solver must apply explicit unit conversions from the template instructions."),
                provenance=[ProvenanceRef(file="instruction.md", section="Constraints")],
                confidence="medium",
            )
        )

    output_names = " ".join(outputs.keys()).lower()
    if any(token in output_names for token in ("within", "compliance", "flag", "margin")):
        points.append(
            PressurePoint(
                id="explicit_range_check",
                type="threshold_decision",
                description=("Solver must calculate margins or pass/fail flags against explicit criteria."),
                provenance=[ProvenanceRef(file="params.toml", section="outputs")],
                confidence="high",
            )
        )

    hidden_params = sorted(
        {
            hidden
            for preset in difficulty.values()
            for hidden in preset.get("hidden_params", [])
            if isinstance(hidden, str)
        }
    )
    if hidden_params:
        points.append(
            PressurePoint(
                id="infer_hidden_parameters",
                type="context_inference",
                description=("Harder variants require inferring hidden parameters from scenario context."),
                provenance=[ProvenanceRef(file="params.toml", section="difficulty.hidden_params")],
                confidence="high",
            )
        )

    if constraints:
        points.append(
            PressurePoint(
                id="constraint_satisfaction",
                type="input_constraint",
                description="Generated instances must satisfy template constraint expressions.",
                provenance=[ProvenanceRef(file="params.toml", section="constraints")],
                confidence="high",
            )
        )

    if not points and params:
        points.append(
            PressurePoint(
                id="parameterised_calculation",
                type="calculation",
                description=("Solver must map supplied parameters to the template calculation outputs."),
                provenance=[ProvenanceRef(file="params.toml", section="params")],
                confidence="medium",
            )
        )
    return points


def _extract_template_difficulty_controls(
    *,
    params: dict[str, Any],
    outputs: dict[str, Any],
    difficulty: dict[str, Any],
    archetypes: dict[str, Any],
    constraints: list[str],
) -> dict[str, Any]:
    return {
        "parameter_count": len(params),
        "output_count": len(outputs),
        "archetype_count": len(archetypes),
        "difficulty_levels": list(difficulty.keys()),
        "constraint_count": len(constraints),
        "hidden_parameter_count": sum(len(preset.get("hidden_params", [])) for preset in difficulty.values()),
    }


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
