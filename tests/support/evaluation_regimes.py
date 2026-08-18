# ABOUTME: Builds compact evaluation regimes and references for contract tests.
# ABOUTME: Keeps test fixtures on the published-regime contract instead of component hash matrices.

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.evaluation_plane import (
    AcceptanceManifestCommitment,
    AcceptancePolicy,
    CalibrationPolicy,
    Critic,
    CriticFeedbackVisibility,
    DenominatorPolicy,
    EligibilityPolicy,
    EvaluationBudget,
    EvaluationBudgetPartition,
    EvaluationRegime,
    EvidencePolicy,
    MonitoringPolicy,
    RepositoryCriticSource,
    StoppingPolicy,
)
from aec_bench.contracts.evaluation_refs import CriticRole, EvaluationRegimeRef
from aec_bench.evaluation.regime import EVALUATION_REGIME_MEDIA_TYPE, publish_evaluation_regime
from aec_bench.ledger.artifact_repository import ArtifactRepository


def sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def make_regime(*, regime_id: str = "evaluation.standard", **changes: Any) -> EvaluationRegime:
    partition = EvaluationBudgetPartition(
        case_count=8,
        max_attempts=8,
        max_turns=32,
        max_tokens=100_000,
        max_cost_usd=1.0,
        max_wall_time_seconds=600.0,
    )
    commitment = AcceptanceManifestCommitment.create(
        critic_id="critic.acceptance",
        case_manifest={"case_ids": ["hidden-01", "hidden-02"]},
        scoring_policy={"threshold": 0.8},
        salt="test-acceptance-salt",
    )
    regime = EvaluationRegime(
        regime_id=regime_id,
        critics=(
            Critic(
                critic_id="critic.development",
                role=CriticRole.DEVELOPMENT,
                source=RepositoryCriticSource(
                    source_revision="1" * 40,
                    entrypoint="aec_bench.evaluation.rubric_scorer",
                ),
                configuration={"rubric": "shared", "cases": ["public-01"]},
                feedback_visibility=CriticFeedbackVisibility.VISIBLE,
                execution_principal_id="principal.development",
            ),
            Critic(
                critic_id="critic.acceptance",
                role=CriticRole.ACCEPTANCE,
                source=RepositoryCriticSource(
                    source_revision="1" * 40,
                    entrypoint="aec_bench.evaluation.rubric_scorer",
                ),
                configuration={"runtime_mode": "host_only"},
                feedback_visibility=CriticFeedbackVisibility.HOST_ONLY,
                execution_principal_id="principal.acceptance",
                acceptance_manifest_commitment=commitment,
            ),
        ),
        budget=EvaluationBudget(
            proposal=partition,
            execution=partition,
            development=partition,
            acceptance=partition,
            red_team=partition,
            monitor=partition,
            audit=partition,
        ),
        acceptance_policy=AcceptancePolicy(policy_id="acceptance.standard", configuration={"threshold": 0.8}),
        eligibility_policy=EligibilityPolicy(
            policy_id="eligibility.complete-evidence",
            configuration={"require_complete_evidence": True},
        ),
        denominator_policy=DenominatorPolicy(
            policy_id="denominator.all-planned",
            configuration={"population": "all_planned_cases"},
        ),
        evidence_policy=EvidencePolicy(
            policy_id="evidence.authority-owned",
            configuration={"invalid_evidence": "fail"},
        ),
        calibration_policy=CalibrationPolicy(
            policy_id="calibration.executable-anchor",
            configuration={"cadence": "every_critic_release"},
        ),
        stopping_policy=StoppingPolicy(policy_id="stopping.fixed", configuration={"max_rounds": 8}),
        monitoring_policy=MonitoringPolicy(policy_id="monitoring.standard", configuration={"enabled": True}),
    )
    return regime.model_copy(update=changes)


def fake_regime_ref(*, label: str = "evaluation-regime", regime_id: str = "evaluation.standard") -> EvaluationRegimeRef:
    digest = sha(label)
    return EvaluationRegimeRef(
        regime_id=regime_id,
        artifact=ArtifactRef(
            artifact_id=f"artifacts/sha256/{digest[:2]}/{digest}",
            sha256=digest,
            size_bytes=1,
            media_type=EVALUATION_REGIME_MEDIA_TYPE,
        ),
    )


def publish_regime(root: Path, regime: EvaluationRegime | None = None) -> tuple[EvaluationRegimeRef, EvaluationRegime]:
    selected = regime or make_regime()
    return publish_evaluation_regime(ArtifactRepository(root), selected), selected


__all__ = ("fake_regime_ref", "make_regime", "publish_regime", "sha")
