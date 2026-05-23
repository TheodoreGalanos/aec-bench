# ABOUTME: Extracts task genome sidecar manifests from existing task directories.
# ABOUTME: Uses deterministic parsers first and marks semantic fields for lite review.

from __future__ import annotations

import json
import re
import tomllib
from ast import literal_eval
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
    TaskGenomeEvidencePacket,
    TaskGenomeManifest,
    VerifierContract,
)
from aec_bench.tasks.loader import load_task_definition

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
_FENCED_JSON_RE = re.compile(r"```json\s*\n(.*?)\n\s*```", re.DOTALL | re.IGNORECASE)
_JSON_FIELD_RE = re.compile(r'"([A-Za-z_][A-Za-z0-9_]*)"\s*:')
_TOLERANCE_FIELD_RE = re.compile(
    r'"([A-Za-z_][A-Za-z0-9_]*)"\s*:\s*\{[^}]*?"exact"\s*:\s*(True|False)',
    re.DOTALL,
)


def extract_task_genome(task_dir: Path, tasks_root: Path) -> TaskGenomeManifest:
    """Extract a sidecar manifest from a task directory."""
    task_dir = task_dir.resolve()
    tasks_root = tasks_root.resolve()
    task = load_task_definition(task_dir, tasks_root)
    instruction_path = task_dir / "instruction.md"
    instruction = instruction_path.read_text(encoding="utf-8")
    sections = _parse_markdown_sections(instruction)

    raw_task_toml = _read_toml(task_dir / "task.toml")
    validation_rules = _read_toml(task_dir / "validation_rules.toml")
    template_meta = _read_toml(task_dir / "template_meta.toml")
    source_task = _read_json(task_dir / "source_task.json")

    output_contract = _extract_output_contract(instruction, task.verifier.expected_output_path)
    verifier_contract = _extract_verifier_contract(task_dir, task.verifier.script, validation_rules)
    pressure_points = _extract_pressure_points(sections, validation_rules)
    input_bundle = _extract_input_bundle(sections, task_dir, template_meta, source_task)
    reasoning_moves = _extract_reasoning_moves(instruction, output_contract, verifier_contract)

    deterministic_fields = [
        "domain_frame",
        "input_bundle",
        "output_contract",
        "verifier_contract",
        "difficulty_controls",
    ]
    if pressure_points:
        deterministic_fields.append("pressure_points")

    reasoning_review_fields = ["scenario", "reasoning_moves"]
    if not validation_rules:
        reasoning_review_fields.append("pressure_points")
    if source_task:
        reasoning_review_fields.append("source_task_mapping")

    missing_fields = []
    if not pressure_points:
        missing_fields.append("pressure_points")

    source_path = f"{tasks_root.name}/{task_dir.relative_to(tasks_root).as_posix()}"

    return TaskGenomeManifest(
        task_id=task.task_id,
        source_task_path=source_path,
        status="extracted",
        domain_frame=DomainFrame(
            discipline=task.domain,
            subdomain=_extract_subdomain(task.task_id, task.task_type, task.metadata),
            role=_extract_role(instruction),
            standards=_extract_standards(sections, source_task),
        ),
        scenario=Scenario(summary=_extract_scenario_summary(sections, instruction)),
        input_bundle=input_bundle,
        reasoning_moves=reasoning_moves,
        pressure_points=pressure_points,
        output_contract=output_contract,
        verifier_contract=verifier_contract,
        difficulty_controls=_extract_difficulty_controls(
            task.metadata,
            input_bundle,
            output_contract,
            validation_rules,
            raw_task_toml,
        ),
        trajectory_affordances=_extract_trajectory_affordances(output_contract),
        extraction=ExtractionSummary(
            deterministic_fields=deterministic_fields,
            reasoning_review_fields=reasoning_review_fields,
            missing_fields=missing_fields,
            notes=[
                "Deterministic extraction should be reviewed before task recombination.",
                "Lite reviewer should check semantic pressure labels and scenario summary.",
            ],
        ),
    )


def task_genome_to_yaml(manifest: TaskGenomeManifest) -> str:
    """Serialise a task genome manifest as stable YAML for sidecar files."""
    payload = manifest.model_dump(mode="json", exclude_none=True)
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)


def build_task_genome_evidence(task_dir: Path, tasks_root: Path) -> TaskGenomeEvidencePacket:
    """Build a bounded evidence packet for LLM-driven task decomposition."""
    task_dir = task_dir.resolve()
    tasks_root = tasks_root.resolve()
    deterministic_manifest = extract_task_genome(task_dir, tasks_root)

    instruction = (task_dir / "instruction.md").read_text(encoding="utf-8")
    task_toml = _read_toml(task_dir / "task.toml")
    verifier_files = _read_verifier_files(task_dir)

    return TaskGenomeEvidencePacket(
        task_id=deterministic_manifest.task_id,
        source_task_path=deterministic_manifest.source_task_path,
        deterministic_manifest=deterministic_manifest,
        task_toml=task_toml,
        instruction_sections=_parse_markdown_sections(instruction),
        verifier_files=verifier_files,
        artifact_paths=deterministic_manifest.input_bundle.artifacts,
    )


def task_genome_evidence_to_yaml(packet: TaskGenomeEvidencePacket) -> str:
    """Serialise an evidence packet as YAML for inspection or model prompts."""
    payload = packet.model_dump(mode="json", exclude_none=True)
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)


def _read_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    return json.loads(text)


def _read_verifier_files(task_dir: Path) -> dict[str, str]:
    verifier_files: dict[str, str] = {}
    tests_dir = task_dir / "tests"
    for name in ("test.sh", "verify.py", "ground_truth.json"):
        path = tests_dir / name
        if path.exists():
            verifier_files[path.relative_to(task_dir).as_posix()] = path.read_text(encoding="utf-8")
    return verifier_files


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


def _extract_role(instruction: str) -> str | None:
    first_line = instruction.strip().splitlines()[0] if instruction.strip() else ""
    if first_line.lower().startswith("you are "):
        return first_line.rstrip(".")
    return None


def _extract_subdomain(task_id: str, task_type: str, metadata: dict[str, Any]) -> str:
    if task_id.startswith("generated/") and isinstance(metadata.get("category"), str):
        return metadata["category"]
    return task_type


def _extract_scenario_summary(sections: dict[str, str], instruction: str) -> str:
    source = sections.get("problem") or sections.get("body") or instruction
    for paragraph in re.split(r"\n\s*\n", source.strip()):
        cleaned = " ".join(line.strip() for line in paragraph.splitlines()).strip()
        if cleaned:
            return cleaned[:280]
    return "Task scenario requires review."


def _extract_standards(sections: dict[str, str], source_task: dict[str, Any]) -> list[str]:
    standards: list[str] = []
    standards_text = sections.get("applicable_standards", "")
    for line in standards_text.splitlines():
        if not line.lstrip().startswith("-"):
            continue
        stripped = line.strip(" -*")
        if stripped:
            standards.append(stripped.split(" — ")[0].strip())

    source = source_task.get("source", {})
    raw_standards = source.get("standards", [])
    if isinstance(raw_standards, list):
        standards.extend(str(item) for item in raw_standards if str(item).strip())

    return _dedupe(standards)


def _extract_input_bundle(
    sections: dict[str, str],
    task_dir: Path,
    template_meta: dict[str, Any],
    source_task: dict[str, Any],
) -> InputBundle:
    quantities = _extract_table_first_column(sections.get("given", ""))

    placeholders = template_meta.get("placeholders", {})
    if isinstance(placeholders, dict):
        quantities.extend(placeholders.keys())

    source = source_task.get("source", {})
    source_inputs = source.get("inputs", [])
    if isinstance(source_inputs, list):
        quantities.extend(_normalise_key(str(item)) for item in source_inputs)

    artifacts = _extract_artifacts(task_dir)
    assumptions = _extract_assumptions(sections)
    return InputBundle(
        quantities=_dedupe(_normalise_key(item) for item in quantities if item),
        artifacts=artifacts,
        assumptions=_dedupe(assumptions),
    )


def _extract_table_first_column(section_text: str) -> list[str]:
    values: list[str] = []
    for line in section_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or set(stripped.replace("|", "").strip()) <= {"-", ":"}:
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not cells:
            continue
        first = cells[0]
        if first.lower() in {"parameter", "field", "name"}:
            continue
        values.append(first)
    return values


def _extract_artifacts(task_dir: Path) -> list[str]:
    artifacts: list[str] = []
    for directory_name in ("reference_data", "tests/fixtures"):
        directory = task_dir / directory_name
        if not directory.is_dir():
            continue
        for path in sorted(item for item in directory.rglob("*") if item.is_file()):
            artifacts.append(path.relative_to(task_dir).as_posix())
    calc_files = sorted(task_dir.glob("*_calc.py")) + sorted((task_dir / "environment").glob("*_calc.py"))
    for path in calc_files:
        artifacts.append(path.relative_to(task_dir).as_posix())
    return artifacts


def _extract_assumptions(sections: dict[str, str]) -> list[str]:
    assumptions: list[str] = []
    constraints = sections.get("constraints", "")
    lowered = constraints.lower()
    if "no internet" in lowered:
        assumptions.append("no_internet_access")
    if "impedance method" in lowered:
        assumptions.append("impedance_method_required")
    if "not simplified" in lowered or "resistance-only" in lowered:
        assumptions.append("avoid_simplified_method")
    return assumptions


def _extract_output_contract(instruction: str, output_path: str) -> OutputContract:
    required_fields: list[str] = []
    json_blocks = _FENCED_JSON_RE.findall(instruction)
    if json_blocks:
        required_fields = _dedupe(_JSON_FIELD_RE.findall(json_blocks[-1]))

    if json_blocks and output_path.endswith(".md"):
        output_format = "markdown_with_json_block"
    elif output_path.endswith(".jsonl"):
        output_format = "jsonl"
    elif output_path.endswith(".json"):
        output_format = "json"
    elif output_path.endswith(".md"):
        output_format = "markdown"
    else:
        output_format = "text"

    return OutputContract(
        format=output_format,
        required_fields=required_fields,
        output_path=output_path,
    )


def _extract_verifier_contract(
    task_dir: Path,
    verifier_script: str,
    validation_rules: dict[str, Any],
) -> VerifierContract:
    field_scores: dict[str, str] = {}
    script_path = task_dir / verifier_script
    script_text = script_path.read_text(encoding="utf-8") if script_path.exists() else ""

    verify_py = task_dir / "tests" / "verify.py"
    if verify_py.exists():
        script_text += "\n" + verify_py.read_text(encoding="utf-8")

    for field, exact in _TOLERANCE_FIELD_RE.findall(script_text):
        field_scores[field] = "exact" if exact == "True" else "relative_tolerance"

    for field in _extract_literal_dict_keys(script_text, "TOLERANCES"):
        field_scores.setdefault(field, "relative_tolerance")
    for field in _extract_literal_dict_keys(script_text, "GROUND_TRUTH"):
        field_scores.setdefault(field, "relative_tolerance")

    validation_counts = _validation_rule_counts(validation_rules)
    if validation_counts:
        mode = "section_validation"
    elif field_scores:
        mode = "deterministic_numeric"
    else:
        mode = "scripted_verifier"

    return VerifierContract(
        mode=mode,
        script=verifier_script,
        field_scores=field_scores,
        validation_rules=validation_counts,
    )


def _extract_literal_dict_keys(script_text: str, name: str) -> list[str]:
    match = re.search(rf"{name}[^=]*=\s*(\{{.*?\}})", script_text, re.DOTALL)
    if not match:
        return []
    try:
        payload = literal_eval(match.group(1))
    except (SyntaxError, ValueError):
        return []
    if not isinstance(payload, dict):
        return []
    return [str(key) for key in payload.keys()]


def _validation_rule_counts(validation_rules: dict[str, Any]) -> dict[str, int]:
    if not validation_rules:
        return {}
    sections = validation_rules.get("sections", [])
    return {
        "global_rules": len(validation_rules.get("global_rules", [])),
        "sections": len(sections),
        "section_rules": sum(len(section.get("rules", [])) for section in sections),
    }


def _extract_pressure_points(
    sections: dict[str, str],
    validation_rules: dict[str, Any],
) -> list[PressurePoint]:
    points: list[PressurePoint] = []
    constraints = sections.get("constraints", "")
    lowered = constraints.lower()
    if "resistance-only" in lowered or "not simplified" in lowered:
        points.append(
            PressurePoint(
                id="include_reactance_term",
                type="omitted_term",
                description=(
                    "Solver must preserve the impedance-method pressure rather than "
                    "falling back to a resistance-only shortcut."
                ),
                provenance=[
                    ProvenanceRef(
                        file="instruction.md",
                        section="Constraints",
                        signal="resistance-only shortcut excluded",
                    )
                ],
                confidence="high",
            )
        )

    if "no internet" in lowered:
        points.append(
            PressurePoint(
                id="no_external_lookup",
                type="tool_constraint",
                description="Solver must rely on supplied context and engineering knowledge.",
                provenance=[
                    ProvenanceRef(
                        file="instruction.md",
                        section="Constraints",
                        signal="no internet",
                    )
                ],
                confidence="high",
            )
        )

    points.extend(_pressure_points_from_validation_rules(validation_rules))
    return points


def _pressure_points_from_validation_rules(
    validation_rules: dict[str, Any],
) -> list[PressurePoint]:
    points: list[PressurePoint] = []
    for rule in validation_rules.get("global_rules", []):
        points.append(_pressure_point_from_rule(rule, "global_rules"))

    for section in validation_rules.get("sections", []):
        section_id = str(section.get("id", "section"))
        for rule in section.get("rules", []):
            points.append(_pressure_point_from_rule(rule, f"section:{section_id}"))

    return points


def _pressure_point_from_rule(rule: dict[str, Any], section: str) -> PressurePoint:
    rule_id = _normalise_key(str(rule.get("id", "validation_rule")))
    level = str(rule.get("level", "warning"))
    category = str(rule.get("category", "validation"))
    return PressurePoint(
        id=rule_id,
        type=f"{category}_{level}",
        description=str(rule.get("text", rule_id)),
        provenance=[
            ProvenanceRef(
                file="validation_rules.toml",
                section=section,
                signal=str(rule.get("pattern", rule_id)),
            )
        ],
        confidence="high",
    )


def _extract_reasoning_moves(
    instruction: str,
    output_contract: OutputContract,
    verifier_contract: VerifierContract,
) -> list[str]:
    lowered = instruction.lower()
    moves: list[str] = []
    if any(token in lowered for token in ("calculate", "compute", "calculation")):
        moves.append("calculation")
    if any(token in lowered for token in ("review", "audit", "check", "verify")):
        moves.append("audit_review")
    if any(token in lowered for token in ("compliance", "limit", "threshold")):
        moves.append("threshold_compliance")
    if any(token in lowered for token in ("write", "draft", "report", "section")):
        moves.append("drafting")
    if output_contract.required_fields or output_contract.format in {"json", "jsonl"}:
        moves.append("structured_output")
    if any(token in lowered for token in ("cite", "evidence", "reference")):
        moves.append("evidence_grounding")
    if verifier_contract.validation_rules:
        moves.append("rule_satisfaction")
    return _dedupe(moves)


def _extract_difficulty_controls(
    metadata: dict[str, Any],
    input_bundle: InputBundle,
    output_contract: OutputContract,
    validation_rules: dict[str, Any],
    raw_task_toml: dict[str, Any],
) -> dict[str, Any]:
    counts = _validation_rule_counts(validation_rules)
    return {
        "declared_difficulty": str(metadata.get("difficulty", "medium")),
        "quantity_count": len(input_bundle.quantities),
        "artifact_count": len(input_bundle.artifacts),
        "required_field_count": len(output_contract.required_fields),
        "validation_rule_count": counts.get("global_rules", 0) + counts.get("section_rules", 0),
        "tool_count": len(raw_task_toml.get("tools", {}).get("scripts", [])),
    }


def _extract_trajectory_affordances(output_contract: OutputContract) -> dict[str, Any]:
    steps = [f"compute_{field}" for field in output_contract.required_fields]
    return {"expected_intermediate_steps": steps}


def _dedupe(values: Any) -> list[Any]:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
