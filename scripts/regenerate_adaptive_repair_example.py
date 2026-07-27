# ABOUTME: Prepares the offline Stage 1 adaptive-repair example against exact task and kernel bytes.
# ABOUTME: Writes a strict RepairRunSpec without generating tasks, dispatching Harbor, or calling a provider.

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Literal

from aec_bench.contracts.execution_program import (
    ActionNode,
    LiteralValue,
    ProgramArgument,
    ProgramLimits,
    ProgramNode,
    StopNode,
    StopOutcome,
)
from aec_bench.contracts.harness_instance import (
    AgentBindingConfig,
    ComputeBindingConfig,
    ContextBindingConfig,
    HarnessBindingSpec,
    HarnessBudget,
    HarnessCompileRequest,
    HarnessRecipe,
    HarnessTopologyRole,
    ResultImportBindingConfig,
    TaskSourceBindingConfig,
    VerificationBindingConfig,
)
from aec_bench.evolution.paired_repair import RepairAcceptancePolicy
from aec_bench.evolution.repair_loop import (
    RepairCandidate,
    RepairLoopRequest,
    RepairPairingSpec,
    RepairProgramTemplate,
)
from aec_bench.meta_harness.adaptive_diagnosis import (
    AdaptiveDiagnosisConfiguration,
    AdaptiveDiagnosisPolicy,
    HarnessAgentCapabilityDiagnosisRule,
    HarnessMaxTurnsDiagnosisRule,
    ProgramCoalesceTaskBatchDiagnosisRule,
    ProgramMaxTotalAttemptsDiagnosisRule,
)
from aec_bench.meta_harness.kernel_catalogue import HarborBackend, default_kernel_registry
from aec_bench.meta_harness.repair_run import RepairRunSpec, prepare_repair_run_spec
from aec_bench.meta_harness.repair_runtime import RepairEvidenceUsePolicy, RepairVerifierPolicy

DEFAULT_TASK_ID = (
    "civil/drainage-review/drainage-model-run-provenance-issue-review-package/"
    "industrial-precinct-catchment-industrial-precinct-catchment-00"
)
DEFAULT_SECONDARY_TASK_ID = (
    "civil/drainage-review/drainage-model-run-provenance-issue-review-package/"
    "brownfield-drainage-upgrade-industrial-precinct-catchment-02"
)
DEFAULT_MODEL = "au.anthropic.claude-sonnet-4-6"
DEFAULT_BACKEND: HarborBackend = "morph"
_RESEARCH_EXAMPLE_ROOT = "research/adaptive-meta-harness/generated-examples"
DEFAULT_OUTPUT = f"{_RESEARCH_EXAMPLE_ROOT}/adaptive-turn-limit-repair.example.json"
DEFAULT_COMPLETION_OUTPUT = f"{_RESEARCH_EXAMPLE_ROOT}/adaptive-completion-repair.candidate.example.json"
DEFAULT_PROGRAM_OUTPUT = f"{_RESEARCH_EXAMPLE_ROOT}/adaptive-program-recovery.example.json"
DEFAULT_EXPLICIT_PROGRAM_OUTPUT = f"{_RESEARCH_EXAMPLE_ROOT}/adaptive-program-recovery-explicit-final.example.json"
DEFAULT_BATCH_PROGRAM_OUTPUT = f"{_RESEARCH_EXAMPLE_ROOT}/adaptive-program-batch-coalescing.candidate.example.json"
DEFAULT_OUTPUT_COMMIT_BATCH_PROGRAM_OUTPUT = (
    f"{_RESEARCH_EXAMPLE_ROOT}/adaptive-program-batch-coalescing-output-commit.candidate.example.json"
)
HARNESS_GENERATOR_DOMAIN = b"aecbench.adaptive-repair.harness-generator.v1\0"
PROGRAM_GENERATOR_DOMAIN = b"aecbench.adaptive-repair.program-generator.v1\0"
SUPPORTED_BACKENDS: tuple[HarborBackend, ...] = ("docker", "modal", "e2b", "daytona", "morph")
RepairOwnerName = Literal["harness", "program"]
HarnessRepairName = Literal["turn-limit", "completion-policy"]
FixedHarnessName = Literal["explicit-final", "completion-policy", "completion-commit"]
ProgramRepairName = Literal["attempt-limit", "batch-coalescing"]


def main() -> None:
    """Prepare and persist one exact offline repair-run specification."""

    parser = _parser()
    arguments = parser.parse_args()
    spec = prepare_example_spec(
        task_id=arguments.task_id,
        secondary_task_id=arguments.secondary_task_id,
        repair_owner=arguments.repair_owner,
        harness_repair=arguments.harness_repair,
        fixed_harness=arguments.fixed_harness,
        program_repair=arguments.program_repair,
        model=arguments.model,
        backend=arguments.backend,
        tasks_root=Path(arguments.tasks_root),
        attempt_number=arguments.attempt_number,
    )
    try:
        output = _resolve_output(
            repair_owner=arguments.repair_owner,
            harness_repair=arguments.harness_repair,
            fixed_harness=arguments.fixed_harness,
            program_repair=arguments.program_repair,
            attempt_number=arguments.attempt_number,
            output=arguments.output,
        )
        _write_output_once(
            output,
            json.dumps(spec.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        )
    except ValueError as error:
        parser.error(str(error))


def prepare_example_spec(
    *,
    task_id: str = DEFAULT_TASK_ID,
    secondary_task_id: str = DEFAULT_SECONDARY_TASK_ID,
    repair_owner: RepairOwnerName = "harness",
    harness_repair: HarnessRepairName = "turn-limit",
    fixed_harness: FixedHarnessName = "completion-policy",
    program_repair: ProgramRepairName = "attempt-limit",
    model: str = DEFAULT_MODEL,
    backend: HarborBackend = DEFAULT_BACKEND,
    tasks_root: Path = Path("tasks"),
    attempt_number: int = 1,
) -> RepairRunSpec:
    """Build the fixed Stage 1 parent and resolve its exact task snapshots without execution."""

    if repair_owner == "program" and task_id == secondary_task_id:
        raise ValueError("program recovery requires two distinct task ids")
    if repair_owner != "program" and program_repair != "attempt-limit":
        raise ValueError("batch-coalescing repair requires --repair-owner program")
    if attempt_number < 1:
        raise ValueError("attempt number must be positive")

    registry = default_kernel_registry()
    capability = registry.capability
    program_task_ids = (task_id, secondary_task_id)
    task_ids: tuple[str, ...] = (task_id,) if repair_owner == "harness" else program_task_ids
    program_recovery = repair_owner == "program"
    program_batch_coalescing = program_recovery and program_repair == "batch-coalescing"
    completion_repair = repair_owner == "harness" and harness_repair == "completion-policy"
    completion_fixed_harness = program_recovery and fixed_harness != "explicit-final"
    output_commit_fixed_harness = program_recovery and fixed_harness == "completion-commit"
    budget = HarnessBudget(
        max_parallelism=1,
        max_total_attempts=1 if program_batch_coalescing else 2 if program_recovery else 4,
        max_agent_turns=64 if program_recovery else 32,
        max_tool_calls=64,
        max_context_tokens=2_000_000 if program_recovery else 1_000_000,
        max_runtime_seconds=5_400 if program_recovery else 3_600,
        max_tokens=1_000_000 if program_recovery else 500_000,
        max_cost_usd=10.0,
    )
    recipe_variant = (
        "program-batch-coalescing"
        if program_batch_coalescing
        else "program-completion-recovery"
        if completion_fixed_harness
        else "program-recovery"
        if program_recovery
        else "completion-repair"
        if completion_repair
        else "repair"
    )
    recipe = HarnessRecipe(
        recipe_id=f"stage1-drainage-{recipe_variant}-{backend}",
        version="1.0.0",
        summary=(
            "Run two exact long-horizon drainage reviews through a fixed RLM harness."
            if program_recovery
            else "Run one exact long-horizon drainage review through a bounded RLM harness."
        ),
        budget=budget,
        bindings=(
            HarnessBindingSpec(
                binding_id="tasks",
                capability_ref=capability("aecbench.tasks.registry").ref,
                topology_role=HarnessTopologyRole.SOURCE,
                configuration=TaskSourceBindingConfig(task_refs=task_ids),
            ),
            HarnessBindingSpec(
                binding_id="context",
                capability_ref=capability("aecbench.context.workspace-system-prompt").ref,
                depends_on=("tasks",),
                topology_role=HarnessTopologyRole.SOURCE,
                configuration=ContextBindingConfig(
                    source_ids=("workspace.system_prompt",),
                    max_tokens=4_000,
                ),
            ),
            HarnessBindingSpec(
                binding_id="agent",
                capability_ref=capability(
                    "aecbench.adapter.rlm-output-commit"
                    if output_commit_fixed_harness
                    else "aecbench.adapter.rlm-output-contract"
                    if completion_fixed_harness
                    else "aecbench.adapter.rlm-uncached"
                    if completion_repair
                    else "aecbench.adapter.rlm"
                ).ref,
                depends_on=("tasks", "context"),
                topology_role=HarnessTopologyRole.ORCHESTRATOR,
                configuration=AgentBindingConfig(
                    agent_name="stage1-drainage-rlm",
                    model=model,
                    max_turns=32 if program_recovery or completion_repair else 8,
                    timeout_seconds=2_400,
                ),
            ),
            HarnessBindingSpec(
                binding_id="compute",
                capability_ref=capability(f"aecbench.backend.harbor.{backend}").ref,
                depends_on=("agent",),
                topology_role=HarnessTopologyRole.SERVICE,
                configuration=ComputeBindingConfig(
                    max_concurrency=1,
                    timeout_override_seconds=2_700,
                ),
            ),
            HarnessBindingSpec(
                binding_id="verify",
                capability_ref=capability("aecbench.verifier.task").ref,
                depends_on=("compute",),
                topology_role=HarnessTopologyRole.GATE,
                configuration=VerificationBindingConfig(enabled=True, required=True),
            ),
            HarnessBindingSpec(
                binding_id="import",
                capability_ref=capability("aecbench.results.trial-record").ref,
                depends_on=("verify",),
                topology_role=HarnessTopologyRole.SINK,
                configuration=ResultImportBindingConfig(
                    ledger_namespace=f"stage1-drainage-{backend}",
                    required_artifacts=("candidate-manifest",),
                ),
            ),
        ),
    )
    program_nodes: tuple[ProgramNode, ...]
    diagnosis_rule: AdaptiveDiagnosisConfiguration
    if program_recovery:
        program_nodes = (
            ActionNode(
                node_id="run-primary",
                operation_id="run_batch.v1",
                arguments=(ProgramArgument(name="task_ref", value=LiteralValue(value=task_ids[0])),),
            ),
            ActionNode(
                node_id="run-secondary",
                depends_on=("run-primary",),
                operation_id="run_batch.v1",
                arguments=(ProgramArgument(name="task_ref", value=LiteralValue(value=task_ids[1])),),
            ),
            StopNode(
                node_id="stop",
                depends_on=("run-secondary",),
                outcome=StopOutcome.SUCCEEDED,
            ),
        )
        program_limits = ProgramLimits(
            max_nodes=4,
            max_parallelism=1,
            max_total_attempts=1,
            max_recursion_depth=0,
            max_recursive_calls=0,
        )
        diagnosis_rule = (
            ProgramCoalesceTaskBatchDiagnosisRule(
                source_node_ids=("run-primary", "run-secondary"),
                replacement_node_id="run-coalesced",
                task_refs=program_task_ids,
            )
            if program_batch_coalescing
            else ProgramMaxTotalAttemptsDiagnosisRule(max_total_attempts=2)
            if completion_fixed_harness
            else AdaptiveDiagnosisPolicy(
                rules=(
                    ProgramMaxTotalAttemptsDiagnosisRule(max_total_attempts=2),
                    HarnessMaxTurnsDiagnosisRule(binding_id="agent", max_turns=64),
                )
            )
        )
    else:
        program_nodes = (
            ActionNode(node_id="run", operation_id="run_batch.v1"),
            StopNode(node_id="stop", depends_on=("run",), outcome=StopOutcome.SUCCEEDED),
        )
        program_limits = ProgramLimits(
            max_nodes=4,
            max_parallelism=1,
            max_total_attempts=1,
            max_recursion_depth=0,
            max_recursive_calls=0,
        )
        diagnosis_rule = (
            HarnessAgentCapabilityDiagnosisRule(
                binding_id="agent",
                expected_capability_ref=capability("aecbench.adapter.rlm-uncached").ref,
                replacement_capability_ref=capability("aecbench.adapter.rlm-output-contract").ref,
            )
            if completion_repair
            else AdaptiveDiagnosisPolicy(
                rules=(
                    HarnessMaxTurnsDiagnosisRule(binding_id="agent", max_turns=32),
                    ProgramMaxTotalAttemptsDiagnosisRule(max_total_attempts=2),
                )
            )
        )

    namespace_variant = (
        "program-batch-coalescing."
        if program_batch_coalescing
        else "program-completion."
        if completion_fixed_harness
        else "program."
        if program_recovery
        else "completion."
        if completion_repair
        else ""
    )
    candidate_namespace = f"stage1.{backend}.{namespace_variant}"
    parent = RepairCandidate(
        candidate_id=f"{candidate_namespace}parent",
        parent_candidate_id=None,
        iteration=0,
        harness_request=HarnessCompileRequest(
            request_id=f"compile.{candidate_namespace}parent",
            kernel_ref=registry.manifest.ref,
            recipe=recipe,
        ),
        program_template=RepairProgramTemplate(
            program_id="stage1.drainage.serial" if program_recovery else "stage1.drainage.monolithic",
            version="1.0.0",
            nodes=program_nodes,
            limits=program_limits,
        ),
    )
    loop_suffix = (
        ".program-batch-coalescing"
        if program_batch_coalescing
        else ".program-completion"
        if completion_fixed_harness
        else ".program"
        if program_recovery
        else ".completion"
        if completion_repair
        else ""
    )
    loop_namespace = f"stage1.drainage.{backend}{loop_suffix}"
    request = RepairLoopRequest(
        loop_id=loop_namespace,
        attempt_id=f"{loop_namespace}.attempt-{attempt_number}",
        iteration=1,
        parent_candidate_id=parent.candidate_id,
        child_candidate_id=f"{candidate_namespace}child",
        pairing=RepairPairingSpec(
            split="repair_gate",
            task_ids=task_ids,
            seeds=(7_301,),
            budget=budget,
            repetitions=1,
        ),
        acceptance_policy=(
            RepairAcceptancePolicy(
                minimum_mean_reward_delta=-0.05,
                require_positive_lower_bound=False,
                bootstrap_replicates=1_000,
                bootstrap_seed=7_301,
                maximum_cost_ratio=0.95,
                require_all_complete_and_valid=True,
            )
            if completion_repair
            else RepairAcceptancePolicy(
                minimum_mean_reward_delta=0.05,
                require_positive_lower_bound=True,
                bootstrap_replicates=1_000,
                bootstrap_seed=7_301,
                require_all_complete_and_valid=True,
            )
        ),
    )
    script_bytes = Path(__file__).resolve().read_bytes()
    return prepare_repair_run_spec(
        request=request,
        parent=parent,
        verifier_policy=RepairVerifierPolicy(
            minimum_reward=0.0 if program_recovery else 0.8,
            require_valid=True,
            require_complete_provenance=True,
        ),
        evidence_use_policy=RepairEvidenceUsePolicy.exploratory_matched_repair(),
        diagnosis_rule=diagnosis_rule,
        policy_id=f"policy.stage1.drainage.{backend}{loop_suffix}.v1",
        harness_generator_sha256=hashlib.sha256(HARNESS_GENERATOR_DOMAIN + script_bytes).hexdigest(),
        program_generator_sha256=hashlib.sha256(PROGRAM_GENERATOR_DOMAIN + script_bytes).hexdigest(),
        tasks_root=tasks_root,
        registry=registry,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Regenerate the offline Stage 1 adaptive-repair example spec.")
    parser.add_argument("--repair-owner", choices=("harness", "program"), default="harness")
    parser.add_argument("--harness-repair", choices=("turn-limit", "completion-policy"), default="turn-limit")
    parser.add_argument(
        "--fixed-harness",
        choices=("explicit-final", "completion-policy", "completion-commit"),
        default="completion-policy",
    )
    parser.add_argument(
        "--program-repair",
        choices=("attempt-limit", "batch-coalescing"),
        default="attempt-limit",
    )
    parser.add_argument("--task-id", default=DEFAULT_TASK_ID)
    parser.add_argument("--secondary-task-id", default=DEFAULT_SECONDARY_TASK_ID)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--backend", choices=SUPPORTED_BACKENDS, default=DEFAULT_BACKEND)
    parser.add_argument("--tasks-root", default="tasks")
    parser.add_argument("--attempt-number", type=_positive_attempt_number, default=1)
    parser.add_argument("--output", default=None)
    return parser


def _positive_attempt_number(value: str) -> int:
    attempt_number = int(value)
    if attempt_number < 1:
        raise argparse.ArgumentTypeError("attempt number must be positive")
    return attempt_number


def _write_output_once(output: Path, content: str) -> None:
    """Atomically create an immutable generated spec or accept identical bytes."""

    payload = content.encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        existing = output.read_bytes()
    except FileNotFoundError:
        pass
    else:
        if existing == payload:
            return
        raise ValueError(f"refusing to overwrite existing output with different content: {output}")

    descriptor, temporary_name = tempfile.mkstemp(
        dir=output.parent,
        prefix=f".{output.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as temporary_file:
            temporary_file.write(payload)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        temporary.chmod(0o644)
        try:
            os.link(temporary, output)
        except FileExistsError:
            if output.read_bytes() == payload:
                return
            raise ValueError(f"refusing to overwrite existing output with different content: {output}") from None
    finally:
        temporary.unlink(missing_ok=True)


def _resolve_output(
    *,
    repair_owner: RepairOwnerName,
    harness_repair: HarnessRepairName = "turn-limit",
    fixed_harness: FixedHarnessName = "completion-policy",
    program_repair: ProgramRepairName = "attempt-limit",
    attempt_number: int,
    output: str | None,
) -> Path:
    if attempt_number != 1 and output is None:
        raise ValueError("an explicit --output is required for a retry attempt")
    default_output = (
        DEFAULT_OUTPUT_COMMIT_BATCH_PROGRAM_OUTPUT
        if repair_owner == "program" and program_repair == "batch-coalescing" and fixed_harness == "completion-commit"
        else DEFAULT_BATCH_PROGRAM_OUTPUT
        if repair_owner == "program" and program_repair == "batch-coalescing"
        else DEFAULT_PROGRAM_OUTPUT
        if repair_owner == "program" and fixed_harness == "completion-policy"
        else DEFAULT_EXPLICIT_PROGRAM_OUTPUT
        if repair_owner == "program"
        else DEFAULT_COMPLETION_OUTPUT
        if harness_repair == "completion-policy"
        else DEFAULT_OUTPUT
    )
    return Path(output or default_output)


if __name__ == "__main__":
    main()
