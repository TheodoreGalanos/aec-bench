# ABOUTME: Exercises the strict stage-zero command-line boundary with a protocol-compatible Harbor executor.
# ABOUTME: Proves successful runs print only the report path/hash and unknown JSON fields fail before execution.

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from aec_bench.meta_harness.factorial_experiment import (
    FactorialExperimentSpec as StageZeroSpec,
)
from aec_bench.meta_harness.factorial_experiment import (
    prepare_factorial_experiment_spec as prepare_stage_zero_spec,
)
from aec_bench.meta_harness.factorial_experiment_cli import (
    _preflight_harness_runtime,
    _preflight_runtime,
)
from aec_bench.meta_harness.factorial_experiment_cli import (
    run_factorial_experiment_cli as run_cli,
)
from aec_bench.meta_harness.kernel_catalogue import default_kernel_registry
from tests.meta_harness.test_factorial_candidates import _factory_inputs, _recipe
from tests.meta_harness.test_stage_zero import StageZeroHarborExecutor, _one_repetition_factory


def test_stage_zero_cli_runs_real_workflow_surface_and_prints_only_path_and_hash(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    registry, tasks_root, request = _one_repetition_factory(tmp_path)
    spec = prepare_stage_zero_spec(
        candidate_requests=(request,),
        registry=registry,
        tasks_root=tasks_root,
        policy_id="policy.stage-zero.cli",
        randomization_seed=73,
        harness_generator_sha256="1" * 64,
        program_generator_sha256="2" * 64,
        split="discovery",
        bootstrap_replicates=4,
    )
    spec_path = tmp_path / "stage-zero-spec.json"
    spec_path.write_text(json.dumps(spec.model_dump(mode="json")), encoding="utf-8")
    executor = StageZeroHarborExecutor()

    result = run_cli(
        [
            "--spec",
            str(spec_path),
            "--project-root",
            str(tmp_path),
            "--repo-root",
            str(tmp_path),
            "--tasks-root",
            str(tasks_root),
            "--ledger-root",
            str(tmp_path / "ledger"),
            "--jobs-root",
            str(tmp_path / "jobs"),
            "--artifacts-root",
            str(tmp_path / "artifacts"),
        ],
        executor=executor,
    )

    assert capsys.readouterr().out.splitlines() == [str(result.path), result.report.content_sha256]
    assert executor.calls == 4


def test_stage_zero_cli_rejects_unknown_spec_fields_before_harbor_execution(tmp_path: Path) -> None:
    registry, tasks_root, request = _factory_inputs(tmp_path)
    spec = prepare_stage_zero_spec(
        candidate_requests=(request,),
        registry=registry,
        tasks_root=tasks_root,
        policy_id="policy.stage-zero.cli",
        randomization_seed=73,
        harness_generator_sha256="1" * 64,
        program_generator_sha256="2" * 64,
        split="calibration",
        bootstrap_replicates=4,
    )
    payload = spec.model_dump(mode="json") | {"mock_mode": True}
    payload.pop("content_sha256")
    spec_path = tmp_path / "invalid-stage-zero-spec.json"
    spec_path.write_text(json.dumps(payload), encoding="utf-8")
    executor = StageZeroHarborExecutor()

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        run_cli(
            [
                "--spec",
                str(spec_path),
                "--project-root",
                str(tmp_path),
                "--repo-root",
                str(tmp_path),
                "--tasks-root",
                str(tasks_root),
                "--ledger-root",
                str(tmp_path / "ledger"),
                "--jobs-root",
                str(tmp_path / "jobs"),
                "--artifacts-root",
                str(tmp_path / "artifacts"),
            ],
            executor=executor,
        )

    assert executor.calls == 0


def test_stage_zero_cli_uses_the_current_default_fixed_kernel() -> None:
    assert default_kernel_registry().manifest.kernel_id == "aec-bench.adaptive-harness"


def test_checked_in_stage_zero_example_replays_its_historical_kernel_identity() -> None:
    repository_root = Path(__file__).parents[2]
    spec_path = repository_root / "tests" / "fixtures" / "meta_harness" / "adaptive-stage-zero.example.json"
    spec = StageZeroSpec.model_validate_json(spec_path.read_text(encoding="utf-8"))

    assert spec.content_sha256 == "4bc62a2e98d1bea1aa370948e8ff9529e57d97152a906c595db059f8d5ae1213"
    assert {request.kernel_ref.version for request in spec.candidate_requests} == {"1.5.2"}
    assert {request.kernel_ref.content_sha256 for request in spec.candidate_requests} == {
        "85c6f40552da81b102a1852b95bcd19f8ac45090c651763b12a86d05167e09d7"
    }
    assert {request.kernel_ref for request in spec.candidate_requests} != {default_kernel_registry().manifest.ref}


def test_stage_zero_runtime_preflight_reports_missing_morph_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    example_path = (
        Path(__file__).parents[2] / "tests" / "fixtures" / "meta_harness" / "adaptive-stage-zero.example.json"
    )
    spec = StageZeroSpec.model_validate_json(example_path.read_text(encoding="utf-8"))
    monkeypatch.delenv("MORPH_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="requires MORPH_API_KEY"):
        _preflight_runtime(
            spec=spec,
            project_root=tmp_path,
            repo_root=tmp_path,
            tasks_root=tmp_path,
        )


def test_stage_zero_runtime_preflight_checks_direct_provider_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, tasks_root, request = _factory_inputs(tmp_path)
    recipe = _recipe(
        registry,
        recipe_id="direct-preflight",
        task_refs=request.task_refs,
        adapter_capability="aecbench.adapter.direct",
        budget=request.harness_budget,
    )
    checked_models: list[str] = []
    monkeypatch.setattr(
        "aec_bench.meta_harness.factorial_experiment_cli.preflight_pydantic_model_configuration",
        checked_models.append,
    )

    _preflight_harness_runtime(
        recipes=(recipe,),
        project_root=tmp_path,
        repo_root=tmp_path,
        tasks_root=tasks_root,
        surface_name="direct-provider-test",
    )

    assert checked_models == ["claude-test-model"]
