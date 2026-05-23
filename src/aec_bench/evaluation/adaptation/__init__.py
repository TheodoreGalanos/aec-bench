# ABOUTME: Adaptation evaluation subpackage for provenance-preserving task-family variation.
# ABOUTME: Exposes metadata, expansion, and acceptance policy surfaces.

from aec_bench.contracts.adaptation import (
    AdaptationCandidate,
    AdaptationSpec,
    DerivationStep,
    VariationAxis,
    expand_adaptation_spec,
)
from aec_bench.evaluation.adaptation.acceptance import (
    AcceptanceBand,
    AcceptanceBandSummary,
    AcceptanceDecision,
    AcceptanceThresholds,
    classify_adaptation_trial,
    summarize_acceptance_bands,
)
from aec_bench.evaluation.adaptation.artifact_bundle import (
    AdaptationArtifactBundle,
    build_adaptation_artifact_bundle,
    export_adaptation_artifact_bundle_json,
)

__all__ = [
    "AcceptanceBand",
    "AcceptanceBandSummary",
    "AcceptanceDecision",
    "AcceptanceThresholds",
    "AdaptationArtifactBundle",
    "AdaptationCandidate",
    "AdaptationSpec",
    "DerivationStep",
    "VariationAxis",
    "build_adaptation_artifact_bundle",
    "classify_adaptation_trial",
    "expand_adaptation_spec",
    "export_adaptation_artifact_bundle_json",
    "summarize_acceptance_bands",
]
