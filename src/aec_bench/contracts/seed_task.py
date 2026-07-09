# ABOUTME: Pydantic contract for source_task.json seed files — mirrors seeds/seed_schema.json.
# ABOUTME: Validates the subset of fields the library catalogue export consumes.

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from aec_bench.contracts.validators import NonEmptyStr, StrictModel


class StructuredSeedField(StrictModel):
    """One structured input/output field on a seed, when the seed uses the object-array form."""

    name: str
    type: Literal["float", "int", "categorical"]
    unit: str | None = None
    values: list[str] | None = None


class SeedSource(BaseModel):
    """The `source` block of a source_task.json seed file.

    Tolerates optional schema fields not consumed by the export (e.g. worked_examples,
    keyword_hits, source_file). Only the fields used by the catalogue export are
    declared here — the rest are silently dropped on validation.
    """

    model_config = ConfigDict(extra="ignore")

    # NOTE: this value set is duplicated across seed_task.py, library_catalogue.py, and
    # seeds/seed_schema.json. Follow-up: unify into one canonical Discipline source.
    discipline: Literal["civil", "electrical", "ground", "maritime", "mechanical", "structural"]
    task_id: NonEmptyStr
    task_name: NonEmptyStr
    description: NonEmptyStr
    inputs: list[str] | list[StructuredSeedField]
    outputs: list[str] | list[StructuredSeedField]
    standards: list[str]
    complexity: Literal["low", "medium", "high"]
    category_id: str | None = None
    category_name: str | None = None
    community: str | None = None


class SeedTask(BaseModel):
    """Top-level shape of a source_task.json seed file.

    Tolerates optional top-level schema fields not consumed by the export (e.g.
    created_by, feasibility). Only the fields used by the catalogue export are
    declared here — the rest are silently dropped on validation.
    """

    model_config = ConfigDict(extra="ignore")

    status: str
    seed_origin: str
    source: SeedSource
