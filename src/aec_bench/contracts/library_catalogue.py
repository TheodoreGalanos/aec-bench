# ABOUTME: Defines the deterministic public library catalogue content contract.
# ABOUTME: Keeps deployment metadata and derived counts out of canonical catalogue bytes.

from __future__ import annotations

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
    # NOTE: this value set is duplicated across seed_task.py, library_catalogue.py, and
    # seeds/seed_schema.json. Follow-up: unify into one canonical Discipline source.
    discipline: Literal["civil", "electrical", "ground", "maritime", "mechanical", "structural"]
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


class LibraryCatalogue(StrictModel):
    """Deterministic catalogue content consumed by public clients."""

    schema_version: Literal[2] = 2
    templates: list[TemplateEntry]
    seeds: list[SeedEntry]
