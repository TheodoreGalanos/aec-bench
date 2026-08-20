# ABOUTME: Exercises the strict harness-program study command-line boundary with a protocol-compatible Harbor executor.
# ABOUTME: Proves successful runs print only the report path/hash and unknown JSON fields fail before execution.

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from aec_bench.experimentation.qualification.harness_program_study import HarnessProgramStudySpec
from aec_bench.experimentation.qualification.harness_program_study import (
    prepare_harness_program_study_spec as prepare_harness_program_study_spec,
)
from aec_bench.experimentation.qualification.harness_program_study_cli import (
    _preflight_harness_runtime,
    _preflight_runtime,
)
from aec_bench.experimentation.qualification.harness_program_study_cli import (
    run_harness_program_study_cli as run_cli,
)
from aec_bench.harness.kernel_catalogue import default_kernel_registry
from tests.experimentation.qualification.test_harness_program_candidates import _factory_inputs, _recipe
from tests.experimentation.qualification.test_harness_program_study import (
    HarnessProgramStudyHarborExecutor,
    _one_repetition_factory,
)


def test_harness_program_study_cli_runs_real_workflow_surface_and_prints_only_path_and_hash(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    registry, tasks_root, request = _one_repetition_factory(tmp_path)
    spec = prepare_harness_program_study_spec(
        candidate_requests=(request,),
        registry=registry,
        tasks_root=tasks_root,
        policy_id="policy.harness-program-study.cli",
        randomization_seed=73,
        harness_generator_sha256="1" * 64,
        program_generator_sha256="2" * 64,
        split="discovery",
        bootstrap_replicates=4,
    )
    spec_path = tmp_path / "harness-program-study-spec.json"
    spec_path.write_text(json.dumps(spec.model_dump(mode="json")), encoding="utf-8")
    executor = HarnessProgramStudyHarborExecutor()

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


def test_harness_program_study_cli_rejects_unknown_spec_fields_before_harbor_execution(tmp_path: Path) -> None:
    registry, tasks_root, request = _factory_inputs(tmp_path)
    spec = prepare_harness_program_study_spec(
        candidate_requests=(request,),
        registry=registry,
        tasks_root=tasks_root,
        policy_id="policy.harness-program-study.cli",
        randomization_seed=73,
        harness_generator_sha256="1" * 64,
        program_generator_sha256="2" * 64,
        split="calibration",
        bootstrap_replicates=4,
    )
    payload = spec.model_dump(mode="json") | {"mock_mode": True}
    payload.pop("content_sha256")
    spec_path = tmp_path / "invalid-harness-program-study-spec.json"
    spec_path.write_text(json.dumps(payload), encoding="utf-8")
    executor = HarnessProgramStudyHarborExecutor()

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


def test_harness_program_study_cli_uses_the_current_default_fixed_kernel() -> None:
    assert default_kernel_registry().manifest.kernel_id == "aec-bench.adaptive-harness"


def test_checked_in_harness_program_study_example_uses_the_current_kernel_identity() -> None:
    repository_root = Path(__file__).parents[3]
    spec_path = repository_root / "tests" / "fixtures" / "meta_harness" / "harness-program-study.example.json"
    spec = HarnessProgramStudySpec.model_validate_json(spec_path.read_text(encoding="utf-8"))

    current_ref = default_kernel_registry().manifest.ref

    assert spec.content_sha256 == "d95aac321e7d151dd31e3f93df0be39ba55e796fdc72c097116b1b86cce7c1bd"
    assert {request.kernel_ref for request in spec.candidate_requests} == {current_ref}


def test_harness_program_study_runtime_preflight_reports_missing_morph_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    example_path = (
        Path(__file__).parents[3] / "tests" / "fixtures" / "meta_harness" / "harness-program-study.example.json"
    )
    spec = HarnessProgramStudySpec.model_validate_json(example_path.read_text(encoding="utf-8"))
    monkeypatch.delenv("MORPH_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="requires MORPH_API_KEY"):
        _preflight_runtime(
            spec=spec,
            project_root=tmp_path,
            repo_root=tmp_path,
            tasks_root=tmp_path,
        )


def test_harness_program_study_runtime_preflight_checks_direct_provider_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, tasks_root, request = _factory_inputs(tmp_path)
    harness_spec = _recipe(
        registry,
        task_refs=request.task_refs,
        adapter_capability="aecbench.adapter.direct",
        budget=request.harness_budget,
    )
    checked_models: list[str] = []
    monkeypatch.setattr(
        "aec_bench.experimentation.qualification.harness_program_study_cli.preflight_pydantic_model_configuration",
        checked_models.append,
    )

    _preflight_harness_runtime(
        specs=(harness_spec,),
        project_root=tmp_path,
        repo_root=tmp_path,
        tasks_root=tasks_root,
        surface_name="direct-provider-test",
    )

    assert checked_models == ["claude-test-model"]
