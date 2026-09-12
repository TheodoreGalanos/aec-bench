# ABOUTME: Shared report state and public validation for guided and lambda agents.
# ABOUTME: Preserves accepted content, dependency order, and explicit completion diagnostics.

from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any

from aec_bench.contracts.repl import DependencyTreeSchema
from aec_bench.contracts.report_rules import ReportRule
from aec_bench.contracts.rubric import Rubric
from aec_bench.templates.report.criteria import build_criteria_bundle, validate_rubric
from aec_bench.templates.report.parser import FIELD_TYPES, validate_report_schema
from aec_bench.templates.report.sources import SourceIndex


@dataclass(frozen=True)
class ValidationIssue:
    rule_id: str
    message: str
    field: str | None = None


@dataclass(frozen=True)
class ValidationResult:
    errors: tuple[ValidationIssue, ...] = ()
    warnings: tuple[ValidationIssue, ...] = ()
    unchecked: tuple[ValidationIssue, ...] = ()

    @property
    def valid(self) -> bool:
        return not self.errors


@dataclass(frozen=True)
class FillResult:
    """Result of attempting to fill a section."""

    success: bool
    error: str = ""
    validation: ValidationResult = field(default_factory=ValidationResult)
    invalidated: tuple[str, ...] = ()


@dataclass(frozen=True)
class TemplateStatus:
    """Current fill state of the template."""

    total_sections: int
    completed_sections: int
    unlocked: list[str] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)
    completed: list[str] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SubmissionResult:
    """Result of submitting the template."""

    complete: bool
    sections: dict[str, dict[str, Any]] = field(default_factory=dict)
    gaps: list[str] = field(default_factory=list)
    diagnostics: dict[str, ValidationResult] = field(default_factory=dict)


class ReportSession:
    """Active template object for the RLM REPL.

    Wraps a DependencyTreeSchema, tracks which sections have been
    filled, enforces dependency ordering, and provides progress
    information to the agent.
    """

    def __init__(
        self,
        schema: DependencyTreeSchema,
        *,
        rules: tuple[ReportRule, ...] = (),
        rubric: Rubric | None = None,
        sources: SourceIndex | None = None,
    ) -> None:
        validate_report_schema(schema)
        validate_rubric(schema, rubric)
        self._schema = deepcopy(schema)
        self._section_map = {s.id: s for s in self._schema.sections}
        self._filled: dict[str, dict[str, Any]] = {}
        self.rules = deepcopy(rules)
        self.rubric = deepcopy(rubric)
        self.sources = sources

        for rule in rules:
            for sid in rule.sections or tuple(self._section_map):
                if sid not in self._section_map:
                    raise ValueError(f"Unknown rule section: {sid}")
                if rule.field is not None and rule.field not in self._section_map[sid].fields:
                    raise ValueError(f"Unknown rule field: {sid}.{rule.field}")
        self._patterns = {r.id: re.compile(r.pattern) for r in rules if r.pattern is not None}

    @property
    def schema(self) -> DependencyTreeSchema:
        return deepcopy(self._schema)

    def fresh(self) -> ReportSession:
        return ReportSession(self._schema, rules=self.rules, rubric=self.rubric, sources=self.sources)

    def configuration(self) -> dict[str, Any]:
        """Record resolved public guidance; task artifacts own retained source integrity."""
        return {
            "template": asdict(self._schema),
            "rules": [rule.model_dump(mode="json") for rule in self.rules],
            "rubric": self.rubric.model_dump(mode="json") if self.rubric else None,
            "source_ids": list(self.sources.paths) if self.sources else [],
        }

    def validate_section(self, section_id: str, content: dict[str, Any]) -> ValidationResult:
        section = self._section_map.get(section_id)
        errors: list[ValidationIssue] = []
        warnings: list[ValidationIssue] = []
        unchecked: list[ValidationIssue] = []
        if section is None:
            return ValidationResult(errors=(ValidationIssue("section", f"Unknown section: {section_id}"),))
        if not isinstance(content, dict):
            return ValidationResult(errors=(ValidationIssue("fields", "Section content must be a field dictionary"),))
        try:
            json.dumps(content, allow_nan=False)
        except (TypeError, ValueError, OverflowError):
            return ValidationResult(errors=(ValidationIssue("fields", "Section fields must be finite JSON values"),))
        for dep in section.depends_on:
            if dep not in self._filled:
                errors.append(ValidationIssue("dependency", f"Section {section_id} depends on unfilled section {dep}"))
        for name, spec in section.fields.items():
            value = content.get(name)
            if spec.required and (
                value is None
                or value == ""
                or value == []
                or value == {}
                or isinstance(value, str)
                and not value.strip()
            ):
                errors.append(ValidationIssue("required", f"Required field: {name}", name))
            elif name in content and not _matches_type(value, spec.dtype):
                errors.append(ValidationIssue("type", f"Field {name} must have type {spec.dtype}", name))
        for rule in self.rules:
            if rule.sections and section_id not in rule.sections:
                continue
            issue = ValidationIssue(rule.id, rule.message, rule.field)
            if rule.kind == "prose":
                unchecked.append(issue)
                continue
            target = content.get(rule.field, "") if rule.field else content
            text = target if isinstance(target, str) else json.dumps(target, ensure_ascii=False)
            matched = self._patterns[rule.id].search(text) is not None
            if (rule.kind == "required_pattern" and not matched) or (rule.kind == "forbidden_pattern" and matched):
                (errors if rule.severity == "error" else warnings).append(issue)
        return ValidationResult(tuple(errors), tuple(warnings), tuple(unchecked))

    def fill_section(
        self,
        section_id: str,
        content: dict[str, Any],
    ) -> FillResult:
        """Fill a section's fields. Checks dependencies are met first."""
        validation = self.validate_section(section_id, content)
        if not validation.valid:
            return FillResult(False, "; ".join(i.message for i in validation.errors), validation)
        invalidated: set[str] = set()
        if section_id in self._filled and self._filled[section_id] != content:
            changed = {section_id}
            while True:
                dependants = {s.id for s in self._schema.sections if set(s.depends_on) & changed} - changed
                if not dependants:
                    break
                changed.update(dependants)
            invalidated = (changed - {section_id}) & self._filled.keys()
            for sid in invalidated:
                del self._filled[sid]
        self._filled[section_id] = deepcopy(content)
        return FillResult(
            True, validation=validation, invalidated=tuple(s.id for s in self._schema.sections if s.id in invalidated)
        )

    def get_status(self) -> TemplateStatus:
        """Current fill state — completed, pending, and unlocked."""
        completed = [s.id for s in self._schema.sections if s.id in self._filled]
        pending = [s.id for s in self._schema.sections if s.id not in self._filled]

        unlocked = []
        for s in self._schema.sections:
            if s.id in self._filled:
                continue
            deps_met = all(d in self._filled for d in s.depends_on)
            if deps_met:
                unlocked.append(s.id)

        return TemplateStatus(
            total_sections=len(self._schema.sections),
            completed_sections=len(completed),
            unlocked=unlocked,
            pending=pending,
            completed=completed,
            blocked=[sid for sid in pending if sid not in unlocked],
        )

    def get_dependencies(self, section_id: str) -> list[str]:
        """What sections must be completed before this one."""
        section = self._section_map.get(section_id)
        if section is None:
            return []
        return list(section.depends_on)

    def get_section_context(self, section_id: str) -> dict[str, Any]:
        """Get filled data from dependency sections for cross-referencing."""
        section = self._section_map.get(section_id)
        if section is None:
            return {}
        return {dep: deepcopy(self._filled[dep]) for dep in section.depends_on if dep in self._filled}

    def get_writing_guidance(self, section_id: str) -> list[str]:
        """Get expert decomposition hints for this section."""
        section = self._section_map.get(section_id)
        if section is None:
            return []
        return list(section.writing_guidance)

    def get_extraction_context(self, section_id: str) -> dict[str, Any] | None:
        """Get everything needed for goal-directed extraction for a section.

        Returns a dict with section_title, generation_mode, writing_guidance,
        and dependency_context — the same information lambda-RLM uses for
        its extraction prompts. Returns None for unknown sections.
        """
        section = self._section_map.get(section_id)
        if section is None:
            return None

        dep_context: dict[str, str] = {}
        for dep in section.depends_on:
            if dep in self._filled:
                content = self._filled[dep]
                dep_context[dep] = str(content)

        return {
            "section_title": section.title,
            "generation_mode": section.generation_mode or "transform",
            "writing_guidance": list(section.writing_guidance),
            "dependency_context": dep_context,
            "criteria": build_criteria_bundle(section=section, rubric=self.rubric).format_for_judge(),
        }

    def submit(self) -> SubmissionResult:
        """Finalise and submit. Returns completed output and any gaps."""
        gaps = [s.id for s in self._schema.sections if s.id not in self._filled]
        diagnostics = {
            s.id: self.validate_section(s.id, self._filled[s.id]) for s in self._schema.sections if s.id in self._filled
        }
        return SubmissionResult(
            complete=not gaps and all(v.valid for v in diagnostics.values()),
            sections={s.id: deepcopy(self._filled[s.id]) for s in self._schema.sections if s.id in self._filled},
            gaps=gaps,
            diagnostics=diagnostics,
        )

    def __getattr__(self, name: str) -> Any:
        """Provide helpful error messages for common agent mistakes."""
        suggestions: dict[str, str] = {
            "fill": "Use report.fill_section(section_id, content_dict)",
            "status": "Use report.get_status()",
            "sections": "Use report.submit() or report.get_status()",
            "complete": "Use report.get_status() to check completion",
            "gaps": "Use report.get_status() to see pending sections",
            "unlocked": "Use report.get_status() to see unlocked sections",
            "pending": "Use report.get_status() to see pending sections",
            "completed_sections": "Use report.get_status().completed_sections",
            "total_sections": "Use report.get_status().total_sections",
            "section_context": "Use report.get_section_context(section_id)",
            "guidance": "Use report.get_writing_guidance(section_id)",
            "dependencies": "Use report.get_dependencies(section_id)",
            "get_context": "Use report.get_section_context(section_id)",
            "context": "Use report.get_section_context(section_id)",
            "write": "Use report.fill_section(section_id, content_dict)",
            "set_section": "Use report.fill_section(section_id, content_dict)",
            "update_section": "Use report.fill_section(section_id, content_dict)",
            "submit_section": "Use report.fill_section(section_id, content_dict)",
            "get_sections": "Use report.get_status() to see all sections",
            "list_sections": "Use report.get_status() to see all sections",
        }
        hint = suggestions.get(name, "Use report.get_status() to see available methods")
        raise AttributeError(f"'ReportSession' has no attribute '{name}'. {hint}")


def _matches_type(value: Any, dtype: str) -> bool:
    if dtype in {"int", "float"} and isinstance(value, bool):
        return False
    return isinstance(value, FIELD_TYPES[dtype])
