# ABOUTME: Verifies the stable evaluation-governance contracts are public package exports.
# ABOUTME: Keeps host runtime modules private while making durable boundary models importable.

from __future__ import annotations

import aec_bench.contracts as contracts
from aec_bench.contracts import (
    AuthorityEvent,
    CriticEvaluationOutcome,
    CriticReleaseAuthorityRef,
    CriticSpec,
    EvaluationOutcome,
    EvaluationPlanAuthorityScope,
    EvaluationPlanRef,
    HumanAuthorityApproval,
    MotifPromotionAssurance,
    MotifPromotionQualification,
    PromotionMonitorAttestation,
    PromotionSubjectLineage,
    SelectionNullEstimate,
)


def test_evaluation_governance_boundary_contracts_are_public() -> None:
    exported = set(contracts.__all__)

    assert {
        AuthorityEvent.__name__,
        CriticEvaluationOutcome.__name__,
        CriticReleaseAuthorityRef.__name__,
        CriticSpec.__name__,
        EvaluationOutcome.__name__,
        EvaluationPlanAuthorityScope.__name__,
        EvaluationPlanRef.__name__,
        HumanAuthorityApproval.__name__,
        MotifPromotionAssurance.__name__,
        MotifPromotionQualification.__name__,
        PromotionMonitorAttestation.__name__,
        PromotionSubjectLineage.__name__,
        SelectionNullEstimate.__name__,
    }.issubset(exported)
