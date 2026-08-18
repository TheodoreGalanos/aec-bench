# ABOUTME: Tests for the DatasetProvider Command Palette provider.
# ABOUTME: Verifies fuzzy search returns matching dataset entries.

from aec_bench.tui.commands.datasets import DatasetHit, search_datasets


def _entries():
    return [
        DatasetHit(dataset_id="voltage-drop", label="public-2026", task_count=15),
        DatasetHit(dataset_id="electrical-full", label="qualification", task_count=75),
    ]


def test_search_by_name():
    hits = search_datasets(_entries(), "voltage")
    assert len(hits) == 1
    assert hits[0].dataset_id == "voltage-drop"


def test_search_by_label():
    assert len(search_datasets(_entries(), "qualification")) == 1


def test_search_empty_returns_all():
    assert len(search_datasets(_entries(), "")) == 2
