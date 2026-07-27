# ABOUTME: Defines prepared proposal tasks and outcome-blind evaluation generations.
# ABOUTME: Checks cohort, critic, policy, kernel, budget, and candidate-manifest bindings.

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from aec_bench.contracts.evaluation_generation.cohort import (
    EvaluationCohortBinding,
    EvaluationCohortManifest,
    EvaluationCohortTask,
    validate_cohort_binding,
)
from aec_bench.contracts.evaluation_generation.spec import (
    EvaluationGenerationSourceRef,
    EvaluationGenerationSpec,
    ProposalGenerationPolicy,
)
from aec_bench.contracts.evaluation_plane import (
    CandidateManifestScope,
    EvaluationPlanAuthorityScope,
    EvaluationPlanRef,
)
from aec_bench.contracts.harness_instance import HarnessBudget
from aec_bench.contracts.harness_kernel import ContentAddressedModel, validate_sha256
from aec_bench.contracts.program_proposal import (
    CandidateGenerationManifest,
    DecompositionLeakageAudit,
    DecompositionProblemView,
)
from aec_bench.contracts.validators import NonEmptyStr


class PreparedProposalTask(ContentAddressedModel):
    """One public task surface prepared before proposal generation."""

    schema_version: Literal["aecbench.prepared-proposal-task.v2"] = "aecbench.prepared-proposal-task.v2"
    prepared_task_id: NonEmptyStr
    cohort_task: EvaluationCohortTask
    problem_view: DecompositionProblemView
    leakage_audit: DecompositionLeakageAudit
    candidate_manifest: CandidateGenerationManifest

    @model_validator(mode="after")
    def validate_public_task_surface(self) -> Self:
        task = self.cohort_task.task
        view = self.problem_view
        if (
            view.task_id != task.task_id
            or view.task_revision != task.public_snapshot.definition_sha256
            or view.public_task_snapshot_sha256 != task.public_task_snapshot_sha256
        ):
            raise ValueError(
                "prepared proposal task problem view differs from its cohort task",
            )
        if not self.leakage_audit.passed or self.leakage_audit.problem_view_sha256 != view.content_sha256:
            raise ValueError(
                "prepared proposal task requires its exact passed leakage audit",
            )
        if self.candidate_manifest.problem_view_sha256 != view.content_sha256:
            raise ValueError(
                "prepared proposal task candidate manifest does not bind its problem view",
            )
        return self


class PreparedEvaluationGeneration(ContentAddressedModel):
    """Provider-ready, outcome-blind inputs checked against one supplied design."""

    schema_version: Literal["aecbench.prepared-evaluation-generation.v2"] = "aecbench.prepared-evaluation-generation.v2"
    generation_id: NonEmptyStr
    cohort: EvaluationCohortManifest
    cohort_binding: EvaluationCohortBinding
    candidate_manifest_scope: CandidateManifestScope
    kernel_sha256: str
    fixed_harness_sha256: str
    evaluation_plan_ref: EvaluationPlanRef
    evaluation_authority_scope: EvaluationPlanAuthorityScope
    proposal_policy: ProposalGenerationPolicy
    candidate_manifest_proposal_policy_sha256: str
    compilation_policies_sha256: str
    runtime_archive_sha256: str
    monitor_policy_sha256: str
    monitor_cycle_plan_sha256: str
    motif_assurance_snapshot_sha256: str
    candidate_budget: HarnessBudget
    spec: EvaluationGenerationSpec
    task_inputs: tuple[PreparedProposalTask, ...] = Field(min_length=1)
    source_contracts: tuple[EvaluationGenerationSourceRef, ...] = ()
    proposals_realized: Literal[False] = False
    outcomes_observed: Literal[False] = False
    promotion_permitted: Literal[False] = False

    @field_validator(
        "kernel_sha256",
        "fixed_harness_sha256",
        "candidate_manifest_proposal_policy_sha256",
        "compilation_policies_sha256",
        "runtime_archive_sha256",
        "monitor_policy_sha256",
        "monitor_cycle_plan_sha256",
        "motif_assurance_snapshot_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("task_inputs")
    @classmethod
    def canonicalize_task_inputs(
        cls,
        value: tuple[PreparedProposalTask, ...],
    ) -> tuple[PreparedProposalTask, ...]:
        task_ids = tuple(item.cohort_task.task.task_id for item in value)
        prepared_ids = tuple(item.prepared_task_id for item in value)
        manifest_ids = tuple(item.candidate_manifest.content_sha256 for item in value)
        for label, identities in (
            ("task identities", task_ids),
            ("prepared task identities", prepared_ids),
            ("candidate manifest identities", manifest_ids),
        ):
            if len(identities) != len(set(identities)):
                raise ValueError(
                    f"prepared evaluation generation {label} must be unique",
                )
        return tuple(
            sorted(
                value,
                key=lambda item: item.cohort_task.task.task_id,
            )
        )

    @field_validator("source_contracts")
    @classmethod
    def validate_source_contracts(
        cls,
        value: tuple[EvaluationGenerationSourceRef, ...],
    ) -> tuple[EvaluationGenerationSourceRef, ...]:
        roles = tuple(item.role for item in value)
        digests = tuple(item.content_sha256 for item in value)
        if len(roles) != len(set(roles)) or len(digests) != len(set(digests)):
            raise ValueError(
                "evaluation-generation compatibility sources must be unique",
            )
        return value

    @model_validator(mode="after")
    def validate_generation_bindings(self) -> Self:
        validate_cohort_binding(self.cohort, self.cohort_binding)
        if self.evaluation_authority_scope.evaluation_plan_ref != self.evaluation_plan_ref:
            raise ValueError(
                "prepared generation critic authority differs from its evaluation plan",
            )
        if self.cohort.evaluation_generation != self.evaluation_plan_ref.evaluation_generation:
            raise ValueError(
                "prepared generation cohort differs from its evaluation generation",
            )
        if len(self.task_inputs) != self.spec.task_count:
            raise ValueError(
                "prepared generation task count differs from its supplied spec",
            )
        expected_tasks = {item.content_sha256 for item in self.cohort.tasks}
        actual_tasks = {item.cohort_task.content_sha256 for item in self.task_inputs}
        if actual_tasks != expected_tasks:
            raise ValueError(
                "prepared generation task inputs must match the exact cohort",
            )
        expected_candidate_manifests = {item.candidate_manifest.content_sha256 for item in self.task_inputs}
        if set(self.candidate_manifest_scope.candidate_manifest_sha256s) != expected_candidate_manifests:
            raise ValueError(
                "candidate manifest scope must contain every prepared task manifest",
            )
        for item in self.task_inputs:
            if (
                item.problem_view.fixed_harness.kernel_sha256 != self.kernel_sha256
                or item.problem_view.fixed_harness.aggregate_budget != self.candidate_budget
            ):
                raise ValueError(
                    "prepared proposal task differs from the frozen kernel or candidate budget",
                )
            if (
                item.candidate_manifest.proposal_policy_sha256 != self.candidate_manifest_proposal_policy_sha256
                or item.candidate_manifest.policy_checkpoint_sha256 != self.proposal_policy.policy_checkpoint_sha256
            ):
                raise ValueError(
                    "prepared proposal task differs from the frozen proposal policy",
                )
            if (
                item.candidate_manifest.expected_candidate_count != self.spec.proposal_candidate_count_per_task
                or self.proposal_policy.expected_candidate_count != self.spec.proposal_candidate_count_per_task
            ):
                raise ValueError(
                    "prepared proposal count differs from the supplied generation spec",
                )
        return self
