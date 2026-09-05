# ABOUTME: Tests explicit group splits and verifier failures at the Prime lifecycle boundary.
# ABOUTME: Uses generated public hydraulic lineages and the installed Verifiers scoring runtime.

import asyncio
from pathlib import Path
from typing import Any, Literal

import pytest

from aec_bench.prime_lab import lifecycle_environment as runtime


def test_lifecycle_verifier_error_does_not_become_training_reward(monkeypatch: pytest.MonkeyPatch) -> None:
    vf = pytest.importorskip("verifiers")

    async def broken(state: Any) -> float:
        raise ValueError("invalid verifier evidence")

    monkeypatch.setattr(runtime, "aec_bench_lifecycle_reward", broken)
    rubric = runtime._build_lifecycle_rubric(vf)
    state = vf.State(input={"prompt": [], "answer": "", "info": {}})
    state["completion"] = []
    with pytest.raises(vf.InfraError):
        asyncio.run(rubric.score_rollout(state))
    assert state["reward"] is None
    assert isinstance(state["error"], vf.InfraError)


def test_explicit_group_split_supports_revision_siblings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import json

    vf = pytest.importorskip("verifiers")
    monkeypatch.syspath_prepend(str(Path(vf.__file__).parents[1]))

    from aec_bench.lifecycles.stormwater_design.hydraulic_review import materialize_hydraulic_review_lifecycle
    from aec_bench.lifecycles.stormwater_design.hydraulics.lineages import HydraulicLineage
    from aec_bench.prime_lab.lifecycle_exporter import (
        LifecycleDatasetAssignment,
        PrimeLifecycleExportConfig,
        export_prime_lifecycle_environment,
    )

    assignments = {}
    groups: tuple[tuple[int, Literal["train", "eval"]], ...] = ((2, "train"), (8, "eval"))
    for seed, split in groups:
        lineage = HydraulicLineage(seed=seed)
        for revision in ("administrative_no_op", "major_idf_revision"):
            package = materialize_hydraulic_review_lifecycle(
                tmp_path / str(seed) / revision,
                variant_id=revision,
                lineage=lineage,
            )
            assignments[package] = LifecycleDatasetAssignment(group_id=lineage.lineage_id, split=split)
    exported = export_prime_lifecycle_environment(
        PrimeLifecycleExportConfig(
            name="hydraulic_training_test",
            package_dirs=tuple(assignments),
            dataset_assignments=assignments,
            output_dir=tmp_path / "exports",
        )
    )
    environment = runtime.load_local_lifecycle_environment(manifest_path=exported.manifest_path, split="train")
    train = [json.loads(row["info"])["dataset_assignment"]["group_id"] for row in environment.get_dataset()]
    evaluation = [json.loads(row["info"])["dataset_assignment"]["group_id"] for row in environment.get_eval_dataset()]
    assert len(train) == len(evaluation) == 2
    assert set(train).isdisjoint(evaluation)
    eval_only = runtime.load_local_lifecycle_environment(manifest_path=exported.manifest_path)
    assert eval_only.dataset is None
    assert len(eval_only.get_eval_dataset()) == 2
    # A caller cannot put revision siblings in different splits.
    path = next(iter(assignments))
    assignments[path] = LifecycleDatasetAssignment(group_id=HydraulicLineage(seed=2).lineage_id, split="eval")
    with pytest.raises(ValueError, match="cannot cross"):
        export_prime_lifecycle_environment(
            PrimeLifecycleExportConfig(
                name="leaking_training_test",
                package_dirs=tuple(assignments),
                dataset_assignments=assignments,
                output_dir=tmp_path / "exports",
            )
        )


@pytest.mark.parametrize("reward", [float("nan"), float("inf"), -0.1, 1.1])
def test_lifecycle_invalid_reward_aborts_scoring(monkeypatch: pytest.MonkeyPatch, reward: float) -> None:
    vf = pytest.importorskip("verifiers")

    async def invalid(state: Any) -> float:
        return reward

    monkeypatch.setattr(runtime, "aec_bench_lifecycle_reward", invalid)
    state = vf.State(input={"prompt": [], "answer": "", "info": {}})
    state["completion"] = []
    with pytest.raises(vf.InfraError):
        asyncio.run(runtime._build_lifecycle_rubric(vf).score_rollout(state))
    assert state["reward"] is None
