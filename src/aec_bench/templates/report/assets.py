# ABOUTME: Loads provider-neutral report assets from the actor-visible workspace.
# ABOUTME: Binds source containment, public rules, rubric visibility, and compose fragments once.

from __future__ import annotations

import tomllib
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from aec_bench.contracts.repl import DependencyTreeSchema
from aec_bench.contracts.report_rules import ReportRule, ReportRuleSet
from aec_bench.templates.report.criteria import validate_rubric
from aec_bench.templates.report.parser import parse_report_template_with_rubric
from aec_bench.templates.report.session import ReportSession
from aec_bench.templates.report.sources import (
    SourceIndex,
    contained_path,
    discover_source_index,
    is_special_source_label,
    resolve_source_label,
)


@dataclass(frozen=True)
class ReportAssets:
    session: ReportSession
    sources: SourceIndex
    source_docs: dict[str, str]
    boilerplate: dict[str, Any]


def load_report_assets(
    template_path: Path,
    *,
    workspace: Path,
    source_mapping: str | None = None,
    validation_rules: str | None = None,
) -> ReportAssets:
    root = workspace.resolve()
    path = contained_path(root, template_path)
    text = path.read_text(encoding="utf-8")
    data = tomllib.loads(text)
    schema, parsed_rubric = parse_report_template_with_rubric(text)
    rubric = parsed_rubric if data.get("rubric", {}).get("visibility") == "public" else None
    mapping_path = contained_path(root, path.parent / (source_mapping or "source_mapping.toml"))
    mapping: dict[str, Any] = {}
    if source_mapping or mapping_path.exists():
        mapping = tomllib.loads(mapping_path.read_text(encoding="utf-8"))
        unknown = set(mapping) - {"sources", "sections"}
        if unknown:
            raise ValueError(f"Unknown source mapping keys: {sorted(unknown)}")
    if "sources" in mapping:
        paths: dict[str, str] = {}
        for sid, source in mapping["sources"].items():
            if set(source) != {"path", "visibility"} or source["visibility"] != "public":
                raise ValueError(f"Source {sid} requires a path and explicit public visibility")
            source_path = contained_path(root, path.parent / source["path"])
            paths[sid] = str(source_path.relative_to(root))
        index = SourceIndex(root, paths)
    else:
        index = discover_source_index(root)
    docs = index.read_all()
    section_maps = mapping.get("sections", {})
    unknown_sections = set(section_maps) - {s.id for s in schema.sections}
    if unknown_sections:
        raise ValueError(f"Unknown mapped sections: {sorted(unknown_sections)}")
    sections = []
    for section in schema.sections:
        overlay = section_maps.get(section.id, {})
        if set(overlay) - {"sources", "priority"}:
            raise ValueError(f"Unknown section source mapping keys: {section.id}")
        section = replace(
            section,
            input_mapping=tuple(overlay.get("sources", section.input_mapping)),
            source_priority=overlay.get("priority", section.source_priority),
        )
        labels = list(section.input_mapping)
        for block in section.blocks or ():
            labels.extend(getattr(block, "sources", ()))
        for label in labels:
            if is_special_source_label(label) and any(k.startswith("references/") for k in docs):
                continue
            if resolve_source_label(label, docs).resolved is None:
                raise ValueError(f"Unknown source in section {section.id}: {label}")
        sections.append(section)
    schema = DependencyTreeSchema(sections=sections)
    rules_path = contained_path(root, path.parent / (validation_rules or "validation_rules.toml"))
    rules: tuple[ReportRule, ...] = ()
    if validation_rules or rules_path.exists():
        rules = ReportRuleSet.model_validate(tomllib.loads(rules_path.read_text(encoding="utf-8"))).rules
    validate_rubric(schema, rubric, docs)
    boilerplate = {}
    if "boilerplate" in data:
        boilerplate_path = contained_path(root, path.parent / data["boilerplate"]["path"])
        boilerplate = tomllib.loads(boilerplate_path.read_text(encoding="utf-8"))
    session = ReportSession(schema, rules=rules, rubric=rubric, sources=index)
    return ReportAssets(session, index, docs, boilerplate)
