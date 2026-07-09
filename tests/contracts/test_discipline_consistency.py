# ABOUTME: Guards that the discipline value set stays in sync across all three seams
# ABOUTME: that currently duplicate it: SeedSource, LibraryEntryBase, and seed_schema.json.

import json
import typing
from pathlib import Path

from aec_bench.contracts.library_catalogue import LibraryEntryBase
from aec_bench.contracts.seed_task import SeedSource

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "seeds" / "seed_schema.json"


def _seed_task_disciplines() -> frozenset[str]:
    annotation = SeedSource.model_fields["discipline"].annotation
    return frozenset(typing.get_args(annotation))


def _library_catalogue_disciplines() -> frozenset[str]:
    annotation = LibraryEntryBase.model_fields["discipline"].annotation
    return frozenset(typing.get_args(annotation))


def _seed_schema_disciplines() -> frozenset[str]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    enum = schema["$defs"]["source"]["properties"]["discipline"]["enum"]
    return frozenset(enum)


def test_discipline_sets_match_across_all_sites() -> None:
    seed_task = _seed_task_disciplines()
    library_catalogue = _library_catalogue_disciplines()
    seed_schema = _seed_schema_disciplines()

    assert seed_task == library_catalogue == seed_schema, (
        "discipline value sets have drifted apart: "
        f"seed_task.py={sorted(seed_task)!r}, "
        f"library_catalogue.py={sorted(library_catalogue)!r}, "
        f"seed_schema.json={sorted(seed_schema)!r}"
    )


def test_maritime_is_registered_everywhere() -> None:
    seed_task = _seed_task_disciplines()
    library_catalogue = _library_catalogue_disciplines()
    seed_schema = _seed_schema_disciplines()

    assert "maritime" in seed_task, "maritime missing from SeedSource.discipline"
    assert "maritime" in library_catalogue, "maritime missing from LibraryEntryBase.discipline"
    assert "maritime" in seed_schema, "maritime missing from seed_schema.json discipline enum"
