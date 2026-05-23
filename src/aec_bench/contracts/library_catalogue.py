# ABOUTME: Pydantic contract for the public library catalogue export artefact.
# ABOUTME: Public boundary to aec-bench site repo (schema v1). NOTE: OutputField/InputField
# ABOUTME: collide with aec_bench.contracts.repl — do not re-export from contracts/__init__.py.

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from aec_bench.contracts.validators import StrictModel


class InputField(StrictModel):
    """An input parameter on a template or a seed."""

    name: str
    description: str | None = None
    unit: str | None = None
    type: Literal["float", "int", "enum", "categorical"] | None = None


class OutputField(StrictModel):
    """An output on a template or a seed."""

    name: str
    description: str | None = None
    unit: str | None = None
    tolerance: float | None = None


class LibraryEntryBase(StrictModel):
    """Fields shared by both TemplateEntry and SeedEntry."""

    task_id: str
    discipline: Literal["civil", "electrical", "ground", "mechanical", "structural"]
    category: str
    category_label: str | None = None
    standards: list[str] = Field(default_factory=list)
    inputs: list[InputField] = Field(default_factory=list)
    outputs: list[OutputField] = Field(default_factory=list)


class TemplateEntry(LibraryEntryBase):
    """A built template — the library can generate parameterised instances from it."""

    status: Literal["built"] = "built"
    task_name: str
    description: str
    long_description: str | None = None
    tags: list[str] = Field(default_factory=list)
    tool_mode: Literal["with-tool", "no-tool", "both"]
    difficulty_tiers: list[str]
    archetype_count: int


class SeedEntry(LibraryEntryBase):
    """A proposed seed — task described but not yet built as a template or instance."""

    status: Literal["proposed"] = "proposed"
    task_name: str
    description: str
    complexity: Literal["low", "medium", "high"] | None = None


class CatalogueCounts(StrictModel):
    """Derived aggregate counts so the site can render headers without reiterating."""

    total_templates: int
    total_seeds: int
    by_discipline: dict[str, dict[str, int]]
    # Inner dict is {"templates": N, "seeds": N}.


class LibraryCatalogue(StrictModel):
    """Top-level envelope — the full export artefact consumed by the aec-bench site."""

    schema_version: Literal[1] = 1
    generated_at: datetime
    library_version: str
    library_commit: str | None = None
    templates: list[TemplateEntry]
    seeds: list[SeedEntry]
    counts: CatalogueCounts
