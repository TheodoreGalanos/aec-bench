# ABOUTME: Defines the allowlisted adaptive diagnosis rules shared by repair-only and full-cycle runners.
# ABOUTME: Maps verifier/runtime evidence to one typed Hx or px patch without owning orchestration.

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator

from aec_bench.contracts.execution_program import ActionNode, ExecutionProgramRef, FanoutNode, RetryPolicy
from aec_bench.contracts.harness_instance import AgentBindingConfig, prohibited_retry_safe_error_codes
from aec_bench.contracts.harness_kernel import FrozenStrictModel, KernelCapabilityRef
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.evolution.repair_lifecycle import RepairCandidate, RepairPairingSpec
from aec_bench.experimentation.qualification.repair_rule_registry import (
    RepairDiagnosisRuleRegistration,
    RepairDiagnosisRuleRegistry,
    RepairFeasibilityRuleRegistration,
    RepairFeasibilityRuleRegistry,
)
from aec_bench.experimentation.qualification.repair_runtime import (
    CONFLICTING_MUTABLE_FAILURE_ATTRIBUTION_CODE,
    DiagnosisFunction,
    HarnessAgentCapabilityPatch,
    ProgramCoalesceTaskBatchPatch,
    RepairNoPatchProposal,
    RepairPatchProposal,
    RepairRuntimeEvidence,
    conflicting_mutable_failure_attribution,
    diagnose_harness_agent_capability,
    diagnose_harness_turn_limit,
    diagnose_program_attempt_limit,
    diagnose_program_batch_coalescing,
    diagnose_program_declared_stage_graph_materialization,
    diagnose_program_retry,
    validate_program_batch_coalescing_source,
    validate_program_declared_stage_graph_source,
)


class ProgramRetryDiagnosisRule(FrozenStrictModel):
    """Allowlisted verifier-triggered px repair that changes one retry-capable node."""

    kind: Literal["program_retry"] = "program_retry"
    node_id: NonEmptyStr
    retry: RetryPolicy
    retryable_error_codes: tuple[NonEmptyStr, ...] = Field(min_length=1)
    code: NonEmptyStr = "verifier_failure_program_retry"
    message: NonEmptyStr = "Verifier-backed failures require a bounded retry on the selected program node."

    @field_validator("retryable_error_codes")
    @classmethod
    def validate_retryable_error_codes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("program retry rule requires unique retryable error codes")
        if "harbor_workflow_failed" in value:
            raise ValueError("catch-all Harbor failure code is not safe evidence for program retry")
        prohibited = prohibited_retry_safe_error_codes(value)
        if prohibited:
            raise ValueError("program retry rule contains prohibited retry-safe error codes: " + ", ".join(prohibited))
        return value

    @model_validator(mode="after")
    def validate_installed_retry_codes(self) -> Self:
        if self.retry.max_attempts < 2:
            raise ValueError("program retry rule requires at least two attempts")
        if set(self.retry.retry_on) != set(self.retryable_error_codes):
            raise ValueError("program retry policy must install exactly the declared retryable error codes")
        return self


class ProgramMaxTotalAttemptsDiagnosisRule(FrozenStrictModel):
    """Allowlisted px repair that increases only the exhausted program attempt limit."""

    kind: Literal["program_max_total_attempts"] = "program_max_total_attempts"
    max_total_attempts: int = Field(ge=1, le=10_000)
    code: NonEmptyStr = "program_attempt_limit_exhausted"
    message: NonEmptyStr = (
        "Program-owned execution evidence proves that px exhausted its total operation-attempt limit."
    )


class ProgramCoalesceTaskBatchDiagnosisRule(FrozenStrictModel):
    """Allowlisted px repair for one exact serial pair that fits one batch operation."""

    kind: Literal["program_coalesce_task_batch"] = "program_coalesce_task_batch"
    source_node_ids: tuple[NonEmptyStr, NonEmptyStr]
    replacement_node_id: NonEmptyStr
    task_refs: tuple[NonEmptyStr, NonEmptyStr]
    code: NonEmptyStr = "program_task_batch_coalescing_required"
    message: NonEmptyStr = "Program-owned evidence supports one exact serial-to-batch orchestration repair."

    @model_validator(mode="after")
    def validate_coordinates(self) -> Self:
        ProgramCoalesceTaskBatchPatch(
            expected_program_ref=ExecutionProgramRef(program_id="validation", version="validation"),
            source_node_ids=self.source_node_ids,
            replacement_node_id=self.replacement_node_id,
            task_refs=self.task_refs,
        )
        return self


class ProgramMaterializeDeclaredStageGraphDiagnosisRule(FrozenStrictModel):
    """Allowlisted px repair that materializes exact pinned task-review stage graphs."""

    kind: Literal["program_materialize_declared_stage_graph"] = "program_materialize_declared_stage_graph"
    code: NonEmptyStr = "program_declared_stage_graph_unmaterialized"
    message: NonEmptyStr = (
        "A successful monolithic parent underperformed against content-pinned verifier evidence "
        "for a task with an unmaterialized declared stage graph."
    )


class HarnessMaxTurnsDiagnosisRule(FrozenStrictModel):
    """Allowlisted verifier-triggered Hx repair that changes one agent turn limit."""

    kind: Literal["harness_max_turns"] = "harness_max_turns"
    binding_id: NonEmptyStr
    max_turns: int = Field(ge=1, le=1_000)
    code: NonEmptyStr = "verifier_failure_harness_turns"
    message: NonEmptyStr = "Verifier-backed failures require a different bounded agent turn limit."


class HarnessAgentCapabilityDiagnosisRule(FrozenStrictModel):
    """Allowlisted Hx repair for an agent that produced valid output but did not finalize."""

    kind: Literal["harness_agent_capability"] = "harness_agent_capability"
    binding_id: NonEmptyStr
    expected_capability_ref: KernelCapabilityRef
    replacement_capability_ref: KernelCapabilityRef
    code: NonEmptyStr = "harness_completion_capability_required"
    message: NonEmptyStr = (
        "Trusted iteration-cap evidence and a valid nonempty output artifact require a different agent capability."
    )

    @model_validator(mode="after")
    def validate_capability_change(self) -> Self:
        HarnessAgentCapabilityPatch(
            binding_id=self.binding_id,
            expected_capability_ref=self.expected_capability_ref,
            replacement_capability_ref=self.replacement_capability_ref,
        )
        return self


AdaptiveDiagnosisRule = Annotated[
    ProgramRetryDiagnosisRule
    | ProgramMaxTotalAttemptsDiagnosisRule
    | ProgramCoalesceTaskBatchDiagnosisRule
    | ProgramMaterializeDeclaredStageGraphDiagnosisRule
    | HarnessMaxTurnsDiagnosisRule
    | HarnessAgentCapabilityDiagnosisRule,
    Field(discriminator="kind"),
]


class AdaptiveDiagnosisPolicy(FrozenStrictModel):
    """Evaluate an allowlisted rule set against one immutable evidence payload."""

    kind: Literal["evidence_select"] = "evidence_select"
    rules: tuple[AdaptiveDiagnosisRule, ...] = Field(min_length=1)


AdaptiveDiagnosisConfiguration = Annotated[
    ProgramRetryDiagnosisRule
    | ProgramMaxTotalAttemptsDiagnosisRule
    | ProgramCoalesceTaskBatchDiagnosisRule
    | ProgramMaterializeDeclaredStageGraphDiagnosisRule
    | HarnessMaxTurnsDiagnosisRule
    | HarnessAgentCapabilityDiagnosisRule
    | AdaptiveDiagnosisPolicy,
    Field(discriminator="kind"),
]


@dataclass(frozen=True, slots=True)
class _RepairFeasibilityContext:
    """Exact parent candidate and paired budget used by static rule validation."""

    candidate: RepairCandidate
    pairing: RepairPairingSpec


def validate_adaptive_diagnosis_feasibility(
    configuration: AdaptiveDiagnosisConfiguration,
    *,
    candidate: RepairCandidate,
    pairing: RepairPairingSpec,
) -> None:
    """Reject diagnosis patches that cannot fit the exact parent and fixed Hx budget."""

    if candidate.harness_request.spec.budget != pairing.budget:
        raise ValueError("candidate Hx budget must match the exact paired budget")
    rules = configuration.rules if isinstance(configuration, AdaptiveDiagnosisPolicy) else (configuration,)
    context = _RepairFeasibilityContext(candidate=candidate, pairing=pairing)
    for rule in rules:
        _ADAPTIVE_FEASIBILITY_RULE_REGISTRY.validate(context, rule)


def _validate_harness_max_turns_feasibility(
    context: _RepairFeasibilityContext,
    rule: HarnessMaxTurnsDiagnosisRule,
) -> None:
    matches = tuple(
        binding for binding in context.candidate.harness_request.spec.bindings if binding.binding_id == rule.binding_id
    )
    if len(matches) != 1 or not isinstance(
        matches[0].configuration,
        AgentBindingConfig,
    ):
        raise ValueError("harness turn rule must target exactly one agent binding")
    if rule.max_turns <= matches[0].configuration.max_turns:
        raise ValueError("harness turn rule must strictly increase binding max_turns")
    if rule.max_turns > context.pairing.budget.max_agent_turns:
        raise ValueError("harness turn rule exceeds fixed Hx max_agent_turns")


def _validate_harness_agent_capability_feasibility(
    context: _RepairFeasibilityContext,
    rule: HarnessAgentCapabilityDiagnosisRule,
) -> None:
    matches = tuple(
        binding for binding in context.candidate.harness_request.spec.bindings if binding.binding_id == rule.binding_id
    )
    if len(matches) != 1 or not isinstance(
        matches[0].configuration,
        AgentBindingConfig,
    ):
        raise ValueError("harness capability rule must target exactly one agent binding")
    if matches[0].capability_ref != rule.expected_capability_ref:
        raise ValueError(
            "harness capability rule expected capability does not match the target binding",
        )


def _validate_program_attempt_limit_feasibility(
    context: _RepairFeasibilityContext,
    rule: ProgramMaxTotalAttemptsDiagnosisRule,
) -> None:
    current_limit = context.candidate.program_template.limits.max_total_attempts
    if rule.max_total_attempts <= current_limit:
        raise ValueError(
            "program attempt-limit rule must strictly increase program max_total_attempts",
        )
    if rule.max_total_attempts > context.pairing.budget.max_total_attempts:
        raise ValueError(
            "program attempt-limit rule exceeds fixed Hx max_total_attempts",
        )


def _validate_program_batch_coalescing_feasibility(
    context: _RepairFeasibilityContext,
    rule: ProgramCoalesceTaskBatchDiagnosisRule,
) -> None:
    if context.pairing.task_ids != rule.task_refs:
        raise ValueError(
            "program batch-coalescing rule task refs must equal the exact paired task order",
        )
    validate_program_batch_coalescing_source(
        context.candidate.program_template,
        source_node_ids=rule.source_node_ids,
        replacement_node_id=rule.replacement_node_id,
        task_refs=rule.task_refs,
    )
    agent_configurations = tuple(
        binding.configuration
        for binding in context.candidate.harness_request.spec.bindings
        if isinstance(binding.configuration, AgentBindingConfig)
    )
    if len(agent_configurations) != 1:
        raise ValueError(
            "program batch-coalescing rule requires exactly one agent binding",
        )
    required_turn_capacity = agent_configurations[0].max_turns * len(rule.task_refs)
    if required_turn_capacity > context.pairing.budget.max_agent_turns:
        raise ValueError(
            "program batch-coalescing rule exceeds fixed Hx aggregate agent-turn capacity",
        )


def _validate_program_declared_stage_graph_feasibility(
    context: _RepairFeasibilityContext,
    rule: ProgramMaterializeDeclaredStageGraphDiagnosisRule,
) -> None:
    del rule
    validate_program_declared_stage_graph_source(
        context.candidate.program_template,
        task_refs=context.pairing.task_ids,
    )


def _validate_program_retry_feasibility(
    context: _RepairFeasibilityContext,
    rule: ProgramRetryDiagnosisRule,
) -> None:
    node_matches = tuple(node for node in context.candidate.program_template.nodes if node.node_id == rule.node_id)
    if len(node_matches) != 1 or not isinstance(node_matches[0], ActionNode | FanoutNode):
        raise ValueError("program retry rule must target exactly one retry-capable action or fanout node")
    target = node_matches[0]
    current_attempts = target.retry.max_attempts if target.retry is not None else 1
    if rule.retry.max_attempts <= current_attempts:
        raise ValueError("program retry rule must strictly increase effective node max_attempts")
    if rule.retry.max_attempts > context.candidate.program_template.limits.max_total_attempts:
        raise ValueError("program retry rule max_attempts exceeds program max_total_attempts")
    if rule.retry.max_attempts > context.pairing.budget.max_total_attempts:
        raise ValueError("program retry rule max_attempts exceeds fixed Hx max_total_attempts")


_ADAPTIVE_FEASIBILITY_RULE_REGISTRY = RepairFeasibilityRuleRegistry[_RepairFeasibilityContext](
    (
        RepairFeasibilityRuleRegistration(
            rule_id="harness_agent_capability",
            rule_type=HarnessAgentCapabilityDiagnosisRule,
            validate=_validate_harness_agent_capability_feasibility,
        ),
        RepairFeasibilityRuleRegistration(
            rule_id="harness_max_turns",
            rule_type=HarnessMaxTurnsDiagnosisRule,
            validate=_validate_harness_max_turns_feasibility,
        ),
        RepairFeasibilityRuleRegistration(
            rule_id="program_coalesce_task_batch",
            rule_type=ProgramCoalesceTaskBatchDiagnosisRule,
            validate=_validate_program_batch_coalescing_feasibility,
        ),
        RepairFeasibilityRuleRegistration(
            rule_id="program_materialize_declared_stage_graph",
            rule_type=ProgramMaterializeDeclaredStageGraphDiagnosisRule,
            validate=_validate_program_declared_stage_graph_feasibility,
        ),
        RepairFeasibilityRuleRegistration(
            rule_id="program_max_total_attempts",
            rule_type=ProgramMaxTotalAttemptsDiagnosisRule,
            validate=_validate_program_attempt_limit_feasibility,
        ),
        RepairFeasibilityRuleRegistration(
            rule_id="program_retry",
            rule_type=ProgramRetryDiagnosisRule,
            validate=_validate_program_retry_feasibility,
        ),
    ),
)


def _require_diagnostic_evidence(diagnosis: DiagnosisFunction) -> DiagnosisFunction:
    """Guard every registered diagnosis rule with the common evidence precondition."""

    def diagnose(evidence: RepairRuntimeEvidence) -> RepairPatchProposal | RepairNoPatchProposal:
        if not evidence.diagnostic_codes:
            raise ValueError("adaptive diagnosis requires verifier-backed diagnostic codes")
        return diagnosis(evidence)

    return diagnose


def _bind_program_retry(rule: ProgramRetryDiagnosisRule) -> DiagnosisFunction:
    def diagnose(evidence: RepairRuntimeEvidence) -> RepairPatchProposal | RepairNoPatchProposal:
        return diagnose_program_retry(
            evidence,
            node_id=rule.node_id,
            retry=rule.retry,
            retryable_error_codes=rule.retryable_error_codes,
            code=rule.code,
            message=rule.message,
        )

    return _require_diagnostic_evidence(diagnose)


def _bind_program_attempt_limit(rule: ProgramMaxTotalAttemptsDiagnosisRule) -> DiagnosisFunction:
    def diagnose(evidence: RepairRuntimeEvidence) -> RepairPatchProposal | RepairNoPatchProposal:
        return diagnose_program_attempt_limit(
            evidence,
            max_total_attempts=rule.max_total_attempts,
            code=rule.code,
            message=rule.message,
        )

    return _require_diagnostic_evidence(diagnose)


def _bind_program_batch_coalescing(rule: ProgramCoalesceTaskBatchDiagnosisRule) -> DiagnosisFunction:
    def diagnose(evidence: RepairRuntimeEvidence) -> RepairPatchProposal | RepairNoPatchProposal:
        return diagnose_program_batch_coalescing(
            evidence,
            source_node_ids=rule.source_node_ids,
            replacement_node_id=rule.replacement_node_id,
            task_refs=rule.task_refs,
            code=rule.code,
            message=rule.message,
        )

    return _require_diagnostic_evidence(diagnose)


def _bind_program_declared_stage_graph(
    rule: ProgramMaterializeDeclaredStageGraphDiagnosisRule,
) -> DiagnosisFunction:
    def diagnose(evidence: RepairRuntimeEvidence) -> RepairPatchProposal | RepairNoPatchProposal:
        return diagnose_program_declared_stage_graph_materialization(
            evidence,
            code=rule.code,
            message=rule.message,
        )

    return _require_diagnostic_evidence(diagnose)


def _bind_harness_max_turns(rule: HarnessMaxTurnsDiagnosisRule) -> DiagnosisFunction:
    def diagnose(evidence: RepairRuntimeEvidence) -> RepairPatchProposal | RepairNoPatchProposal:
        return diagnose_harness_turn_limit(
            evidence,
            binding_id=rule.binding_id,
            max_turns=rule.max_turns,
            code=rule.code,
            message=rule.message,
        )

    return _require_diagnostic_evidence(diagnose)


def _bind_harness_agent_capability(rule: HarnessAgentCapabilityDiagnosisRule) -> DiagnosisFunction:
    def diagnose(evidence: RepairRuntimeEvidence) -> RepairPatchProposal | RepairNoPatchProposal:
        return diagnose_harness_agent_capability(
            evidence,
            binding_id=rule.binding_id,
            expected_capability_ref=rule.expected_capability_ref,
            replacement_capability_ref=rule.replacement_capability_ref,
            code=rule.code,
            message=rule.message,
        )

    return _require_diagnostic_evidence(diagnose)


_ADAPTIVE_DIAGNOSIS_RULE_REGISTRY = RepairDiagnosisRuleRegistry[DiagnosisFunction](
    (
        RepairDiagnosisRuleRegistration(
            rule_id="program_retry",
            rule_type=ProgramRetryDiagnosisRule,
            bind=_bind_program_retry,
        ),
        RepairDiagnosisRuleRegistration(
            rule_id="program_max_total_attempts",
            rule_type=ProgramMaxTotalAttemptsDiagnosisRule,
            bind=_bind_program_attempt_limit,
        ),
        RepairDiagnosisRuleRegistration(
            rule_id="program_coalesce_task_batch",
            rule_type=ProgramCoalesceTaskBatchDiagnosisRule,
            bind=_bind_program_batch_coalescing,
        ),
        RepairDiagnosisRuleRegistration(
            rule_id="program_materialize_declared_stage_graph",
            rule_type=ProgramMaterializeDeclaredStageGraphDiagnosisRule,
            bind=_bind_program_declared_stage_graph,
        ),
        RepairDiagnosisRuleRegistration(
            rule_id="harness_max_turns",
            rule_type=HarnessMaxTurnsDiagnosisRule,
            bind=_bind_harness_max_turns,
        ),
        RepairDiagnosisRuleRegistration(
            rule_id="harness_agent_capability",
            rule_type=HarnessAgentCapabilityDiagnosisRule,
            bind=_bind_harness_agent_capability,
        ),
    )
)


def diagnosis_function_for_rule(rule: AdaptiveDiagnosisRule) -> DiagnosisFunction:
    """Bind one declarative allowlisted rule through the exact-type rule registry."""

    return _ADAPTIVE_DIAGNOSIS_RULE_REGISTRY.bind(rule)


def diagnosis_function_for_policy(policy: AdaptiveDiagnosisPolicy) -> DiagnosisFunction:
    """Select one uniquely evidence-supported patch without relying on rule order."""
    diagnosis_functions = tuple(diagnosis_function_for_rule(rule) for rule in policy.rules)

    def diagnose(evidence: RepairRuntimeEvidence) -> RepairPatchProposal | RepairNoPatchProposal:
        outcomes = tuple(diagnosis(evidence) for diagnosis in diagnosis_functions)
        no_patches = tuple(outcome for outcome in outcomes if isinstance(outcome, RepairNoPatchProposal))
        if any(outcome.code == CONFLICTING_MUTABLE_FAILURE_ATTRIBUTION_CODE for outcome in no_patches):
            return conflicting_mutable_failure_attribution(evidence)

        unique_patches: list[RepairPatchProposal] = []
        for outcome in outcomes:
            if isinstance(outcome, RepairPatchProposal) and outcome not in unique_patches:
                unique_patches.append(outcome)
        if len(unique_patches) == 1:
            return unique_patches[0]
        if len(unique_patches) > 1:
            return conflicting_mutable_failure_attribution(evidence)

        return min(
            no_patches,
            key=lambda outcome: (
                outcome.failure_domain.value,
                outcome.code,
                outcome.message,
                outcome.evidence_codes,
            ),
        )

    return diagnose


def diagnosis_function_for_configuration(
    configuration: AdaptiveDiagnosisConfiguration,
) -> DiagnosisFunction:
    """Bind either one legacy rule or one evidence-selecting policy to the runtime seam."""

    if isinstance(configuration, AdaptiveDiagnosisPolicy):
        return diagnosis_function_for_policy(configuration)
    return diagnosis_function_for_rule(configuration)
