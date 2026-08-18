# ABOUTME: Exercises offline generation of the Stage 1 adaptive-repair example specification.
# ABOUTME: Proves CLI overrides bind an isolated real task fixture without contacting a provider.

from __future__ import annotations

import hashlib
import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

from aec_bench.contracts.execution_program import ActionNode, LiteralValue, ProgramArgument, StopNode
from aec_bench.contracts.harness_instance import (
    AgentBindingConfig,
    ComputeBindingConfig,
    ContextBindingConfig,
)
from aec_bench.evolution.repair_lifecycle import RepairOwner
from aec_bench.experimentation.qualification.adaptive_diagnosis import (
    AdaptiveDiagnosisPolicy,
    HarnessAgentCapabilityDiagnosisRule,
    HarnessMaxTurnsDiagnosisRule,
    ProgramCoalesceTaskBatchDiagnosisRule,
    ProgramMaxTotalAttemptsDiagnosisRule,
    diagnosis_function_for_configuration,
    validate_adaptive_diagnosis_feasibility,
)
from aec_bench.experimentation.qualification.repair_run import RepairRunSpec
from aec_bench.experimentation.qualification.repair_runtime import (
    HarnessAgentCapabilityPatch,
    ProgramCoalesceTaskBatchPatch,
    ProgramMaxTotalAttemptsPatch,
    RepairEvidenceUsePolicy,
    RepairPatchProposal,
    RepairRuntime,
)
from aec_bench.harness.budget import HarnessBudgetLedger
from aec_bench.harness.harbor_lowering import lower_run_bundle
from aec_bench.harness.harbor_workflow import SynchronousHarborWorkflow
from aec_bench.harness.kernel_catalogue import default_kernel_registry
from tests.support.adaptive_harness import write_adaptive_task

HARNESS_GENERATOR_DOMAIN = b"aecbench.adaptive-repair.harness-generator.v1\0"
PROGRAM_GENERATOR_DOMAIN = b"aecbench.adaptive-repair.program-generator.v1\0"

OUTPUT_COMPLETION_CONTRACT = {
    "schema_version": "aecbench.output-completion-contract.v1",
    "output_path": "/workspace/output.md",
    "format": "markdown_final_fenced_json",
    "required_top_level_keys": ["answer", "evidence"],
    "require_single_final_json_block": True,
}


def test_regenerate_adaptive_repair_example_prepares_exact_offline_spec_with_overrides(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "scripts" / "regenerate_adaptive_repair_example.py"
    tasks_root = tmp_path / "tasks"
    task_id = "civil/review/offline-repair-fixture"
    task_dir = write_adaptive_task(tasks_root, task_id=task_id)
    task_bytes = (task_dir / "instruction.md").read_bytes()
    output = tmp_path / "generated" / "repair-run-spec.json"

    subprocess.run(
        [
            sys.executable,
            str(script),
            "--task-id",
            task_id,
            "--model",
            "offline-test-model",
            "--backend",
            "docker",
            "--tasks-root",
            str(tasks_root),
            "--output",
            str(output),
        ],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )

    spec = RepairRunSpec.model_validate_json(output.read_text(encoding="utf-8"))
    script_bytes = script.read_bytes()
    assert spec.harness_generator_sha256 == hashlib.sha256(HARNESS_GENERATOR_DOMAIN + script_bytes).hexdigest()
    assert spec.program_generator_sha256 == hashlib.sha256(PROGRAM_GENERATOR_DOMAIN + script_bytes).hexdigest()
    assert spec.request.pairing.task_ids == (task_id,)
    assert spec.request.attempt_id == "stage1.drainage.docker.attempt-1"
    assert spec.request.pairing.seeds == (7_301,)
    assert spec.request.pairing.repetitions == 1
    assert spec.request.pairing.split == "repair_gate"
    assert spec.evidence_use_policy == RepairEvidenceUsePolicy.exploratory_matched_repair()
    assert spec.request.pairing.budget.model_dump() == {
        "max_parallelism": 1,
        "max_total_attempts": 4,
        "max_agent_turns": 32,
        "max_tool_calls": 64,
        "max_context_tokens": 1_000_000,
        "max_runtime_seconds": 3_600,
        "max_tokens": 500_000,
        "max_cost_usd": 10.0,
    }
    assert spec.request.acceptance_policy.minimum_mean_reward_delta == 0.05
    assert spec.request.acceptance_policy.require_positive_lower_bound is True
    assert spec.request.acceptance_policy.bootstrap_replicates == 1_000
    assert spec.request.acceptance_policy.bootstrap_seed == 7_301
    assert spec.request.acceptance_policy.require_all_complete_and_valid is True
    assert spec.verifier_policy.minimum_reward == 0.8
    assert spec.verifier_policy.require_valid is True
    assert spec.verifier_policy.require_complete_provenance is True
    assert spec.diagnosis_rule == AdaptiveDiagnosisPolicy(
        rules=(
            HarnessMaxTurnsDiagnosisRule(binding_id="agent", max_turns=32),
            ProgramMaxTotalAttemptsDiagnosisRule(max_total_attempts=2),
        )
    )
    bindings = {binding.binding_id: binding for binding in spec.parent.harness_request.recipe.bindings}
    agent = bindings["agent"]
    compute = bindings["compute"]
    context = bindings["context"]
    assert context.capability_ref.capability_id == "aecbench.context.workspace-system-prompt"
    assert context.configuration == ContextBindingConfig(
        source_ids=("workspace.system_prompt",),
        max_tokens=4_000,
    )
    assert agent.depends_on == ("tasks", "context")
    assert agent.capability_ref.capability_id == "aecbench.adapter.rlm"
    assert agent.configuration == AgentBindingConfig(
        agent_name="stage1-drainage-rlm",
        model="offline-test-model",
        max_turns=8,
        timeout_seconds=2_400,
    )
    assert compute.capability_ref.capability_id == "aecbench.backend.harbor.docker"
    assert compute.configuration == ComputeBindingConfig(max_concurrency=1, timeout_override_seconds=2_700)
    assert spec.parent.program_template.limits.model_dump() == {
        "max_nodes": 4,
        "max_total_attempts": 1,
        "max_parallelism": 1,
        "max_recursion_depth": 0,
        "max_recursive_calls": 0,
    }
    assert isinstance(spec.parent.program_template.nodes[0], ActionNode)
    assert isinstance(spec.parent.program_template.nodes[1], StopNode)
    assert tuple(snapshot.task_id for snapshot in spec.task_snapshots) == (task_id,)
    assert (task_dir / "instruction.md").read_bytes() == task_bytes


def test_regenerate_adaptive_repair_example_prepares_serial_program_recovery_spec(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "scripts" / "regenerate_adaptive_repair_example.py"
    tasks_root = tmp_path / "tasks"
    task_ids = (
        "civil/review/offline-program-repair-alpha",
        "civil/review/offline-program-repair-beta",
    )
    task_bytes = {
        task_id: (
            write_adaptive_task(
                tasks_root,
                task_id=task_id,
                output_completion_contract=OUTPUT_COMPLETION_CONTRACT,
            )
            / "instruction.md"
        ).read_bytes()
        for task_id in task_ids
    }
    output = tmp_path / "generated" / "program-recovery-spec.json"

    subprocess.run(
        [
            sys.executable,
            str(script),
            "--repair-owner",
            "program",
            "--task-id",
            task_ids[0],
            "--secondary-task-id",
            task_ids[1],
            "--model",
            "offline-test-model",
            "--backend",
            "docker",
            "--tasks-root",
            str(tasks_root),
            "--output",
            str(output),
        ],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )

    spec = RepairRunSpec.model_validate_json(output.read_text(encoding="utf-8"))
    assert spec.request.pairing.task_ids == task_ids
    assert spec.request.attempt_id == "stage1.drainage.docker.program-completion.attempt-1"
    assert spec.request.pairing.seeds == (7_301,)
    assert spec.request.pairing.repetitions == 1
    assert spec.evidence_use_policy == RepairEvidenceUsePolicy.exploratory_matched_repair()
    assert spec.request.pairing.budget.max_total_attempts == 2
    assert spec.request.pairing.budget.max_agent_turns == 64
    assert spec.verifier_policy.minimum_reward == 0.0
    assert spec.verifier_policy.require_valid is True
    assert spec.verifier_policy.require_complete_provenance is True
    assert spec.diagnosis_rule == ProgramMaxTotalAttemptsDiagnosisRule(max_total_attempts=2)

    bindings = {binding.binding_id: binding for binding in spec.parent.harness_request.recipe.bindings}
    assert bindings["context"].configuration == ContextBindingConfig(
        source_ids=("workspace.system_prompt",),
        max_tokens=4_000,
    )
    assert bindings["agent"].depends_on == ("tasks", "context")
    assert bindings["agent"].capability_ref.capability_id == "aecbench.adapter.rlm-output-contract"
    assert bindings["agent"].configuration == AgentBindingConfig(
        agent_name="stage1-drainage-rlm",
        model="offline-test-model",
        max_turns=32,
        timeout_seconds=2_400,
    )
    assert bindings["compute"].configuration == ComputeBindingConfig(
        max_concurrency=1,
        timeout_override_seconds=2_700,
    )
    assert spec.parent.program_template.limits.max_total_attempts == 1

    first, second, stop = spec.parent.program_template.nodes
    assert first == ActionNode(
        node_id="run-primary",
        operation_id="run_batch.v1",
        arguments=(ProgramArgument(name="task_ref", value=LiteralValue(value=task_ids[0])),),
    )
    assert second == ActionNode(
        node_id="run-secondary",
        depends_on=("run-primary",),
        operation_id="run_batch.v1",
        arguments=(ProgramArgument(name="task_ref", value=LiteralValue(value=task_ids[1])),),
    )
    assert isinstance(stop, StopNode)
    assert stop.depends_on == ("run-secondary",)
    assert tuple(snapshot.task_id for snapshot in spec.task_snapshots) == task_ids
    for task_id in task_ids:
        assert (tasks_root / task_id / "instruction.md").read_bytes() == task_bytes[task_id]


def test_completion_policy_repair_keeps_turn_capacity_fixed_and_changes_only_agent_capability(
    tmp_path: Path,
) -> None:
    generator = importlib.import_module("scripts.regenerate_adaptive_repair_example")
    tasks_root = tmp_path / "tasks"
    task_id = "civil/review/offline-completion-policy"
    write_adaptive_task(
        tasks_root,
        task_id=task_id,
        output_completion_contract=OUTPUT_COMPLETION_CONTRACT,
    )

    spec = generator.prepare_example_spec(
        task_id=task_id,
        repair_owner="harness",
        harness_repair="completion-policy",
        model="offline-test-model",
        backend="docker",
        tasks_root=tasks_root,
    )
    registry = default_kernel_registry()
    ordinary_ref = registry.capability("aecbench.adapter.rlm-uncached").ref
    completion_ref = registry.capability("aecbench.adapter.rlm-output-contract").ref

    assert spec.request.pairing.budget.max_agent_turns == 32
    assert spec.request.acceptance_policy.minimum_mean_reward_delta == -0.05
    assert spec.request.acceptance_policy.require_positive_lower_bound is False
    assert spec.request.acceptance_policy.maximum_cost_ratio == 0.95
    assert spec.diagnosis_rule == HarnessAgentCapabilityDiagnosisRule(
        binding_id="agent",
        expected_capability_ref=ordinary_ref,
        replacement_capability_ref=completion_ref,
    )
    parent_agent = next(
        binding for binding in spec.parent.harness_request.recipe.bindings if binding.binding_id == "agent"
    )
    assert parent_agent.capability_ref == ordinary_ref
    assert parent_agent.configuration == AgentBindingConfig(
        agent_name="stage1-drainage-rlm",
        model="offline-test-model",
        max_turns=32,
        timeout_seconds=2_400,
    )

    runtime = RepairRuntime(
        request=spec.request,
        parent=spec.parent,
        registry=registry,
        workflow=SynchronousHarborWorkflow(
            project_root=Path(__file__).resolve().parents[3],
            repo_root=Path(__file__).resolve().parents[3],
            tasks_root=tasks_root,
            ledger_root=tmp_path / "ledger",
            jobs_root=tmp_path / "jobs",
        ),
        artifacts_root=tmp_path / "artifacts",
        policy_id=spec.policy_id,
        harness_generator_sha256=spec.harness_generator_sha256,
        program_generator_sha256=spec.program_generator_sha256,
        verifier_policy=spec.verifier_policy,
        evidence_use_policy=spec.evidence_use_policy,
        diagnosis=diagnosis_function_for_configuration(spec.diagnosis_rule),
        preregistered_task_snapshots=spec.task_snapshots,
    )
    parent = runtime.dependencies.compiler(spec.parent, spec.request.pairing)
    child_candidate = runtime.apply_patch(
        RepairPatchProposal(
            owner=RepairOwner.HARNESS,
            code="harness_completion_capability_required",
            message="The output is structurally complete but explicit finalization was not reached.",
            patch=HarnessAgentCapabilityPatch(
                binding_id="agent",
                expected_capability_ref=ordinary_ref,
                replacement_capability_ref=completion_ref,
            ),
        )
    )
    child = runtime.dependencies.compiler(child_candidate, spec.request.pairing)
    parent_bindings = {binding.binding_id: binding for binding in parent.harness.bindings}
    child_bindings = {binding.binding_id: binding for binding in child.harness.bindings}

    assert parent.program.nodes == child.program.nodes
    assert parent.harness.budget == child.harness.budget
    assert parent_bindings["agent"].configuration == child_bindings["agent"].configuration
    assert parent_bindings["agent"].capability_ref == ordinary_ref
    assert child_bindings["agent"].capability_ref == completion_ref
    assert {binding_id: binding for binding_id, binding in parent_bindings.items() if binding_id != "agent"} == {
        binding_id: binding for binding_id, binding in child_bindings.items() if binding_id != "agent"
    }


def test_program_recovery_can_fix_completion_policy_harness_without_an_hx_fallback(
    tmp_path: Path,
) -> None:
    generator = importlib.import_module("scripts.regenerate_adaptive_repair_example")
    tasks_root = tmp_path / "tasks"
    task_ids = (
        "civil/review/offline-program-completion-alpha",
        "civil/review/offline-program-completion-beta",
    )
    for task_id in task_ids:
        write_adaptive_task(
            tasks_root,
            task_id=task_id,
            output_completion_contract=OUTPUT_COMPLETION_CONTRACT,
        )

    spec = generator.prepare_example_spec(
        task_id=task_ids[0],
        secondary_task_id=task_ids[1],
        repair_owner="program",
        fixed_harness="completion-policy",
        model="offline-test-model",
        backend="docker",
        tasks_root=tasks_root,
    )

    bindings = {binding.binding_id: binding for binding in spec.parent.harness_request.recipe.bindings}
    assert bindings["agent"].capability_ref.capability_id == "aecbench.adapter.rlm-output-contract"
    assert bindings["agent"].configuration.max_turns == 32
    assert spec.request.pairing.budget.max_agent_turns == 64
    assert spec.diagnosis_rule == ProgramMaxTotalAttemptsDiagnosisRule(max_total_attempts=2)


def test_program_batch_coalescing_spec_preserves_one_attempt_and_fixed_aggregate_capacity(
    tmp_path: Path,
) -> None:
    generator = importlib.import_module("scripts.regenerate_adaptive_repair_example")
    tasks_root = tmp_path / "tasks"
    task_ids = (
        "civil/review/offline-batch-alpha",
        "civil/review/offline-batch-beta",
    )
    for task_id in task_ids:
        write_adaptive_task(
            tasks_root,
            task_id=task_id,
            output_completion_contract=OUTPUT_COMPLETION_CONTRACT,
        )

    spec = generator.prepare_example_spec(
        task_id=task_ids[0],
        secondary_task_id=task_ids[1],
        repair_owner="program",
        program_repair="batch-coalescing",
        fixed_harness="completion-policy",
        model="offline-test-model",
        backend="docker",
        tasks_root=tasks_root,
    )

    assert spec.request.pairing.budget.max_total_attempts == 1
    assert spec.request.pairing.budget.max_agent_turns == 64
    assert spec.parent.program_template.limits.max_total_attempts == 1
    assert spec.parent.program_template.limits == spec.parent.program_template.limits.model_copy()
    assert spec.diagnosis_rule == ProgramCoalesceTaskBatchDiagnosisRule(
        source_node_ids=("run-primary", "run-secondary"),
        replacement_node_id="run-coalesced",
        task_refs=task_ids,
    )
    assert spec.request.loop_id == "stage1.drainage.docker.program-batch-coalescing"
    assert spec.request.attempt_id == "stage1.drainage.docker.program-batch-coalescing.attempt-1"


def test_program_batch_coalescing_can_fix_the_output_commit_harness_without_more_capacity(
    tmp_path: Path,
) -> None:
    generator = importlib.import_module("scripts.regenerate_adaptive_repair_example")
    tasks_root = tmp_path / "tasks"
    task_ids = (
        "civil/review/offline-output-commit-alpha",
        "civil/review/offline-output-commit-beta",
    )
    for task_id in task_ids:
        write_adaptive_task(
            tasks_root,
            task_id=task_id,
            output_completion_contract=OUTPUT_COMPLETION_CONTRACT,
        )

    spec = generator.prepare_example_spec(
        task_id=task_ids[0],
        secondary_task_id=task_ids[1],
        repair_owner="program",
        program_repair="batch-coalescing",
        fixed_harness="completion-commit",
        model="offline-test-model",
        backend="docker",
        tasks_root=tasks_root,
    )

    bindings = {binding.binding_id: binding for binding in spec.parent.harness_request.recipe.bindings}
    assert bindings["agent"].capability_ref.capability_id == "aecbench.adapter.rlm-output-commit"
    assert bindings["agent"].configuration == AgentBindingConfig(
        agent_name="stage1-drainage-rlm",
        model="offline-test-model",
        max_turns=32,
        timeout_seconds=2_400,
    )
    assert spec.request.pairing.budget.max_total_attempts == 1
    assert spec.request.pairing.budget.max_agent_turns == 64
    assert spec.parent.program_template.limits.max_total_attempts == 1
    assert spec.diagnosis_rule == ProgramCoalesceTaskBatchDiagnosisRule(
        source_node_ids=("run-primary", "run-secondary"),
        replacement_node_id="run-coalesced",
        task_refs=task_ids,
    )


def test_regenerate_adaptive_repair_example_can_issue_a_new_attempt_identity(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "scripts" / "regenerate_adaptive_repair_example.py"
    tasks_root = tmp_path / "tasks"
    task_id = "civil/review/offline-repair-retry-fixture"
    write_adaptive_task(tasks_root, task_id=task_id)
    outputs = (tmp_path / "attempt-1.json", tmp_path / "attempt-2.json")

    for attempt_number, output in enumerate(outputs, start=1):
        subprocess.run(
            [
                sys.executable,
                str(script),
                "--task-id",
                task_id,
                "--model",
                "offline-test-model",
                "--backend",
                "docker",
                "--tasks-root",
                str(tasks_root),
                "--attempt-number",
                str(attempt_number),
                "--output",
                str(output),
            ],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )

    first = RepairRunSpec.model_validate_json(outputs[0].read_text(encoding="utf-8"))
    second = RepairRunSpec.model_validate_json(outputs[1].read_text(encoding="utf-8"))
    assert first.request.attempt_id == "stage1.drainage.docker.attempt-1"
    assert second.request.attempt_id == "stage1.drainage.docker.attempt-2"
    assert first.content_sha256 != second.content_sha256
    first_payload = first.model_dump(mode="json")
    second_payload = second.model_dump(mode="json")
    first_payload["content_sha256"] = second_payload["content_sha256"]
    first_payload["request"]["attempt_id"] = second_payload["request"]["attempt_id"]
    assert first_payload == second_payload


@pytest.mark.parametrize("use_explicit_output", (False, True))
def test_regenerate_adaptive_repair_example_refuses_to_overwrite_different_existing_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    use_explicit_output: bool,
) -> None:
    generator = importlib.import_module("scripts.regenerate_adaptive_repair_example")
    tasks_root = tmp_path / "tasks"
    task_id = "civil/review/offline-immutable-output-fixture"
    write_adaptive_task(tasks_root, task_id=task_id)
    output = tmp_path / "explicit-repair-spec.json" if use_explicit_output else tmp_path / generator.DEFAULT_OUTPUT
    output.parent.mkdir(parents=True, exist_ok=True)
    historical_bytes = b'{"historical_provider_result": true}\n'
    output.write_bytes(historical_bytes)
    arguments = [
        str(Path(generator.__file__).resolve()),
        "--task-id",
        task_id,
        "--model",
        "offline-test-model",
        "--backend",
        "docker",
        "--tasks-root",
        str(tasks_root),
    ]
    if use_explicit_output:
        arguments.extend(("--output", str(output)))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", arguments)

    with pytest.raises(SystemExit):
        generator.main()

    assert output.read_bytes() == historical_bytes


def test_regenerate_adaptive_repair_example_identical_existing_output_is_a_no_op(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generator = importlib.import_module("scripts.regenerate_adaptive_repair_example")
    tasks_root = tmp_path / "tasks"
    task_id = "civil/review/offline-idempotent-output-fixture"
    write_adaptive_task(tasks_root, task_id=task_id)
    output = tmp_path / "repair-spec.json"
    arguments = [
        str(Path(generator.__file__).resolve()),
        "--task-id",
        task_id,
        "--model",
        "offline-test-model",
        "--backend",
        "docker",
        "--tasks-root",
        str(tasks_root),
        "--output",
        str(output),
    ]
    monkeypatch.setattr(sys, "argv", arguments)
    generator.main()
    generated_bytes = output.read_bytes()
    preserved_timestamp_ns = 1_000_000_000
    output.touch()
    output.chmod(0o644)
    os.utime(
        output,
        ns=(preserved_timestamp_ns, preserved_timestamp_ns),
    )

    generator.main()

    assert output.read_bytes() == generated_bytes
    assert output.stat().st_mtime_ns == preserved_timestamp_ns


def test_regenerate_adaptive_repair_example_requires_explicit_retry_output() -> None:
    generator = importlib.import_module("scripts.regenerate_adaptive_repair_example")

    with pytest.raises(ValueError, match="explicit --output"):
        generator._resolve_output(
            repair_owner="harness",
            attempt_number=2,
            output=None,
        )


def test_default_turn_limit_output_cannot_overwrite_the_historical_provider_spec() -> None:
    generator = importlib.import_module("scripts.regenerate_adaptive_repair_example")

    output = generator._resolve_output(
        repair_owner="harness",
        harness_repair="turn-limit",
        attempt_number=1,
        output=None,
    )

    assert output.name == "adaptive-turn-limit-repair.example.json"


def test_default_completion_output_cannot_overwrite_the_executed_attempt_one_spec() -> None:
    generator = importlib.import_module("scripts.regenerate_adaptive_repair_example")

    output = generator._resolve_output(
        repair_owner="harness",
        harness_repair="completion-policy",
        attempt_number=1,
        output=None,
    )

    assert output.name == "adaptive-completion-repair.candidate.example.json"


def test_program_outputs_separate_completion_fixed_and_explicit_final_specs() -> None:
    generator = importlib.import_module("scripts.regenerate_adaptive_repair_example")

    completion = generator._resolve_output(
        repair_owner="program",
        harness_repair="turn-limit",
        fixed_harness="completion-policy",
        attempt_number=1,
        output=None,
    )
    explicit = generator._resolve_output(
        repair_owner="program",
        harness_repair="turn-limit",
        fixed_harness="explicit-final",
        attempt_number=1,
        output=None,
    )

    assert completion.name == "adaptive-program-recovery.example.json"
    assert explicit.name == "adaptive-program-recovery-explicit-final.example.json"


def test_batch_coalescing_uses_a_distinct_unexecuted_output_path() -> None:
    generator = importlib.import_module("scripts.regenerate_adaptive_repair_example")

    output = generator._resolve_output(
        repair_owner="program",
        program_repair="batch-coalescing",
        fixed_harness="completion-policy",
        attempt_number=1,
        output=None,
    )

    assert output.name == "adaptive-program-batch-coalescing.candidate.example.json"


def test_output_commit_batch_coalescing_cannot_overwrite_the_executed_spec() -> None:
    generator = importlib.import_module("scripts.regenerate_adaptive_repair_example")

    output = generator._resolve_output(
        repair_owner="program",
        program_repair="batch-coalescing",
        fixed_harness="completion-commit",
        attempt_number=1,
        output=None,
    )

    assert output.name != "adaptive-program-batch-coalescing.example.json"
    assert "output-commit" in output.name


def test_current_program_recovery_candidate_compiles_the_exact_parent_and_predicted_child(
    tmp_path: Path,
) -> None:
    repository_root = Path(__file__).resolve().parents[3]
    generator = importlib.import_module("scripts.regenerate_adaptive_repair_example")
    spec = generator.prepare_example_spec(
        repair_owner="program",
        fixed_harness="completion-policy",
        tasks_root=repository_root / "tasks",
    )
    registry = default_kernel_registry()
    runtime = RepairRuntime(
        request=spec.request,
        parent=spec.parent,
        registry=registry,
        workflow=SynchronousHarborWorkflow(
            project_root=repository_root,
            repo_root=repository_root,
            tasks_root=repository_root / "tasks",
            ledger_root=tmp_path / "ledger",
            jobs_root=tmp_path / "jobs",
        ),
        artifacts_root=tmp_path / "artifacts",
        policy_id=spec.policy_id,
        harness_generator_sha256=spec.harness_generator_sha256,
        program_generator_sha256=spec.program_generator_sha256,
        verifier_policy=spec.verifier_policy,
        evidence_use_policy=spec.evidence_use_policy,
        diagnosis=diagnosis_function_for_configuration(spec.diagnosis_rule),
        preregistered_task_snapshots=spec.task_snapshots,
    )

    parent = runtime.dependencies.compiler(spec.parent, spec.request.pairing)
    parent_agent = parent.harness.binding("agent")
    assert parent_agent is not None
    assert parent_agent.capability_ref == registry.capability("aecbench.adapter.rlm-output-contract").ref
    lowered = lower_run_bundle(
        parent.bundle,
        registry=registry,
        tasks_root=repository_root / "tasks",
        program_node_id="run-primary",
        task_refs=(spec.request.pairing.task_ids[0],),
    )
    assert lowered.manifest.agents[0].parameters["prompt_cache"] is False
    budget = HarnessBudgetLedger(parent.harness.budget)
    budget.reserve_invocation_capacity(
        agent_turns=lowered.agent_turn_capacity,
        tool_calls=lowered.tool_call_capacity,
        context_tokens=lowered.context_token_capacity,
    )
    child_candidate = runtime.apply_patch(
        RepairPatchProposal(
            owner=RepairOwner.PROGRAM,
            code="program_attempt_limit_exhausted",
            message="The exact program-wide attempt limit was exhausted.",
            patch=ProgramMaxTotalAttemptsPatch(max_total_attempts=2),
        )
    )
    child = runtime.dependencies.compiler(child_candidate, spec.request.pairing)

    assert parent.harness == child.harness
    assert parent.bundle.kernel_ref == child.bundle.kernel_ref == registry.manifest.ref
    assert parent.bundle.task_snapshots == child.bundle.task_snapshots == spec.task_snapshots
    assert parent.program.ref != child.program.ref
    assert parent.program.limits.max_total_attempts == 1
    assert child.program.limits.max_total_attempts == 2
    child_second = lower_run_bundle(
        child.bundle,
        registry=registry,
        tasks_root=repository_root / "tasks",
        program_node_id="run-secondary",
        task_refs=(spec.request.pairing.task_ids[1],),
    )
    budget.reserve_invocation_capacity(
        agent_turns=child_second.agent_turn_capacity,
        tool_calls=child_second.tool_call_capacity,
        context_tokens=child_second.context_token_capacity,
    )
    assert budget.snapshot().reserved_agent_turns == 64


def test_current_batch_coalescing_fixture_compiles(
    tmp_path: Path,
) -> None:
    repository_root = Path(__file__).resolve().parents[3]
    registry = default_kernel_registry()

    generator = importlib.import_module("scripts.regenerate_adaptive_repair_example")
    spec = generator.prepare_example_spec(
        repair_owner="program",
        fixed_harness="completion-commit",
        program_repair="batch-coalescing",
        backend="morph",
        tasks_root=repository_root / "tasks",
        attempt_number=4,
    )
    assert spec.request.attempt_id.endswith(".attempt-4")
    assert isinstance(spec.diagnosis_rule, ProgramCoalesceTaskBatchDiagnosisRule)
    validate_adaptive_diagnosis_feasibility(
        spec.diagnosis_rule,
        candidate=spec.parent,
        pairing=spec.request.pairing,
    )
    runtime = RepairRuntime(
        request=spec.request,
        parent=spec.parent,
        registry=registry,
        workflow=SynchronousHarborWorkflow(
            project_root=repository_root,
            repo_root=repository_root,
            tasks_root=repository_root / "tasks",
            ledger_root=tmp_path / "ledger",
            jobs_root=tmp_path / "jobs",
        ),
        artifacts_root=tmp_path / "artifacts",
        policy_id=spec.policy_id,
        harness_generator_sha256=spec.harness_generator_sha256,
        program_generator_sha256=spec.program_generator_sha256,
        verifier_policy=spec.verifier_policy,
        evidence_use_policy=spec.evidence_use_policy,
        diagnosis=diagnosis_function_for_configuration(spec.diagnosis_rule),
        preregistered_task_snapshots=spec.task_snapshots,
    )
    parent = runtime.dependencies.compiler(spec.parent, spec.request.pairing)
    parent_agent = parent.harness.binding("agent")
    assert parent_agent is not None
    assert parent_agent.capability_ref == registry.capability("aecbench.adapter.rlm-output-commit").ref
    rule = spec.diagnosis_rule
    child_source = runtime.apply_patch(
        RepairPatchProposal(
            owner=RepairOwner.PROGRAM,
            code=rule.code,
            message=rule.message,
            patch=ProgramCoalesceTaskBatchPatch(
                expected_program_ref=parent.program.ref,
                source_node_ids=rule.source_node_ids,
                replacement_node_id=rule.replacement_node_id,
                task_refs=rule.task_refs,
            ),
        )
    )
    child = runtime.dependencies.compiler(child_source, spec.request.pairing)
    lowered = lower_run_bundle(
        child.bundle,
        registry=registry,
        tasks_root=repository_root / "tasks",
        program_node_id="run-coalesced",
        task_refs=rule.task_refs,
    )

    assert parent.harness == child.harness
    assert parent.program.limits == child.program.limits
    assert child.program.limits.max_total_attempts == 1
    assert lowered.agent_turn_capacity == spec.request.pairing.budget.max_agent_turns == 64
    assert len(lowered.tasks) == 2
    assert lowered.manifest.agents[0].parameters["output_completion_commit"] is True
    assert lowered.manifest.agents[0].parameters["prompt_cache"] is False
