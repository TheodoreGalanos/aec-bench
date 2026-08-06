# ABOUTME: Interprets trusted repair evidence into typed patch or no-patch proposals.
# ABOUTME: Assigns only evidence-supported failure ownership through allowlisted diagnosis surfaces.

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from aec_bench.adapters.base import AdapterStopReason
from aec_bench.contracts.agent_output import AgentOutputStatus
from aec_bench.contracts.execution_program import RetryPolicy
from aec_bench.contracts.harness_instance import prohibited_retry_safe_error_codes
from aec_bench.contracts.harness_kernel import KernelCapabilityRef
from aec_bench.contracts.output_completion import OutputCompletionReason
from aec_bench.evolution.repair_lifecycle import RepairFailureDomain, RepairOwner
from aec_bench.meta_harness.program_execution import ProgramExecutionStatus
from aec_bench.meta_harness.repair_runtime.contracts import (
    HarnessAgentCapabilityPatch,
    HarnessAgentMaxTurnsPatch,
    ProgramCoalesceTaskBatchPatch,
    ProgramMaterializeDeclaredStageGraphPatch,
    ProgramMaxTotalAttemptsPatch,
    ProgramNodeRetryPatch,
    RepairNoPatchProposal,
    RepairPatchProposal,
    RepairRuntimeEvidence,
)
from aec_bench.meta_harness.repair_runtime.evidence import (
    _is_exact_harness_turn_limit,
)
from aec_bench.meta_harness.repair_runtime.patching import (
    _declared_stage_materialization_fits_limits,
)

DiagnosisFunction = Callable[[RepairRuntimeEvidence], RepairPatchProposal | RepairNoPatchProposal]
CONFLICTING_MUTABLE_FAILURE_ATTRIBUTION_CODE = "conflicting_mutable_failure_attribution"
_ACCEPTANCE_ONLY_DIAGNOSTIC_CODES = frozenset({"cost_evidence_incomplete"})


def diagnose_harness_turn_limit(
    evidence: RepairRuntimeEvidence,
    *,
    binding_id: str,
    max_turns: int,
    code: str = "harness_turn_limit_reached",
    message: str = "Trusted adapter evidence proves that Hx exhausted its bounded turn capacity.",
) -> RepairPatchProposal | RepairNoPatchProposal:
    """Patch Hx only when trusted adapter evidence proves actual turn-cap exhaustion."""
    unowned_domain = _unowned_failure_domain(evidence)
    if unowned_domain is not RepairFailureDomain.UNDETERMINED:
        return _no_applicable_repair(evidence, preferred_domain=unowned_domain)
    claimed_exhaustion = tuple(trial for trial in evidence.trials if trial.agent.failure_kind == "turn_limit_reached")
    if not claimed_exhaustion:
        return _no_applicable_repair(evidence)
    if any(not trial.agent.runtime_execution_attested for trial in claimed_exhaustion):
        return _no_applicable_repair(evidence, preferred_domain=RepairFailureDomain.RUNTIME)
    if any(trial.agent.stop_reason is not AdapterStopReason.ITERATION_CAP for trial in claimed_exhaustion):
        return _no_applicable_repair(evidence, preferred_domain=RepairFailureDomain.RUNTIME)
    if any(
        trial.agent.turns_used is None
        or trial.agent.max_turns is None
        or trial.agent.turns_used != trial.agent.max_turns
        for trial in claimed_exhaustion
    ):
        return _no_applicable_repair(evidence, preferred_domain=RepairFailureDomain.RUNTIME)
    observed_limits = {cast(int, trial.agent.max_turns) for trial in claimed_exhaustion}
    if _has_exact_program_failure_evidence(evidence):
        return conflicting_mutable_failure_attribution(evidence)
    highest_observed = max(observed_limits)
    if max_turns <= highest_observed:
        raise ValueError("harness turn-limit repair must increase the exhausted runtime limit")
    return RepairPatchProposal(
        owner=RepairOwner.HARNESS,
        code=code,
        message=message,
        patch=HarnessAgentMaxTurnsPatch(binding_id=binding_id, max_turns=max_turns),
    )


def diagnose_harness_agent_capability(
    evidence: RepairRuntimeEvidence,
    *,
    binding_id: str,
    expected_capability_ref: KernelCapabilityRef,
    replacement_capability_ref: KernelCapabilityRef,
    code: str = "harness_completion_capability_required",
    message: str = (
        "Trusted iteration-cap evidence and a valid nonempty output artifact identify the agent completion capability."
    ),
) -> RepairPatchProposal | RepairNoPatchProposal:
    """Patch one agent capability only when completion failure has direct artifact evidence."""
    patch = HarnessAgentCapabilityPatch(
        binding_id=binding_id,
        expected_capability_ref=expected_capability_ref,
        replacement_capability_ref=replacement_capability_ref,
    )
    unowned_domain = _unowned_failure_domain(evidence)
    if unowned_domain is not RepairFailureDomain.UNDETERMINED:
        return _no_applicable_repair(evidence, preferred_domain=unowned_domain)
    verifier_blockers = {"invalid_verifier_evidence", "reward_below_verifier_threshold"}
    if any(verifier_blockers.intersection(trial.error_codes) for trial in evidence.trials):
        return _no_applicable_repair(evidence)
    claimed_exhaustion = tuple(trial for trial in evidence.trials if trial.agent.failure_kind == "turn_limit_reached")
    if not claimed_exhaustion:
        return _no_applicable_repair(evidence)
    if any(not _is_exact_harness_turn_limit(trial.agent) for trial in claimed_exhaustion):
        return _no_applicable_repair(evidence, preferred_domain=RepairFailureDomain.RUNTIME)
    if any(
        trial.agent.output_artifact is None
        or not trial.agent.output_artifact.completion_evaluation.complete
        or trial.agent.output_artifact.completion_evaluation.reason is not OutputCompletionReason.COMPLETE
        for trial in claimed_exhaustion
    ):
        return _no_applicable_repair(evidence)
    if _has_exact_program_failure_evidence(evidence):
        return conflicting_mutable_failure_attribution(evidence)
    return RepairPatchProposal(
        owner=RepairOwner.HARNESS,
        code=code,
        message=message,
        patch=patch,
    )


def diagnose_program_retry(
    evidence: RepairRuntimeEvidence,
    *,
    node_id: str,
    retry: RetryPolicy,
    retryable_error_codes: tuple[str, ...],
    code: str = "retryable_program_node_failure",
    message: str = "Program-owned node evidence proves a retryable execution failure.",
) -> RepairPatchProposal | RepairNoPatchProposal:
    """Patch px only for an exact failed node carrying an allowlisted retryable runtime code."""
    if retry.max_attempts < 2:
        raise ValueError("program retry diagnosis requires at least two attempts")
    if not retryable_error_codes or len(retryable_error_codes) != len(set(retryable_error_codes)):
        raise ValueError("program retry diagnosis requires unique retryable error codes")
    if "harbor_workflow_failed" in retryable_error_codes:
        raise ValueError("catch-all Harbor failure code is not safe evidence for program retry")
    prohibited = prohibited_retry_safe_error_codes(retryable_error_codes)
    if prohibited:
        raise ValueError("program retry diagnosis contains prohibited retry-safe error codes: " + ", ".join(prohibited))
    if set(retry.retry_on) != set(retryable_error_codes):
        raise ValueError("program retry diagnosis must install exactly its declared retryable error codes")
    unowned_domain = _unowned_failure_domain(evidence)
    if unowned_domain is not RepairFailureDomain.UNDETERMINED:
        return _no_applicable_repair(evidence, preferred_domain=unowned_domain)
    failures = tuple(failure for execution in evidence.program_executions for failure in execution.failed_nodes)
    matching = tuple(
        failure for failure in failures if failure.node_id == node_id and failure.error_code in retryable_error_codes
    )
    if not matching or len(matching) != len(failures):
        return _no_applicable_repair(evidence)
    if _has_exact_harness_turn_limit_evidence(evidence):
        return conflicting_mutable_failure_attribution(evidence)
    return RepairPatchProposal(
        owner=RepairOwner.PROGRAM,
        code=code,
        message=message,
        patch=ProgramNodeRetryPatch(node_id=node_id, retry=retry),
    )


def diagnose_program_attempt_limit(
    evidence: RepairRuntimeEvidence,
    *,
    max_total_attempts: int,
    code: str = "program_attempt_limit_exhausted",
    message: str = "Program-owned execution evidence proves that px exhausted its total operation-attempt limit.",
) -> RepairPatchProposal | RepairNoPatchProposal:
    """Patch px only when every seed proves the exact program-wide attempt-limit failure."""
    unowned_domain = _unowned_failure_domain(evidence)
    if unowned_domain is not RepairFailureDomain.UNDETERMINED:
        return _no_applicable_repair(evidence, preferred_domain=unowned_domain)
    expected_code = "global_attempt_budget_exhausted"
    failures = tuple(
        execution
        for execution in evidence.program_executions
        if execution.status is ProgramExecutionStatus.FAILED
        and execution.error_code == expected_code
        and execution.failed_nodes
        and all(node.error_code == expected_code for node in execution.failed_nodes)
    )
    if len(failures) != len(evidence.program_executions):
        return _no_applicable_repair(evidence)
    if _has_exact_harness_turn_limit_evidence(evidence):
        return conflicting_mutable_failure_attribution(evidence)
    observed_attempts = max(execution.total_attempts for execution in failures)
    if max_total_attempts <= observed_attempts:
        raise ValueError("program attempt-limit repair must increase the exhausted runtime limit")
    return RepairPatchProposal(
        owner=RepairOwner.PROGRAM,
        code=code,
        message=message,
        patch=ProgramMaxTotalAttemptsPatch(max_total_attempts=max_total_attempts),
    )


def diagnose_program_batch_coalescing(
    evidence: RepairRuntimeEvidence,
    *,
    source_node_ids: tuple[str, str],
    replacement_node_id: str,
    task_refs: tuple[str, str],
    code: str = "program_task_batch_coalescing_required",
    message: str = "Program-owned attempt evidence supports one exact serial-to-batch orchestration repair.",
) -> RepairPatchProposal | RepairNoPatchProposal:
    """Coalesce only an exact one-attempt partial matrix with valid primary-task evidence."""
    patch = ProgramCoalesceTaskBatchPatch(
        expected_program_sha256=evidence.program_sha256,
        source_node_ids=source_node_ids,
        replacement_node_id=replacement_node_id,
        task_refs=task_refs,
    )
    unowned_domain = _unowned_failure_domain(evidence)
    if unowned_domain is not RepairFailureDomain.UNDETERMINED:
        return _no_applicable_repair(evidence, preferred_domain=unowned_domain)
    if evidence.pairing.task_ids != task_refs:
        return _no_applicable_repair(evidence)
    required_diagnostics = {
        "program_execution_failed",
        "program_failure:global_attempt_budget_exhausted",
    }
    allowed_diagnostics = {*required_diagnostics, *_ACCEPTANCE_ONLY_DIAGNOSTIC_CODES}
    if not required_diagnostics.issubset(evidence.diagnostic_codes) or not set(evidence.diagnostic_codes).issubset(
        allowed_diagnostics
    ):
        return _no_applicable_repair(evidence)
    if any(
        execution.status is not ProgramExecutionStatus.FAILED
        or execution.error_code != "global_attempt_budget_exhausted"
        or execution.total_attempts != 1
        or len(execution.failed_nodes) != 1
        or execution.failed_nodes[0].node_id != source_node_ids[1]
        or execution.failed_nodes[0].error_code != "global_attempt_budget_exhausted"
        for execution in evidence.program_executions
    ):
        return _no_applicable_repair(evidence)
    expected_primary_coordinates = {
        (task_refs[0], repetition, seed) for repetition, seed in enumerate(evidence.pairing.seeds, start=1)
    }
    actual_trial_coordinates = {(trial.task_id, trial.repetition, trial.seed) for trial in evidence.trials}
    if actual_trial_coordinates != expected_primary_coordinates:
        return _no_applicable_repair(evidence)
    if any(
        not trial.complete
        or not trial.valid
        or trial.agent.status is not AgentOutputStatus.COMPLETED
        or trial.agent.failure_kind is not None
        or trial.agent.stop_reason is not None
        or not trial.agent.runtime_execution_attested
        or not trial.verifier.output_parseable
        or not trial.verifier.schema_valid
        or not trial.verifier.completed
        or bool(trial.verifier.errors)
        or not set(trial.error_codes).issubset(_ACCEPTANCE_ONLY_DIAGNOSTIC_CODES)
        for trial in evidence.trials
    ):
        return _no_applicable_repair(evidence)
    return RepairPatchProposal(
        owner=RepairOwner.PROGRAM,
        code=code,
        message=message,
        patch=patch,
    )


def diagnose_program_declared_stage_graph_materialization(
    evidence: RepairRuntimeEvidence,
    *,
    code: str = "program_declared_stage_graph_unmaterialized",
    message: str = (
        "A successful monolithic parent underperformed against content-pinned verifier evidence "
        "for a task with an unmaterialized declared stage graph."
    ),
) -> RepairPatchProposal | RepairNoPatchProposal:
    """Materialize staged px only when complete evidence uniquely supports that structural change."""
    unowned_domain = _unowned_failure_domain(evidence)
    if unowned_domain is not RepairFailureDomain.UNDETERMINED:
        return _no_applicable_repair(evidence, preferred_domain=unowned_domain)

    required_diagnostic = "reward_below_verifier_threshold"
    allowed_diagnostics = {required_diagnostic, *_ACCEPTANCE_ONLY_DIAGNOSTIC_CODES}
    if required_diagnostic not in evidence.diagnostic_codes or not set(evidence.diagnostic_codes).issubset(
        allowed_diagnostics
    ):
        return _no_applicable_repair(evidence)
    if (
        evidence.monolithic_run_batch is None
        or evidence.monolithic_run_batch.task_refs != evidence.pairing.task_ids
        or not evidence.declared_stage_graphs
        or evidence.program_limits is None
        or evidence.verifier_minimum_reward is None
    ):
        return _no_applicable_repair(evidence)
    if any(len(item.stage_graph.stages) < 2 or not item.stage_graph.routes for item in evidence.declared_stage_graphs):
        return _no_applicable_repair(evidence)
    if any(
        execution.status is not ProgramExecutionStatus.SUCCEEDED
        or execution.error_code is not None
        or execution.failed_nodes
        for execution in evidence.program_executions
    ):
        return _no_applicable_repair(evidence)

    expected_coordinates = {
        (task_id, repetition, seed)
        for repetition, seed in enumerate(evidence.pairing.seeds, start=1)
        for task_id in evidence.pairing.task_ids
    }
    actual_coordinates = {(trial.task_id, trial.repetition, trial.seed) for trial in evidence.trials}
    if actual_coordinates != expected_coordinates or len(evidence.trials) != len(expected_coordinates):
        return _no_applicable_repair(evidence)
    if any(
        not trial.complete
        or not trial.valid
        or trial.reward >= evidence.verifier_minimum_reward
        or trial.agent.status is not AgentOutputStatus.COMPLETED
        or trial.agent.failure_kind is not None
        or trial.agent.stop_reason is not None
        or trial.agent.provider_error is not None
        or not trial.agent.runtime_execution_attested
        or not trial.verifier.output_parseable
        or not trial.verifier.schema_valid
        or not trial.verifier.completed
        or bool(trial.verifier.errors)
        or trial.verifier.breakdown is None
        or trial.verifier.breakdown_sha256 is None
        or required_diagnostic not in trial.error_codes
        or not set(trial.error_codes).issubset(allowed_diagnostics)
        for trial in evidence.trials
    ):
        return _no_applicable_repair(evidence)
    if not _declared_stage_materialization_fits_limits(
        evidence.declared_stage_graphs,
        evidence.program_limits,
    ):
        return _no_applicable_repair(evidence)
    if _has_exact_harness_turn_limit_evidence(evidence):
        return conflicting_mutable_failure_attribution(evidence)
    return RepairPatchProposal(
        owner=RepairOwner.PROGRAM,
        code=code,
        message=message,
        patch=ProgramMaterializeDeclaredStageGraphPatch(
            expected_program_sha256=evidence.program_sha256,
            task_graphs=evidence.declared_stage_graphs,
        ),
    )


def conflicting_mutable_failure_attribution(
    evidence: RepairRuntimeEvidence,
) -> RepairNoPatchProposal:
    """Abstain when trusted evidence simultaneously supports mutable Hx and px ownership."""
    if not evidence.diagnostic_codes:
        raise ValueError("conflicting mutable attribution requires verified failure evidence")
    return RepairNoPatchProposal(
        failure_domain=RepairFailureDomain.UNDETERMINED,
        code=CONFLICTING_MUTABLE_FAILURE_ATTRIBUTION_CODE,
        message="Verified failure evidence identifies both mutable Hx and px surfaces, so ownership is ambiguous.",
        evidence_codes=evidence.diagnostic_codes,
    )


def _has_exact_harness_turn_limit_evidence(evidence: RepairRuntimeEvidence) -> bool:
    return any(
        trial.agent.failure_kind == "turn_limit_reached"
        and trial.agent.stop_reason is AdapterStopReason.ITERATION_CAP
        and trial.agent.runtime_execution_attested
        and trial.agent.turns_used is not None
        and trial.agent.max_turns is not None
        and trial.agent.turns_used == trial.agent.max_turns
        for trial in evidence.trials
    )


def _has_exact_program_failure_evidence(evidence: RepairRuntimeEvidence) -> bool:
    return any(
        execution.status is ProgramExecutionStatus.FAILED
        and execution.error_code is not None
        and bool(execution.failed_nodes)
        for execution in evidence.program_executions
    )


def _no_applicable_repair(
    evidence: RepairRuntimeEvidence,
    *,
    preferred_domain: RepairFailureDomain | None = None,
) -> RepairNoPatchProposal:
    codes = evidence.diagnostic_codes
    if not codes:
        raise ValueError("no-applicable-repair diagnosis requires verified failure evidence")
    domain = preferred_domain or _unowned_failure_domain(evidence)
    return RepairNoPatchProposal(
        failure_domain=domain,
        code="no_supported_repair_attribution",
        message="Verified failure evidence does not identify one supported mutable repair surface.",
        evidence_codes=codes,
    )


def _unowned_failure_domain(evidence: RepairRuntimeEvidence) -> RepairFailureDomain:
    if "task_world_interface_mismatch" in evidence.diagnostic_codes:
        return RepairFailureDomain.TASK_WORLD
    if any(
        (trial.agent.failure_kind == "turn_limit_reached" or trial.agent.stop_reason is not None)
        and not _is_exact_harness_turn_limit(trial.agent)
        for trial in evidence.trials
    ):
        return RepairFailureDomain.RUNTIME
    runtime_codes = {
        "agent_failure:adapter_exception",
        "agent_failure:billable_input_budget_reached",
        "agent_failure:context_limit_reached",
        "agent_failure:cost_budget_reached",
        "agent_failure:provider_error",
        "agent_failure:subcall_limit_reached",
        "agent_failure:timeout",
        "agent_failure:token_budget_reached",
        "program_failure:harbor_workflow_failed",
        "runtime_attestation_missing",
        "runtime_stop_evidence_incomplete",
    }
    if runtime_codes.intersection(evidence.diagnostic_codes):
        return RepairFailureDomain.RUNTIME
    if "verifier_execution_failed" in evidence.diagnostic_codes:
        return RepairFailureDomain.VERIFIER
    return RepairFailureDomain.UNDETERMINED
