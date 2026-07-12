# ABOUTME: Proves campaign preflight can smoke the real action-driven SSC-03 hydraulic lifecycle.
# ABOUTME: Keeps variant smoke and four-condition plan expansion write-free during dry-run inspection.

from pathlib import Path

from aec_bench.contracts.experiment_manifest import AgentConfig
from aec_bench.meta_harness.evidence_lifecycle import (
    open_checkpoint_attempt,
    prepare_evidence_checkpoint,
    read_evidence_lifecycle_state,
)
from aec_bench.meta_harness.evidence_lifecycle_ablation import inspect_lifecycle_ablation_plan
from aec_bench.meta_harness.evidence_lifecycle_ablation_plan import (
    LifecycleAblationLimits,
    LifecycleAblationManifest,
    LifecycleAblationStudyDesign,
)
from aec_bench.task_world_templates.catalogue import get_template
from aec_bench.task_world_templates.lifecycles import materialize_lifecycle_template
from aec_bench.task_world_templates.lifecycles.ssc03_hydraulic_interaction_smoke import (
    write_ssc03_hydraulic_smoke_submission,
)


def test_hydraulic_smoke_helper_writes_without_submitting(tmp_path: Path) -> None:
    package = materialize_lifecycle_template(
        get_template("hydraulic-interaction-lifecycle-review"),
        tmp_path / "package",
        variant_id="tailwater_revision",
    )
    run_dir = tmp_path / "run"
    prepared = prepare_evidence_checkpoint(package, run_dir)
    session_id = "smoke.session-001"
    open_checkpoint_attempt(
        package,
        run_dir,
        session_id=session_id,
        execution_mode="fresh_context",
    )

    write_ssc03_hydraulic_smoke_submission(
        package,
        run_dir,
        "baseline_analysis",
        session_id,
        Path(prepared["submission_path"]),
    )

    state = read_evidence_lifecycle_state(package, run_dir)
    assert Path(prepared["submission_path"]).is_file()
    assert state["status"] == "awaiting_checkpoint_submission"
    assert state["active_checkpoint_id"] == "baseline_analysis"
    assert state["checkpoint_runs"][0]["status"] == "active"


def test_hydraulic_campaign_dry_run_smokes_actions_without_writing(tmp_path: Path) -> None:
    output_root = tmp_path / "outputs"
    ledger_root = tmp_path / "ledger"
    manifest = LifecycleAblationManifest(
        experiment_id="ssc03-hydraulic-smoke",
        lifecycle_template_id="hydraulic-interaction-lifecycle-review",
        variants=(
            "administrative_no_op",
            "major_idf_revision",
            "outlet_geometry_revision",
            "tailwater_revision",
        ),
        agents=(
            AgentConfig(
                name="smoke-model",
                adapter="tool_loop",
                model="deterministic-smoke-probe",
                parameters={"max_turns_per_session": 1},
            ),
        ),
        study_design=LifecycleAblationStudyDesign(
            interpretation="descriptive_calibration",
            turn_budget_scope="per_session",
            execution_order="deterministic_sequential_plan_order",
            randomized=False,
            counterbalanced=False,
            causal_effects_supported=False,
        ),
        repetitions=1,
        output_root=str(output_root),
        ledger_root=str(ledger_root),
        limits=LifecycleAblationLimits(max_trials=16, max_concurrency=1),
    )

    result = inspect_lifecycle_ablation_plan(manifest)

    assert result["plan"]["trial_count"] == 16
    assert {item["status"] for item in result["trial_statuses"]} == {"pending"}
    assert {item["variant_id"] for item in result["trial_statuses"]} == {
        "administrative_no_op",
        "major_idf_revision",
        "outlet_geometry_revision",
        "tailwater_revision",
    }
    assert {(item["execution_mode"], item["memory_visibility_policy"]) for item in result["trial_statuses"]} == {
        ("fresh_context", "artifact_memory"),
        ("fresh_context", "current_release_only"),
        ("fresh_context", "raw_evidence_only"),
        ("persistent_context", "persistent_context"),
    }
    assert not output_root.exists()
    assert not ledger_root.exists()
