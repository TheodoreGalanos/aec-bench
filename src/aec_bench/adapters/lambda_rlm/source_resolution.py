# ABOUTME: Source label resolution helpers for lambda-RLM planning and execution.
# ABOUTME: Keeps document discovery explicit and reports unresolved source mappings.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SourceResolution:
    requested: str
    resolved: str | None
    content: str


def is_special_source_label(label: str) -> bool:
    """Return True for labels resolved outside normal document discovery."""
    return label.startswith("references/*:")


def resolve_source_label(label: str, source_docs: dict[str, str]) -> SourceResolution:
    """Resolve a template source label to discovered document content.

    Resolution is intentionally conservative: exact label, document key before
    ``:``, then existing prefix compatibility for older labels. It does not
    perform semantic filename guessing.
    """
    if label in source_docs:
        return SourceResolution(requested=label, resolved=label, content=source_docs[label])

    if ":" in label:
        doc_key = label.split(":", 1)[0]
        if doc_key in source_docs:
            return SourceResolution(requested=label, resolved=doc_key, content=source_docs[doc_key])

    for key, content in source_docs.items():
        if key.startswith(label) or label.startswith(key):
            return SourceResolution(requested=label, resolved=key, content=content)

    return SourceResolution(requested=label, resolved=None, content="")


def audit_section_sources(
    sections: list[dict[str, Any]],
    source_docs: dict[str, str],
) -> list[dict[str, str]]:
    """Return unresolved normal source labels by section."""
    unresolved: list[dict[str, str]] = []
    for section in sections:
        section_id = str(section["id"])
        for source in section.get("input_mapping", []):
            if is_special_source_label(source):
                continue
            resolved = resolve_source_label(source, source_docs)
            if resolved.resolved is None:
                unresolved.append({"section_id": section_id, "source": source})
    return unresolved
