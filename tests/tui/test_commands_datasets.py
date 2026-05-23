# ABOUTME: Tests for the DatasetProvider Command Palette provider.
# ABOUTME: Verifies fuzzy search returns matching dataset entries.

from aec_bench.tui.commands.datasets import DatasetHit, search_datasets


def _entries():
    return [
        DatasetHit(name="voltage-drop-v2", version="1.0.0", task_count=15),
        DatasetHit(name="electrical-full", version="2.1.0", task_count=75),
    ]


def test_search_by_name():
    hits = search_datasets(_entries(), "voltage")
    assert len(hits) == 1
    assert hits[0].name == "voltage-drop-v2"


def test_search_by_version():
    assert len(search_datasets(_entries(), "2.1")) == 1


def test_search_empty_returns_all():
    assert len(search_datasets(_entries(), "")) == 2
