# ABOUTME: Tests for the ExperimentProvider Command Palette provider.
# ABOUTME: Verifies fuzzy search returns matching experiment entries.

from aec_bench.tui.commands.experiments import ExperimentHit, search_experiments


def _entries():
    return [
        ExperimentHit(experiment_id="exp-rlm-sonnet", trial_count=10),
        ExperimentHit(experiment_id="exp-gpt-mini", trial_count=5),
        ExperimentHit(experiment_id="local", trial_count=1),
    ]


def test_search_by_id():
    assert len(search_experiments(_entries(), "rlm")) == 1
    assert search_experiments(_entries(), "rlm")[0].experiment_id == "exp-rlm-sonnet"


def test_search_empty_returns_all():
    assert len(search_experiments(_entries(), "")) == 3


def test_search_no_match():
    assert len(search_experiments(_entries(), "zzzzz")) == 0
