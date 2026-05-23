# ABOUTME: Parser for report_template.toml files.
# ABOUTME: Converts TOML section definitions into a DependencyTreeSchema, with optional rubric.

from __future__ import annotations

from typing import Any

from aec_bench.contracts.repl import (
    DependencyTreeSchema,
    OutputField,
    TreeSection,
)
from aec_bench.contracts.report_template import parse_block
from aec_bench.contracts.rubric import Rubric, RubricCriterion, RubricDimension

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]


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
                fields[name] = OutputField(
                    name=name,
                    dtype=dtype.get("dtype", "str"),
                    description=dtype.get("description", ""),
                    tolerance=dtype.get("tolerance"),
                    unit=dtype.get("unit"),
                    required=dtype.get("required", False),
                )
    else:
        # List format: [{name: ..., dtype: ...}, ...]
        for fd in field_data:
            name = fd["name"]
            fields[name] = OutputField(
                name=name,
                dtype=fd["dtype"],
                description=fd.get("description", ""),
                tolerance=fd.get("tolerance"),
                unit=fd.get("unit"),
                required=fd.get("required", False),
            )

    return fields


def _parse_sections(section_list: list[dict[str, Any]]) -> list[TreeSection]:
    """Parse a list of section dicts into TreeSection objects."""
    sections: list[TreeSection] = []
    for section_data in section_list:
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


def _parse_blocks(section_data: dict[str, Any], generation_mode: str | None) -> tuple | None:
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
