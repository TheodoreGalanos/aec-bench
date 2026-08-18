# ABOUTME: Validates proposal dispatch inputs against their freeze, schedule, and bundle.
# ABOUTME: Preserves fail-closed validation order before any authority evidence is persisted.

from __future__ import annotations

from pathlib import Path

from aec_bench.contracts.authority import (
    AuthorityPrincipal,
    AuthorityPrincipalKind,
)
from aec_bench.contracts.program_proposal.candidate import ProgramCandidateRef
from aec_bench.contracts.program_proposal.freeze import ProposalFreeze
from aec_bench.contracts.program_proposal.study import MatchedEvaluationCoordinate
from aec_bench.contracts.program_proposal.types import ProgramCandidateKind
from aec_bench.contracts.task_definition import TaskDefinition
from aec_bench.experimentation.governance.authority_ledger import StoredAuthorityEvent
from aec_bench.experimentation.proposals.decomposition_optimization import (
    CandidateExecutionAssignment,
    DecompositionExecutionSchedule,
)
from aec_bench.experimentation.proposals.freezing import (
    GovernedProposalFreezeResult,
)
from aec_bench.experimentation.proposals.harbor import ProposalHarborDispatchInput
from aec_bench.experimentation.proposals.program_compilation import (
    ProposalRunSessionBundle,
)
from aec_bench.experimentation.proposals.proposal_dispatch.errors import (
    ProposalDispatchGovernanceError,
)
from aec_bench.experimentation.proposals.session_config import ProposalSessionHostConfig
from aec_bench.experimentation.proposals.task_package import ProposalTaskPackageManifest


def validate_dispatch_inputs(
    *,
    candidate_ref: ProgramCandidateRef,
    execution_schedule: DecompositionExecutionSchedule,
    execution_assignment: CandidateExecutionAssignment,
    evaluation_coordinate: MatchedEvaluationCoordinate,
    bundle: ProposalRunSessionBundle,
    host_config: ProposalSessionHostConfig,
    dispatch: ProposalHarborDispatchInput,
    host_runtime: AuthorityPrincipal,
) -> tuple[
    ProgramCandidateRef,
    DecompositionExecutionSchedule,
    CandidateExecutionAssignment,
    MatchedEvaluationCoordinate,
    ProposalRunSessionBundle,
    ProposalSessionHostConfig,
    ProposalHarborDispatchInput,
    AuthorityPrincipal,
]:
    """Normalize and validate all caller-owned dispatch inputs."""

    try:
        selected_candidate = ProgramCandidateRef.model_validate(
            candidate_ref.model_dump(mode="python"),
        )
        selected_schedule = DecompositionExecutionSchedule.model_validate(
            execution_schedule.model_dump(mode="python"),
        )
        selected_assignment = CandidateExecutionAssignment.model_validate(
            execution_assignment.model_dump(mode="python"),
        )
        selected_coordinate = MatchedEvaluationCoordinate.model_validate(
            evaluation_coordinate.model_dump(mode="python"),
        )
        selected_bundle = ProposalRunSessionBundle.model_validate(
            bundle.model_dump(mode="python"),
        )
        selected_host_config = ProposalSessionHostConfig.model_validate(
            host_config.model_dump(mode="python"),
        )
        selected_task = TaskDefinition.model_validate(
            dispatch.derived_task.model_dump(mode="python"),
        )
        selected_manifest = ProposalTaskPackageManifest.model_validate(
            dispatch.derived_task_manifest.model_dump(mode="python"),
        )
        runtime_principal = AuthorityPrincipal.model_validate(
            host_runtime.model_dump(mode="python"),
        )
    except ValueError as error:
        raise ProposalDispatchGovernanceError(
            f"proposal dispatch input contract is invalid: {error}",
        ) from error
    if runtime_principal.kind is not AuthorityPrincipalKind.HOST_RUNTIME:
        raise ProposalDispatchGovernanceError(
            "proposal dispatch governance requires a host_runtime principal",
        )
    if selected_host_config != dispatch.host_config:
        raise ProposalDispatchGovernanceError(
            "proposal host configuration differs from the exact dispatch input",
        )
    if (
        selected_host_config.evaluation_coordinate != selected_coordinate
        or selected_host_config.execution_schedule_sha256 != selected_schedule.content_sha256
        or selected_host_config.execution_assignment_sha256 != selected_assignment.content_sha256
    ):
        raise ProposalDispatchGovernanceError(
            "proposal host configuration evaluation coordinate or assignment differs from dispatch",
        )
    selected_dispatch = ProposalHarborDispatchInput(
        host_config=selected_host_config,
        derived_task_path=Path(dispatch.derived_task_path),
        derived_task=selected_task,
        derived_task_manifest=selected_manifest,
        repetitions=dispatch.repetitions,
    )
    return (
        selected_candidate,
        selected_schedule,
        selected_assignment,
        selected_coordinate,
        selected_bundle,
        selected_host_config,
        selected_dispatch,
        runtime_principal,
    )


def validate_freeze_compilation_join(
    *,
    governed_freeze: GovernedProposalFreezeResult,
    stored_freeze: StoredAuthorityEvent,
    candidate_ref: ProgramCandidateRef,
    execution_schedule: DecompositionExecutionSchedule,
    execution_assignment: CandidateExecutionAssignment,
    evaluation_coordinate: MatchedEvaluationCoordinate,
    bundle: ProposalRunSessionBundle,
) -> None:
    """Join the selected candidate and coordinate to the exact governed freeze."""

    compilation = bundle.compilation
    if candidate_ref != compilation.candidate_ref:
        raise ProposalDispatchGovernanceError(
            "proposal candidate differs from the exact session bundle compilation",
        )
    if not candidate_is_exactly_frozen(
        freeze=governed_freeze.freeze,
        candidate_ref=candidate_ref,
    ):
        raise ProposalDispatchGovernanceError(
            "proposal candidate is outside the governed freeze",
        )
    if (
        execution_schedule.proposal_freeze != governed_freeze.freeze
        or execution_schedule.kernel_ref != bundle.compilation.kernel_ref
        or execution_schedule.fixed_harness_ref != bundle.fixed_harness.ref
        or execution_schedule.aggregate_budget != bundle.fixed_harness.budget
        or execution_schedule.evaluation_regime_ref != governed_freeze.freeze.evaluation_regime_ref
    ):
        raise ProposalDispatchGovernanceError(
            "execution schedule differs from the exact governed freeze, K9, H0, or budget",
        )
    validate_evaluation_coordinate(
        coordinate=evaluation_coordinate,
        freeze=governed_freeze.freeze,
    )
    if (
        execution_assignment not in execution_schedule.assignments
        or execution_assignment.candidate != candidate_ref
        or execution_assignment.coordinate != evaluation_coordinate
    ):
        raise ProposalDispatchGovernanceError(
            "execution assignment is outside the exact frozen schedule",
        )
    if (
        compilation.proposal_freeze != governed_freeze.freeze
        or compilation.proposal_freeze.content_sha256 != governed_freeze.freeze.content_sha256
    ):
        raise ProposalDispatchGovernanceError(
            "proposal bundle compilation differs from the governed freeze",
        )
    if (
        compilation.freeze_authority_event_sha256 != stored_freeze.event.content_sha256
        or stored_freeze.event != governed_freeze.authority_event
    ):
        raise ProposalDispatchGovernanceError(
            "proposal bundle compilation differs from the exact freeze authority",
        )


def candidate_is_exactly_frozen(
    *,
    freeze: ProposalFreeze,
    candidate_ref: ProgramCandidateRef,
) -> bool:
    """Return whether a candidate is one of the exact frozen candidates."""

    if candidate_ref.kind is ProgramCandidateKind.INCUMBENT:
        return candidate_ref == freeze.incumbent_candidate
    return candidate_ref in freeze.realized_candidates


def validate_evaluation_coordinate(
    *,
    coordinate: MatchedEvaluationCoordinate,
    freeze: ProposalFreeze,
) -> None:
    """Validate the exact task, split, and review lineage."""

    view = freeze.problem_view
    if (
        coordinate.task_id != view.task_id
        or coordinate.task_revision != view.task_revision
        or coordinate.split is not freeze.split
        or coordinate.review_lineage_id != freeze.selected_review_lineage_id
    ):
        raise ProposalDispatchGovernanceError(
            "evaluation coordinate differs from the governed task, split, or review lineage",
        )
