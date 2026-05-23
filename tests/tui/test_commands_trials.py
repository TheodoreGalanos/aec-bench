# ABOUTME: Tests for the TrialProvider Command Palette provider.
# ABOUTME: Verifies fuzzy search returns matching trial records.

from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.trial_record import AgentReference, TaskReference
from aec_bench.tui.commands.trials import TrialHit, search_trials
from tests.support.trial_record_factories import make_trial_record

_VALID = ValidityCheck(output_parseable=True, schema_valid=True, verifier_completed=True)


def _make(trial_id: str, model: str, task_id: str, reward: float):
    return make_trial_record(
        trial_id=trial_id,
        experiment_id="exp-1",
        task=TaskReference(task_id=task_id, task_revision="sha"),
        agent=AgentReference(adapter="rlm", model=model, adapter_revision="git-sha-rlm"),
        evaluation=EvaluationResult(reward=reward, validity=_VALID),
    )


def _records():
    return [
        _make("t1", "claude-sonnet-4-6", "electrical/voltage-drop", 0.85),
        _make("t2", "gpt-4.1-mini", "electrical/cable-sizing", 0.50),
        _make("t3", "claude-sonnet-4-6", "civil/drainage-calc", 1.0),
    ]


def test_search_by_task_id():
    hits = search_trials(_records(), "voltage")
    assert len(hits) == 1
    assert hits[0].trial_id == "t1"


def test_search_by_model():
    hits = search_trials(_records(), "sonnet")
    assert len(hits) == 2


def test_search_by_trial_id():
    hits = search_trials(_records(), "t2")
    assert len(hits) == 1


def test_search_empty_returns_all():
    hits = search_trials(_records(), "")
    assert len(hits) == 3


def test_search_no_match():
    hits = search_trials(_records(), "zzzzz")
    assert len(hits) == 0


def test_trial_hit_fields():
    hits = search_trials(_records(), "voltage")
    hit = hits[0]
    assert isinstance(hit, TrialHit)
    assert hit.trial_id == "t1"
    assert hit.experiment_id == "exp-1"
    assert "voltage" in hit.task_id
