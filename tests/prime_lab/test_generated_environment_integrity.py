# ABOUTME: Tests training splits and verifier failures in installed-style Prime exports.
# ABOUTME: Exercises both generated harnesses through the real Verifiers dataset and rubric APIs.

from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from aec_bench.prime_lab.exporter import PrimeExportHarnessMode, PrimeLabExportConfig, export_prime_lab_environment
from tests.prime_lab.test_exporter import _make_task

try:
    vf = importlib.import_module("verifiers")
except ModuleNotFoundError:
    pytest.skip("requires the Prime optional dependencies", allow_module_level=True)


@pytest.fixture(params=[PrimeExportHarnessMode.SINGLE_TURN, PrimeExportHarnessMode.STATEFUL_WORKSPACE])
def generated(request: pytest.FixtureRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    tasks_root = tmp_path / "tasks"
    task_ids = [f"electrical/task-{index}" for index in range(10)]
    for index, task_id in enumerate(task_ids):
        _make_task(tasks_root, task_id, difficulty="easy" if index % 2 == 0 else "hard")
    name = f"integrity_{tmp_path.name}"
    result = export_prime_lab_environment(
        PrimeLabExportConfig(
            name=name,
            tasks_root=tasks_root,
            task_ids=task_ids,
            output_dir=tmp_path / "exports",
            harness_mode=request.param,
        )
    )
    # Match installed imports: the repository agents directory is not openai-agents.
    assert vf.__file__ is not None
    monkeypatch.syspath_prepend(str(Path(vf.__file__).parents[1]))
    if request.param is PrimeExportHarnessMode.STATEFUL_WORKSPACE:
        pytest.importorskip("agents.function_schema")
    monkeypatch.syspath_prepend(str(result.package_dir))
    return importlib.import_module(f"{result.package_dir.name}.environment")


def test_training_environment_has_disjoint_evaluation_rows(generated: ModuleType) -> None:
    environment = generated.load_environment()
    train = {row["answer"] for row in environment.get_dataset()}
    evaluation = {row["answer"] for row in environment.get_eval_dataset()}
    assert len(train) == 8
    assert len(evaluation) == 2
    assert train.isdisjoint(evaluation)


def test_filtering_and_shuffling_preserve_split_membership(generated: ModuleType) -> None:
    baseline = generated.load_environment()
    environment = generated.load_environment(difficulty="easy", num_examples=2, seed=17)
    train = {row["answer"] for row in environment.get_dataset()}
    evaluation = {row["answer"] for row in environment.get_eval_dataset()}
    assert train <= {row["answer"] for row in baseline.get_dataset()}
    assert evaluation <= {row["answer"] for row in baseline.get_eval_dataset()}
    assert train.isdisjoint(evaluation)


def test_small_training_set_is_disjoint_and_single_task_requires_explicit_evaluation(generated: ModuleType) -> None:
    generated.__dict__["TASKS"] = generated.TASKS[:4]
    environment = generated.load_environment()
    assert len(environment.get_dataset()) == 3
    assert len(environment.get_eval_dataset()) == 1
    generated.__dict__["TASKS"] = generated.TASKS[:1]
    with pytest.raises(ValueError, match="at least two"):
        generated.load_environment()
    environment = generated.load_environment(split="all")
    assert environment.dataset is None
    assert len(environment.get_eval_dataset()) == 1


@pytest.mark.parametrize("split", ["eval", "all", "validation", "test"])
def test_evaluation_only_environment_does_not_supply_training_rows(generated: ModuleType, split: str) -> None:
    environment = generated.load_environment(split=split)
    assert environment.dataset is None
    assert len(environment.get_eval_dataset()) == (10 if split == "all" else 2)


def test_invalid_split_and_empty_filtered_split_are_rejected(generated: ModuleType) -> None:
    with pytest.raises(ValueError, match="unsupported split"):
        generated.load_environment(split="typo")
    with pytest.raises(ValueError, match="no tasks"):
        generated.load_environment(difficulty="medium")


def _state(environment: Any) -> dict[str, Any]:
    state: dict[str, Any] = vf.State.for_task(environment.get_eval_dataset()[0])
    state["completion"] = [{"role": "assistant", "content": "42"}]
    return state


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        "missing",
        "crash",
        "no_reward",
        "malformed",
        "out_of_range",
        "nonfinite",
        "boolean",
        "timeout",
        "missing_key",
        "array",
    ],
)
async def test_verifier_failure_remains_an_error_in_the_rubric(generated: ModuleType, failure: str) -> None:
    environment = generated.load_environment(split="all")
    state = _state(environment)
    info = json.loads(state["info"])
    assert generated.__file__ is not None
    verifier = Path(generated.__file__).parent / "tasks" / info["task_id"] / "tests" / "verify.py"
    if failure == "missing":
        verifier.unlink()
    else:
        sources = {
            "crash": "raise RuntimeError('verifier failed')\n",
            "no_reward": "pass\n",
            "timeout": "import time; time.sleep(2)\n",
            "missing_key": "'{}'",
            "array": "'[]'",
            "malformed": "'not json'",
            "out_of_range": "'{\"reward\": 2}'",
            "nonfinite": "'{\"reward\": NaN}'",
            "boolean": "'{\"reward\": true}'",
        }
        source = sources[failure]
        if failure not in {"crash", "no_reward", "timeout"}:
            source = f"import sys\nfrom pathlib import Path\nPath(sys.argv[-1]).write_text({source})\n"
        verifier.write_text(source)
    if failure == "timeout":
        state["info"] = json.dumps({**info, "verifier_timeout_seconds": 1})
    await environment.setup_state(state)
    with pytest.raises(vf.InfraError):
        await environment.rubric.score_rollout(state)
    assert isinstance(state["error"], vf.InfraError)
    assert state["reward"] is None
    if state.get("workspace_path"):
        assert not Path(state["workspace_path"]).exists()


@pytest.mark.asyncio
async def test_valid_zero_and_group_rewards_are_preserved(generated: ModuleType) -> None:
    environment = generated.load_environment(split="all")
    right, wrong = _state(environment), _state(environment)
    wrong["completion"] = [{"role": "assistant", "content": "incorrect"}]
    await environment.rubric.score_group([right, wrong])
    assert [right["reward"], wrong["reward"]] == [1.0, 0.0]
    assert right["error"] is None and wrong["error"] is None


@pytest.mark.asyncio
async def test_verifier_error_aborts_group_scoring(generated: ModuleType) -> None:
    environment = generated.load_environment(split="all")
    healthy = _state(environment)
    broken = vf.State.for_task(environment.get_eval_dataset()[1])
    broken["completion"] = [{"role": "assistant", "content": "42"}]
    info = json.loads(broken["info"])
    assert generated.__file__ is not None
    verifier = Path(generated.__file__).parent / "tasks" / info["task_id"] / "tests" / "verify.py"
    verifier.unlink()
    with pytest.raises(vf.InfraError):
        await environment.rubric.score_group([healthy, broken])
    assert isinstance(broken["error"], vf.InfraError)
    assert broken["reward"] is None


def test_stale_reward_cannot_hide_a_verifier_that_writes_nothing(generated: ModuleType, tmp_path: Path) -> None:
    task_dir = tmp_path / "private-task"
    (task_dir / "tests").mkdir(parents=True)
    (task_dir / "tests" / "verify.py").write_text("pass\n")
    (tmp_path / "reward.json").write_text('{"reward": 1}')
    with pytest.raises(vf.InfraError):
        generated._score_submission(task_dir, 10)
