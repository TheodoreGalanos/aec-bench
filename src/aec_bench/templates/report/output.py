# ABOUTME: Assembles accepted report sections in the declared output format.
# ABOUTME: Writes partial or complete artifacts without granting execution completion.

from __future__ import annotations

import json
import re
from pathlib import Path

from aec_bench.templates.report.session import ReportSession, SubmissionResult
from aec_bench.templates.report.sources import contained_path

REPORT_OUTPUT_FORMATS = frozenset({"markdown", "json", "jsonl", "markdown_final_fenced_json"})


def render_report(session: ReportSession, output_format: str) -> tuple[SubmissionResult, str]:
    if output_format not in REPORT_OUTPUT_FORMATS:
        raise ValueError(f"Unsupported report output format: {output_format}")
    result = session.submit()
    if output_format == "json":
        text = json.dumps(result.sections, ensure_ascii=False, indent=2) + "\n"
    elif output_format == "jsonl":
        text = "".join(
            json.dumps({"section_id": sid, "fields": fields}, ensure_ascii=False) + "\n"
            for sid, fields in result.sections.items()
        )
    else:
        blocks = []
        for number, section in enumerate(session.schema.sections, start=1):
            if section.id not in result.sections:
                continue
            fields = result.sections[section.id]
            body = "\n\n".join(
                value if isinstance(value, str) else json.dumps(value, ensure_ascii=False) for value in fields.values()
            )
            body = re.sub(r"^# [^\n]*\n+", "", body, count=1)
            blocks.append(f"# {number}. {section.title}\n\n{body}")
        text = "\n\n".join(blocks) + "\n"
        if output_format == "markdown_final_fenced_json":
            text += "\n```json\n" + json.dumps(result.sections, ensure_ascii=False, indent=2) + "\n```\n"
    return result, text


def write_report(
    session: ReportSession, output_path: str, output_format: str, *, workspace: str | None = None
) -> SubmissionResult:
    result, text = render_report(session, output_format)
    path = contained_path(Path(workspace), output_path) if workspace else Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return result


def report_artifact_matches(
    session: ReportSession, output_path: str, output_format: str, *, workspace: str | None = None
) -> bool:
    """Check that the submitted bytes still represent the accepted report state."""
    result, expected = render_report(session, output_format)
    if not result.complete:
        return False
    try:
        path = contained_path(Path(workspace), output_path) if workspace else Path(output_path)
        return path.read_bytes() == expected.encode("utf-8")
    except (OSError, ValueError):
        return False
