# ABOUTME: Tests declarative adaptive diagnosis rules before they reach the runtime evidence boundary.
# ABOUTME: Keeps catch-all Harbor failures outside the allowlist for program-owned retry patches.

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from aec_bench.adapters.base import AdapterStopReason
from aec_bench.contracts.agent_output import AgentOutputStatus
from aec_bench.contracts.execution_program import (
    ActionNode,
    FanoutNode,
    LiteralValue,
    ProgramArgument,
    ProgramLimits,
    ProgramOutputRef,
    RetryPolicy,
    StopNode,
    StopOutcome,
)
from aec_bench.contracts.harness_instance import (
    AgentBindingConfig,
    ComputeBindingConfig,
    HarnessBindingSpec,
    HarnessBudget,
    HarnessCompileRequest,
    HarnessRecipe,
    HarnessTopologyRole,
)
from aec_bench.contracts.output_completion import OutputCompletionEvaluation, OutputCompletionReason
from aec_bench.contracts.stage_execution import DeclaredStage, DeclaredStageGraph
from aec_bench.evolution.repair_loop import (
    RepairCandidate,
    RepairFailureDomain,
    RepairOwner,
    RepairPairingSpec,
    RepairProgramTemplate,
)
from aec_bench.meta_harness.adaptive_diagnosis import (
    AdaptiveDiagnosisConfiguration,
    AdaptiveDiagnosisPolicy,
    AdaptiveDiagnosisRule,
    HarnessAgentCapabilityDiagnosisRule,
    HarnessMaxTurnsDiagnosisRule,
    ProgramCoalesceTaskBatchDiagnosisRule,
    ProgramMaterializeDeclaredStageGraphDiagnosisRule,
    ProgramMaxTotalAttemptsDiagnosisRule,
    ProgramRetryDiagnosisRule,
    diagnosis_function_for_configuration,
    diagnosis_function_for_policy,
    diagnosis_function_for_rule,
    validate_adaptive_diagnosis_feasibility,
)
from aec_bench.meta_harness.kernel_catalogue import default_kernel_registry
from aec_bench.meta_harness.program_runtime import ProgramExecutionStatus
from aec_bench.meta_harness.repair_runtime import (
    HarnessAgentCapabilityPatch,
    HarnessAgentMaxTurnsPatch,
    ProgramCoalesceTaskBatchPatch,
    ProgramMaterializeDeclaredStageGraphPatch,
    ProgramMaxTotalAttemptsPatch,
    RepairAgentExecutionEvidence,
    RepairDeclaredStageGraphEvidence,
    RepairMonolithicRunBatchEvidence,
    RepairNoPatchProposal,
    RepairOutputArtifactEvidence,
    RepairPatchProposal,
    RepairProgramExecutionEvidence,
    RepairProgramNodeFailureEvidence,
    RepairRuntimeEvidence,
    RepairTrialEvidence,
    RepairVerifierEvidence,
    diagnose_harness_agent_capability,
    diagnose_harness_turn_limit,
    diagnose_program_attempt_limit,
    diagnose_program_batch_coalescing,
    diagnose_program_declared_stage_graph_materialization,
    diagnose_program_retry,
)

_BATCH_TASK_IDS = (
    "civil/calculation/batch-alpha",
    "civil/calculation/batch-beta",
)


def test_program_retry_rule_requires_an_explicit_safe_error_taxonomy() -> None:
    with pytest.raises(ValidationError, match="retryable_error_codes"):
        ProgramRetryDiagnosisRule.model_validate(
            {
                "node_id": "run",
                "retry": RetryPolicy(
                    max_attempts=2,
                    retry_on=("pre_dispatch_capacity_timeout",),
                ),
            }
        )


def test_program_retry_rule_rejects_the_catch_all_harbor_failure_code() -> None:
    with pytest.raises(ValidationError, match="catch-all Harbor failure"):
        ProgramRetryDiagnosisRule(
            node_id="run",
            retry=RetryPolicy(max_attempts=2, retry_on=("harbor_workflow_failed",)),
            retryable_error_codes=("harbor_workflow_failed",),
        )


def test_program_retry_rule_installs_exactly_its_declared_error_codes() -> None:
    with pytest.raises(ValidationError, match="install exactly the declared retryable error codes"):
        ProgramRetryDiagnosisRule(
            node_id="run",
            retry=RetryPolicy(max_attempts=2, retry_on=("provider_throttled",)),
            retryable_error_codes=("pre_dispatch_capacity_timeout",),
        )


def test_program_retry_rule_requires_at_least_two_attempts() -> None:
    with pytest.raises(ValidationError, match="at least two attempts"):
        ProgramRetryDiagnosisRule(
            node_id="run",
            retry=RetryPolicy(
                max_attempts=1,
                retry_on=("pre_dispatch_capacity_timeout",),
            ),
            retryable_error_codes=("pre_dispatch_capacity_timeout",),
        )


@pytest.mark.parametrize(
    "error_code",
    [
        "handler_exception",
        "incomplete_harbor_import",
        "harness_cost_budget_exceeded",
        "global_attempt_budget_exhausted",
    ],
)
def test_program_retry_rule_rejects_effect_unsafe_error_codes(error_code: str) -> None:
    with pytest.raises(ValidationError, match="prohibited retry-safe error codes"):
        ProgramRetryDiagnosisRule(
            node_id="run",
            retry=RetryPolicy(max_attempts=2, retry_on=(error_code,)),
            retryable_error_codes=(error_code,),
        )


def test_declared_stage_graph_rule_emits_one_content_bound_program_patch() -> None:
    evidence = _declared_stage_graph_evidence()

    proposal = diagnosis_function_for_rule(ProgramMaterializeDeclaredStageGraphDiagnosisRule())(evidence)

    assert proposal == RepairPatchProposal(
        owner=RepairOwner.PROGRAM,
        code="program_declared_stage_graph_unmaterialized",
        message=(
            "A successful monolithic parent underperformed against content-pinned verifier evidence "
            "for a task with an unmaterialized declared stage graph."
        ),
        patch=ProgramMaterializeDeclaredStageGraphPatch(
            expected_program_sha256=evidence.program_sha256,
            task_graphs=evidence.declared_stage_graphs,
        ),
    )


@pytest.mark.parametrize(
    "mutation",
    (
        "not_monolithic",
        "incomplete_trial_matrix",
        "invalid_trial",
        "missing_breakdown",
        "reward_not_below_threshold",
        "runtime_confound",
        "insufficient_attempt_budget",
    ),
)
def test_declared_stage_graph_diagnosis_abstains_on_ambiguous_evidence(
    mutation: str,
) -> None:
    payload = _declared_stage_graph_evidence().model_dump(
        mode="python",
        exclude={"content_sha256"},
    )
    if mutation == "not_monolithic":
        payload["monolithic_run_batch"] = None
    elif mutation == "incomplete_trial_matrix":
        payload["trials"] = ()
    elif mutation == "invalid_trial":
        payload["trials"][0]["valid"] = False
    elif mutation == "missing_breakdown":
        payload["trials"][0]["verifier"]["breakdown"] = None
        payload["trials"][0]["verifier"]["breakdown_sha256"] = None
    elif mutation == "reward_not_below_threshold":
        payload["trials"][0]["reward"] = 0.75
    elif mutation == "runtime_confound":
        payload["diagnostic_codes"] = (
            "reward_below_verifier_threshold",
            "runtime_attestation_missing",
        )
    else:
        payload["program_limits"]["max_total_attempts"] = 3
    evidence = RepairRuntimeEvidence.model_validate(payload)

    proposal = diagnose_program_declared_stage_graph_materialization(evidence)

    assert isinstance(proposal, RepairNoPatchProposal)


def test_declared_stage_graph_rule_requires_an_exact_monolithic_source() -> None:
    budget = HarnessBudget(max_total_attempts=8)
    pairing = _pairing(budget=budget)
    rule = ProgramMaterializeDeclaredStageGraphDiagnosisRule()

    validate_adaptive_diagnosis_feasibility(
        rule,
        candidate=_candidate(
            budget=budget,
            limits=ProgramLimits(max_total_attempts=8),
        ),
        pairing=pairing,
    )

    with pytest.raises(ValueError, match="exact monolithic run_batch"):
        validate_adaptive_diagnosis_feasibility(
            rule,
            candidate=_candidate(
                budget=budget,
                nodes=(
                    ActionNode(node_id="first", operation_id="run_batch.v1"),
                    ActionNode(
                        node_id="second",
                        depends_on=("first",),
                        operation_id="run_batch.v1",
                    ),
                    StopNode(
                        node_id="stop",
                        depends_on=("second",),
                        outcome=StopOutcome.SUCCEEDED,
                    ),
                ),
                limits=ProgramLimits(max_total_attempts=8),
            ),
            pairing=pairing,
        )


def test_program_attempt_limit_rule_round_trips_through_the_discriminated_union() -> None:
    adapter = TypeAdapter(AdaptiveDiagnosisRule)

    rule = adapter.validate_python(
        {
            "kind": "program_max_total_attempts",
            "max_total_attempts": 2,
            "code": "px_attempts_exhausted",
            "message": "The exact program attempt limit was exhausted.",
        }
    )

    assert isinstance(rule, ProgramMaxTotalAttemptsDiagnosisRule)
    assert adapter.validate_json(adapter.dump_json(rule)) == rule


def test_multi_rule_policy_round_trips_as_an_adaptive_diagnosis_configuration() -> None:
    adapter = TypeAdapter(AdaptiveDiagnosisConfiguration)

    configuration = adapter.validate_python(
        {
            "kind": "evidence_select",
            "rules": [
                {
                    "kind": "harness_max_turns",
                    "binding_id": "agent",
                    "max_turns": 4,
                },
                {
                    "kind": "program_max_total_attempts",
                    "max_total_attempts": 2,
                },
            ],
        }
    )

    assert isinstance(configuration, AdaptiveDiagnosisPolicy)
    assert adapter.validate_json(adapter.dump_json(configuration)) == configuration
    proposal = diagnosis_function_for_configuration(configuration)(_attempt_limit_evidence())
    assert isinstance(proposal, RepairPatchProposal)
    assert proposal.owner is RepairOwner.PROGRAM


def test_program_attempt_limit_rule_dispatches_to_the_typed_evidence_predicate() -> None:
    rule = ProgramMaxTotalAttemptsDiagnosisRule(max_total_attempts=2)

    proposal = diagnosis_function_for_rule(rule)(_attempt_limit_evidence())

    assert isinstance(proposal, RepairPatchProposal)
    assert proposal.owner is RepairOwner.PROGRAM
    assert proposal.patch == ProgramMaxTotalAttemptsPatch(max_total_attempts=2)
    assert proposal.code == rule.code
    assert proposal.message == rule.message


def test_program_batch_coalescing_rule_round_trips_and_dispatches_an_evidence_bound_patch() -> None:
    rule = _batch_coalescing_rule()
    payload = TypeAdapter(AdaptiveDiagnosisConfiguration).dump_python(rule, mode="json")
    parsed = TypeAdapter(AdaptiveDiagnosisConfiguration).validate_python(payload)

    assert parsed == rule
    proposal = diagnosis_function_for_rule(rule)(_batch_coalescing_evidence())
    assert isinstance(proposal, RepairPatchProposal)
    assert proposal.patch == ProgramCoalesceTaskBatchPatch(
        expected_program_sha256="c" * 64,
        source_node_ids=("run-primary", "run-secondary"),
        replacement_node_id="run-coalesced",
        task_refs=_BATCH_TASK_IDS,
    )


@pytest.mark.parametrize(
    "payload_update",
    (
        {"source_node_ids": ("run-primary", "run-primary")},
        {"replacement_node_id": "run-primary"},
        {"task_refs": (_BATCH_TASK_IDS[0], _BATCH_TASK_IDS[0])},
    ),
)
def test_program_batch_coalescing_rule_rejects_ambiguous_coordinates(
    payload_update: dict[str, object],
) -> None:
    payload = _batch_coalescing_rule().model_dump(mode="python")
    payload.update(payload_update)

    with pytest.raises(ValidationError):
        ProgramCoalesceTaskBatchDiagnosisRule.model_validate(payload)


def test_program_batch_coalescing_diagnosis_requires_exact_partial_matrix_evidence() -> None:
    evidence = _batch_coalescing_evidence()

    proposal = diagnose_program_batch_coalescing(
        evidence,
        source_node_ids=("run-primary", "run-secondary"),
        replacement_node_id="run-coalesced",
        task_refs=_BATCH_TASK_IDS,
    )

    assert isinstance(proposal, RepairPatchProposal)
    assert proposal.patch.expected_program_sha256 == evidence.program_sha256


@pytest.mark.parametrize(
    ("mutation", "value"),
    (
        ("failed_node", "run-primary"),
        ("total_attempts", 2),
        ("primary_valid", False),
        ("include_secondary_trial", True),
    ),
)
def test_program_batch_coalescing_diagnosis_abstains_on_non_causal_evidence(
    mutation: str,
    value: object,
) -> None:
    evidence = _batch_coalescing_evidence(**{mutation: value})

    proposal = diagnose_program_batch_coalescing(
        evidence,
        source_node_ids=("run-primary", "run-secondary"),
        replacement_node_id="run-coalesced",
        task_refs=_BATCH_TASK_IDS,
    )

    assert isinstance(proposal, RepairNoPatchProposal)


def test_harness_turn_limit_diagnosis_abstains_when_exact_program_failure_evidence_co_occurs() -> None:
    proposal = diagnose_harness_turn_limit(
        _attempt_limit_evidence(include_turn_limit=True),
        binding_id="agent",
        max_turns=4,
    )

    _assert_conflicting_mutable_failure(proposal)


def test_program_attempt_limit_diagnosis_abstains_when_harness_turn_limit_evidence_co_occurs() -> None:
    proposal = diagnose_program_attempt_limit(
        _attempt_limit_evidence(include_turn_limit=True),
        max_total_attempts=2,
    )

    _assert_conflicting_mutable_failure(proposal)


def test_program_retry_diagnosis_abstains_when_harness_turn_limit_evidence_co_occurs() -> None:
    failure_code = "pre_dispatch_capacity_timeout"
    proposal = diagnose_program_retry(
        _program_failure_evidence(
            failure_code=failure_code,
            node_id="run",
            include_turn_limit=True,
        ),
        node_id="run",
        retry=RetryPolicy(max_attempts=2, retry_on=(failure_code,)),
        retryable_error_codes=(failure_code,),
    )

    _assert_conflicting_mutable_failure(proposal)


def test_multi_rule_policy_selects_the_only_evidence_supported_patch_independent_of_rule_order() -> None:
    harness_rule = HarnessMaxTurnsDiagnosisRule(binding_id="agent", max_turns=4)
    program_rule = ProgramMaxTotalAttemptsDiagnosisRule(max_total_attempts=2)
    evidence = _attempt_limit_evidence()

    forward = diagnosis_function_for_policy(AdaptiveDiagnosisPolicy(rules=(harness_rule, program_rule)))(evidence)
    reverse = diagnosis_function_for_policy(AdaptiveDiagnosisPolicy(rules=(program_rule, harness_rule)))(evidence)

    assert forward == reverse
    assert isinstance(forward, RepairPatchProposal)
    assert forward.owner is RepairOwner.PROGRAM
    assert forward.patch == ProgramMaxTotalAttemptsPatch(max_total_attempts=2)


def test_multi_rule_policy_selects_harness_patch_from_harness_only_evidence() -> None:
    policy = AdaptiveDiagnosisPolicy(
        rules=(
            ProgramMaxTotalAttemptsDiagnosisRule(max_total_attempts=2),
            HarnessMaxTurnsDiagnosisRule(binding_id="agent", max_turns=4),
        )
    )

    proposal = diagnosis_function_for_policy(policy)(_turn_limit_evidence())

    assert isinstance(proposal, RepairPatchProposal)
    assert proposal.owner is RepairOwner.HARNESS
    assert proposal.patch == HarnessAgentMaxTurnsPatch(binding_id="agent", max_turns=4)


def test_capability_rule_requires_attested_turn_cap_and_valid_nonempty_output() -> None:
    registry = default_kernel_registry()
    expected = registry.capability("aecbench.adapter.rlm-uncached").ref
    replacement = registry.capability("aecbench.adapter.rlm-output-contract").ref
    rule = HarnessAgentCapabilityDiagnosisRule(
        binding_id="agent",
        expected_capability_ref=expected,
        replacement_capability_ref=replacement,
    )

    proposal = diagnosis_function_for_rule(rule)(_completion_capability_evidence())

    assert isinstance(proposal, RepairPatchProposal)
    assert proposal.owner is RepairOwner.HARNESS
    assert proposal.patch == HarnessAgentCapabilityPatch(
        binding_id="agent",
        expected_capability_ref=expected,
        replacement_capability_ref=replacement,
    )


def test_capability_rule_round_trips_through_adaptive_diagnosis_configuration() -> None:
    registry = default_kernel_registry()
    rule = HarnessAgentCapabilityDiagnosisRule(
        binding_id="agent",
        expected_capability_ref=registry.capability("aecbench.adapter.rlm-uncached").ref,
        replacement_capability_ref=registry.capability("aecbench.adapter.rlm-output-contract").ref,
    )

    parsed = TypeAdapter(AdaptiveDiagnosisConfiguration).validate_python(rule.model_dump(mode="json"))

    assert parsed == rule


def test_capability_diagnosis_never_uses_reward_without_output_artifact() -> None:
    registry = default_kernel_registry()
    evidence_payload = _completion_capability_evidence().model_dump(mode="json", exclude={"content_sha256"})
    evidence_payload["trials"][0]["reward"] = 1.0
    evidence_payload["trials"][0]["agent"]["output_artifact"] = None
    evidence = RepairRuntimeEvidence.model_validate(evidence_payload)

    proposal = diagnose_harness_agent_capability(
        evidence,
        binding_id="agent",
        expected_capability_ref=registry.capability("aecbench.adapter.rlm-uncached").ref,
        replacement_capability_ref=registry.capability("aecbench.adapter.rlm-output-contract").ref,
    )

    assert isinstance(proposal, RepairNoPatchProposal)


def test_capability_diagnosis_rejects_structurally_incomplete_output() -> None:
    registry = default_kernel_registry()
    payload = _completion_capability_evidence().model_dump(mode="json", exclude={"content_sha256"})
    payload["trials"][0]["agent"]["output_artifact"]["completion_evaluation"] = {
        "complete": False,
        "reason": "required_top_level_keys_missing",
        "present_top_level_keys": [],
        "missing_top_level_keys": ["answer"],
        "final_json_block_count": 1,
    }
    evidence = RepairRuntimeEvidence.model_validate(payload)

    proposal = diagnose_harness_agent_capability(
        evidence,
        binding_id="agent",
        expected_capability_ref=registry.capability("aecbench.adapter.rlm-uncached").ref,
        replacement_capability_ref=registry.capability("aecbench.adapter.rlm-output-contract").ref,
    )

    assert isinstance(proposal, RepairNoPatchProposal)


@pytest.mark.parametrize(
    "blocking_diagnostic",
    ("invalid_verifier_evidence", "reward_below_verifier_threshold"),
)
def test_capability_diagnosis_abstains_on_unreliable_verifier_evidence(
    blocking_diagnostic: str,
) -> None:
    registry = default_kernel_registry()
    payload = _completion_capability_evidence().model_dump(mode="json", exclude={"content_sha256"})
    payload["trials"][0]["error_codes"] = [
        *payload["trials"][0]["error_codes"],
        blocking_diagnostic,
    ]
    evidence = RepairRuntimeEvidence.model_validate(payload)

    proposal = diagnose_harness_agent_capability(
        evidence,
        binding_id="agent",
        expected_capability_ref=registry.capability("aecbench.adapter.rlm-uncached").ref,
        replacement_capability_ref=registry.capability("aecbench.adapter.rlm-output-contract").ref,
    )

    assert isinstance(proposal, RepairNoPatchProposal)


@pytest.mark.parametrize(
    ("expected_id", "replacement_id"),
    (
        ("aecbench.adapter.direct", "aecbench.adapter.tool-loop"),
        ("aecbench.adapter.rlm", "aecbench.adapter.rlm-output-contract"),
        ("aecbench.adapter.rlm-output-contract", "aecbench.adapter.rlm-uncached"),
    ),
)
def test_capability_rule_rejects_non_allowlisted_transition(
    expected_id: str,
    replacement_id: str,
) -> None:
    registry = default_kernel_registry()

    with pytest.raises(ValidationError, match="rlm-uncached.*rlm-output-contract"):
        HarnessAgentCapabilityDiagnosisRule(
            binding_id="agent",
            expected_capability_ref=registry.capability(expected_id).ref,
            replacement_capability_ref=registry.capability(replacement_id).ref,
        )


def test_multi_rule_policy_abstains_from_mixed_mutable_owner_evidence() -> None:
    policy = AdaptiveDiagnosisPolicy(
        rules=(
            HarnessMaxTurnsDiagnosisRule(binding_id="agent", max_turns=4),
            ProgramMaxTotalAttemptsDiagnosisRule(max_total_attempts=2),
        )
    )

    proposal = diagnosis_function_for_policy(policy)(_attempt_limit_evidence(include_turn_limit=True))

    _assert_conflicting_mutable_failure(proposal)


def test_multi_rule_policy_does_not_select_px_when_turn_stop_evidence_is_incomplete() -> None:
    policy = AdaptiveDiagnosisPolicy(
        rules=(
            HarnessMaxTurnsDiagnosisRule(binding_id="agent", max_turns=4),
            ProgramMaxTotalAttemptsDiagnosisRule(max_total_attempts=2),
        )
    )
    payload = _attempt_limit_evidence(include_turn_limit=True).model_dump(
        mode="json",
        exclude={"content_sha256"},
    )
    payload["trials"][0]["agent"]["stop_reason"] = None
    evidence = RepairRuntimeEvidence.model_validate(payload)

    proposal = diagnosis_function_for_policy(policy)(evidence)

    assert isinstance(proposal, RepairNoPatchProposal)
    assert proposal.failure_domain is RepairFailureDomain.RUNTIME


def test_adaptive_diagnosis_policy_requires_every_rule_to_be_statically_feasible() -> None:
    budget = HarnessBudget(max_agent_turns=4, max_total_attempts=4)
    candidate = _candidate(budget=budget)
    policy = AdaptiveDiagnosisPolicy(
        rules=(
            HarnessMaxTurnsDiagnosisRule(binding_id="agent", max_turns=4),
            ProgramMaxTotalAttemptsDiagnosisRule(max_total_attempts=4),
            ProgramRetryDiagnosisRule(
                node_id="run",
                retry=RetryPolicy(max_attempts=2, retry_on=("pre_dispatch_capacity_timeout",)),
                retryable_error_codes=("pre_dispatch_capacity_timeout",),
            ),
        )
    )

    validate_adaptive_diagnosis_feasibility(
        policy,
        candidate=candidate,
        pairing=_pairing(budget=budget),
    )


def test_adaptive_diagnosis_feasibility_requires_the_candidate_fixed_hx_budget() -> None:
    candidate_budget = HarnessBudget(max_total_attempts=4)

    with pytest.raises(ValueError, match="candidate Hx budget must match the exact paired budget"):
        validate_adaptive_diagnosis_feasibility(
            ProgramMaxTotalAttemptsDiagnosisRule(max_total_attempts=4),
            candidate=_candidate(
                budget=candidate_budget,
                limits=ProgramLimits(max_total_attempts=3),
            ),
            pairing=_pairing(budget=HarnessBudget(max_total_attempts=5)),
        )


@pytest.mark.parametrize("binding_id", ["missing", "compute"])
def test_harness_turn_rule_requires_exactly_one_agent_binding(binding_id: str) -> None:
    budget = HarnessBudget(max_agent_turns=4)

    with pytest.raises(ValueError, match="exactly one agent binding"):
        validate_adaptive_diagnosis_feasibility(
            HarnessMaxTurnsDiagnosisRule(binding_id=binding_id, max_turns=4),
            candidate=_candidate(budget=budget),
            pairing=_pairing(budget=budget),
        )


@pytest.mark.parametrize(
    ("max_turns", "message"),
    [
        (2, "strictly increase"),
        (5, "fixed Hx max_agent_turns"),
    ],
)
def test_harness_turn_rule_must_increase_within_the_fixed_hx_budget(
    max_turns: int,
    message: str,
) -> None:
    budget = HarnessBudget(max_agent_turns=4)

    with pytest.raises(ValueError, match=message):
        validate_adaptive_diagnosis_feasibility(
            HarnessMaxTurnsDiagnosisRule(binding_id="agent", max_turns=max_turns),
            candidate=_candidate(budget=budget),
            pairing=_pairing(budget=budget),
        )


@pytest.mark.parametrize(
    ("max_total_attempts", "message"),
    [
        (3, "strictly increase"),
        (5, "fixed Hx max_total_attempts"),
    ],
)
def test_program_attempt_limit_rule_must_increase_within_the_fixed_hx_budget(
    max_total_attempts: int,
    message: str,
) -> None:
    budget = HarnessBudget(max_total_attempts=4)

    with pytest.raises(ValueError, match=message):
        validate_adaptive_diagnosis_feasibility(
            ProgramMaxTotalAttemptsDiagnosisRule(max_total_attempts=max_total_attempts),
            candidate=_candidate(budget=budget),
            pairing=_pairing(budget=budget),
        )


def test_program_batch_coalescing_rule_accepts_only_the_exact_serial_parent() -> None:
    budget = HarnessBudget(max_agent_turns=4, max_total_attempts=1, max_parallelism=1)
    candidate = _batch_coalescing_candidate(budget=budget)

    validate_adaptive_diagnosis_feasibility(
        _batch_coalescing_rule(),
        candidate=candidate,
        pairing=_batch_coalescing_pairing(budget=budget),
    )


def test_program_batch_coalescing_rule_rejects_insufficient_aggregate_agent_capacity() -> None:
    budget = HarnessBudget(max_agent_turns=3, max_total_attempts=1, max_parallelism=1)

    with pytest.raises(ValueError, match="aggregate agent-turn capacity"):
        validate_adaptive_diagnosis_feasibility(
            _batch_coalescing_rule(),
            candidate=_batch_coalescing_candidate(budget=budget),
            pairing=_batch_coalescing_pairing(budget=budget),
        )


def test_program_batch_coalescing_rule_rejects_serial_graph_drift() -> None:
    budget = HarnessBudget(max_agent_turns=4, max_total_attempts=1, max_parallelism=1)
    candidate = _batch_coalescing_candidate(budget=budget)
    drifted_nodes = tuple(
        node.model_copy(update={"depends_on": ()}) if node.node_id == "run-secondary" else node
        for node in candidate.program_template.nodes
    )
    drifted = candidate.model_copy(
        update={"program_template": candidate.program_template.model_copy(update={"nodes": drifted_nodes})}
    )

    with pytest.raises(ValueError, match="exact serial batch source"):
        validate_adaptive_diagnosis_feasibility(
            _batch_coalescing_rule(),
            candidate=drifted,
            pairing=_batch_coalescing_pairing(budget=budget),
        )


@pytest.mark.parametrize("node_id", ["missing", "stop"])
def test_program_retry_rule_requires_exactly_one_retry_capable_action_or_fanout(
    node_id: str,
) -> None:
    budget = HarnessBudget(max_total_attempts=4)

    with pytest.raises(ValueError, match="exactly one retry-capable action or fanout"):
        validate_adaptive_diagnosis_feasibility(
            _program_retry_rule(node_id=node_id, max_attempts=2),
            candidate=_candidate(budget=budget),
            pairing=_pairing(budget=budget),
        )


def test_program_retry_rule_accepts_an_exact_fanout_target() -> None:
    budget = HarnessBudget(max_total_attempts=4)
    candidate = _candidate(
        budget=budget,
        nodes=(
            ActionNode(node_id="source", operation_id="run_batch.v1"),
            FanoutNode(
                node_id="fanout",
                depends_on=("source",),
                operation_id="run_batch.v1",
                items=ProgramOutputRef(node_id="source"),
                item_argument="task_ref",
            ),
            StopNode(node_id="stop", depends_on=("fanout",), outcome=StopOutcome.SUCCEEDED),
        ),
    )

    validate_adaptive_diagnosis_feasibility(
        _program_retry_rule(node_id="fanout", max_attempts=2),
        candidate=candidate,
        pairing=_pairing(budget=budget),
    )


def test_program_retry_rule_must_strictly_increase_effective_attempts() -> None:
    budget = HarnessBudget(max_total_attempts=4)
    candidate = _candidate(
        budget=budget,
        nodes=(
            ActionNode(
                node_id="run",
                operation_id="run_batch.v1",
                retry=RetryPolicy(max_attempts=2, retry_on=("pre_dispatch_capacity_timeout",)),
            ),
            StopNode(node_id="stop", depends_on=("run",), outcome=StopOutcome.SUCCEEDED),
        ),
    )

    with pytest.raises(ValueError, match="strictly increase effective node max_attempts"):
        validate_adaptive_diagnosis_feasibility(
            _program_retry_rule(node_id="run", max_attempts=2),
            candidate=candidate,
            pairing=_pairing(budget=budget),
        )


@pytest.mark.parametrize(
    ("program_limit", "harness_limit", "message"),
    [
        (2, 4, "program max_total_attempts"),
        (4, 2, "fixed Hx max_total_attempts"),
    ],
)
def test_program_retry_rule_must_fit_both_attempt_ceilings(
    program_limit: int,
    harness_limit: int,
    message: str,
) -> None:
    budget = HarnessBudget(max_total_attempts=harness_limit)

    with pytest.raises(ValueError, match=message):
        validate_adaptive_diagnosis_feasibility(
            _program_retry_rule(node_id="run", max_attempts=3),
            candidate=_candidate(
                budget=budget,
                limits=ProgramLimits(max_total_attempts=program_limit),
            ),
            pairing=_pairing(budget=budget),
        )


def _assert_conflicting_mutable_failure(
    proposal: RepairPatchProposal | RepairNoPatchProposal,
) -> None:
    assert isinstance(proposal, RepairNoPatchProposal)
    assert proposal.failure_domain is RepairFailureDomain.UNDETERMINED
    assert proposal.code == "conflicting_mutable_failure_attribution"


def _attempt_limit_evidence(*, include_turn_limit: bool = False) -> RepairRuntimeEvidence:
    failure_code = "global_attempt_budget_exhausted"
    return _program_failure_evidence(
        failure_code=failure_code,
        node_id="run.second",
        include_turn_limit=include_turn_limit,
    )


def _program_failure_evidence(
    *,
    failure_code: str,
    node_id: str,
    include_turn_limit: bool,
) -> RepairRuntimeEvidence:
    trials = (_turn_limit_trial(),) if include_turn_limit else ()
    diagnostic_codes = ["program_execution_failed", f"program_failure:{failure_code}"]
    if include_turn_limit:
        diagnostic_codes.extend(
            (
                "agent_execution_failed",
                "agent_failure:turn_limit_reached",
                "harness_turn_limit_reached",
            )
        )
    return RepairRuntimeEvidence(
        candidate_id="candidate.parent",
        run_id="run.parent",
        kernel_sha256="a" * 64,
        harness_sha256="b" * 64,
        program_sha256="c" * 64,
        compiled_bundle_sha256="d" * 64,
        run_artifact_sha256="e" * 64,
        pairing=_pairing(),
        program_executions=(
            RepairProgramExecutionEvidence(
                repetition=1,
                seed=17,
                status=ProgramExecutionStatus.FAILED,
                error_code=failure_code,
                error_message="The program consumed its one allowed operation attempt.",
                total_attempts=1,
                failed_nodes=(
                    RepairProgramNodeFailureEvidence(
                        node_id=node_id,
                        error_code=failure_code,
                        error_message="The program consumed its one allowed operation attempt.",
                    ),
                ),
            ),
        ),
        trials=trials,
        diagnostic_codes=tuple(diagnostic_codes),
    )


def _turn_limit_evidence() -> RepairRuntimeEvidence:
    return RepairRuntimeEvidence(
        candidate_id="candidate.parent",
        run_id="run.parent",
        kernel_sha256="a" * 64,
        harness_sha256="b" * 64,
        program_sha256="c" * 64,
        compiled_bundle_sha256="d" * 64,
        run_artifact_sha256="e" * 64,
        pairing=_pairing(),
        trials=(_turn_limit_trial(),),
        program_executions=(
            RepairProgramExecutionEvidence(
                repetition=1,
                seed=17,
                status=ProgramExecutionStatus.SUCCEEDED,
                total_attempts=1,
            ),
        ),
        diagnostic_codes=(
            "agent_execution_failed",
            "agent_failure:turn_limit_reached",
            "harness_turn_limit_reached",
        ),
    )


def _declared_stage_graph_evidence() -> RepairRuntimeEvidence:
    task_id = "civil/calculation/attempt-limit"
    world_sha256 = "9" * 64
    graph = DeclaredStageGraph(
        task_id=task_id,
        world_package_sha256=world_sha256,
        stages=(
            DeclaredStage(
                stage_id="inventory",
                consumes=("document_register",),
                produces=("source_inventory",),
            ),
            DeclaredStage(
                stage_id="authority",
                consumes=("source_inventory",),
                produces=("provenance_ledger",),
            ),
            DeclaredStage(
                stage_id="decision",
                consumes=("source_inventory", "provenance_ledger"),
                produces=("readiness_decision",),
            ),
        ),
    )
    task_graph = RepairDeclaredStageGraphEvidence(
        task_id=task_id,
        task_package_sha256="8" * 64,
        world_package_sha256=world_sha256,
        stage_graph=graph,
    )
    trial = RepairTrialEvidence(
        trial_id="trial.semantic-program",
        task_id=task_id,
        repetition=1,
        seed=17,
        reward=0.2,
        complete=True,
        valid=True,
        agent=RepairAgentExecutionEvidence(
            status=AgentOutputStatus.COMPLETED,
            runtime_execution_attested=True,
        ),
        verifier=RepairVerifierEvidence(
            output_parseable=True,
            schema_valid=True,
            completed=True,
            breakdown={"gates": {"closure": {"passed": False, "score": 0.2}}},
        ),
        resource_sha256=task_graph.task_package_sha256,
        world_lineage_sha256=world_sha256,
        error_codes=("reward_below_verifier_threshold",),
    )
    return RepairRuntimeEvidence(
        candidate_id="candidate.parent",
        run_id="run.parent",
        kernel_sha256="a" * 64,
        harness_sha256="b" * 64,
        program_sha256="c" * 64,
        compiled_bundle_sha256="d" * 64,
        run_artifact_sha256="e" * 64,
        pairing=_pairing(budget=HarnessBudget(max_total_attempts=8)),
        trials=(trial,),
        program_executions=(
            RepairProgramExecutionEvidence(
                repetition=1,
                seed=17,
                status=ProgramExecutionStatus.SUCCEEDED,
                total_attempts=1,
            ),
        ),
        monolithic_run_batch=RepairMonolithicRunBatchEvidence(
            run_node_id="run",
            stop_node_id="stop",
            task_refs=(task_id,),
        ),
        declared_stage_graphs=(task_graph,),
        program_limits=ProgramLimits(max_total_attempts=8),
        verifier_minimum_reward=0.5,
        diagnostic_codes=("reward_below_verifier_threshold",),
    )


def _pairing(*, budget: HarnessBudget | None = None) -> RepairPairingSpec:
    return RepairPairingSpec(
        split="repair_gate",
        task_ids=("civil/calculation/attempt-limit",),
        seeds=(17,),
        budget=budget or HarnessBudget(),
        repetitions=1,
    )


def _batch_coalescing_rule() -> ProgramCoalesceTaskBatchDiagnosisRule:
    return ProgramCoalesceTaskBatchDiagnosisRule(
        source_node_ids=("run-primary", "run-secondary"),
        replacement_node_id="run-coalesced",
        task_refs=_BATCH_TASK_IDS,
    )


def _batch_coalescing_pairing(*, budget: HarnessBudget) -> RepairPairingSpec:
    return RepairPairingSpec(
        split="repair_gate",
        task_ids=_BATCH_TASK_IDS,
        seeds=(17,),
        budget=budget,
        repetitions=1,
    )


def _batch_coalescing_nodes() -> tuple[ActionNode | StopNode, ...]:
    return (
        ActionNode(
            node_id="run-primary",
            operation_id="run_batch.v1",
            arguments=(ProgramArgument(name="task_ref", value=LiteralValue(value=_BATCH_TASK_IDS[0])),),
        ),
        ActionNode(
            node_id="run-secondary",
            depends_on=("run-primary",),
            operation_id="run_batch.v1",
            arguments=(ProgramArgument(name="task_ref", value=LiteralValue(value=_BATCH_TASK_IDS[1])),),
        ),
        StopNode(
            node_id="stop",
            depends_on=("run-secondary",),
            outcome=StopOutcome.SUCCEEDED,
        ),
    )


def _batch_coalescing_candidate(*, budget: HarnessBudget) -> RepairCandidate:
    return _candidate(
        budget=budget,
        nodes=_batch_coalescing_nodes(),
        limits=ProgramLimits(max_total_attempts=1, max_parallelism=1),
    )


def _batch_coalescing_evidence(
    *,
    failed_node: str = "run-secondary",
    total_attempts: int = 1,
    primary_valid: bool = True,
    include_secondary_trial: bool = False,
) -> RepairRuntimeEvidence:
    budget = HarnessBudget(max_agent_turns=4, max_total_attempts=1, max_parallelism=1)
    trials = [
        RepairTrialEvidence(
            trial_id="trial.batch-alpha",
            task_id=_BATCH_TASK_IDS[0],
            repetition=1,
            seed=17,
            reward=0.9,
            complete=True,
            valid=primary_valid,
            agent=RepairAgentExecutionEvidence(
                status=AgentOutputStatus.COMPLETED,
                runtime_execution_attested=True,
            ),
            verifier=RepairVerifierEvidence(
                output_parseable=True,
                schema_valid=True,
                completed=True,
            ),
            resource_sha256="f" * 64,
            world_lineage_sha256="0" * 64,
        )
    ]
    if include_secondary_trial:
        trials.append(
            trials[0].model_copy(
                update={
                    "trial_id": "trial.batch-beta",
                    "task_id": _BATCH_TASK_IDS[1],
                }
            )
        )
    failure_code = "global_attempt_budget_exhausted"
    return RepairRuntimeEvidence(
        candidate_id="candidate.parent",
        run_id="run.parent",
        kernel_sha256="a" * 64,
        harness_sha256="b" * 64,
        program_sha256="c" * 64,
        compiled_bundle_sha256="d" * 64,
        run_artifact_sha256="e" * 64,
        pairing=_batch_coalescing_pairing(budget=budget),
        trials=tuple(trials),
        program_executions=(
            RepairProgramExecutionEvidence(
                repetition=1,
                seed=17,
                status=ProgramExecutionStatus.FAILED,
                error_code=failure_code,
                total_attempts=total_attempts,
                failed_nodes=(
                    RepairProgramNodeFailureEvidence(
                        node_id=failed_node,
                        error_code=failure_code,
                    ),
                ),
            ),
        ),
        diagnostic_codes=(
            "program_execution_failed",
            f"program_failure:{failure_code}",
        ),
    )


def _candidate(
    *,
    budget: HarnessBudget,
    nodes: tuple[ActionNode | FanoutNode | StopNode, ...] | None = None,
    limits: ProgramLimits | None = None,
) -> RepairCandidate:
    registry = default_kernel_registry()
    return RepairCandidate(
        candidate_id="candidate.feasibility",
        parent_candidate_id=None,
        iteration=0,
        harness_request=HarnessCompileRequest(
            request_id="compile.feasibility",
            kernel_ref=registry.manifest.ref,
            recipe=HarnessRecipe(
                recipe_id="harness.feasibility",
                version="1.0.0",
                summary="Exercise static diagnosis-rule feasibility against a fixed Hx budget.",
                budget=budget,
                bindings=(
                    HarnessBindingSpec(
                        binding_id="agent",
                        capability_ref=registry.capability("aecbench.adapter.tool-loop").ref,
                        topology_role=HarnessTopologyRole.ORCHESTRATOR,
                        configuration=AgentBindingConfig(
                            agent_name="feasibility-agent",
                            model="claude-test-model",
                            max_turns=2,
                        ),
                    ),
                    HarnessBindingSpec(
                        binding_id="compute",
                        capability_ref=registry.capability("aecbench.backend.harbor.docker").ref,
                        depends_on=("agent",),
                        topology_role=HarnessTopologyRole.SERVICE,
                        configuration=ComputeBindingConfig(max_concurrency=1),
                    ),
                ),
            ),
        ),
        program_template=RepairProgramTemplate(
            program_id="program.feasibility",
            version="1.0.0",
            nodes=nodes
            or (
                ActionNode(node_id="run", operation_id="run_batch.v1"),
                StopNode(node_id="stop", depends_on=("run",), outcome=StopOutcome.SUCCEEDED),
            ),
            limits=limits or ProgramLimits(max_total_attempts=3),
        ),
    )


def _program_retry_rule(*, node_id: str, max_attempts: int) -> ProgramRetryDiagnosisRule:
    error_code = "pre_dispatch_capacity_timeout"
    return ProgramRetryDiagnosisRule(
        node_id=node_id,
        retry=RetryPolicy(max_attempts=max_attempts, retry_on=(error_code,)),
        retryable_error_codes=(error_code,),
    )


def _turn_limit_trial() -> RepairTrialEvidence:
    return RepairTrialEvidence(
        trial_id="trial.turn-limit",
        task_id="civil/calculation/attempt-limit",
        repetition=1,
        seed=17,
        reward=0.0,
        complete=False,
        valid=False,
        agent=RepairAgentExecutionEvidence(
            status=AgentOutputStatus.PARTIAL,
            failure_kind="turn_limit_reached",
            stop_reason=AdapterStopReason.ITERATION_CAP,
            provider_error="turn limit reached",
            turns_used=1,
            max_turns=1,
            runtime_execution_attested=True,
        ),
        verifier=RepairVerifierEvidence(
            output_parseable=True,
            schema_valid=True,
            completed=True,
        ),
        resource_sha256="f" * 64,
        world_lineage_sha256="0" * 64,
        error_codes=(
            "agent_execution_failed",
            "agent_failure:turn_limit_reached",
            "harness_turn_limit_reached",
        ),
    )


def _completion_capability_evidence() -> RepairRuntimeEvidence:
    payload = _turn_limit_evidence().model_dump(mode="json", exclude={"content_sha256"})
    payload["trials"][0]["agent"]["output_artifact"] = RepairOutputArtifactEvidence(
        path="jobs/trial/artifacts/agent/output.md",
        sha256="a" * 64,
        media_type="text/markdown",
        size_bytes=128,
        completion_contract_sha256="b" * 64,
        completion_contract_content_sha256="c" * 64,
        completion_evaluation=OutputCompletionEvaluation(
            complete=True,
            reason=OutputCompletionReason.COMPLETE,
            present_top_level_keys=("answer",),
            final_json_block_count=1,
        ),
    ).model_dump(mode="json")
    return RepairRuntimeEvidence.model_validate(payload)


@pytest.mark.parametrize(
    "stop_reason",
    (
        AdapterStopReason.TOKEN_BUDGET,
        AdapterStopReason.SUBCALL_LIMIT,
        AdapterStopReason.COST_BUDGET,
        AdapterStopReason.BILLABLE_INPUT_BUDGET,
        AdapterStopReason.CONTEXT_LIMIT,
    ),
)
def test_harness_turn_diagnosis_rejects_non_iteration_guardrail_stops(
    stop_reason: AdapterStopReason,
) -> None:
    payload = _turn_limit_evidence().model_dump(mode="json", exclude={"content_sha256"})
    payload["trials"][0]["agent"]["stop_reason"] = stop_reason.value
    evidence = RepairRuntimeEvidence.model_validate(payload)

    proposal = diagnose_harness_turn_limit(evidence, binding_id="agent", max_turns=4)

    assert isinstance(proposal, RepairNoPatchProposal)
    assert proposal.failure_domain is RepairFailureDomain.RUNTIME


@pytest.mark.parametrize(("turns_used", "max_turns"), ((None, 1), (0, 1), (1, None), (1, 2)))
def test_harness_turn_diagnosis_requires_observed_exhaustion(
    turns_used: int | None,
    max_turns: int | None,
) -> None:
    payload = _turn_limit_evidence().model_dump(mode="json", exclude={"content_sha256"})
    payload["trials"][0]["agent"]["turns_used"] = turns_used
    payload["trials"][0]["agent"]["max_turns"] = max_turns
    evidence = RepairRuntimeEvidence.model_validate(payload)

    proposal = diagnose_harness_turn_limit(evidence, binding_id="agent", max_turns=4)

    assert isinstance(proposal, RepairNoPatchProposal)
    assert proposal.failure_domain is RepairFailureDomain.RUNTIME
