# ABOUTME: Parser for report_template.toml files.
# ABOUTME: Converts TOML section definitions into a DependencyTreeSchema, with optional rubric.

from __future__ import annotations

import tomllib
from typing import Any

from aec_bench.contracts.repl import (
    DependencyTreeSchema,
    OutputField,
    TreeSection,
)
from aec_bench.contracts.report_template import Block, parse_block
from aec_bench.contracts.rubric import Rubric, RubricCriterion, RubricDimension

FIELD_TYPES: dict[str, type | tuple[type, ...]] = {
    "str": str,
    "int": int,
    "float": (int, float),
    "bool": bool,
    "list": list,
    "dict": dict,
    "table": (str, list),
}


def validate_report_schema(schema: DependencyTreeSchema) -> None:
    sections = {s.id: s for s in schema.sections}
    if len(sections) != len(schema.sections):
        raise ValueError("Duplicate report section IDs")
    for section in schema.sections:
        if not section.id:
            raise ValueError("Report section ID cannot be empty")
        if section.generation_mode not in {
            None,
            "transform",
            "guided",
            "prose",
            "compose",
            "verbatim",
            "creative",
            "boilerplate",
            "external",
        }:
            raise ValueError(f"Unsupported generation mode: {section.generation_mode}")
        for name, spec in section.fields.items():
            if (
                not isinstance(name, str)
                or not name
                or name != spec.name
                or not isinstance(spec.dtype, str)
                or spec.dtype not in FIELD_TYPES
                or not isinstance(spec.required, bool)
            ):
                raise ValueError(f"Invalid field definition: {section.id}.{name} ({spec.dtype})")
        for dep in section.depends_on:
            if dep not in sections:
                raise ValueError(f"Unknown dependency: {section.id} -> {dep}")
        if set(section.source_priority) - set(section.input_mapping):
            raise ValueError(f"Source priority refers to an unmapped source in {section.id}")
    pending = set(sections)
    while pending:
        ready = {sid for sid in pending if not set(sections[sid].depends_on) & pending}
        if not ready:
            raise ValueError(f"Cyclic report dependencies: {', '.join(sorted(pending))}")
        pending -= ready


def _parse_fields(
    field_data: list[dict[str, Any]] | dict[str, Any],
) -> dict[str, OutputField]:
    """Parse fields into a name-keyed OutputField dict.

    Handles two TOML formats:
      - Array of tables: [{name = "x", dtype = "str"}, ...]
      - Inline dict:     {field_name = "dtype", ...}
    """
    fields: dict[str, OutputField] = {}

    if isinstance(field_data, dict):
        # Dict format: {field_name: dtype_string, ...}
        for name, dtype in field_data.items():
            if isinstance(dtype, str):
                fields[name] = OutputField(
                    name=name,
                    dtype=dtype,
                    description="",
                )
            elif isinstance(dtype, dict):
                fields[name] = _parse_field(name, dtype)
            else:
                raise ValueError(f"Invalid report field definition: {name}")
    elif isinstance(field_data, list):
        # List format: [{name: ..., dtype: ...}, ...]
        for fd in field_data:
            if not isinstance(fd, dict) or not isinstance(fd.get("name"), str):
                raise ValueError("Each report field requires a string name")
            if "dtype" not in fd:
                raise ValueError(f"Report field {fd['name']} requires a dtype")
            name = fd["name"]
            if name in fields:
                raise ValueError(f"Duplicate report field: {name}")
            fields[name] = _parse_field(name, {key: value for key, value in fd.items() if key != "name"})
    else:
        raise ValueError("Report fields must be a table or array of tables")

    return fields


def _parse_field(name: str, data: dict[str, Any]) -> OutputField:
    unknown = set(data) - {"dtype", "description", "tolerance", "unit", "required"}
    if unknown:
        raise ValueError(f"Unknown report field keys for {name}: {sorted(unknown)}")
    return OutputField(
        name=name,
        dtype=data.get("dtype", "str"),
        description=data.get("description", ""),
        tolerance=data.get("tolerance"),
        unit=data.get("unit"),
        required=data.get("required", False),
    )


def _parse_sections(section_list: list[dict[str, Any]]) -> list[TreeSection]:
    """Parse a list of section dicts into TreeSection objects."""
    sections: list[TreeSection] = []
    for section_data in section_list:
        unknown = set(section_data) - {
            "id",
            "title",
            "fields",
            "depends_on",
            "generation_mode",
            "per_discipline",
            "writing_guidance",
            "input_mapping",
            "blocks",
        }
        if unknown:
            raise ValueError(f"Unknown report section keys: {sorted(unknown)}")
        fields = _parse_fields(section_data.get("fields", []))
        input_mapping, source_priority = _parse_input_mapping(
            section_data.get("input_mapping", []),
        )
        generation_mode = section_data.get("generation_mode")
        blocks = _parse_blocks(section_data, generation_mode)
        sections.append(
            TreeSection(
                id=section_data["id"],
                title=section_data["title"],
                fields=fields,
                depends_on=tuple(section_data.get("depends_on", [])),
                generation_mode=generation_mode,
                per_discipline=section_data.get("per_discipline", False),
                writing_guidance=_parse_writing_guidance(
                    section_data.get("writing_guidance", []),
                ),
                input_mapping=input_mapping,
                source_priority=source_priority,
                blocks=blocks,
            )
        )
    return sections


def _parse_blocks(section_data: dict[str, Any], generation_mode: str | None) -> tuple[Block, ...] | None:
    """Parse compose-mode blocks if present, validating against generation_mode."""
    raw_blocks = section_data.get("blocks")
    section_id = section_data.get("id", "<unknown>")

    if generation_mode == "compose":
        if not raw_blocks:
            msg = f"section {section_id!r}: generation_mode='compose' requires at least one entry in blocks"
            raise ValueError(msg)
        return tuple(parse_block(b) for b in raw_blocks)

    if raw_blocks:
        msg = f"section {section_id!r}: blocks are only valid when generation_mode='compose' (got {generation_mode!r})"
        raise ValueError(msg)
    return None


def _parse_writing_guidance(raw: list[str] | dict[str, Any]) -> tuple[str, ...]:
    """Parse writing_guidance from either a bare list or a sub-table with rules."""
    if isinstance(raw, dict):
        # Sub-table format: {summary: "...", rules: [...]}
        rules = list(raw.get("rules", []))
        summary = raw.get("summary", "")
        if summary:
            rules.insert(0, summary)
        return tuple(rules)
    return tuple(raw)


def _parse_input_mapping(
    raw: list[str] | dict[str, Any],
) -> tuple[tuple[str, ...], dict[str, int]]:
    """Parse input_mapping returning (sources, priority) tuple.

    Accepts either a bare list of source strings or a sub-table with
    keys ``sources`` (list[str]) and optional ``priority`` (dict[str, int]).
    The priority mapping is keyed by the same "source:field" strings used
    in sources; lower integer = higher authority (1 = highest).
    Returns an empty priority dict when no priority is configured.
    """
    if isinstance(raw, dict):
        sources = tuple(raw.get("sources", []))
        priority = {k: int(v) for k, v in raw.get("priority", {}).items()}
        return sources, priority
    return tuple(raw), {}


def parse_report_template_with_rubric(
    toml_str: str,
) -> tuple[DependencyTreeSchema, Rubric | None]:
    """Parse a report_template.toml returning both schema and optional rubric."""
    data = tomllib.loads(toml_str)

    sections = _parse_sections(data.get("sections", []))
    schema = DependencyTreeSchema(sections=sections)
    validate_report_schema(schema)

    rubric = None
    rubric_data = data.get("rubric")
    if rubric_data is not None:
        dimensions = []
        for d in rubric_data.get("dimensions", []):
            raw_criteria = d.get("criteria", [])
            criteria: list[RubricCriterion] = []
            for c in raw_criteria:
                if isinstance(c, dict):
                    criteria.append(
                        RubricCriterion(
                            text=c["text"],
                            category=c.get("category", "essential"),
                        )
                    )
                else:
                    # Backward compat: plain string → essential criterion
                    criteria.append(RubricCriterion(text=str(c), category="essential"))
            dimensions.append(
                RubricDimension(
                    id=d["id"],
                    name=d.get("name") or d.get("label", d["id"]),
                    description=d.get("description", ""),
                    weight=float(d.get("weight", 1.0)),
                    max_score=float(d.get("max_score", 10.0)),
                    eval_method=d.get("eval_method") or d.get("evaluation_method", "automated"),
                    criteria=tuple(criteria),
                    eval_sections=tuple(d.get("eval_sections", [])),
                    eval_references=tuple(d.get("eval_references", [])),
                    expert_persona=d.get("expert_persona", ""),
                )
            )
        rubric = Rubric(
            dimensions=dimensions,
            rollup_strategy=rubric_data.get("rollup_strategy", "weighted_mean"),
        )

    return schema, rubric


def parse_report_template(toml_str: str) -> DependencyTreeSchema:
    """Parse a report_template.toml string into a DependencyTreeSchema."""
    schema, _ = parse_report_template_with_rubric(toml_str)
    return schema
