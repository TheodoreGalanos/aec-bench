# ABOUTME: Tests deterministic RunBundle lowering into exact Harbor runtime inputs.
# ABOUTME: Covers content drift, trusted primitive resolution, executable bindings, and lineage injection.

from __future__ import annotations

from pathlib import Path

import pytest
from harbor.models.job.config import JobConfig  # type: ignore[import-untyped]

from aec_bench.meta_harness.harbor_lowering import HarborLoweringError, lower_run_bundle
from aec_bench.meta_harness.kernel_catalogue import default_kernel_registry
from tests.support.adaptive_harness import build_adaptive_bundle, write_adaptive_task

OUTPUT_COMPLETION_CONTRACT = {
    "schema_version": "aecbench.output-completion-contract.v1",
    "output_path": "/workspace/output.md",
    "format": "markdown_final_fenced_json",
    "required_top_level_keys": ["status", "evidence"],
    "require_single_final_json_block": True,
}


def test_lowering_materializes_every_selected_harness_binding_and_exact_task(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_dir = write_adaptive_task(tasks_root)
    bundle = build_adaptive_bundle(tasks_root=tasks_root, repetitions=3)

    lowered = lower_run_bundle(
        bundle,
        registry=default_kernel_registry(),
        tasks_root=tasks_root,
        program_node_id="run",
        attempt=2,
        execution_seed=91,
        motif_ids=("motif.serial-review",),
    )

    assert tuple(task.task_id for task in lowered.tasks) == bundle.harbor.task_refs
    assert lowered.manifest.experiment_id == "adaptive-experiment-run-a2"
    assert lowered.manifest.repetitions == 3
    assert lowered.manifest.compute.backend == "docker"
    assert lowered.manifest.compute.resource_limits == {"n_concurrent_trials": 2}
    assert lowered.manifest.compute.timeout_override == 360
    assert lowered.manifest.disable_verification is False
    assert lowered.ledger_namespace == "adaptive-harness"
    assert lowered.required_artifact_kinds == ("candidate-manifest",)
    assert lowered.agent_turn_capacity == 24
    assert lowered.tool_call_capacity == 48
    assert lowered.context_token_capacity == 12_000

    agent = lowered.manifest.agents[0]
    assert agent.name == "adaptive-tool-loop"
    assert agent.adapter == "tool_loop"
    assert agent.model == "claude-test-model"
    assert agent.parameters["max_turns"] == 8
    assert agent.parameters["timeout_sec"] == 300
    assert agent.parameters["prompt_cache"] is True
    assert agent.parameters["execution_seed"] == 91
    assert agent.parameters["system_prompt"] == (task_dir / "environment/system_prompt.md").read_text()
    assert agent.parameters["tools"][0]["name"] == "bash"
    assert agent.parameters["tool_access_mode"] == "execute"
    assert agent.parameters["max_tool_calls"] == 16
    assert agent.parameters["context_budget_tokens"] == 4_000
    assert agent.parameters["context_utf8_bytes"] == len((task_dir / "environment/system_prompt.md").read_bytes())
    assert agent.parameters["context_accounting"] == "utf8_bytes_upper_bound"
    assert "max_context_tokens" not in agent.parameters
    assert "output_completion_contract" not in agent.parameters
    lineage = agent.parameters["meta_harness_context"]
    assert lineage["kernel_sha256"] == bundle.kernel_ref.content_sha256
    assert lineage["harness_sha256"] == bundle.harness.content_sha256
    assert lineage["program_sha256"] == bundle.program.content_sha256
    assert lineage["bundle_sha256"] == bundle.content_sha256
    assert lineage["program_node_id"] == "run"
    assert lineage["attempt"] == 2
    assert lineage["execution_seed"] == 91
    assert lineage["motif_ids"] == ["motif.serial-review"]
    assert "target_settings" not in lowered.manifest.model_dump(mode="json")

    config = lowered.harbor_job_config(jobs_dir=tmp_path / "jobs")
    parsed = JobConfig.model_validate(config)
    assert parsed.jobs_dir == tmp_path / "jobs"
    assert parsed.agents[0].override_timeout_sec == 360


def test_output_contract_rlm_lowers_only_the_task_owned_completion_contract(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    write_adaptive_task(
        tasks_root,
        output_completion_contract=OUTPUT_COMPLETION_CONTRACT,
    )
    bundle = build_adaptive_bundle(
        tasks_root=tasks_root,
        agent_capability_id="aecbench.adapter.rlm-output-contract",
        include_tool_binding=False,
    )

    lowered = lower_run_bundle(
        bundle,
        registry=default_kernel_registry(),
        tasks_root=tasks_root,
        program_node_id="run",
    )

    agent = lowered.manifest.agents[0]
    assert agent.adapter == "rlm"
    assert agent.parameters["output_completion_contract"] == OUTPUT_COMPLETION_CONTRACT
    assert "output_completion_commit" not in agent.parameters


def test_output_commit_rlm_lowers_the_task_contract_and_commit_surface(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    write_adaptive_task(
        tasks_root,
        output_completion_contract=OUTPUT_COMPLETION_CONTRACT,
    )
    bundle = build_adaptive_bundle(
        tasks_root=tasks_root,
        agent_capability_id="aecbench.adapter.rlm-output-commit",
        include_tool_binding=False,
    )

    lowered = lower_run_bundle(
        bundle,
        registry=default_kernel_registry(),
        tasks_root=tasks_root,
        program_node_id="run",
    )

    agent = lowered.manifest.agents[0]
    assert agent.adapter == "rlm"
    assert agent.parameters["output_completion_contract"] == OUTPUT_COMPLETION_CONTRACT
    assert agent.parameters["output_completion_commit"] is True


@pytest.mark.parametrize(
    "agent_capability_id",
    (
        "aecbench.adapter.rlm-uncached",
        "aecbench.adapter.rlm-output-contract",
        "aecbench.adapter.rlm-output-commit",
    ),
)
def test_explicit_and_output_contract_rlm_capabilities_pin_prompt_cache_off(
    tmp_path: Path,
    agent_capability_id: str,
) -> None:
    tasks_root = tmp_path / "tasks"
    write_adaptive_task(
        tasks_root,
        output_completion_contract=OUTPUT_COMPLETION_CONTRACT,
    )
    bundle = build_adaptive_bundle(
        tasks_root=tasks_root,
        agent_capability_id=agent_capability_id,
        include_tool_binding=False,
    )

    lowered = lower_run_bundle(
        bundle,
        registry=default_kernel_registry(),
        tasks_root=tasks_root,
        program_node_id="run",
    )

    assert lowered.manifest.agents[0].parameters["prompt_cache"] is False


def test_output_contract_rlm_rejects_a_missing_task_completion_contract(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    write_adaptive_task(tasks_root)
    bundle = build_adaptive_bundle(
        tasks_root=tasks_root,
        agent_capability_id="aecbench.adapter.rlm-output-contract",
        include_tool_binding=False,
    )

    with pytest.raises(HarborLoweringError) as captured:
        lower_run_bundle(
            bundle,
            registry=default_kernel_registry(),
            tasks_root=tasks_root,
            program_node_id="run",
        )

    assert captured.value.diagnostic.owner.value == "world"
    assert captured.value.diagnostic.code == "output_completion_contract_missing"


def test_output_contract_rlm_rejects_a_contract_for_another_output_path(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    mismatched = {**OUTPUT_COMPLETION_CONTRACT, "output_path": "/workspace/other.md"}
    write_adaptive_task(tasks_root, output_completion_contract=mismatched)
    bundle = build_adaptive_bundle(
        tasks_root=tasks_root,
        agent_capability_id="aecbench.adapter.rlm-output-contract",
        include_tool_binding=False,
    )

    with pytest.raises(HarborLoweringError) as captured:
        lower_run_bundle(
            bundle,
            registry=default_kernel_registry(),
            tasks_root=tasks_root,
            program_node_id="run",
        )

    assert captured.value.diagnostic.owner.value == "world"
    assert captured.value.diagnostic.code == "output_completion_contract_path_mismatch"


def test_output_contract_rlm_rejects_noncanonical_harbor_output_path(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    alternative_path = "/workspace/other.md"
    task_dir = write_adaptive_task(
        tasks_root,
        output_completion_contract={**OUTPUT_COMPLETION_CONTRACT, "output_path": alternative_path},
    )
    (task_dir / "instruction.md").write_text(
        f"Solve the task and write {alternative_path}.\n",
        encoding="utf-8",
    )
    bundle = build_adaptive_bundle(
        tasks_root=tasks_root,
        agent_capability_id="aecbench.adapter.rlm-output-contract",
        include_tool_binding=False,
    )

    with pytest.raises(HarborLoweringError) as captured:
        lower_run_bundle(
            bundle,
            registry=default_kernel_registry(),
            tasks_root=tasks_root,
            program_node_id="run",
        )

    assert captured.value.diagnostic.owner.value == "runtime"
    assert captured.value.diagnostic.code == "unsupported_output_completion_path"


def test_output_contract_rlm_rejects_reward_bearing_contract_data(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    leaking = {**OUTPUT_COMPLETION_CONTRACT, "verifier_reward": 1.0}
    write_adaptive_task(tasks_root, output_completion_contract=leaking)
    bundle = build_adaptive_bundle(
        tasks_root=tasks_root,
        agent_capability_id="aecbench.adapter.rlm-output-contract",
        include_tool_binding=False,
    )

    with pytest.raises(HarborLoweringError) as captured:
        lower_run_bundle(
            bundle,
            registry=default_kernel_registry(),
            tasks_root=tasks_root,
            program_node_id="run",
        )

    assert captured.value.diagnostic.owner.value == "world"
    assert captured.value.diagnostic.code == "output_completion_contract_invalid"


def test_lowering_serializes_inner_harbor_trials_inside_parallel_px_fanout(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_ids = ("civil/calculation/alpha", "civil/calculation/beta")
    for task_id in task_ids:
        write_adaptive_task(tasks_root, task_id=task_id)
    bundle = build_adaptive_bundle(
        tasks_root=tasks_root,
        task_ids=task_ids,
        program_kind="fanout",
    )

    lowered = lower_run_bundle(
        bundle,
        registry=default_kernel_registry(),
        tasks_root=tasks_root,
        program_node_id="run-each",
        fanout_index=0,
        task_refs=(task_ids[0],),
    )

    assert lowered.manifest.compute.resource_limits == {"n_concurrent_trials": 1}


def test_lowering_rejects_non_uniform_typed_task_tool_surfaces(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_ids = ("civil/calculation/alpha", "civil/calculation/beta")
    first_task_dir = write_adaptive_task(tasks_root, task_id=task_ids[0])
    second_task_dir = write_adaptive_task(tasks_root, task_id=task_ids[1])
    first_task_toml = (first_task_dir / "task.toml").read_text(encoding="utf-8")
    (second_task_dir / "task.toml").write_text(
        first_task_toml.replace(
            "Run task-declared shell commands inside the isolated workspace.",
            "Run a task-specific shell surface with different semantics.",
        ),
        encoding="utf-8",
    )
    bundle = build_adaptive_bundle(tasks_root=tasks_root, task_ids=task_ids)

    with pytest.raises(HarborLoweringError) as captured:
        lower_run_bundle(
            bundle,
            registry=default_kernel_registry(),
            tasks_root=tasks_root,
            program_node_id="run",
        )

    assert captured.value.diagnostic.owner.value == "harness"
    assert captured.value.diagnostic.code == "non_uniform_task_tools"
    assert captured.value.diagnostic.subject_ids == task_ids


def test_lowering_rejects_task_package_drift_after_bundle_compilation(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_dir = write_adaptive_task(tasks_root)
    bundle = build_adaptive_bundle(tasks_root=tasks_root)
    (task_dir / "instruction.md").write_text("Changed after compilation.\n", encoding="utf-8")

    with pytest.raises(HarborLoweringError) as captured:
        lower_run_bundle(
            bundle,
            registry=default_kernel_registry(),
            tasks_root=tasks_root,
            program_node_id="run",
        )

    assert captured.value.diagnostic.owner.value == "world"
    assert captured.value.diagnostic.code == "task_snapshot_mismatch"
