# ABOUTME: Tests phase-neutral evaluation-generation terminal and retirement contracts.
# ABOUTME: Proves lifecycle variants reject nullable-state ambiguity and preserve exact joins.

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from pydantic import TypeAdapter, ValidationError

from aec_bench.contracts.evaluation_generation.cohort import EvaluationCohortBinding, EvaluationCohortRetirement
from aec_bench.contracts.evaluation_generation.lifecycle import (
    CandidateBatchRejectionClosure,
    EvaluationCriticRetirementRef,
    EvaluationGenerationClosure,
    EvaluationGenerationEvidenceRef,
    EvaluationGenerationEvidenceRole,
    EvaluationGenerationRetirementClosure,
    GovernedBatchExecutionClosure,
    ProposalGenerationClosure,
)
from aec_bench.contracts.evaluation_refs import CriticRole
from tests.support.evaluation_regimes import fake_regime_ref


@dataclass(frozen=True)
class _PreparedView:
    content_sha256: str
    cohort_binding: EvaluationCohortBinding


@dataclass(frozen=True)
class _BatchView:
    content_sha256: str
    ordered_assignment_sha256s: tuple[str, ...]


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _evidence(
    role: EvaluationGenerationEvidenceRole,
    label: str,
) -> EvaluationGenerationEvidenceRef:
    return EvaluationGenerationEvidenceRef(
        artifact_id=f"artifact.{label}",
        role=role,
        schema_version=f"test.{label}.v1",
        content_sha256=_sha(label),
    )


def _generation_views() -> tuple[_PreparedView, _BatchView]:
    prepared = _PreparedView(
        content_sha256=_sha("prepared-generation"),
        cohort_binding=EvaluationCohortBinding(
            cohort_id="cohort.generic",
            evaluation_generation="generation.generic",
            cohort_sha256=_sha("cohort"),
            release_authority_event_sha256=_sha("cohort-release"),
        ),
    )
    batch = _BatchView(
        content_sha256=_sha("batch-plan"),
        ordered_assignment_sha256s=(
            _sha("assignment.1"),
            _sha("assignment.2"),
        ),
    )
    return prepared, batch


def test_terminal_variants_round_trip_without_nullable_state_bags() -> None:
    prepared, batch = _generation_views()
    source = _evidence(
        EvaluationGenerationEvidenceRole.SOURCE_TERMINAL,
        "source-terminal",
    )
    closures: tuple[EvaluationGenerationClosure, ...] = (
        ProposalGenerationClosure(
            execution_id="execution.proposal-failed",
            status="failed",
            prepared_generation_sha256=prepared.content_sha256,
            proposal_result_sha256s=(_sha("proposal-result"),),
            source_terminal=source,
            completed_at=datetime(2026, 7, 25, tzinfo=UTC),
        ),
        CandidateBatchRejectionClosure(
            execution_id="execution.compile-rejected",
            prepared_generation_sha256=prepared.content_sha256,
            batch_plan_sha256=batch.content_sha256,
            rejected_assignment_sha256s=(batch.ordered_assignment_sha256s[0],),
            source_terminal=source,
            completed_at=datetime(2026, 7, 25, tzinfo=UTC),
        ),
        GovernedBatchExecutionClosure(
            execution_id="execution.completed",
            status="completed",
            prepared_generation_sha256=prepared.content_sha256,
            batch_plan_sha256=batch.content_sha256,
            ordered_assignment_terminal_sha256s=tuple(
                _sha(f"terminal.{index}")
                for index, _ in enumerate(
                    batch.ordered_assignment_sha256s,
                )
            ),
            execution_evidence=_evidence(
                EvaluationGenerationEvidenceRole.BATCH_EXECUTION,
                "batch-execution",
            ),
            source_terminal=source,
            completed_at=datetime(2026, 7, 25, tzinfo=UTC),
        ),
    )
    adapter = TypeAdapter(EvaluationGenerationClosure)

    assert tuple(adapter.validate_json(adapter.dump_json(closure)) for closure in closures) == closures
    assert {closure.closure_kind for closure in closures} == {
        "proposal_generation",
        "batch_rejection",
        "batch_execution",
    }


def test_completed_batch_terminal_requires_exact_execution_role() -> None:
    prepared, batch = _generation_views()
    arguments = {
        "execution_id": "execution.completed",
        "status": "completed",
        "prepared_generation_sha256": prepared.content_sha256,
        "batch_plan_sha256": batch.content_sha256,
        "ordered_assignment_terminal_sha256s": tuple(
            _sha(f"terminal.{index}") for index, _ in enumerate(batch.ordered_assignment_sha256s)
        ),
        "execution_evidence": _evidence(
            EvaluationGenerationEvidenceRole.BATCH_EXECUTION,
            "execution",
        ),
        "source_terminal": _evidence(
            EvaluationGenerationEvidenceRole.SOURCE_TERMINAL,
            "source",
        ),
        "completed_at": datetime(2026, 7, 25, tzinfo=UTC),
    }

    assert GovernedBatchExecutionClosure(**arguments).status == "completed"

    with pytest.raises(ValidationError, match="batch-execution"):
        GovernedBatchExecutionClosure(
            **{
                **arguments,
                "execution_evidence": _evidence(
                    EvaluationGenerationEvidenceRole.CRITIC_RETIREMENT,
                    "wrong-role",
                ),
            },
        )


def test_retirement_closure_requires_exact_cohort_and_critic_roles() -> None:
    prepared, batch = _generation_views()
    execution = GovernedBatchExecutionClosure(
        execution_id="execution.completed",
        status="completed",
        prepared_generation_sha256=prepared.content_sha256,
        batch_plan_sha256=batch.content_sha256,
        ordered_assignment_terminal_sha256s=tuple(
            _sha(f"terminal.{index}") for index, _ in enumerate(batch.ordered_assignment_sha256s)
        ),
        execution_evidence=_evidence(
            EvaluationGenerationEvidenceRole.BATCH_EXECUTION,
            "execution",
        ),
        source_terminal=_evidence(
            EvaluationGenerationEvidenceRole.SOURCE_TERMINAL,
            "source",
        ),
        completed_at=datetime(2026, 7, 25, tzinfo=UTC),
    )
    critic_retirements = tuple(
        EvaluationCriticRetirementRef(
            critic={
                "regime": fake_regime_ref(),
                "critic_id": f"critic.{role.value}",
                "role": role,
            },
            retirement_authority_event_sha256=_sha(
                f"authority.{role.value}",
            ),
            evidence=_evidence(
                EvaluationGenerationEvidenceRole.CRITIC_RETIREMENT,
                f"retirement.{role.value}",
            ),
        )
        for role in (
            CriticRole.DEVELOPMENT,
            CriticRole.ACCEPTANCE,
        )
    )

    retirement = EvaluationGenerationRetirementClosure(
        retirement_id="retirement.evaluation-generation",
        generation_closure_sha256=execution.content_sha256,
        cohort_retirement=EvaluationCohortRetirement(
            retirement_id="retirement.cohort",
            cohort=prepared.cohort_binding,
        ),
        cohort_retirement_evidence=_evidence(
            EvaluationGenerationEvidenceRole.COHORT_RETIREMENT,
            "cohort-retirement",
        ),
        required_critic_roles=(
            CriticRole.ACCEPTANCE,
            CriticRole.DEVELOPMENT,
        ),
        critic_retirements=critic_retirements,
        acceptance_manifest_reveal=_evidence(
            EvaluationGenerationEvidenceRole.ACCEPTANCE_MANIFEST_REVEAL,
            "acceptance-reveal",
        ),
    )

    assert retirement.required_critic_roles == (
        CriticRole.DEVELOPMENT,
        CriticRole.ACCEPTANCE,
    )
    assert tuple(item.critic.role for item in retirement.critic_retirements) == (
        CriticRole.DEVELOPMENT,
        CriticRole.ACCEPTANCE,
    )

    with pytest.raises(ValidationError, match="critic roles"):
        EvaluationGenerationRetirementClosure(
            **{
                **retirement.model_dump(
                    mode="python",
                    exclude={"content_sha256"},
                ),
                "required_critic_roles": (CriticRole.ACCEPTANCE,),
            }
        )
