# ABOUTME: Binds permitted report source IDs and resolves declared references.
# ABOUTME: Keeps document discovery explicit and reports unresolved source mappings.

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any


def contained_path(root: Path, path: str | Path) -> Path:
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"Report asset escapes permitted root: {path}")
    return resolved


@dataclass(frozen=True)
class SourceIndex:
    """Source IDs bound to files in the already actor-visible workspace."""

    root: Path
    paths: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "paths", MappingProxyType(dict(self.paths)))

    def read(self, source_id: str) -> str:
        if source_id not in self.paths:
            raise ValueError(f"Unknown report source ID: {source_id}")
        return contained_path(self.root, self.paths[source_id]).read_text(encoding="utf-8")

    def read_all(self) -> dict[str, str]:
        return {sid: self.read(sid) for sid in self.paths}


def discover_source_index(workspace: Path) -> SourceIndex:
    """Index text files from the task-staged documents directory only."""
    root = workspace.resolve()
    docs = contained_path(root, "documents")
    paths: dict[str, str] = {}
    for path in sorted(docs.rglob("*")) if docs.is_dir() else []:
        if not path.is_file() or path.suffix.lower() not in {".md", ".txt", ".toml", ".csv", ".json"}:
            continue
        contained_path(root, path)
        key = str(path.relative_to(docs).with_suffix(""))
        if key in paths:
            raise ValueError(f"Duplicate source ID: {key}")
        paths[key] = str(path.relative_to(root))
    return SourceIndex(root, paths)


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

    matches = [key for key in source_docs if key.startswith(label) or label.startswith(key)]
    if len(matches) == 1:
        key = matches[0]
        return SourceResolution(requested=label, resolved=key, content=source_docs[key])
    if len(matches) > 1:
        raise ValueError(f"Ambiguous source label: {label}")

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
