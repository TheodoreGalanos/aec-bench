# ABOUTME: Defines immutable contracts for repair proposals, evidence, runs, and terminal decisions.
# ABOUTME: Keeps schema, canonical identity, and ownership invariants independent of runtime orchestration.

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Literal, Self

from pydantic import Field, JsonValue, field_validator, model_validator

from aec_bench.adapters.base import AdapterStopReason
from aec_bench.contracts.agent_output import AgentOutputStatus
from aec_bench.contracts.content_address import ContentAddressedModel
from aec_bench.contracts.execution_program import ExecutionProgramRef, ProgramLimits, RetryPolicy
from aec_bench.contracts.harness_instance import HarnessInstanceRef, prohibited_retry_safe_error_codes
from aec_bench.contracts.harness_kernel import (
    FrozenStrictModel,
    KernelCapabilityRef,
    KernelRef,
    canonical_json_sha256,
    validate_sha256,
)
from aec_bench.contracts.output_completion import OutputCompletionEvaluation
from aec_bench.contracts.stage_execution import DeclaredStageGraph
from aec_bench.contracts.task_review_snapshot import TaskReviewSnapshot
from aec_bench.contracts.task_snapshot import TaskSnapshotRef, task_snapshot_commitment
from aec_bench.contracts.trial_record import ArtifactReference
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.evolution.repair_lifecycle import (
    RepairCandidate,
    RepairFailureDomain,
    RepairLoopRequest,
    RepairLoopResult,
    RepairOwner,
    RepairPairingSpec,
)
from aec_bench.harness.budget import HarnessBudgetObservation
from aec_bench.harness.program_execution import (
    ProgramExecutionResult,
    ProgramExecutionStatus,
)


class RepairDeclaredStageGraphEvidence(FrozenStrictModel):
    """Exact task, task-review, and declared-stage graph identity exposed to diagnosis."""

    task_id: NonEmptyStr
    task_snapshot: TaskSnapshotRef
    review: TaskReviewSnapshot

    @model_validator(mode="after")
    def validate_graph_identity(self) -> Self:
        if self.task_snapshot.task_id != self.task_id or self.review.task_id != self.task_id:
            raise ValueError("declared-stage repair evidence does not match its task")
        if self.review.stage_graph is None:
            raise ValueError("declared-stage repair evidence requires a stage graph")
        if self.review.stage_graph.task_id != self.task_id:
            raise ValueError("declared-stage repair evidence graph does not match its task")
        return self

    @property
    def stage_graph(self) -> DeclaredStageGraph:
        """Return the graph carried by the one embedded review value."""

        assert self.review.stage_graph is not None
        return self.review.stage_graph


class RepairMonolithicRunBatchEvidence(FrozenStrictModel):
    """Exact two-node parent px shape eligible for declared-stage materialization."""

    run_node_id: NonEmptyStr
    stop_node_id: NonEmptyStr
    task_refs: tuple[NonEmptyStr, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_coordinates(self) -> Self:
        if self.run_node_id == self.stop_node_id:
            raise ValueError("monolithic run and stop node ids must differ")
        if len(self.task_refs) != len(set(self.task_refs)):
            raise ValueError("monolithic run task refs must be unique")
        return self


class HarnessAgentMaxTurnsPatch(FrozenStrictModel):
    """Replace one agent binding's turn limit without changing model, tasks, or budget."""

    kind: Literal["harness_agent_max_turns"] = "harness_agent_max_turns"
    binding_id: NonEmptyStr
    max_turns: int = Field(ge=1, le=1_000)


class HarnessAgentCapabilityPatch(FrozenStrictModel):
    """Replace one exact agent capability binding while preserving its configuration."""

    kind: Literal["harness_agent_capability"] = "harness_agent_capability"
    binding_id: NonEmptyStr
    expected_capability_ref: KernelCapabilityRef
    replacement_capability_ref: KernelCapabilityRef

    @model_validator(mode="after")
    def validate_capability_change(self) -> Self:
        transition = (
            self.expected_capability_ref.capability_id,
            self.replacement_capability_ref.capability_id,
        )
        if transition != (
            "aecbench.adapter.rlm-uncached",
            "aecbench.adapter.rlm-output-contract",
        ):
            raise ValueError(
                "harness agent capability patch supports only "
                "aecbench.adapter.rlm-uncached -> aecbench.adapter.rlm-output-contract"
            )
        return self


class ProgramNodeRetryPatch(FrozenStrictModel):
    """Replace the retry policy of one retry-capable executable px node."""

    kind: Literal["program_node_retry"] = "program_node_retry"
    node_id: NonEmptyStr
    retry: RetryPolicy

    @model_validator(mode="after")
    def validate_retry_increase_candidate(self) -> Self:
        if self.retry.max_attempts < 2:
            raise ValueError("program retry patch requires at least two attempts")
        prohibited = prohibited_retry_safe_error_codes(self.retry.retry_on)
        if prohibited:
            raise ValueError("program retry patch contains prohibited retry-safe error codes: " + ", ".join(prohibited))
        return self


class ProgramMaxTotalAttemptsPatch(FrozenStrictModel):
    """Increase only the program-wide operation-attempt limit within the fixed Hx budget."""

    kind: Literal["program_max_total_attempts"] = "program_max_total_attempts"
    max_total_attempts: int = Field(ge=1, le=10_000)


class ProgramCoalesceTaskBatchPatch(FrozenStrictModel):
    """Replace one exact two-action serial px fragment with one literal batch action."""

    kind: Literal["program_coalesce_task_batch"] = "program_coalesce_task_batch"
    expected_program_ref: ExecutionProgramRef
    source_node_ids: tuple[NonEmptyStr, NonEmptyStr]
    replacement_node_id: NonEmptyStr
    task_refs: tuple[NonEmptyStr, NonEmptyStr]

    @model_validator(mode="after")
    def validate_coordinates(self) -> Self:
        if len(set(self.source_node_ids)) != 2:
            raise ValueError("program batch-coalescing patch requires two distinct source nodes")
        if self.replacement_node_id in self.source_node_ids:
            raise ValueError("program batch-coalescing replacement must differ from both source nodes")
        if len(set(self.task_refs)) != 2:
            raise ValueError("program batch-coalescing patch requires two distinct task refs")
        return self


class ProgramMaterializeDeclaredStageGraphPatch(FrozenStrictModel):
    """Replace one exact monolithic px with its pinned task-review stage graphs."""

    kind: Literal["program_materialize_declared_stage_graph"] = "program_materialize_declared_stage_graph"
    expected_program_ref: ExecutionProgramRef
    task_graphs: tuple[RepairDeclaredStageGraphEvidence, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_task_graphs(self) -> Self:
        task_ids = tuple(item.task_id for item in self.task_graphs)
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("declared-stage graph patch task ids must be unique")
        if any(len(item.stage_graph.stages) < 2 or not item.stage_graph.routes for item in self.task_graphs):
            raise ValueError("declared-stage graph patch requires nontrivial routed stage graphs")
        return self


RepairRuntimePatch = Annotated[
    HarnessAgentMaxTurnsPatch
    | HarnessAgentCapabilityPatch
    | ProgramNodeRetryPatch
    | ProgramMaxTotalAttemptsPatch
    | ProgramCoalesceTaskBatchPatch
    | ProgramMaterializeDeclaredStageGraphPatch,
    Field(discriminator="kind"),
]


class RepairPatchProposal(FrozenStrictModel):
    """Closed diagnosis output whose only executable effect is a typed patch operation."""

    owner: RepairOwner
    code: NonEmptyStr
    message: NonEmptyStr
    patch: RepairRuntimePatch

    @field_validator("patch", mode="before")
    @classmethod
    def reject_unknown_patch_kind(cls, value: object) -> object:
        if isinstance(value, Mapping) and value.get("kind") not in {
            "harness_agent_max_turns",
            "harness_agent_capability",
            "program_node_retry",
            "program_max_total_attempts",
            "program_coalesce_task_batch",
            "program_materialize_declared_stage_graph",
        }:
            raise ValueError("unsupported repair patch kind")
        return value

    @model_validator(mode="after")
    def validate_owner(self) -> Self:
        expected = (
            RepairOwner.HARNESS
            if isinstance(self.patch, HarnessAgentMaxTurnsPatch | HarnessAgentCapabilityPatch)
            else RepairOwner.PROGRAM
        )
        if self.owner is not expected:
            raise ValueError("repair patch owner does not match its typed patch surface")
        return self


class RepairNoPatchProposal(FrozenStrictModel):
    """Evidence-backed diagnosis for which no allowlisted patch applies."""

    failure_domain: RepairFailureDomain
    code: NonEmptyStr
    message: NonEmptyStr
    evidence_codes: tuple[NonEmptyStr, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_evidence_codes(self) -> Self:
        if len(self.evidence_codes) != len(set(self.evidence_codes)):
            raise ValueError("no-patch diagnosis evidence codes must be unique")
        return self


class RepairVerifierPolicy(FrozenStrictModel):
    """Deterministic interpretation of independent verifier-backed TrialRecords."""

    minimum_reward: float = Field(default=1.0, ge=0.0, le=1.0)
    require_valid: bool = True
    require_complete_provenance: bool = False


class RepairEvidenceUsePolicy(FrozenStrictModel):
    """Machine-readable boundary on what one paired repair result may support."""

    interpretation: Literal[
        "exploratory_matched_repair",
        "calibration_gated_adaptive_cycle",
    ]
    supported_claim_scope: Literal[
        "observed_matched_blocks_only",
        "calibration_gated_motif_learning",
    ]
    generalized_causal_effects_supported: Literal[False]
    motif_evidence_eligible: bool
    execution_seed_semantics: Literal["paired_repetition_label_only"]

    @classmethod
    def exploratory_matched_repair(cls) -> Self:
        """Return the fail-closed policy for a standalone Stage 1 pilot."""

        return cls(
            interpretation="exploratory_matched_repair",
            supported_claim_scope="observed_matched_blocks_only",
            generalized_causal_effects_supported=False,
            motif_evidence_eligible=False,
            execution_seed_semantics="paired_repetition_label_only",
        )

    @classmethod
    def calibration_gated_adaptive_cycle(cls) -> Self:
        """Permit capture only as one input to the separately calibrated adaptive cycle."""

        return cls(
            interpretation="calibration_gated_adaptive_cycle",
            supported_claim_scope="calibration_gated_motif_learning",
            generalized_causal_effects_supported=False,
            motif_evidence_eligible=True,
            execution_seed_semantics="paired_repetition_label_only",
        )

    @model_validator(mode="after")
    def validate_closed_policy(self) -> Self:
        expected = {
            "exploratory_matched_repair": (
                "observed_matched_blocks_only",
                False,
            ),
            "calibration_gated_adaptive_cycle": (
                "calibration_gated_motif_learning",
                True,
            ),
        }[self.interpretation]
        if (self.supported_claim_scope, self.motif_evidence_eligible) != expected:
            raise ValueError("repair evidence-use policy contains an unsupported claim combination")
        return self


class RepairOutputArtifactEvidence(FrozenStrictModel):
    """Content-pinned nonempty output artifact observed at the trusted import boundary."""

    path: NonEmptyStr
    sha256: str
    media_type: NonEmptyStr
    size_bytes: int = Field(ge=1)
    completion_contract_sha256: str
    completion_contract_content_sha256: str
    completion_evaluation: OutputCompletionEvaluation

    @field_validator(
        "sha256",
        "completion_contract_sha256",
        "completion_contract_content_sha256",
    )
    @classmethod
    def validate_artifact_sha256(cls, value: str) -> str:
        return validate_sha256(value)


class RepairAgentExecutionEvidence(FrozenStrictModel):
    """Trusted agent/runtime signals retained for failure ownership diagnosis."""

    status: AgentOutputStatus
    failure_kind: NonEmptyStr | None = None
    stop_reason: AdapterStopReason | None = None
    provider_error: str | None = None
    turns_used: int | None = Field(default=None, ge=0)
    max_turns: int | None = Field(default=None, ge=1)
    lifecycle_status: NonEmptyStr | None = None
    runtime_execution_attested: bool
    output_artifact: RepairOutputArtifactEvidence | None = None
    output_commit_attested: bool = False

    @model_validator(mode="after")
    def validate_turn_usage(self) -> Self:
        if self.turns_used is not None and self.max_turns is not None and self.turns_used > self.max_turns:
            raise ValueError("agent turns used cannot exceed its configured turn limit")
        return self


class RepairVerifierEvidence(FrozenStrictModel):
    """Independent verifier validity and content-pinned gate-level diagnostic evidence."""

    output_parseable: bool
    schema_valid: bool
    completed: bool
    errors: tuple[str, ...] = ()
    breakdown: dict[str, JsonValue] | None = None
    breakdown_sha256: str | None = None

    @model_validator(mode="after")
    def validate_breakdown_hash(self) -> Self:
        expected = canonical_json_sha256(self.breakdown) if self.breakdown is not None else None
        if self.breakdown_sha256 is not None:
            validate_sha256(self.breakdown_sha256)
            if self.breakdown_sha256 != expected:
                raise ValueError("verifier breakdown hash does not match its diagnostic evidence")
        object.__setattr__(self, "breakdown_sha256", expected)
        return self


class RepairTrialEvidence(FrozenStrictModel):
    """One immutable trial observation exposed to the diagnosis boundary."""

    trial_id: NonEmptyStr
    task_id: NonEmptyStr
    repetition: int = Field(ge=1)
    seed: int
    reward: float = Field(ge=0.0, le=1.0)
    complete: bool
    valid: bool
    agent: RepairAgentExecutionEvidence
    verifier: RepairVerifierEvidence
    resource_sha256: str
    review_lineage_sha256: str
    estimated_cost_usd: float | None = Field(default=None, ge=0.0)
    error_codes: tuple[NonEmptyStr, ...] = ()

    @field_validator("resource_sha256", "review_lineage_sha256")
    @classmethod
    def validate_lineage_hashes(cls, value: str) -> str:
        return validate_sha256(value)


class RepairProgramNodeFailureEvidence(FrozenStrictModel):
    """One failed p-owned node and the runtime code that justifies program attribution."""

    node_id: NonEmptyStr
    error_code: NonEmptyStr
    error_message: str | None = None


class RepairProgramExecutionEvidence(FrozenStrictModel):
    """Seed-pinned px terminal state retained independently of verifier reward."""

    repetition: int = Field(ge=1)
    seed: int
    status: ProgramExecutionStatus
    error_code: NonEmptyStr | None = None
    error_message: str | None = None
    total_attempts: int = Field(ge=0)
    failed_nodes: tuple[RepairProgramNodeFailureEvidence, ...] = ()

    @model_validator(mode="after")
    def validate_failure_shape(self) -> Self:
        if self.status is ProgramExecutionStatus.SUCCEEDED and (
            self.error_code is not None or self.error_message is not None or self.failed_nodes
        ):
            raise ValueError("successful program evidence cannot contain failure details")
        if self.status is ProgramExecutionStatus.FAILED and self.error_code is None:
            raise ValueError("failed program evidence requires a terminal error code")
        return self


class RepairRuntimeEvidence(ContentAddressedModel):
    """Content-addressed verifier/runtime evidence supplied to a typed diagnoser."""

    candidate_id: NonEmptyStr
    run_id: NonEmptyStr
    kernel_ref: KernelRef
    harness_ref: HarnessInstanceRef
    program_ref: ExecutionProgramRef
    bundle_id: NonEmptyStr
    run_artifact_sha256: str
    pairing: RepairPairingSpec
    trials: tuple[RepairTrialEvidence, ...] = ()
    program_executions: tuple[RepairProgramExecutionEvidence, ...] = Field(min_length=1)
    monolithic_run_batch: RepairMonolithicRunBatchEvidence | None = None
    declared_stage_graphs: tuple[RepairDeclaredStageGraphEvidence, ...] = ()
    program_limits: ProgramLimits | None = None
    verifier_minimum_reward: float | None = Field(default=None, ge=0.0, le=1.0)
    diagnostic_codes: tuple[NonEmptyStr, ...]

    @field_validator(
        "run_artifact_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_evidence_matrix(self) -> Self:
        expected_program_coordinates = tuple(enumerate(self.pairing.seeds, start=1))
        actual_program_coordinates = tuple(
            (execution.repetition, execution.seed) for execution in self.program_executions
        )
        if actual_program_coordinates != expected_program_coordinates:
            raise ValueError("repair runtime evidence requires the exact paired program execution matrix")
        trial_coordinates = tuple((trial.task_id, trial.repetition, trial.seed) for trial in self.trials)
        expected_trial_coordinates = {
            (task_id, repetition, seed)
            for repetition, seed in expected_program_coordinates
            for task_id in self.pairing.task_ids
        }
        if len(trial_coordinates) != len(set(trial_coordinates)):
            raise ValueError("repair runtime evidence trial coordinates must be unique")
        if not set(trial_coordinates).issubset(expected_trial_coordinates):
            raise ValueError("repair runtime evidence trials must remain within the exact paired matrix")
        if self.monolithic_run_batch is not None and self.monolithic_run_batch.task_refs != self.pairing.task_ids:
            raise ValueError("monolithic run evidence must bind the exact paired task order")
        if self.declared_stage_graphs:
            graph_task_ids = tuple(item.task_id for item in self.declared_stage_graphs)
            if graph_task_ids != self.pairing.task_ids:
                raise ValueError("declared-stage evidence must bind the exact paired task order")
            graphs_by_task = {item.task_id: item for item in self.declared_stage_graphs}
            for trial in self.trials:
                graph = graphs_by_task[trial.task_id]
                if trial.resource_sha256 != task_snapshot_commitment(
                    graph.task_snapshot
                ) or trial.review_lineage_sha256 != canonical_json_sha256(graph.review.model_dump(mode="json")):
                    raise ValueError("trial evidence does not match its declared task-review graph identity")
        return self


class RepairAttemptPlan(ContentAddressedModel):
    """Pre-run causal artifact shared by both arms of one paired repair attempt."""

    schema_version: Literal["aecbench.repair-attempt-plan.v2"] = "aecbench.repair-attempt-plan.v2"
    request: RepairLoopRequest
    parent: RepairCandidate
    evidence_use_policy: RepairEvidenceUsePolicy
    repair_run_spec: ArtifactReference | None = None


class RepairSeedExecution(FrozenStrictModel):
    """One seed's exact program, budget, and genuine imported TrialRecord evidence."""

    repetition: int = Field(ge=1)
    seed: int
    run_id: NonEmptyStr
    execution_bundle_id: NonEmptyStr
    program_execution: ProgramExecutionResult
    budget: HarnessBudgetObservation
    trial_records: tuple[ArtifactReference, ...] = ()
    harbor_invocation_receipts: tuple[ArtifactReference, ...] = ()

    @model_validator(mode="after")
    def validate_trial_records(self) -> Self:
        identities = [(item.path, item.sha256) for item in self.trial_records]
        if len(identities) != len(set(identities)):
            raise ValueError("repair seed execution contains duplicate TrialRecord artifacts")
        receipt_identities = [(item.path, item.sha256) for item in self.harbor_invocation_receipts]
        if len(receipt_identities) != len(set(receipt_identities)):
            raise ValueError("repair seed execution contains duplicate Harbor invocation receipts")
        if any(item.kind != "harbor-invocation-receipt" for item in self.harbor_invocation_receipts):
            raise ValueError("repair seed execution accepts only Harbor invocation receipts")
        return self


class RepairRunArtifactManifest(ContentAddressedModel):
    """Persisted, tamper-evident manifest for every seeded execution of one candidate."""

    schema_version: Literal["aecbench.repair-run.v3"] = "aecbench.repair-run.v3"
    attempt_id: NonEmptyStr
    iteration: int = Field(ge=1)
    run_id: NonEmptyStr
    candidate_id: NonEmptyStr
    parent_candidate_id: NonEmptyStr | None
    kernel_ref: KernelRef
    harness_ref: HarnessInstanceRef
    program_ref: ExecutionProgramRef
    bundle_id: NonEmptyStr
    attempt_plan: ArtifactReference
    pairing: RepairPairingSpec
    executions: tuple[RepairSeedExecution, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_seed_matrix(self) -> Self:
        coordinates = tuple((item.repetition, item.seed) for item in self.executions)
        expected = tuple(enumerate(self.pairing.seeds, start=1))
        if coordinates != expected:
            raise ValueError("repair run must execute every paired repetition under its exact seed")
        expected_trial_count = len(self.pairing.task_ids)
        if any(item.program_execution.program_ref != self.program_ref for item in self.executions):
            raise ValueError("repair seed program evidence must match the manifested px identity")
        if any(len(item.trial_records) > expected_trial_count for item in self.executions):
            raise ValueError("repair seed execution cannot exceed the exact paired task matrix")
        if any(
            item.program_execution.status is ProgramExecutionStatus.SUCCEEDED
            and len(item.trial_records) != expected_trial_count
            for item in self.executions
        ):
            raise ValueError("successful repair seed execution requires exactly one trial per paired task")
        return self


class RepairTerminalRecord(ContentAddressedModel):
    """Final content-addressed repair decision linked to its controlling attempt plan."""

    schema_version: Literal["aecbench.repair-terminal.v3"] = "aecbench.repair-terminal.v3"
    attempt_plan_sha256: str
    evidence_use_policy: RepairEvidenceUsePolicy
    repair_run_spec: ArtifactReference | None = None
    result: RepairLoopResult
    diagnosis_evidence: RepairRuntimeEvidence | None = None
    patch_proposal: RepairPatchProposal | None = None

    @field_validator("attempt_plan_sha256")
    @classmethod
    def validate_plan_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_diagnosis_lineage(self) -> Self:
        if self.result.diagnosis is None:
            if self.diagnosis_evidence is not None or self.patch_proposal is not None:
                raise ValueError("no-repair terminal record cannot contain diagnosis evidence")
            return self
        if self.diagnosis_evidence is None:
            raise ValueError("repair terminal record requires diagnosis evidence")
        if self.result.diagnosis.owner is None and self.patch_proposal is not None:
            raise ValueError("unowned diagnosis cannot contain a typed patch")
        if self.result.diagnosis.owner is not None and self.patch_proposal is None:
            raise ValueError("owned diagnosis requires a typed patch")
        assert self.diagnosis_evidence is not None
        if (
            self.diagnosis_evidence.candidate_id != self.result.parent_candidate_id
            or self.diagnosis_evidence.run_id != self.result.parent_verification.run_id
        ):
            raise ValueError("terminal diagnosis evidence must identify the exact repaired parent run")
        if self.patch_proposal is not None and self.patch_proposal.owner is not self.result.diagnosis.owner:
            raise ValueError("terminal typed patch must match the diagnosed owner")
        return self
