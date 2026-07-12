# ABOUTME: Tests typed planning and execution for reproducible evidence-lifecycle ablations.
# ABOUTME: Covers deterministic expansion, limits, resume, TrialRecord import, and ledger summaries.

from __future__ import annotations

import inspect
import json
import platform
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

import aec_bench.ledger.writer as ledger_writer
import aec_bench.meta_harness.evidence_lifecycle_ablation as ablation_runtime
import aec_bench.meta_harness.evidence_lifecycle_ablation_plan as ablation_plan_runtime
import aec_bench.meta_harness.evidence_lifecycle_experiment as experiment_runtime
from aec_bench.contracts.experiment_manifest import AgentConfig
from aec_bench.contracts.trial_record import Completeness, TrialRecord
from aec_bench.ledger.writer import DuplicateTrialRecordError
from aec_bench.meta_harness.evidence_lifecycle import (
    open_checkpoint_attempt,
    prepare_evidence_checkpoint,
    read_evidence_lifecycle_state,
    submit_evidence_checkpoint,
)
from aec_bench.meta_harness.evidence_lifecycle_ablation import (
    LifecycleAblationCondition,
    LifecycleAblationLimits,
    LifecycleAblationManifest,
    LifecycleAblationStudyDesign,
    LifecycleAblationTrial,
    LifecycleExecutionMode,
    build_lifecycle_ablation_plan,
    inspect_lifecycle_ablation_plan,
    load_lifecycle_ablation_manifest,
    run_lifecycle_ablation,
)
from aec_bench.meta_harness.evidence_lifecycle_evaluation import (
    build_lifecycle_ablation_evaluation,
    write_lifecycle_ablation_evaluation,
)
from aec_bench.meta_harness.evidence_lifecycle_experiment import LifecycleExperimentSweepContext, repository_provenance
from aec_bench.meta_harness.evidence_lifecycle_local import (
    LifecycleVisibilityPolicy,
    run_local_evidence_lifecycle_fresh_context,
)
from aec_bench.meta_harness.evidence_lifecycle_trial_record import (
    build_lifecycle_trial_record,
    finalize_lifecycle_trial_record,
)
from aec_bench.task_world_templates.catalogue import get_template
from aec_bench.task_world_templates.lifecycles import registered_lifecycle_verifier
from aec_bench.task_world_templates.materializer import (
    materialize_template_lifecycle,
    verify_template_lifecycle,
)

TEMPLATE_ID = "drainage-model-evidence-lifecycle-review"
VARIANTS = (
    "staged_full_correction",
    "semantic_no_op_release",
    "response_assertion_only",
    "memo_closeout_missing",
)


def test_lifecycle_ablation_condition_rejects_invalid_mode_policy_pairs() -> None:
    with pytest.raises(ValidationError, match="persistent_context execution requires persistent_context visibility"):
        LifecycleAblationCondition(
            execution_mode=LifecycleExecutionMode.PERSISTENT_CONTEXT,
            memory_visibility_policy=LifecycleVisibilityPolicy.ARTIFACT_MEMORY,
        )
    with pytest.raises(ValidationError, match="fresh_context execution cannot use persistent_context visibility"):
        LifecycleAblationCondition(
            execution_mode=LifecycleExecutionMode.FRESH_CONTEXT,
            memory_visibility_policy=LifecycleVisibilityPolicy.PERSISTENT_CONTEXT,
        )


def test_lifecycle_ablation_manifest_rejects_duplicate_dimensions() -> None:
    payload = _manifest(Path("outputs"), Path("ledger")).model_dump(mode="json")
    payload["variants"] = [VARIANTS[0], VARIANTS[0]]
    with pytest.raises(ValidationError, match="variant ids must be unique"):
        LifecycleAblationManifest.model_validate(payload)


def test_lifecycle_ablation_manifest_requires_descriptive_per_session_study_design() -> None:
    payload = _manifest(Path("outputs"), Path("ledger")).model_dump(mode="json")
    payload.pop("study_design")
    with pytest.raises(ValidationError, match="study_design"):
        LifecycleAblationManifest.model_validate(payload)

    payload = _manifest(Path("outputs"), Path("ledger")).model_dump(mode="json")
    payload["study_design"]["causal_effects_supported"] = True
    with pytest.raises(ValidationError, match="causal_effects_supported"):
        LifecycleAblationManifest.model_validate(payload)


def test_lifecycle_ablation_manifest_requires_explicit_per_session_turn_limit() -> None:
    payload = _manifest(Path("outputs"), Path("ledger")).model_dump(mode="json")
    payload["agents"][0]["parameters"] = {"max_turns": 10}
    with pytest.raises(ValidationError, match="max_turns_per_session"):
        LifecycleAblationManifest.model_validate(payload)

    payload = _manifest(Path("outputs"), Path("ledger")).model_dump(mode="json")
    payload["agents"][0]["parameters"] = {}
    with pytest.raises(ValidationError, match="max_turns_per_session"):
        LifecycleAblationManifest.model_validate(payload)

    payload = _manifest(Path("outputs"), Path("ledger")).model_dump(mode="json")
    payload["agents"][0]["parameters"] = {"max_turns_per_session": 0}
    with pytest.raises(ValidationError, match="positive integer"):
        LifecycleAblationManifest.model_validate(payload)

    payload = _manifest(Path("outputs"), Path("ledger")).model_dump(mode="json")
    payload["agents"] = [payload["agents"][0], payload["agents"][0]]
    with pytest.raises(ValidationError, match="agent names must be unique"):
        LifecycleAblationManifest.model_validate(payload)

    payload = _manifest(Path("outputs"), Path("ledger")).model_dump(mode="json")
    payload["conditions"] = [payload["conditions"][0], payload["conditions"][0]]
    with pytest.raises(ValidationError, match="ablation conditions must be unique"):
        LifecycleAblationManifest.model_validate(payload)


def test_lifecycle_ablation_plan_expands_deterministically_with_unique_ids(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path / "outputs", tmp_path / "ledger", repetitions=2)

    first = build_lifecycle_ablation_plan(manifest)
    second = build_lifecycle_ablation_plan(manifest)

    assert first == second
    assert first.trial_count == 64
    assert len({trial.trial_id for trial in first.trials}) == first.trial_count
    assert {trial.variant_id for trial in first.trials} == set(VARIANTS)
    assert all(trial.adaptation.variation == {"change_topology": trial.variant_id} for trial in first.trials)
    assert {trial.agent.name for trial in first.trials} == {"agent-a", "agent-b"}
    assert {trial.memory_visibility_policy for trial in first.trials} == set(LifecycleVisibilityPolicy)
    assert {trial.repetition for trial in first.trials} == {1, 2}
    assert all(len(trial.trial_id) == len("trial-") + 64 for trial in first.trials)
    assert all(Path(trial.run_dir).parent == tmp_path / "outputs" / "trials" for trial in first.trials)
    assert all(Path(trial.ledger_path).parent == tmp_path / "ledger" / "ssc03-ablation" for trial in first.trials)
    assert len(first.manifest_sha256) == 64
    assert len(first.plan_sha256) == 64
    assert first.plan_sha256 != first.manifest_sha256
    assert all(len(trial.package_sha256) == 64 for trial in first.trials)
    assert all(len(trial.spec_sha256) == 64 for trial in first.trials)
    assert len(first.code_provenance.verifier_source_sha256) == 64
    task_verifier = registered_lifecycle_verifier(TEMPLATE_ID)
    verifier_path = Path(inspect.getsourcefile(task_verifier) or "")
    assert first.code_provenance.verifier_qualified_name == f"{task_verifier.__module__}.{task_verifier.__qualname__}"
    assert first.code_provenance.verifier_source_sha256 == _sha256(verifier_path)
    assert len(first.code_provenance.source_inventory_sha256) == 64
    assert first.study_design == manifest.study_design
    assert first.study_design.interpretation == "descriptive_calibration"
    assert first.study_design.turn_budget_scope == "per_session"
    assert first.study_design.execution_order == "deterministic_sequential_plan_order"
    assert first.study_design.randomized is False
    assert first.study_design.counterbalanced is False
    assert first.study_design.causal_effects_supported is False
    assert {trial.max_turns_per_session for trial in first.trials} == {10}


def test_lifecycle_ablation_plan_identity_binds_per_session_turn_limit(tmp_path: Path) -> None:
    baseline_manifest = _single_manifest(tmp_path)
    baseline = build_lifecycle_ablation_plan(baseline_manifest)
    changed_agent = baseline_manifest.agents[0].model_copy(update={"parameters": {"max_turns_per_session": 11}})
    changed_manifest = baseline_manifest.model_copy(update={"agents": (changed_agent,)})

    changed = build_lifecycle_ablation_plan(changed_manifest)

    assert changed.manifest_sha256 != baseline.manifest_sha256
    assert changed.plan_sha256 != baseline.plan_sha256
    assert changed.trials[0].trial_id != baseline.trials[0].trial_id


def test_lifecycle_ablation_plan_and_trial_ids_bind_code_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _single_manifest(tmp_path)
    baseline = build_lifecycle_ablation_plan(manifest)
    drifted_provenance = baseline.code_provenance.model_copy(update={"trial_importer_source_sha256": "0" * 64})
    monkeypatch.setattr(ablation_plan_runtime, "_ablation_code_provenance", lambda _template_id: drifted_provenance)

    drifted = build_lifecycle_ablation_plan(manifest)

    assert drifted.manifest_sha256 == baseline.manifest_sha256
    assert drifted.plan_sha256 != baseline.plan_sha256
    assert [trial.trial_id for trial in drifted.trials] != [trial.trial_id for trial in baseline.trials]


def test_repository_provenance_uses_content_identity_outside_git(tmp_path: Path) -> None:
    source = Path(inspect.getsourcefile(repository_provenance) or "").parents[2]
    installed = tmp_path / "site-packages" / "aec_bench"
    shutil.copytree(source / "aec_bench", installed)

    first = repository_provenance(installed)
    second = repository_provenance(installed)

    assert first == second
    assert first["repository_kind"] == "source_tree"
    assert first["commit"] == f"source-sha256:{first['source_inventory_sha256']}"
    assert first["dirty"] is False

    importer = installed / "meta_harness" / "evidence_lifecycle_trial_record.py"
    importer.write_text(importer.read_text(encoding="utf-8") + "\n# source drift\n", encoding="utf-8")
    changed = repository_provenance(installed)
    assert changed["source_inventory_sha256"] != first["source_inventory_sha256"]
    assert changed["commit"] != first["commit"]


def test_repository_provenance_does_not_attribute_ignored_install_to_caller_git(
    tmp_path: Path,
) -> None:
    caller = tmp_path / "caller"
    caller.mkdir()
    (caller / ".gitignore").write_text(".venv/\n", encoding="utf-8")
    (caller / "pyproject.toml").write_text("[project]\nname='caller'\nversion='1'\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=caller, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=caller, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=caller, check=True)
    subprocess.run(["git", "add", ".gitignore", "pyproject.toml"], cwd=caller, check=True)
    subprocess.run(["git", "commit", "-qm", "caller"], cwd=caller, check=True)
    source = Path(inspect.getsourcefile(repository_provenance) or "").parents[2]
    installed = caller / ".venv" / "lib" / "site-packages" / "aec_bench"
    shutil.copytree(source / "aec_bench", installed)

    provenance = repository_provenance(installed)

    assert provenance["repository_kind"] == "source_tree"
    assert Path(provenance["root"]) == installed.parent
    assert provenance["commit"].startswith("source-sha256:")


def test_repository_provenance_binds_installed_dependency_metadata(tmp_path: Path) -> None:
    source = Path(inspect.getsourcefile(repository_provenance) or "").parents[2]
    site_packages = tmp_path / "site-packages"
    shutil.copytree(source / "aec_bench", site_packages / "aec_bench")
    metadata_dir = site_packages / "pydantic_ai-1.0.0.dist-info"
    metadata_dir.mkdir()
    metadata_path = metadata_dir / "METADATA"
    metadata_path.write_text("Name: pydantic-ai\nVersion: 1.0.0\n", encoding="utf-8")
    first = repository_provenance(site_packages / "aec_bench")

    metadata_path.write_text("Name: pydantic-ai\nVersion: 99.0.0\n", encoding="utf-8")
    second = repository_provenance(site_packages / "aec_bench")

    assert second["source_inventory_sha256"] != first["source_inventory_sha256"]
    assert second["commit"] != first["commit"]


def test_runtime_dependency_provenance_hashes_realized_bytes_not_stale_record(tmp_path: Path) -> None:
    site_packages = tmp_path / "site-packages"
    dependency = site_packages / "pydantic_ai" / "__init__.py"
    dependency.parent.mkdir(parents=True)
    dependency.write_text("BEHAVIOR = 'baseline'\n", encoding="utf-8")
    metadata_dir = site_packages / "pydantic_ai-1.0.0.dist-info"
    metadata_dir.mkdir()
    (metadata_dir / "METADATA").write_text("Name: pydantic-ai\nVersion: 1.0.0\n", encoding="utf-8")
    (metadata_dir / "RECORD").write_text(
        "pydantic_ai/__init__.py,,\npydantic_ai-1.0.0.dist-info/METADATA,,\n",
        encoding="utf-8",
    )

    before = experiment_runtime.runtime_dependency_provenance(
        adapter_kind="tool_loop",
        model_name="deterministic-replay",
        search_paths=(site_packages,),
    )
    dependency.write_text("BEHAVIOR = 'changed-runtime'\n", encoding="utf-8")
    after = experiment_runtime.runtime_dependency_provenance(
        adapter_kind="tool_loop",
        model_name="deterministic-replay",
        search_paths=(site_packages,),
    )

    assert before["distributions"] == after["distributions"]
    assert before["dependency_inventory_sha256"] != after["dependency_inventory_sha256"]


def test_runtime_dependency_provenance_resolves_explicit_openai_provider(tmp_path: Path) -> None:
    site_packages = tmp_path / "site-packages"
    for distribution_name, package_name in (("pydantic-ai", "pydantic_ai"), ("openai", "openai")):
        package = site_packages / package_name / "__init__.py"
        package.parent.mkdir(parents=True)
        package.write_text(f"BEHAVIOR = '{distribution_name}-baseline'\n", encoding="utf-8")
        metadata_dir = site_packages / f"{package_name}-1.0.0.dist-info"
        metadata_dir.mkdir()
        (metadata_dir / "METADATA").write_text(
            f"Name: {distribution_name}\nVersion: 1.0.0\n",
            encoding="utf-8",
        )
        (metadata_dir / "RECORD").write_text(f"{package_name}/__init__.py,,\n", encoding="utf-8")

    before = experiment_runtime.runtime_dependency_provenance(
        adapter_kind="tool_loop",
        model_name="openai:gpt-5.2",
        search_paths=(site_packages,),
    )
    (site_packages / "openai" / "__init__.py").write_text(
        "BEHAVIOR = 'openai-changed-runtime'\n",
        encoding="utf-8",
    )
    after = experiment_runtime.runtime_dependency_provenance(
        adapter_kind="tool_loop",
        model_name="openai:gpt-5.2",
        search_paths=(site_packages,),
    )

    assert before["provider"] == "openai"
    assert "openai==1.0.0" in before["distributions"]
    assert before["dependency_inventory_sha256"] != after["dependency_inventory_sha256"]


def test_runtime_dependency_provenance_uses_first_distribution_search_path(tmp_path: Path) -> None:
    roots = (tmp_path / "first", tmp_path / "second")
    for root, version in zip(roots, ("1.0.0", "2.0.0"), strict=True):
        package = root / "pydantic_ai" / "__init__.py"
        package.parent.mkdir(parents=True)
        package.write_text(f"BEHAVIOR = '{version}'\n", encoding="utf-8")
        metadata_dir = root / f"pydantic_ai-{version}.dist-info"
        metadata_dir.mkdir()
        (metadata_dir / "METADATA").write_text(
            f"Name: pydantic-ai\nVersion: {version}\n",
            encoding="utf-8",
        )
        (metadata_dir / "RECORD").write_text("pydantic_ai/__init__.py,,\n", encoding="utf-8")

    before = experiment_runtime.runtime_dependency_provenance(
        adapter_kind="tool_loop",
        model_name="deterministic-replay",
        search_paths=roots,
    )
    (roots[0] / "pydantic_ai" / "__init__.py").write_text(
        "BEHAVIOR = 'first-path-changed'\n",
        encoding="utf-8",
    )
    after = experiment_runtime.runtime_dependency_provenance(
        adapter_kind="tool_loop",
        model_name="deterministic-replay",
        search_paths=roots,
    )

    assert "pydantic-ai==1.0.0" in before["distributions"]
    assert "pydantic-ai==2.0.0" not in before["distributions"]
    assert before["dependency_inventory_sha256"] != after["dependency_inventory_sha256"]


def test_lifecycle_ablation_plan_identity_binds_realized_dependency_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site_packages = tmp_path / "site-packages"
    dependency = site_packages / "pydantic_ai" / "__init__.py"
    dependency.parent.mkdir(parents=True)
    dependency.write_text("BEHAVIOR = 'baseline'\n", encoding="utf-8")
    metadata_dir = site_packages / "pydantic_ai-1.0.0.dist-info"
    metadata_dir.mkdir()
    (metadata_dir / "METADATA").write_text("Name: pydantic-ai\nVersion: 1.0.0\n", encoding="utf-8")
    (metadata_dir / "RECORD").write_text("pydantic_ai/__init__.py,,\n", encoding="utf-8")
    monkeypatch.setattr(experiment_runtime, "_runtime_distribution_search_paths", lambda: (site_packages,))
    manifest = _single_manifest(tmp_path)

    baseline = build_lifecycle_ablation_plan(manifest)
    dependency.write_text("BEHAVIOR = 'changed-runtime'\n", encoding="utf-8")
    changed = build_lifecycle_ablation_plan(manifest)

    assert baseline.trials[0].runtime_provenance != changed.trials[0].runtime_provenance
    assert baseline.plan_sha256 != changed.plan_sha256
    assert baseline.trials[0].trial_id != changed.trials[0].trial_id


def test_repository_provenance_hashes_tracked_nonstandard_package_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    benchmark = root / "vendor" / "aec_bench"
    benchmark.mkdir(parents=True)
    (benchmark / "__init__.py").write_text('"""Tracked benchmark."""\n', encoding="utf-8")
    adapter = benchmark / "adapters" / "tool_loop.py"
    adapter.parent.mkdir()
    adapter.write_text("BEHAVIOR = 'baseline'\n", encoding="utf-8")
    (root / "pyproject.toml").write_text("[project]\nname='tracked-vendor'\nversion='1.0.0'\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "initial"], cwd=root, check=True)
    monkeypatch.setattr(ablation_plan_runtime, "repository_provenance", lambda _path: repository_provenance(benchmark))
    manifest = _single_manifest(tmp_path)

    before_provenance = repository_provenance(benchmark)
    before_plan = build_lifecycle_ablation_plan(manifest)
    adapter.write_text("BEHAVIOR = 'changed-runtime'\n", encoding="utf-8")
    after_provenance = repository_provenance(benchmark)
    after_plan = build_lifecycle_ablation_plan(manifest)

    assert before_provenance["repository_kind"] == "git"
    assert before_provenance["source_inventory_sha256"] != after_provenance["source_inventory_sha256"]
    assert before_plan.plan_sha256 != after_plan.plan_sha256
    assert before_plan.trials[0].trial_id != after_plan.trials[0].trial_id


def test_lifecycle_ablation_dry_run_applies_smoke_gate_without_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _single_manifest(tmp_path)

    def failing_verifier(_package: Path, _run: Path) -> dict[str, object]:
        return {
            "lifecycle_id": "drainage-model-evidence-lifecycle-review-v1",
            "overall": "fail",
            "passed": False,
            "reward": 0.0,
            "gates": {"probe": {"passed": False, "score": 0.0, "failures": ["forced"]}},
        }

    monkeypatch.setattr(ablation_runtime, "verify_template_lifecycle", failing_verifier)

    inspection = inspect_lifecycle_ablation_plan(manifest)

    assert inspection["trial_statuses"][0]["status"] == "conflict"
    assert "failed deterministic smoke verification" in inspection["trial_statuses"][0]["reason"]
    assert not Path(manifest.output_root).exists()
    assert not Path(manifest.ledger_root).exists()


def test_lifecycle_ablation_plan_rejects_unknown_public_variant(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path / "outputs", tmp_path / "ledger").model_copy(update={"variants": ("not_registered",)})

    with pytest.raises(ValueError, match="unknown lifecycle variants.*not_registered"):
        build_lifecycle_ablation_plan(manifest)


def test_lifecycle_ablation_plan_enforces_trial_and_cost_limits(tmp_path: Path) -> None:
    trial_limited = _manifest(tmp_path / "outputs", tmp_path / "ledger").model_copy(
        update={"limits": LifecycleAblationLimits(max_trials=15)}
    )
    with pytest.raises(ValueError, match="planned trial count 32 exceeds max_trials 15"):
        build_lifecycle_ablation_plan(trial_limited)

    cost_limited = _manifest(tmp_path / "outputs", tmp_path / "ledger").model_copy(
        update={
            "estimated_cost_per_trial_usd": 0.25,
            "limits": LifecycleAblationLimits(max_trials=100, max_estimated_cost_usd=7.5),
        }
    )
    with pytest.raises(ValueError, match="planned estimated cost 8.0 exceeds limit 7.5"):
        build_lifecycle_ablation_plan(cost_limited)


def test_lifecycle_ablation_cost_limit_requires_per_trial_estimate(tmp_path: Path) -> None:
    payload = _manifest(tmp_path / "outputs", tmp_path / "ledger").model_dump(mode="json")
    payload["limits"]["max_estimated_cost_usd"] = 5.0

    with pytest.raises(ValidationError, match="estimated_cost_per_trial_usd is required"):
        LifecycleAblationManifest.model_validate(payload)


def test_lifecycle_ablation_manifest_rejects_adapter_controls_runner_does_not_apply(
    tmp_path: Path,
) -> None:
    payload = _manifest(tmp_path / "outputs", tmp_path / "ledger").model_dump(mode="json")
    payload["agents"][0]["adapter"] = "direct"
    with pytest.raises(ValidationError, match="require tool_loop or pydantic_ai"):
        LifecycleAblationManifest.model_validate(payload)

    payload = _manifest(tmp_path / "outputs", tmp_path / "ledger").model_dump(mode="json")
    payload["agents"][0]["parameters"] = {"temperature": 0.0}
    with pytest.raises(ValidationError, match="unsupported lifecycle agent parameters: temperature"):
        LifecycleAblationManifest.model_validate(payload)


def test_documented_lifecycle_ablation_example_is_a_valid_sixteen_trial_plan() -> None:
    manifest = load_lifecycle_ablation_manifest(
        Path(__file__).resolve().parents[2] / "docs" / "examples" / "meta-harness" / "lifecycle-ablation.example.yaml"
    )

    plan = build_lifecycle_ablation_plan(manifest)
    assert plan.trial_count == 16
    assert plan.study_design.causal_effects_supported is False
    assert plan.trials[0].max_turns_per_session == 60


def test_build_lifecycle_trial_record_maps_validated_working_provenance(tmp_path: Path) -> None:
    manifest, trial, package, run_dir = _recorded_trial(tmp_path)

    record = build_lifecycle_trial_record(
        manifest=manifest,
        trial=trial,
        package_dir=package,
        run_dir=run_dir,
    )

    assert record.trial_id == trial.trial_id
    assert record.experiment_id == manifest.experiment_id
    assert record.task.task_id == TEMPLATE_ID
    assert record.task.task_revision == json.loads((run_dir / "state.json").read_text())["package_sha256"]
    assert record.agent.adapter == trial.agent.adapter
    assert record.agent.model == trial.agent.model
    assert record.agent.adapter_revision
    assert record.agent.configuration["variant_id"] == trial.variant_id
    assert record.agent.configuration["execution_mode"] == trial.execution_mode.value
    assert record.agent.configuration["memory_visibility_policy"] == trial.memory_visibility_policy.value
    assert record.agent.configuration["plan_sha256"] == build_lifecycle_ablation_plan(manifest).plan_sha256
    assert record.environment.tool_versions
    assert record.inputs.input_files
    assert {item.path for item in record.inputs.input_files} == set(
        json.loads((run_dir / "experiment-manifest.json").read_text())["lifecycle"]["package_files"]
    )
    assert record.outputs.agent_output is not None
    assert record.outputs.agent_result is not None
    assert record.evaluation.reward == 1.0
    assert record.evaluation.validity.verifier_completed is True
    assert record.evaluation.breakdown is not None
    assert record.evaluation.breakdown["semantic_transition"]["aggregate"]["retention"] == 1.0
    assert record.adaptation is not None
    assert record.adaptation.variation == {"change_topology": trial.variant_id}
    assert record.lifecycle_execution is not None
    assert record.lifecycle_provenance is not None
    assert record.lifecycle_provenance.runtime_provider == trial.runtime_provenance.provider
    assert record.lifecycle_provenance.runtime_distributions == trial.runtime_provenance.distributions
    assert record.lifecycle_provenance.runtime_dependency_sha256 == trial.runtime_provenance.dependency_inventory_sha256
    assert record.completeness is Completeness.PARTIAL
    task_verifier = registered_lifecycle_verifier(TEMPLATE_ID)
    assert record.lifecycle_provenance.verifier_qualified_name == (
        f"{task_verifier.__module__}.{task_verifier.__qualname__}"
    )
    canonical = json.loads(next((run_dir / "experiments").glob("*/experiment-manifest.json")).read_text())
    assert len(canonical["verifier"]["chain"]) == 2


def test_finalize_lifecycle_trial_record_snapshots_artifacts_and_writes_once(tmp_path: Path) -> None:
    manifest, trial, package, run_dir = _recorded_trial(tmp_path)

    record_path = finalize_lifecycle_trial_record(
        manifest=manifest,
        trial=trial,
        package_dir=package,
        run_dir=run_dir,
    )
    original_record = record_path.read_bytes()
    record = TrialRecord.model_validate_json(original_record)

    assert record.lifecycle_provenance is not None
    assert record.completeness is (
        Completeness.PARTIAL if record.lifecycle_provenance.repository_dirty else Completeness.COMPLETE
    )
    assert record.outputs.artifacts
    assert record.lifecycle_provenance.invocation_manifest in record.outputs.artifacts
    for artifact in record.outputs.artifacts:
        snapshotted = Path(manifest.ledger_root) / artifact.path
        assert snapshotted.is_file()
        assert _sha256(snapshotted) == artifact.sha256

    shutil.rmtree(run_dir)
    shutil.rmtree(package)
    assert TrialRecord.model_validate_json(record_path.read_bytes()) == record
    for artifact in record.outputs.artifacts:
        assert (Path(manifest.ledger_root) / artifact.path).is_file()

    with pytest.raises(DuplicateTrialRecordError):
        finalize_lifecycle_trial_record(
            manifest=manifest,
            trial=trial,
            package_dir=package,
            run_dir=run_dir,
        )
    assert record_path.read_bytes() == original_record


def test_finalize_lifecycle_trial_record_recovers_snapshot_left_before_record_write(tmp_path: Path) -> None:
    manifest, trial, package, run_dir = _recorded_trial(tmp_path)
    record_path = finalize_lifecycle_trial_record(
        manifest=manifest,
        trial=trial,
        package_dir=package,
        run_dir=run_dir,
    )
    original_record = record_path.read_bytes()
    record = TrialRecord.model_validate_json(original_record)
    assert record.outputs.artifacts
    original_artifacts = {
        artifact.path: (Path(manifest.ledger_root) / artifact.path).read_bytes()
        for artifact in record.outputs.artifacts
    }
    record_path.unlink()

    recovered = finalize_lifecycle_trial_record(
        manifest=manifest,
        trial=trial,
        package_dir=package,
        run_dir=run_dir,
    )

    assert recovered.read_bytes() == original_record
    assert {
        artifact.path: (Path(manifest.ledger_root) / artifact.path).read_bytes()
        for artifact in record.outputs.artifacts
    } == original_artifacts


def test_run_lifecycle_ablation_snapshot_recovery_ignores_later_mutable_state_corruption(
    tmp_path: Path,
) -> None:
    manifest, trial, package, run_dir = _recorded_trial(tmp_path)
    record_path = finalize_lifecycle_trial_record(
        manifest=manifest,
        trial=trial,
        package_dir=package,
        run_dir=run_dir,
    )
    original = record_path.read_bytes()
    record_path.unlink()
    mutable_state_path = run_dir / "state.json"
    mutable_state = json.loads(mutable_state_path.read_text(encoding="utf-8"))
    mutable_state["checkpoint_runs"][0]["attempts"] = []
    mutable_state_path.write_text(json.dumps(mutable_state), encoding="utf-8")

    inspection = inspect_lifecycle_ablation_plan(manifest)
    assert inspection["trial_statuses"][0]["status"] == "finalizable"
    result = run_lifecycle_ablation(
        manifest,
        registry_factory=lambda *_args: (_ for _ in ()).throw(
            AssertionError("immutable snapshot recovery must not inspect or execute the mutable run")
        ),
    )

    assert result.imported_orphans == 1
    assert Path(result.record_paths[0]).read_bytes() == original


def test_lifecycle_ablation_inspection_ignores_malformed_mutable_contract_for_complete_record(
    tmp_path: Path,
) -> None:
    manifest = _single_manifest(tmp_path).model_copy(update={"experiment_id": "ssc03-immutable-inspection"})
    result = run_lifecycle_ablation(
        manifest,
        registry_factory=lambda _trial, package, _run: _GoldFreshRegistry(package),
    )
    (Path(manifest.output_root) / "manifest.json").write_text("{", encoding="utf-8")

    inspection = inspect_lifecycle_ablation_plan(manifest)

    assert inspection["trial_statuses"][0]["status"] == "complete"
    assert Path(result.record_paths[0]).is_file()


def test_finalize_lifecycle_trial_record_recovers_after_atomic_record_publish_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, trial, package, run_dir = _recorded_trial(tmp_path)

    def interrupted_temp_write(path: Path, _payload: str) -> None:
        path.write_text("{", encoding="utf-8")
        raise OSError("simulated power loss while writing record temp file")

    with monkeypatch.context() as patch:
        patch.setattr(ledger_writer, "_write_record_temp", interrupted_temp_write)
        with pytest.raises(OSError, match="simulated power loss"):
            finalize_lifecycle_trial_record(
                manifest=manifest,
                trial=trial,
                package_dir=package,
                run_dir=run_dir,
            )

    record_path = Path(trial.ledger_path)
    artifact_dir = Path(manifest.ledger_root) / manifest.experiment_id / "_artifacts" / trial.trial_id
    assert not record_path.exists()
    assert artifact_dir.is_dir()
    assert not list(record_path.parent.glob(f".{record_path.name}.*.tmp"))

    recovered = finalize_lifecycle_trial_record(
        manifest=manifest,
        trial=trial,
        package_dir=package,
        run_dir=run_dir,
    )

    assert recovered == record_path
    TrialRecord.model_validate_json(recovered.read_text(encoding="utf-8"))


def test_finalize_lifecycle_trial_record_rejects_declared_session_artifact_tamper(tmp_path: Path) -> None:
    manifest, trial, package, run_dir = _recorded_trial(tmp_path)
    agent_result_path = next(run_dir.glob("**/agent_result.json"))
    agent_result = json.loads(agent_result_path.read_text(encoding="utf-8"))
    agent_result["resolved_model"] = "forged-model"
    agent_result_path.write_text(json.dumps(agent_result), encoding="utf-8")

    with pytest.raises(ValueError, match="run artifact hash does not match canonical manifest"):
        finalize_lifecycle_trial_record(
            manifest=manifest,
            trial=trial,
            package_dir=package,
            run_dir=run_dir,
        )


def test_finalize_lifecycle_trial_record_uses_canonical_manifest_not_mutable_alias(tmp_path: Path) -> None:
    manifest, trial, package, run_dir = _recorded_trial(tmp_path)
    mutable_path = run_dir / "experiment-manifest.json"
    mutable = json.loads(mutable_path.read_text(encoding="utf-8"))
    mutable["repository"]["commit"] = "f" * 40
    mutable_path.write_text(json.dumps(mutable), encoding="utf-8")
    canonical_path = next((run_dir / "experiments").glob("*/experiment-manifest.json"))
    canonical = json.loads(canonical_path.read_text(encoding="utf-8"))

    record_path = finalize_lifecycle_trial_record(
        manifest=manifest,
        trial=trial,
        package_dir=package,
        run_dir=run_dir,
    )
    record = TrialRecord.model_validate_json(record_path.read_text(encoding="utf-8"))

    assert record.lifecycle_provenance is not None
    assert record.lifecycle_provenance.repository_commit == canonical["repository"]["commit"]
    assert record.lifecycle_provenance.repository_commit != mutable["repository"]["commit"]


def test_finalized_trial_contains_no_mutable_working_run_references(tmp_path: Path) -> None:
    manifest, trial, package, run_dir = _recorded_trial(tmp_path)
    record_path = finalize_lifecycle_trial_record(
        manifest=manifest,
        trial=trial,
        package_dir=package,
        run_dir=run_dir,
    )
    record = TrialRecord.model_validate_json(record_path.read_text(encoding="utf-8"))
    assert record.outputs.agent_result is not None

    referenced_paths = [
        record.outputs.agent_result["verification_path"],
        record.outputs.agent_result["metrics_path"],
        record.outputs.agent_result["manifest_path"],
        *record.outputs.agent_result["trajectories"],
        *record.outputs.agent_result["conversations"],
        *record.outputs.agent_result["raw_outputs"],
    ]
    shutil.rmtree(run_dir)
    shutil.rmtree(package)

    assert referenced_paths
    assert all(not Path(path).is_absolute() for path in referenced_paths)
    assert all((Path(manifest.ledger_root) / path).is_file() for path in referenced_paths)


def test_build_lifecycle_trial_record_rejects_tampered_metrics(tmp_path: Path) -> None:
    manifest, trial, package, run_dir = _recorded_trial(tmp_path)
    metrics_path = run_dir / "metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics["reads"] = 999
    metrics_path.write_text(json.dumps(metrics), encoding="utf-8")

    with pytest.raises(ValueError, match="lifecycle metrics hash does not match manifest"):
        build_lifecycle_trial_record(
            manifest=manifest,
            trial=trial,
            package_dir=package,
            run_dir=run_dir,
        )


def test_build_lifecycle_trial_record_rejects_self_consistent_forged_token_totals(tmp_path: Path) -> None:
    manifest, trial, package, run_dir = _recorded_trial(tmp_path)
    canonical_manifest_path = next((run_dir / "experiments").glob("*/experiment-manifest.json"))
    canonical_metrics_path = canonical_manifest_path.parent / "metrics.json"
    metrics = json.loads(canonical_metrics_path.read_text(encoding="utf-8"))
    metrics["input_tokens"] = 999
    encoded_metrics = json.dumps(metrics, indent=2, sort_keys=True) + "\n"
    canonical_metrics_path.write_text(encoded_metrics, encoding="utf-8")
    (run_dir / "metrics.json").write_text(encoded_metrics, encoding="utf-8")
    manifest_payload = json.loads(canonical_manifest_path.read_text(encoding="utf-8"))
    metrics_sha256 = _sha256(canonical_metrics_path)
    manifest_payload["outputs"]["metrics.json"] = metrics_sha256
    manifest_payload["outputs"]["artifacts"]["metrics.json"] = metrics_sha256
    canonical_manifest_path.write_text(json.dumps(manifest_payload), encoding="utf-8")
    index_path = run_dir.parent / "experiment-index.jsonl"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["manifest_sha256"] = _sha256(canonical_manifest_path)
    index_path.write_text(json.dumps(index) + "\n", encoding="utf-8")
    seal_path = canonical_manifest_path.parent / "index-entry.json"
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    seal["manifest_sha256"] = _sha256(canonical_manifest_path)
    seal_path.write_text(json.dumps(seal), encoding="utf-8")

    with pytest.raises(ValueError, match="input_tokens does not match session artifacts"):
        build_lifecycle_trial_record(
            manifest=manifest,
            trial=trial,
            package_dir=package,
            run_dir=run_dir,
        )


def test_build_lifecycle_trial_record_rejects_condition_mismatch(tmp_path: Path) -> None:
    manifest, trial, package, run_dir = _recorded_trial(tmp_path)
    mismatched_trial = trial.model_copy(
        update={
            "memory_visibility_policy": LifecycleVisibilityPolicy.RAW_EVIDENCE_ONLY,
        }
    )

    with pytest.raises(ValueError, match="lifecycle run visibility policy does not match planned trial"):
        build_lifecycle_trial_record(
            manifest=manifest,
            trial=mismatched_trial,
            package_dir=package,
            run_dir=run_dir,
        )


def test_build_lifecycle_trial_record_rejects_canonical_turn_limit_outside_plan(tmp_path: Path) -> None:
    manifest, trial, package, run_dir = _recorded_trial(tmp_path)
    experiment_path = next((run_dir / "experiments").glob("*/experiment-manifest.json"))
    experiment = json.loads(experiment_path.read_text(encoding="utf-8"))
    experiment["execution"]["max_turns_per_session"] = 999
    experiment_path.write_text(json.dumps(experiment), encoding="utf-8")
    manifest_hash = _sha256(experiment_path)
    index_path = run_dir.parent / "experiment-index.jsonl"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["manifest_sha256"] = manifest_hash
    index_path.write_text(json.dumps(index) + "\n", encoding="utf-8")
    seal_path = experiment_path.parent / "index-entry.json"
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    seal["manifest_sha256"] = manifest_hash
    seal_path.write_text(json.dumps(seal), encoding="utf-8")

    with pytest.raises(ValueError, match="turn limit does not match planned trial"):
        build_lifecycle_trial_record(
            manifest=manifest,
            trial=trial,
            package_dir=package,
            run_dir=run_dir,
        )


def test_build_lifecycle_trial_record_rejects_runtime_dependency_drift(tmp_path: Path) -> None:
    manifest, trial, package, run_dir = _recorded_trial(tmp_path)
    experiment_path = next((run_dir / "experiments").glob("*/experiment-manifest.json"))
    experiment = json.loads(experiment_path.read_text(encoding="utf-8"))
    experiment["environment"]["runtime_provenance"]["dependency_inventory_sha256"] = "0" * 64
    experiment_path.write_text(json.dumps(experiment), encoding="utf-8")
    manifest_hash = _sha256(experiment_path)
    index_path = run_dir.parent / "experiment-index.jsonl"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["manifest_sha256"] = manifest_hash
    index_path.write_text(json.dumps(index) + "\n", encoding="utf-8")
    seal_path = experiment_path.parent / "index-entry.json"
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    seal["manifest_sha256"] = manifest_hash
    seal_path.write_text(json.dumps(seal), encoding="utf-8")

    with pytest.raises(ValueError, match="runtime dependencies do not match planned trial"):
        build_lifecycle_trial_record(
            manifest=manifest,
            trial=trial,
            package_dir=package,
            run_dir=run_dir,
        )


def test_build_lifecycle_trial_record_rejects_sweep_context_mismatch(tmp_path: Path) -> None:
    manifest, trial, package, run_dir = _recorded_trial(tmp_path)
    experiment_path = next((run_dir / "experiments").glob("*/experiment-manifest.json"))
    experiment = json.loads(experiment_path.read_text(encoding="utf-8"))
    experiment["sweep"]["condition_id"] = "fresh_context__raw_evidence_only"
    experiment_path.write_text(json.dumps(experiment), encoding="utf-8")
    index_path = run_dir.parent / "experiment-index.jsonl"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["sweep"] = experiment["sweep"]
    index["manifest_sha256"] = _sha256(experiment_path)
    index_path.write_text(json.dumps(index) + "\n", encoding="utf-8")
    seal_path = experiment_path.parent / "index-entry.json"
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    seal["sweep"] = experiment["sweep"]
    seal["manifest_sha256"] = _sha256(experiment_path)
    seal_path.write_text(json.dumps(seal), encoding="utf-8")

    with pytest.raises(ValueError, match="lifecycle sweep context does not match planned trial"):
        build_lifecycle_trial_record(
            manifest=manifest,
            trial=trial,
            package_dir=package,
            run_dir=run_dir,
        )


def test_run_lifecycle_ablation_executes_real_in_process_trial_and_skips_completed_resume(
    tmp_path: Path,
) -> None:
    manifest = _single_manifest(tmp_path)
    build_count = 0

    def registry_factory(trial: LifecycleAblationTrial, package: Path, _run_dir: Path) -> object:
        nonlocal build_count
        build_count += 1
        return _GoldFreshRegistry(package)

    first = run_lifecycle_ablation(manifest, registry_factory=registry_factory)

    assert first.planned_trials == 1
    assert first.executed_trials == 1
    assert first.imported_orphans == 0
    assert first.skipped_trials == 0
    assert first.failed_trials == 0
    assert build_count == 1
    assert Path(first.summary_path).is_file()
    record_path = Path(first.record_paths[0])
    record_bytes = record_path.read_bytes()
    record = TrialRecord.model_validate_json(record_bytes)
    assert record.lifecycle_provenance is not None
    assert record.completeness is (
        Completeness.PARTIAL if record.lifecycle_provenance.repository_dirty else Completeness.COMPLETE
    )
    assert record.lifecycle_execution is not None
    assert len(record.lifecycle_execution.sessions) == 3
    assert all(session.artifacts for session in record.lifecycle_execution.sessions)
    invocation_path = Path(first.run_root) / "trials" / first.trial_ids[0] / "experiment-manifest.json"
    invocation = json.loads(invocation_path.read_text())
    assert invocation["sweep"]["planned_trial_id"] == first.trial_ids[0]

    def forbidden_registry_factory(*_args: object) -> object:
        raise AssertionError("completed trial must not invoke an adapter")

    second = run_lifecycle_ablation(manifest, registry_factory=forbidden_registry_factory)

    assert second.executed_trials == 0
    assert second.skipped_trials == 1
    assert second.record_paths == first.record_paths
    assert second.summary_path == first.summary_path
    assert record_path.read_bytes() == record_bytes


def test_run_lifecycle_ablation_rejects_forged_existing_record_before_skip(tmp_path: Path) -> None:
    manifest = _single_manifest(tmp_path)
    first = run_lifecycle_ablation(
        manifest,
        registry_factory=lambda _trial, package, _run: _GoldFreshRegistry(package),
    )
    record_path = Path(first.record_paths[0])
    forged = json.loads(record_path.read_text(encoding="utf-8"))
    forged["agent"]["adapter"] = "pydantic_ai"
    forged["agent"]["configuration"]["requested_model"] = "forged-model"
    forged["agent"]["configuration"]["plan_sha256"] = "0" * 64
    forged["lifecycle_execution"] = None
    forged["lifecycle_provenance"] = None
    forged["completeness"] = "partial"
    TrialRecord.model_validate(forged)
    record_path.write_text(json.dumps(forged), encoding="utf-8")

    with pytest.raises(ValueError, match="existing TrialRecord does not match"):
        run_lifecycle_ablation(
            manifest,
            registry_factory=lambda *_args: (_ for _ in ()).throw(
                AssertionError("forged record must fail before adapter execution")
            ),
        )


def test_lifecycle_ablation_evaluation_rejects_forged_planned_record(tmp_path: Path) -> None:
    manifest = _single_manifest(tmp_path)
    result = run_lifecycle_ablation(
        manifest,
        registry_factory=lambda _trial, package, _run: _GoldFreshRegistry(package),
    )
    record_path = Path(result.record_paths[0])
    forged = json.loads(record_path.read_text(encoding="utf-8"))
    forged["experiment_id"] = manifest.experiment_id
    forged["agent"]["configuration"]["requested_model"] = "forged-model"
    record_path.write_text(json.dumps(forged), encoding="utf-8")

    with pytest.raises(ValueError, match="TrialRecord does not match"):
        build_lifecycle_ablation_evaluation(manifest)


def test_run_lifecycle_ablation_imports_completed_orphan_without_executor(tmp_path: Path) -> None:
    manifest, trial, _package, _run_dir = _recorded_trial(tmp_path)
    assert inspect_lifecycle_ablation_plan(manifest)["trial_statuses"][0]["status"] == "finalizable"

    def forbidden_registry_factory(*_args: object) -> object:
        raise AssertionError("completed orphan must be imported without an adapter")

    result = run_lifecycle_ablation(manifest, registry_factory=forbidden_registry_factory)

    assert result.executed_trials == 0
    assert result.imported_orphans == 1
    assert result.skipped_trials == 0
    assert result.trial_ids == [trial.trial_id]
    assert Path(result.record_paths[0]).is_file()


def test_run_lifecycle_ablation_recovers_missing_shared_index_from_canonical_seal(
    tmp_path: Path,
) -> None:
    manifest, trial, _package, run_dir = _recorded_trial(tmp_path)
    index_path = run_dir.parent / "experiment-index.jsonl"
    index_path.unlink()

    inspection = inspect_lifecycle_ablation_plan(manifest)
    assert inspection["trial_statuses"][0]["status"] == "finalizable"

    def forbidden_registry_factory(*_args: object) -> object:
        raise AssertionError("sealed orphan recovery must not invoke an adapter")

    result = run_lifecycle_ablation(manifest, registry_factory=forbidden_registry_factory)

    assert result.imported_orphans == 1
    assert Path(trial.ledger_path).is_file()
    repaired = [json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines()]
    assert len(repaired) == 1
    assert repaired[0]["sweep"]["planned_trial_id"] == trial.trial_id
    record = TrialRecord.model_validate_json(Path(result.record_paths[0]).read_text(encoding="utf-8"))
    assert record.outputs.artifacts is not None
    assert any(artifact.kind == "lifecycle_invocation_seal" for artifact in record.outputs.artifacts)


def test_run_lifecycle_ablation_rebuilds_truncated_shared_index_from_canonical_seal(
    tmp_path: Path,
) -> None:
    manifest, trial, _package, run_dir = _recorded_trial(tmp_path)
    index_path = run_dir.parent / "experiment-index.jsonl"
    index_path.write_text('{"experiment_id":', encoding="utf-8")

    inspection = inspect_lifecycle_ablation_plan(manifest)
    assert inspection["trial_statuses"][0]["status"] == "finalizable"

    result = run_lifecycle_ablation(
        manifest,
        registry_factory=lambda *_args: (_ for _ in ()).throw(
            AssertionError("truncated index recovery must not invoke an adapter")
        ),
    )

    assert result.imported_orphans == 1
    repaired = [json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines()]
    assert [entry["sweep"]["planned_trial_id"] for entry in repaired] == [trial.trial_id]


def test_concurrent_finalization_repairs_shared_index_without_lost_entries(tmp_path: Path) -> None:
    manifest = _single_manifest(tmp_path).model_copy(
        update={
            "experiment_id": "ssc03-concurrent-index-repair",
            "variants": ("response_assertion_only", "memo_closeout_missing"),
            "limits": LifecycleAblationLimits(max_trials=2),
        }
    )
    plan = build_lifecycle_ablation_plan(manifest)
    prepared: list[tuple[LifecycleAblationTrial, Path, Path]] = []
    for trial in plan.trials:
        package = materialize_template_lifecycle(
            get_template(TEMPLATE_ID),
            Path(trial.package_dir),
            variant_id=trial.variant_id,
        )
        run_dir = Path(trial.run_dir)
        run_local_evidence_lifecycle_fresh_context(
            package_dir=package,
            run_dir=run_dir,
            model=trial.agent.model,
            adapter_kind=trial.agent.adapter,
            max_turns=trial.max_turns_per_session,
            registry=_GoldFreshRegistry(package, resolved_model=trial.agent.model),
            verifier=verify_template_lifecycle,
            visibility_policy=trial.memory_visibility_policy,
            sweep_context=LifecycleExperimentSweepContext(
                sweep_experiment_id=manifest.experiment_id,
                planned_trial_id=trial.trial_id,
                plan_sha256=plan.plan_sha256,
                condition_id=f"{trial.execution_mode.value}__{trial.memory_visibility_policy.value}",
                repetition=trial.repetition,
            ),
        )
        prepared.append((trial, package, run_dir))
    index_path = Path(manifest.output_root) / "trials" / "experiment-index.jsonl"
    index_path.unlink()

    def finalize(item: tuple[LifecycleAblationTrial, Path, Path]) -> Path:
        trial, package, run_dir = item
        return finalize_lifecycle_trial_record(
            manifest=manifest,
            trial=trial,
            package_dir=package,
            run_dir=run_dir,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        records = list(executor.map(finalize, prepared))

    assert all(path.is_file() for path in records)
    entries = [json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines()]
    assert {entry["sweep"]["planned_trial_id"] for entry in entries} == {trial.trial_id for trial in plan.trials}


def test_run_lifecycle_ablation_rejects_submitted_checkpoint_without_attempt_owner(
    tmp_path: Path,
) -> None:
    manifest = _single_manifest(tmp_path).model_copy(update={"experiment_id": "ssc03-unowned-checkpoint"})
    trial = build_lifecycle_ablation_plan(manifest).trials[0]
    package = materialize_template_lifecycle(
        get_template(TEMPLATE_ID),
        Path(trial.package_dir),
        variant_id=trial.variant_id,
    )
    run_dir = Path(trial.run_dir)
    prepared = prepare_evidence_checkpoint(package, run_dir)
    gold = json.loads((package / "hidden" / "gold-submissions.json").read_text(encoding="utf-8"))
    submission = Path(prepared["submission_path"])
    submission.parent.mkdir(parents=True, exist_ok=True)
    submission.write_text(json.dumps(gold["initial_review"]), encoding="utf-8")
    submit_evidence_checkpoint(package, run_dir)

    inspection = inspect_lifecycle_ablation_plan(manifest)
    assert inspection["trial_statuses"][0]["status"] == "conflict"
    assert "submitted checkpoint has no adapter attempt owner" in inspection["trial_statuses"][0]["reason"]

    with pytest.raises(ValueError, match="submitted checkpoint has no adapter attempt owner"):
        run_lifecycle_ablation(
            manifest,
            registry_factory=lambda *_args: (_ for _ in ()).throw(
                AssertionError("unowned state must fail before adapter construction")
            ),
        )
    assert not Path(trial.ledger_path).exists()


def test_run_lifecycle_ablation_records_actual_adapter_mismatch_as_zero_reward_failure(
    tmp_path: Path,
) -> None:
    manifest = _single_manifest(tmp_path).model_copy(update={"experiment_id": "ssc03-adapter-mismatch"})

    result = run_lifecycle_ablation(
        manifest,
        registry_factory=lambda _trial, package, _run: _MismatchedAdapterRegistry(package),
    )

    assert result.failed_trials == 1
    record = TrialRecord.model_validate_json(Path(result.record_paths[0]).read_text(encoding="utf-8"))
    assert record.evaluation.reward == 0.0
    assert record.agent.adapter == "pydantic_ai"
    assert record.agent.configuration["requested_adapter"] == "tool_loop"
    assert record.lifecycle_execution is not None
    assert record.lifecycle_execution.status == "failed"
    assert record.lifecycle_execution.sessions[0].requested_adapter == "tool_loop"
    assert record.lifecycle_execution.sessions[0].adapter == "pydantic_ai"
    assert record.lifecycle_execution.sessions[0].failure_kind == "adapter_identity_mismatch"


def test_run_lifecycle_ablation_dispatches_persistent_condition_to_one_session(tmp_path: Path) -> None:
    manifest = _single_manifest(tmp_path).model_copy(
        update={
            "experiment_id": "ssc03-persistent",
            "conditions": (
                LifecycleAblationCondition(
                    execution_mode=LifecycleExecutionMode.PERSISTENT_CONTEXT,
                    memory_visibility_policy=LifecycleVisibilityPolicy.PERSISTENT_CONTEXT,
                ),
            ),
        }
    )

    result = run_lifecycle_ablation(
        manifest,
        registry_factory=lambda _trial, package, run: _GoldPersistentRegistry(package, run),
    )

    record = TrialRecord.model_validate_json(Path(result.record_paths[0]).read_text(encoding="utf-8"))
    assert record.lifecycle_execution is not None
    assert record.lifecycle_execution.execution_mode == "persistent_context"
    assert record.lifecycle_execution.memory_visibility_policy == "persistent_context"
    assert len(record.lifecycle_execution.sessions) == 1
    assert record.lifecycle_execution.sessions[0].checkpoint_ids == [
        "initial_review",
        "response_review",
        "closeout_review",
    ]
    group = build_lifecycle_ablation_evaluation(manifest).summary["groups"][0]
    assert group["max_turns_per_session"] == 10
    assert group["total_sessions"] == 1
    assert group["total_configured_turn_capacity"] == 10


def test_run_lifecycle_ablation_recovers_terminal_persistent_session_crash_without_adapter(
    tmp_path: Path,
) -> None:
    manifest = _persistent_manifest(tmp_path, experiment_id="ssc03-terminal-persistent-crash")
    _trial, _package, _run_dir, session_id = _terminal_persistent_state(manifest)

    inspection = inspect_lifecycle_ablation_plan(manifest)
    assert inspection["trial_statuses"][0]["status"] == "finalizable"
    result = run_lifecycle_ablation(
        manifest,
        registry_factory=lambda *_args: (_ for _ in ()).throw(
            AssertionError("terminal crash recovery must not rebuild or call an adapter")
        ),
    )

    assert result.imported_orphans == 1
    assert result.failed_trials == 1
    record = TrialRecord.model_validate_json(Path(result.record_paths[0]).read_text(encoding="utf-8"))
    assert record.evaluation.reward == 0.0
    assert record.agent.model == "unresolved"
    assert record.agent.adapter == "unresolved"
    assert record.lifecycle_execution is not None
    assert record.lifecycle_execution.status == "failed"
    assert record.lifecycle_execution.sessions[0].session_id == session_id
    assert record.lifecycle_execution.sessions[0].resolved_model == "unresolved"
    assert record.lifecycle_execution.sessions[0].adapter == "unresolved"
    assert record.lifecycle_execution.sessions[0].failure_kind == "interrupted_after_completion"


def test_run_lifecycle_ablation_quarantines_torn_terminal_agent_result(
    tmp_path: Path,
) -> None:
    manifest = _persistent_manifest(tmp_path, experiment_id="ssc03-torn-terminal-result")
    _trial, _package, run_dir, session_id = _terminal_persistent_state(manifest)
    result_path = run_dir / "sessions" / session_id / "agent_result.json"
    result_path.write_text("{", encoding="utf-8")

    inspection = inspect_lifecycle_ablation_plan(manifest)
    assert inspection["trial_statuses"][0]["status"] == "finalizable"
    result = run_lifecycle_ablation(
        manifest,
        registry_factory=lambda *_args: (_ for _ in ()).throw(
            AssertionError("torn terminal result recovery must not call an adapter")
        ),
    )

    record = TrialRecord.model_validate_json(Path(result.record_paths[0]).read_text(encoding="utf-8"))
    assert record.evaluation.reward == 0.0
    assert record.outputs.artifacts is not None
    assert any(artifact.kind == "corrupt_agent_result" for artifact in record.outputs.artifacts)
    assert record.lifecycle_execution is not None
    assert record.lifecycle_execution.sessions[0].failure_kind == "interrupted_after_completion"


def test_lifecycle_ablation_reports_torn_terminal_trajectory_as_conflict(tmp_path: Path) -> None:
    manifest = _persistent_manifest(tmp_path, experiment_id="ssc03-torn-terminal-trajectory")
    _trial, _package, run_dir, session_id = _terminal_persistent_state(manifest)
    (run_dir / "sessions" / session_id / "trajectory.jsonl").write_text("{", encoding="utf-8")

    inspection = inspect_lifecycle_ablation_plan(manifest)

    assert inspection["trial_statuses"][0]["status"] == "conflict"
    assert "trajectory is malformed" in inspection["trial_statuses"][0]["reason"]


def test_run_lifecycle_ablation_records_provider_failure_after_terminal_submission(
    tmp_path: Path,
) -> None:
    manifest = _persistent_manifest(tmp_path, experiment_id="ssc03-terminal-provider-failure")

    result = run_lifecycle_ablation(
        manifest,
        registry_factory=lambda _trial, package, run: _TerminalProviderFailurePersistentRegistry(package, run),
    )

    assert result.failed_trials == 1
    record = TrialRecord.model_validate_json(Path(result.record_paths[0]).read_text(encoding="utf-8"))
    assert record.evaluation.reward == 0.0
    assert record.evaluation.validity.verifier_completed is False
    assert record.lifecycle_execution is not None
    assert record.lifecycle_execution.status == "failed"
    assert record.lifecycle_execution.sessions[0].status == "failed"
    assert record.lifecycle_execution.sessions[0].failure_kind == "provider_error"
    state = json.loads(
        (Path(result.run_root) / "trials" / result.trial_ids[0] / "state.json").read_text(encoding="utf-8")
    )
    assert state["status"] == "complete"
    assert all(
        attempt["status"] == "submitted"
        for checkpoint in state["checkpoint_runs"]
        for attempt in checkpoint["attempts"]
    )


def test_run_lifecycle_ablation_rejects_attempt_mode_outside_planned_condition(
    tmp_path: Path,
) -> None:
    manifest = _single_manifest(tmp_path).model_copy(update={"experiment_id": "ssc03-attempt-mode-conflict"})
    trial = build_lifecycle_ablation_plan(manifest).trials[0]
    package = materialize_template_lifecycle(
        get_template(TEMPLATE_ID),
        Path(trial.package_dir),
        variant_id=trial.variant_id,
    )
    run_dir = Path(trial.run_dir)
    context = prepare_evidence_checkpoint(package, run_dir)
    open_checkpoint_attempt(
        package,
        run_dir,
        session_id="initial_review.session-001",
        execution_mode="persistent_context",
    )
    gold = json.loads((package / "hidden" / "gold-submissions.json").read_text(encoding="utf-8"))
    submission = Path(context["submission_path"])
    submission.parent.mkdir(parents=True, exist_ok=True)
    submission.write_text(json.dumps(gold["initial_review"]), encoding="utf-8")
    submit_evidence_checkpoint(package, run_dir)

    inspection = inspect_lifecycle_ablation_plan(manifest)
    assert inspection["trial_statuses"][0]["status"] == "conflict"
    assert "attempt execution mode does not match planned trial" in inspection["trial_statuses"][0]["reason"]
    with pytest.raises(ValueError, match="attempt execution mode does not match planned trial"):
        run_lifecycle_ablation(
            manifest,
            registry_factory=lambda *_args: (_ for _ in ()).throw(
                AssertionError("mode conflict must fail before adapter construction")
            ),
        )


def test_run_lifecycle_ablation_rejects_fresh_session_shared_across_checkpoints(
    tmp_path: Path,
) -> None:
    manifest = _single_manifest(tmp_path).model_copy(update={"experiment_id": "ssc03-shared-fresh-session"})
    trial = build_lifecycle_ablation_plan(manifest).trials[0]
    package = materialize_template_lifecycle(
        get_template(TEMPLATE_ID),
        Path(trial.package_dir),
        variant_id=trial.variant_id,
    )
    run_dir = Path(trial.run_dir)
    session_id = "shared.session-001"
    gold = json.loads((package / "hidden" / "gold-submissions.json").read_text(encoding="utf-8"))
    for expected_checkpoint in ("initial_review", "response_review"):
        context = prepare_evidence_checkpoint(package, run_dir)
        assert context["checkpoint_id"] == expected_checkpoint
        open_checkpoint_attempt(
            package,
            run_dir,
            session_id=session_id,
            execution_mode="fresh_context",
        )
        submission = Path(context["submission_path"])
        submission.parent.mkdir(parents=True, exist_ok=True)
        submission.write_text(json.dumps(gold[expected_checkpoint]), encoding="utf-8")
        submit_evidence_checkpoint(package, run_dir)

    inspection = inspect_lifecycle_ablation_plan(manifest)
    assert inspection["trial_statuses"][0]["status"] == "conflict"
    assert "fresh session must own exactly one checkpoint" in inspection["trial_statuses"][0]["reason"]
    with pytest.raises(ValueError, match="fresh session must own exactly one checkpoint"):
        run_lifecycle_ablation(
            manifest,
            registry_factory=lambda *_args: (_ for _ in ()).throw(
                AssertionError("shared fresh session must fail before adapter construction")
            ),
        )


def test_run_lifecycle_ablation_ignores_incomplete_canonical_staging_directory(
    tmp_path: Path,
) -> None:
    manifest, trial, package, run_dir = _recorded_trial(tmp_path)
    canonical = next((run_dir / "experiments").glob("lifecycle-*"))
    staging = canonical.with_name(f".{canonical.name}.staging-crash")
    canonical.replace(staging)
    (run_dir.parent / "experiment-index.jsonl").unlink()
    registry = _GoldFreshRegistry(package)

    inspection = inspect_lifecycle_ablation_plan(manifest)
    assert inspection["trial_statuses"][0]["status"] == "resumable"
    result = run_lifecycle_ablation(
        manifest,
        registry_factory=lambda _trial, _package, _run: registry,
    )

    assert result.executed_trials == 1
    assert registry.build_count == 0
    assert Path(trial.ledger_path).is_file()


def test_run_lifecycle_ablation_resumes_matching_unfinalized_runtime_state(tmp_path: Path) -> None:
    manifest = _single_manifest(tmp_path)
    trial = build_lifecycle_ablation_plan(manifest).trials[0]
    package = materialize_template_lifecycle(
        get_template(TEMPLATE_ID),
        Path(trial.package_dir),
        variant_id=trial.variant_id,
    )
    prepared = prepare_evidence_checkpoint(package, Path(trial.run_dir))
    assert prepared["checkpoint_id"] == "initial_review"
    assert inspect_lifecycle_ablation_plan(manifest)["trial_statuses"][0]["status"] == "resumable"

    result = run_lifecycle_ablation(
        manifest,
        registry_factory=lambda _trial, selected_package, _run: _GoldFreshRegistry(selected_package),
    )

    assert result.executed_trials == 1
    assert result.imported_orphans == 0
    assert inspect_lifecycle_ablation_plan(manifest)["trial_statuses"][0]["status"] == "complete"
    state = read_evidence_lifecycle_state(package, Path(trial.run_dir))
    assert state["status"] == "complete"


def test_run_lifecycle_ablation_seals_interrupted_attempt_before_resume(tmp_path: Path) -> None:
    manifest = _single_manifest(tmp_path).model_copy(update={"experiment_id": "ssc03-interrupted-resume"})
    trial = build_lifecycle_ablation_plan(manifest).trials[0]
    package = materialize_template_lifecycle(
        get_template(TEMPLATE_ID),
        Path(trial.package_dir),
        variant_id=trial.variant_id,
    )
    run_dir = Path(trial.run_dir)
    prepared = prepare_evidence_checkpoint(package, run_dir)
    assert prepared["checkpoint_id"] == "initial_review"
    interrupted_session = "initial_review.session-001"
    open_checkpoint_attempt(
        package,
        run_dir,
        session_id=interrupted_session,
        execution_mode="fresh_context",
    )
    interrupted_dir = run_dir / "episodes" / "initial_review" / interrupted_session
    interrupted_dir.mkdir(parents=True)
    (interrupted_dir / "trajectory.jsonl").write_text("", encoding="utf-8")

    result = run_lifecycle_ablation(
        manifest,
        registry_factory=lambda _trial, selected_package, _run: _GoldFreshRegistry(selected_package),
    )

    assert result.executed_trials == 1
    assert result.failed_trials == 1
    record = TrialRecord.model_validate_json(Path(result.record_paths[0]).read_text(encoding="utf-8"))
    assert record.lifecycle_execution is not None
    sessions = {session.session_id: session for session in record.lifecycle_execution.sessions}
    assert sessions[interrupted_session].status == "failed"
    assert sessions[interrupted_session].failure_kind == "interrupted"
    assert sessions[interrupted_session].resolved_model == "unresolved"
    assert sessions[interrupted_session].checkpoint_ids == ["initial_review"]
    assert any(artifact.kind == "trajectory" for artifact in sessions[interrupted_session].artifacts)


def test_run_lifecycle_ablation_seals_interrupted_persistent_session_before_resume(tmp_path: Path) -> None:
    manifest = _single_manifest(tmp_path).model_copy(
        update={
            "experiment_id": "ssc03-interrupted-persistent-resume",
            "conditions": (
                LifecycleAblationCondition(
                    execution_mode=LifecycleExecutionMode.PERSISTENT_CONTEXT,
                    memory_visibility_policy=LifecycleVisibilityPolicy.PERSISTENT_CONTEXT,
                ),
            ),
        }
    )
    trial = build_lifecycle_ablation_plan(manifest).trials[0]
    package = materialize_template_lifecycle(
        get_template(TEMPLATE_ID),
        Path(trial.package_dir),
        variant_id=trial.variant_id,
    )
    run_dir = Path(trial.run_dir)
    prepare_evidence_checkpoint(package, run_dir)
    open_checkpoint_attempt(
        package,
        run_dir,
        session_id="session-001",
        execution_mode="persistent_context",
    )
    interrupted_dir = run_dir / "sessions" / "session-001"
    interrupted_dir.mkdir(parents=True)
    (interrupted_dir / "trajectory.jsonl").write_text("", encoding="utf-8")

    result = run_lifecycle_ablation(
        manifest,
        registry_factory=lambda _trial, selected_package, selected_run: _GoldPersistentRegistry(
            selected_package, selected_run
        ),
    )

    assert result.failed_trials == 1
    record = TrialRecord.model_validate_json(Path(result.record_paths[0]).read_text(encoding="utf-8"))
    assert record.lifecycle_execution is not None
    sessions = {session.session_id: session for session in record.lifecycle_execution.sessions}
    assert sessions["session-001"].failure_kind == "interrupted"
    assert sessions["session-001"].resolved_model == "unresolved"
    assert sessions["session-002"].status == "completed"


def test_run_lifecycle_ablation_records_provider_failure_as_immutable_trial(tmp_path: Path) -> None:
    manifest = _single_manifest(tmp_path).model_copy(update={"experiment_id": "ssc03-provider-failure"})

    result = run_lifecycle_ablation(
        manifest,
        registry_factory=lambda _trial, _package, _run: _FailedRegistry(),
    )

    assert result.executed_trials == 1
    assert result.failed_trials == 1
    record = TrialRecord.model_validate_json(Path(result.record_paths[0]).read_text(encoding="utf-8"))
    assert record.lifecycle_provenance is not None
    assert record.completeness is (
        Completeness.PARTIAL if record.lifecycle_provenance.repository_dirty else Completeness.COMPLETE
    )
    assert record.lifecycle_execution is not None
    assert record.lifecycle_execution.status == "failed"
    assert record.lifecycle_execution.sessions[0].failure_kind == "provider_error"
    assert record.evaluation.reward == 0.0
    assert record.evaluation.validity.verifier_completed is False
    assert record.cost is not None
    assert record.cost.tokens_in == 3

    second = run_lifecycle_ablation(
        manifest,
        registry_factory=lambda *_args: (_ for _ in ()).throw(
            AssertionError("finalized failure must not be retried under the same trial id")
        ),
    )
    assert second.executed_trials == 0
    assert second.skipped_trials == 1


def test_run_lifecycle_ablation_normalizes_empty_agent_output_as_failed(tmp_path: Path) -> None:
    manifest = _single_manifest(tmp_path).model_copy(update={"experiment_id": "ssc03-empty-output"})

    result = run_lifecycle_ablation(
        manifest,
        registry_factory=lambda _trial, _package, _run: _EmptyRegistry(),
    )

    assert result.failed_trials == 1
    record = TrialRecord.model_validate_json(Path(result.record_paths[0]).read_text(encoding="utf-8"))
    assert record.outputs.agent_output is not None
    assert record.outputs.agent_output.status.value == "failed"
    assert record.lifecycle_execution is not None
    assert record.lifecycle_execution.status == "failed"
    assert record.lifecycle_execution.sessions[0].status == "failed"
    assert record.lifecycle_execution.sessions[0].failure_kind == "agent_failed"
    assert record.evaluation.validity.output_parseable is False
    assert record.evaluation.validity.schema_valid is False


def test_run_lifecycle_ablation_does_not_claim_schema_validity_after_verifier_exception(tmp_path: Path) -> None:
    manifest = _single_manifest(tmp_path).model_copy(update={"experiment_id": "ssc03-invalid-schema"})

    result = run_lifecycle_ablation(
        manifest,
        registry_factory=lambda _trial, package, _run: _InvalidSchemaRegistry(package),
    )

    assert result.failed_trials == 1
    record = TrialRecord.model_validate_json(Path(result.record_paths[0]).read_text(encoding="utf-8"))
    assert record.evaluation.validity.output_parseable is True
    assert record.evaluation.validity.schema_valid is False
    assert record.evaluation.validity.verifier_completed is False
    assert record.evaluation.reward == 0.0


@pytest.mark.parametrize("registry_name", ["provider_failure", "premature_completion"])
def test_run_lifecycle_ablation_finalizes_persistent_execution_failures(
    tmp_path: Path,
    registry_name: str,
) -> None:
    registry = _FailedRegistry() if registry_name == "provider_failure" else _PrematurePersistentRegistry()
    manifest = _single_manifest(tmp_path).model_copy(
        update={
            "experiment_id": f"ssc03-persistent-failure-{registry_name}",
            "conditions": (
                LifecycleAblationCondition(
                    execution_mode=LifecycleExecutionMode.PERSISTENT_CONTEXT,
                    memory_visibility_policy=LifecycleVisibilityPolicy.PERSISTENT_CONTEXT,
                ),
            ),
        }
    )

    result = run_lifecycle_ablation(
        manifest,
        registry_factory=lambda _trial, _package, _run: registry,
    )

    assert result.failed_trials == 1
    record = TrialRecord.model_validate_json(Path(result.record_paths[0]).read_text(encoding="utf-8"))
    assert record.lifecycle_execution is not None
    assert record.lifecycle_execution.status == "failed"
    assert record.lifecycle_execution.sessions[0].status == "failed"
    assert record.lifecycle_execution.sessions[0].checkpoint_ids == ["initial_review"]
    assert record.evaluation.validity.verifier_completed is False


def test_run_lifecycle_ablation_rejects_manifest_drift_before_adapter_call(tmp_path: Path) -> None:
    manifest = _single_manifest(tmp_path)
    first = run_lifecycle_ablation(
        manifest,
        registry_factory=lambda _trial, package, _run: _GoldFreshRegistry(package),
    )
    original_record = Path(first.record_paths[0]).read_bytes()
    drifted = manifest.model_copy(
        update={
            "repetitions": 2,
            "limits": LifecycleAblationLimits(max_trials=2),
        }
    )
    inspection = inspect_lifecycle_ablation_plan(drifted)
    assert {item["status"] for item in inspection["trial_statuses"]} == {"conflict"}
    assert "artifact snapshot ablation manifest does not match requested sweep" in {
        item["reason"] for item in inspection["trial_statuses"]
    }

    with pytest.raises(ValueError, match="does not match requested sweep"):
        run_lifecycle_ablation(
            drifted,
            registry_factory=lambda *_args: (_ for _ in ()).throw(
                AssertionError("manifest drift must fail before adapter execution")
            ),
        )

    assert Path(first.record_paths[0]).read_bytes() == original_record


def test_run_lifecycle_ablation_rejects_package_conflict_before_adapter_call(tmp_path: Path) -> None:
    manifest = _single_manifest(tmp_path)
    trial = build_lifecycle_ablation_plan(manifest).trials[0]
    package = materialize_template_lifecycle(
        get_template(TEMPLATE_ID),
        Path(trial.package_dir),
        variant_id=trial.variant_id,
    )
    gold_path = package / "hidden" / "gold-submissions.json"
    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    gold["closeout_review"]["readiness_decision"] = "not_ready_to_issue"
    gold_path.write_text(json.dumps(gold), encoding="utf-8")
    inspection = inspect_lifecycle_ablation_plan(manifest)
    assert inspection["trial_statuses"][0]["status"] == "conflict"
    assert "variant identity does not match materialized package content" in inspection["trial_statuses"][0]["reason"]

    with pytest.raises(ValueError, match="variant identity does not match materialized package content"):
        run_lifecycle_ablation(
            manifest,
            registry_factory=lambda *_args: (_ for _ in ()).throw(
                AssertionError("package conflict must fail before adapter execution")
            ),
        )

    assert not Path(trial.ledger_path).exists()


def test_lifecycle_ablation_evaluation_reads_only_core_trial_records(tmp_path: Path) -> None:
    manifest = _single_manifest(tmp_path)
    result = run_lifecycle_ablation(
        manifest,
        registry_factory=lambda _trial, package, _run: _GoldFreshRegistry(package),
    )

    first = build_lifecycle_ablation_evaluation(manifest)
    summary = first.summary
    assert summary["planned_trials"] == 1
    assert summary["invocation_records"] == 1
    assert summary["completed_trials"] == 1
    assert summary["failed_trials"] == 0
    assert summary["passed_trials"] == 1
    assert summary["mean_reward"] == 1.0
    assert summary["study_design"] == manifest.study_design.model_dump(mode="json")
    assert summary["groups"] == [
        {
            "agent_name": "gold-replay",
            "adapter": "tool_loop",
            "requested_adapter": "tool_loop",
            "resolved_adapters": ["tool_loop"],
            "requested_model": "deterministic-replay",
            "resolved_models": ["deterministic-replay"],
            "variant_id": "response_assertion_only",
            "execution_mode": "fresh_context",
            "memory_visibility_policy": "artifact_memory",
            "trials": 1,
            "completed": 1,
            "failed": 0,
            "passed": 1,
            "mean_reward": 1.0,
            "mean_retention": 1.0,
            "total_cost_usd": 0.0,
            "turn_budget_scope": "per_session",
            "max_turns_per_session": 10,
            "total_sessions": 3,
            "mean_sessions_per_trial": 3.0,
            "total_configured_turn_capacity": 30,
            "mean_configured_turn_capacity": 30.0,
            "total_requests": 0,
            "mean_requests": 0.0,
            "total_tool_calls": 0,
            "mean_tool_calls": 0.0,
            "total_input_tokens": 30,
            "mean_input_tokens": 30.0,
            "total_output_tokens": 6,
            "mean_output_tokens": 6.0,
            "total_cache_read_tokens": 0,
            "mean_cache_read_tokens": 0.0,
            "total_cache_write_tokens": 0,
            "mean_cache_write_tokens": 0.0,
        }
    ]

    run_dir = Path(result.run_root) / "trials" / result.trial_ids[0]
    verification = json.loads((run_dir / "verification.json").read_text(encoding="utf-8"))
    verification["reward"] = 0.0
    (run_dir / "verification.json").write_text(json.dumps(verification), encoding="utf-8")
    second = build_lifecycle_ablation_evaluation(manifest)
    assert second == first

    path = write_lifecycle_ablation_evaluation(manifest)
    assert path.is_file()
    assert json.loads(path.read_text(encoding="utf-8"))["summary"] == summary


def test_lifecycle_ablation_evaluation_uses_snapshotted_runtime_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _single_manifest(tmp_path)
    result = run_lifecycle_ablation(
        manifest,
        registry_factory=lambda _trial, package, _run: _GoldFreshRegistry(package),
    )
    record = TrialRecord.model_validate_json(Path(result.record_paths[0]).read_text(encoding="utf-8"))
    original_environment = record.environment
    monkeypatch.setattr(platform, "python_version", lambda: "99.99.99")

    evaluation = build_lifecycle_ablation_evaluation(manifest)

    assert evaluation.summary["invocation_records"] == 1
    persisted = TrialRecord.model_validate_json(Path(result.record_paths[0]).read_text(encoding="utf-8"))
    assert persisted.environment == original_environment


def test_lifecycle_ablation_evaluation_uses_snapshotted_historical_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _single_manifest(tmp_path)
    result = run_lifecycle_ablation(
        manifest,
        registry_factory=lambda _trial, package, _run: _GoldFreshRegistry(package),
    )
    record = TrialRecord.model_validate_json(Path(result.record_paths[0]).read_text(encoding="utf-8"))
    assert record.lifecycle_provenance is not None
    assert record.lifecycle_provenance.ablation_plan is not None
    baseline = build_lifecycle_ablation_plan(manifest)
    drifted_provenance = baseline.code_provenance.model_copy(update={"trial_importer_source_sha256": "0" * 64})
    monkeypatch.setattr(ablation_plan_runtime, "_ablation_code_provenance", lambda _template_id: drifted_provenance)

    evaluation = build_lifecycle_ablation_evaluation(manifest)

    assert evaluation.summary["planned_trials"] == 1
    assert evaluation.summary["invocation_records"] == 1


def _manifest(
    output_root: Path,
    ledger_root: Path,
    *,
    repetitions: int = 1,
) -> LifecycleAblationManifest:
    return LifecycleAblationManifest(
        experiment_id="ssc03-ablation",
        lifecycle_template_id=TEMPLATE_ID,
        variants=VARIANTS,
        agents=(
            AgentConfig(
                name="agent-b",
                adapter="tool_loop",
                model="model-b",
                parameters={"max_turns_per_session": 10},
            ),
            AgentConfig(
                name="agent-a",
                adapter="tool_loop",
                model="model-a",
                parameters={"max_turns_per_session": 10},
            ),
        ),
        study_design=_study_design(),
        repetitions=repetitions,
        output_root=str(output_root),
        ledger_root=str(ledger_root),
        limits=LifecycleAblationLimits(max_trials=100),
    )


def _single_manifest(tmp_path: Path) -> LifecycleAblationManifest:
    return LifecycleAblationManifest(
        experiment_id="ssc03-live",
        lifecycle_template_id=TEMPLATE_ID,
        variants=("response_assertion_only",),
        agents=(
            AgentConfig(
                name="gold-replay",
                adapter="tool_loop",
                model="deterministic-replay",
                parameters={"max_turns_per_session": 10},
            ),
        ),
        study_design=_study_design(),
        conditions=(
            LifecycleAblationCondition(
                execution_mode=LifecycleExecutionMode.FRESH_CONTEXT,
                memory_visibility_policy=LifecycleVisibilityPolicy.ARTIFACT_MEMORY,
            ),
        ),
        output_root=str(tmp_path / "live-output"),
        ledger_root=str(tmp_path / "live-ledger"),
        limits=LifecycleAblationLimits(max_trials=1),
    )


def _persistent_manifest(tmp_path: Path, *, experiment_id: str) -> LifecycleAblationManifest:
    return _single_manifest(tmp_path).model_copy(
        update={
            "experiment_id": experiment_id,
            "conditions": (
                LifecycleAblationCondition(
                    execution_mode=LifecycleExecutionMode.PERSISTENT_CONTEXT,
                    memory_visibility_policy=LifecycleVisibilityPolicy.PERSISTENT_CONTEXT,
                ),
            ),
        }
    )


def _recorded_trial(
    tmp_path: Path,
) -> tuple[LifecycleAblationManifest, LifecycleAblationTrial, Path, Path]:
    manifest = LifecycleAblationManifest(
        experiment_id="ssc03-import",
        lifecycle_template_id=TEMPLATE_ID,
        variants=("response_assertion_only",),
        agents=(
            AgentConfig(
                name="agent-a",
                adapter="tool_loop",
                model="model-a",
                parameters={"max_turns_per_session": 20},
            ),
        ),
        study_design=_study_design(),
        conditions=(
            LifecycleAblationCondition(
                execution_mode=LifecycleExecutionMode.FRESH_CONTEXT,
                memory_visibility_policy=LifecycleVisibilityPolicy.ARTIFACT_MEMORY,
            ),
        ),
        repetitions=1,
        output_root=str(tmp_path / "outputs"),
        ledger_root=str(tmp_path / "ledger"),
        limits=LifecycleAblationLimits(max_trials=1),
    )
    trial = build_lifecycle_ablation_plan(manifest).trials[0]
    package = materialize_template_lifecycle(
        get_template(TEMPLATE_ID),
        Path(trial.package_dir),
        variant_id=trial.variant_id,
    )
    run_dir = Path(trial.run_dir)
    run_local_evidence_lifecycle_fresh_context(
        package_dir=package,
        run_dir=run_dir,
        model=trial.agent.model,
        adapter_kind=trial.agent.adapter,
        max_turns=20,
        registry=_GoldFreshRegistry(package, resolved_model=trial.agent.model),
        verifier=verify_template_lifecycle,
        visibility_policy=trial.memory_visibility_policy,
        sweep_context=LifecycleExperimentSweepContext(
            sweep_experiment_id=manifest.experiment_id,
            planned_trial_id=trial.trial_id,
            plan_sha256=build_lifecycle_ablation_plan(manifest).plan_sha256,
            condition_id=f"{trial.execution_mode.value}__{trial.memory_visibility_policy.value}",
            repetition=trial.repetition,
        ),
    )
    return manifest, trial, package, run_dir


def _terminal_persistent_state(
    manifest: LifecycleAblationManifest,
) -> tuple[LifecycleAblationTrial, Path, Path, str]:
    trial = build_lifecycle_ablation_plan(manifest).trials[0]
    package = materialize_template_lifecycle(
        get_template(TEMPLATE_ID),
        Path(trial.package_dir),
        variant_id=trial.variant_id,
    )
    run_dir = Path(trial.run_dir)
    session_id = "session-001"
    session_dir = run_dir / "sessions" / session_id
    session_dir.mkdir(parents=True)
    (session_dir / "trajectory.jsonl").write_text("", encoding="utf-8")
    gold = json.loads((package / "hidden" / "gold-submissions.json").read_text(encoding="utf-8"))
    while True:
        context = prepare_evidence_checkpoint(package, run_dir)
        if context["status"] == "complete":
            break
        checkpoint_id = context["checkpoint_id"]
        open_checkpoint_attempt(
            package,
            run_dir,
            session_id=session_id,
            execution_mode="persistent_context",
        )
        submission = Path(context["submission_path"])
        submission.parent.mkdir(parents=True, exist_ok=True)
        submission.write_text(json.dumps(gold[checkpoint_id]), encoding="utf-8")
        submit_evidence_checkpoint(package, run_dir)
    return trial, package, run_dir, session_id


def _study_design() -> LifecycleAblationStudyDesign:
    return LifecycleAblationStudyDesign(
        interpretation="descriptive_calibration",
        turn_budget_scope="per_session",
        execution_order="deterministic_sequential_plan_order",
        randomized=False,
        counterbalanced=False,
        causal_effects_supported=False,
    )


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


class _GoldFreshRegistry:
    def __init__(self, package: Path, *, resolved_model: str = "deterministic-replay") -> None:
        self.gold = json.loads((package / "hidden" / "gold-submissions.json").read_text(encoding="utf-8"))
        self.resolved_model = resolved_model
        self.build_count = 0

    def build(self, **_kwargs: object) -> object:
        self.build_count += 1
        gold = self.gold
        resolved_model = self.resolved_model

        class _GoldAdapter:
            def execute(self, request: object) -> object:
                output_path = Path(request.output_path)
                checkpoint_id = output_path.stem
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(json.dumps(gold[checkpoint_id]), encoding="utf-8")
                return SimpleNamespace(
                    adapter_name="tool_loop",
                    resolved_model=resolved_model,
                    configuration_record={"model": resolved_model, "source": "in_process_replay"},
                    agent_output=SimpleNamespace(status=SimpleNamespace(value="completed")),
                    transcript=[],
                    raw_output_text=None,
                    provider_error=None,
                    failure_kind=None,
                    usage_input_tokens=10,
                    usage_output_tokens=2,
                    usage_cache_read_tokens=0,
                    usage_cache_write_tokens=0,
                )

        return _GoldAdapter()


class _InvalidSchemaRegistry(_GoldFreshRegistry):
    def __init__(self, package: Path) -> None:
        super().__init__(package)
        self.gold["initial_review"]["review_matrix"] = []


class _MismatchedAdapterRegistry(_GoldFreshRegistry):
    def build(self, **kwargs: object) -> object:
        adapter = super().build(**kwargs)
        original_execute = adapter.execute

        def execute(request: object) -> object:
            result = original_execute(request)
            result.adapter_name = "pydantic_ai"
            return result

        adapter.execute = execute
        return adapter


class _FailedRegistry:
    def build(self, **_kwargs: object) -> object:
        class _FailedAdapter:
            def execute(self, _request: object) -> object:
                return SimpleNamespace(
                    adapter_name="tool_loop",
                    resolved_model="deterministic-replay",
                    configuration_record={"model": "deterministic-replay", "source": "in_process_replay"},
                    agent_output=SimpleNamespace(status=SimpleNamespace(value="failed")),
                    transcript=[],
                    raw_output_text=None,
                    provider_error="provider unavailable",
                    failure_kind=SimpleNamespace(value="provider_error"),
                    usage_input_tokens=3,
                    usage_output_tokens=0,
                    usage_cache_read_tokens=0,
                    usage_cache_write_tokens=0,
                )

        return _FailedAdapter()


class _EmptyRegistry:
    def build(self, **_kwargs: object) -> object:
        class _EmptyAdapter:
            def execute(self, _request: object) -> object:
                return SimpleNamespace(
                    adapter_name="tool_loop",
                    resolved_model="deterministic-replay",
                    configuration_record={"model": "deterministic-replay", "source": "in_process_replay"},
                    agent_output=SimpleNamespace(status=SimpleNamespace(value="empty")),
                    transcript=[],
                    raw_output_text=None,
                    provider_error=None,
                    failure_kind=None,
                    usage_input_tokens=0,
                    usage_output_tokens=0,
                    usage_cache_read_tokens=0,
                    usage_cache_write_tokens=0,
                )

        return _EmptyAdapter()


class _PrematurePersistentRegistry:
    def build(self, **_kwargs: object) -> object:
        class _PrematureAdapter:
            def execute(self, _request: object) -> object:
                return SimpleNamespace(
                    adapter_name="tool_loop",
                    resolved_model="deterministic-replay",
                    configuration_record={"model": "deterministic-replay", "source": "in_process_replay"},
                    agent_output=SimpleNamespace(status=SimpleNamespace(value="completed")),
                    transcript=[],
                    raw_output_text="Stopped before submitting the active checkpoint.",
                    provider_error=None,
                    failure_kind=None,
                    usage_input_tokens=1,
                    usage_output_tokens=1,
                    usage_cache_read_tokens=0,
                    usage_cache_write_tokens=0,
                )

        return _PrematureAdapter()


class _GoldPersistentRegistry:
    def __init__(self, package: Path, run_dir: Path) -> None:
        self.package = package
        self.run_dir = run_dir
        self.gold = json.loads((package / "hidden" / "gold-submissions.json").read_text(encoding="utf-8"))

    def build(self, *, native_tools: list[object], **_kwargs: object) -> object:
        submit_checkpoint = next(tool for tool in native_tools if tool.__name__ == "submit_checkpoint")
        registry = self

        class _GoldPersistentAdapter:
            def execute(self, _request: object) -> object:
                while True:
                    state = read_evidence_lifecycle_state(registry.package, registry.run_dir)
                    checkpoint_id = state["active_checkpoint_id"]
                    if checkpoint_id is None:
                        break
                    submission = registry.run_dir / "workspace" / "submissions" / f"{checkpoint_id}.json"
                    submission.parent.mkdir(parents=True, exist_ok=True)
                    submission.write_text(json.dumps(registry.gold[checkpoint_id]), encoding="utf-8")
                    response = json.loads(submit_checkpoint(checkpoint_id))
                    if response["status"] == "complete":
                        break
                return SimpleNamespace(
                    adapter_name="tool_loop",
                    resolved_model="deterministic-replay",
                    configuration_record={"model": "deterministic-replay", "source": "in_process_replay"},
                    agent_output=SimpleNamespace(status=SimpleNamespace(value="completed")),
                    transcript=[],
                    raw_output_text="Lifecycle complete.",
                    provider_error=None,
                    failure_kind=None,
                    usage_input_tokens=30,
                    usage_output_tokens=6,
                    usage_cache_read_tokens=0,
                    usage_cache_write_tokens=0,
                )

        return _GoldPersistentAdapter()


class _TerminalProviderFailurePersistentRegistry(_GoldPersistentRegistry):
    def build(self, **kwargs: object) -> object:
        adapter = super().build(**kwargs)
        original_execute = adapter.execute

        def execute(request: object) -> object:
            result = original_execute(request)
            result.agent_output = SimpleNamespace(status=SimpleNamespace(value="failed"))
            result.failure_kind = SimpleNamespace(value="provider_error")
            result.provider_error = "provider stream failed after terminal submission"
            return result

        adapter.execute = execute
        return adapter
