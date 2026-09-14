# ABOUTME: Binds generic report commands to one guided RLM session.
# ABOUTME: Uses shared validation, scoped sources, rubric guidance, and declared artifact output.

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from aec_bench.templates.report.criteria import build_criteria_bundle
from aec_bench.templates.report.output import write_report
from aec_bench.templates.report.session import ReportSession, SubmissionResult


def report_commands(
    session: ReportSession, *, output_path: str, output_format: str, workspace: str | None
) -> dict[str, Any]:
    def docs() -> list[str]:
        return list(session.sources.paths) if session.sources else []

    def read(source_id: str) -> str:
        if session.sources is None:
            raise ValueError("This report has no declared source index")
        return session.sources.read(source_id)

    def rules(section_id: str) -> list[dict[str, Any]]:
        if section_id not in {s.id for s in session.schema.sections}:
            raise ValueError(f"Unknown section: {section_id}")
        return [r.model_dump() for r in session.rules if not r.sections or section_id in r.sections]

    def start(section_id: str) -> dict[str, Any]:
        section = next((s for s in session.schema.sections if s.id == section_id), None)
        if section is None:
            raise ValueError(f"Unknown section: {section_id}")
        return {
            "section_id": section_id,
            "title": section.title,
            "fields": {name: asdict(field) for name, field in section.fields.items()},
            "guidance": session.get_writing_guidance(section_id),
            "context": session.get_section_context(section_id),
            "rules": rules(section_id),
            "criteria": asdict(build_criteria_bundle(section=section, rubric=session.rubric)),
            "sources": list(section.input_mapping),
        }

    def submit() -> SubmissionResult:
        return write_report(session, output_path, output_format, workspace=workspace)

    return {
        "DOCS": docs,
        "READ": read,
        "STATUS": session.get_status,
        "START": start,
        "GUIDANCE": session.get_writing_guidance,
        "CONTEXT": session.get_section_context,
        "RULES": rules,
        "VALIDATE": session.validate_section,
        "FILL": session.fill_section,
        "SUBMIT": submit,
    }
