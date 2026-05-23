# ABOUTME: Active ReportTemplate object for the RLM adapter REPL.
# ABOUTME: Tracks fill state, enforces dependencies, provides progress and guidance.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aec_bench.contracts.repl import DependencyTreeSchema


@dataclass(frozen=True)
class FillResult:
    """Result of attempting to fill a section."""

    success: bool
    error: str = ""


@dataclass(frozen=True)
class TemplateStatus:
    """Current fill state of the template."""

    total_sections: int
    completed_sections: int
    unlocked: list[str] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)
    completed: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SubmissionResult:
    """Result of submitting the template."""

    complete: bool
    sections: dict[str, dict[str, Any]] = field(default_factory=dict)
    gaps: list[str] = field(default_factory=list)


class ReportTemplate:
    """Active template object for the RLM REPL.

    Wraps a DependencyTreeSchema, tracks which sections have been
    filled, enforces dependency ordering, and provides progress
    information to the agent.
    """

    def __init__(self, schema: DependencyTreeSchema) -> None:
        self._schema = schema
        self._section_map = {s.id: s for s in schema.sections}
        self._filled: dict[str, dict[str, Any]] = {}

    def fill_section(
        self,
        section_id: str,
        content: dict[str, Any],
    ) -> FillResult:
        """Fill a section's fields. Checks dependencies are met first."""
        section = self._section_map.get(section_id)
        if section is None:
            return FillResult(
                success=False,
                error=f"Unknown section: {section_id}",
            )

        missing_deps = [dep for dep in section.depends_on if dep not in self._filled]
        if missing_deps:
            return FillResult(
                success=False,
                error=(f"Cannot fill '{section_id}': depends on unfilled sections: {', '.join(missing_deps)}"),
            )

        self._filled[section_id] = dict(content)
        return FillResult(success=True)

    def get_status(self) -> TemplateStatus:
        """Current fill state — completed, pending, and unlocked."""
        completed = list(self._filled.keys())
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
        return {dep: self._filled[dep] for dep in section.depends_on if dep in self._filled}

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
                # Provide filled dependency content as context
                if isinstance(content, dict):
                    dep_context[dep] = str(content)[:500]
                else:
                    dep_context[dep] = str(content)[:500]

        return {
            "section_title": section.title,
            "generation_mode": section.generation_mode or "transform",
            "writing_guidance": list(section.writing_guidance),
            "dependency_context": dep_context,
        }

    def submit(self) -> SubmissionResult:
        """Finalise and submit. Returns completed output and any gaps."""
        gaps = [s.id for s in self._schema.sections if s.id not in self._filled]
        return SubmissionResult(
            complete=len(gaps) == 0,
            sections=dict(self._filled),
            gaps=gaps,
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
        raise AttributeError(f"'ReportTemplate' has no attribute '{name}'. {hint}")
