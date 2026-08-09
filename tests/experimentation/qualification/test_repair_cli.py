# ABOUTME: Exercises the repair-only CLI with dotenv loading and protocol-compatible Harbor execution.
# ABOUTME: Proves successful runs print only the terminal artifact path and its verified content hash.

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from aec_bench.contracts.harness_instance import HarnessCompileRequest, HarnessRecipe
from aec_bench.experimentation.qualification.repair_cli import _preflight_repair_runtime, run_cli
from aec_bench.experimentation.qualification.repair_run import RepairRunSpec
from aec_bench.experimentation.qualification.repair_runtime import RepairRuntime
from tests.experimentation.qualification.test_repair_run import _spec
from tests.experimentation.qualification.test_repair_runtime import (
    RewardByTurnsHarborExecutor,
    _build_runtime,
)


def test_repair_cli_runs_real_workflow_surface_and_prints_only_terminal_path_and_hash(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture = _build_runtime(
        tmp_path,
        executor=RewardByTurnsHarborExecutor(),
        diagnosis=lambda _evidence: (_ for _ in ()).throw(AssertionError("fixture diagnosis must not run")),
    )
    spec = _spec(fixture)
    spec_path = tmp_path / "repair-run-spec.json"
    spec_path.write_text(json.dumps(spec.model_dump(mode="json")), encoding="utf-8")
    executor = RewardByTurnsHarborExecutor(emit_turn_limit_failure=True)

    result = run_cli(
        [
            "--spec",
            str(spec_path),
            "--project-root",
            str(tmp_path),
            "--repo-root",
            str(tmp_path),
            "--tasks-root",
            str(fixture.tasks_root),
            "--ledger-root",
            str(tmp_path / "ledger-cli"),
            "--jobs-root",
            str(tmp_path / "jobs-cli"),
            "--artifacts-root",
            str(tmp_path / "repair-cli-artifacts"),
        ],
        executor=executor,
    )

    assert capsys.readouterr().out.splitlines() == [
        str(result.terminal.path),
        result.terminal.reference.sha256,
    ]
    assert executor.calls == [(17, 1), (29, 1), (17, 2), (29, 2)]


def test_repair_cli_default_path_loads_dotenv_preflights_and_uses_subprocess_executor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _build_runtime(
        tmp_path,
        executor=RewardByTurnsHarborExecutor(),
        diagnosis=lambda _evidence: (_ for _ in ()).throw(AssertionError("fixture diagnosis must not run")),
    )
    spec_path = tmp_path / "repair-run-spec.json"
    spec_path.write_text(_spec(fixture).model_dump_json(), encoding="utf-8")
    (tmp_path / ".env").write_text("REPAIR_CLI_DOTENV_SENTINEL=loaded\n", encoding="utf-8")
    monkeypatch.delenv("REPAIR_CLI_DOTENV_SENTINEL", raising=False)
    executor = RewardByTurnsHarborExecutor(emit_turn_limit_failure=True)
    preflight_specs: list[str] = []

    monkeypatch.setattr(
        "aec_bench.experimentation.qualification.repair_cli._preflight_repair_runtime",
        lambda **kwargs: preflight_specs.append(kwargs["spec"].content_sha256),
    )
    monkeypatch.setattr(
        "aec_bench.experimentation.qualification.repair_cli.HarnessProgramStudySubprocessHarborExecutor",
        lambda: executor,
    )

    result = run_cli(
        [
            "--spec",
            str(spec_path),
            "--project-root",
            str(tmp_path),
            "--repo-root",
            str(tmp_path),
            "--tasks-root",
            str(fixture.tasks_root),
            "--ledger-root",
            str(tmp_path / "ledger-default"),
            "--jobs-root",
            str(tmp_path / "jobs-default"),
            "--artifacts-root",
            str(tmp_path / "repair-default-artifacts"),
        ]
    )

    assert result.result.status.value == "accepted"
    assert preflight_specs == [_spec(fixture).content_sha256]
    assert os.environ["REPAIR_CLI_DOTENV_SENTINEL"] == "loaded"


@pytest.mark.parametrize(
    "agent_capability_id",
    (
        "aecbench.adapter.tool-loop",
        "aecbench.adapter.rlm-uncached",
        "aecbench.adapter.rlm-output-contract",
    ),
)
def test_repair_cli_preflight_checks_the_parent_provider_without_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    agent_capability_id: str,
) -> None:
    fixture = _build_runtime(
        tmp_path,
        executor=RewardByTurnsHarborExecutor(),
        diagnosis=lambda _evidence: (_ for _ in ()).throw(AssertionError("fixture diagnosis must not run")),
        agent_capability_id=agent_capability_id,
    )
    checked_models: list[str] = []
    monkeypatch.setattr(
        "aec_bench.experimentation.qualification.harness_program_study_cli.shutil.which",
        lambda _name: "/usr/bin/uv",
    )
    monkeypatch.setattr(
        "aec_bench.experimentation.qualification.harness_program_study_cli.preflight_pydantic_model_configuration",
        checked_models.append,
    )

    _preflight_repair_runtime(
        spec=_spec(fixture),
        project_root=tmp_path,
        repo_root=tmp_path,
        tasks_root=fixture.tasks_root,
    )

    assert checked_models == ["claude-test-model"]


def test_repair_cli_preflight_reports_missing_morph_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _build_runtime(
        tmp_path,
        executor=RewardByTurnsHarborExecutor(),
        diagnosis=lambda _evidence: (_ for _ in ()).throw(AssertionError("fixture diagnosis must not run")),
    )
    spec = _with_morph_backend(_spec(fixture), fixture)
    monkeypatch.setattr(
        "aec_bench.experimentation.qualification.harness_program_study_cli.shutil.which",
        lambda _name: "/usr/bin/uv",
    )
    monkeypatch.delenv("MORPH_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="repair Morph execution requires MORPH_API_KEY"):
        _preflight_repair_runtime(
            spec=spec,
            project_root=tmp_path,
            repo_root=tmp_path,
            tasks_root=fixture.tasks_root,
        )


def _with_morph_backend(spec: RepairRunSpec, fixture: RepairRuntime) -> RepairRunSpec:
    morph_ref = fixture.registry.capability("aecbench.backend.harbor.morph").ref
    bindings = tuple(
        binding.model_copy(update={"capability_ref": morph_ref}) if binding.binding_id == "compute" else binding
        for binding in spec.parent.harness_request.recipe.bindings
    )
    recipe = HarnessRecipe(
        **spec.parent.harness_request.recipe.model_dump(
            mode="python",
            exclude={"content_sha256", "bindings"},
        ),
        bindings=bindings,
    )
    request = HarnessCompileRequest(
        request_id=spec.parent.harness_request.request_id,
        kernel_ref=spec.parent.harness_request.kernel_ref,
        recipe=recipe,
    )
    parent = spec.parent.model_copy(update={"harness_request": request})
    return RepairRunSpec(
        **spec.model_dump(
            mode="python",
            exclude={"content_sha256", "parent"},
        ),
        parent=parent,
    )
