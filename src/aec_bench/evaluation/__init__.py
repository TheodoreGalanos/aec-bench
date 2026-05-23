# ABOUTME: Evaluation package for scoring, trace analysis, and confidence enrichment in aec-bench.
# ABOUTME: Most modules here are intended to remain pure computation over trial artefacts.

from aec_bench.evaluation.aggregation import (
    BehavioralTrialSummary,
    build_behavioral_trial_summaries,
    summarize_behavioral_records,
)
from aec_bench.evaluation.behavioral import (
    BOND_TAXONOMY,
    BehavioralClassificationError,
    BondType,
    ClassifiedTrace,
    LLMTurnClassifier,
    StructuralScore,
    TransitionMatrix,
    TurnClassification,
    build_ideal_pattern,
    build_ideal_sequence,
    build_transition_matrix,
    load_behavioral_trace,
    score_trace_structural,
)
from aec_bench.evaluation.confidence import summarize_behavioral_confidence
from aec_bench.evaluation.llm_judge import judge_dimension, judge_dimensions
from aec_bench.evaluation.pipeline import (
    AutomatedJudgmentReadiness,
    assess_automated_judgment_readiness,
    summarize_evaluation_records,
)
from aec_bench.evaluation.rubric_scorer import score_rubric
from aec_bench.evaluation.stats import cohen_kappa, mean, wilson_confidence_interval

__all__ = [
    "BOND_TAXONOMY",
    "BehavioralClassificationError",
    "BondType",
    "AutomatedJudgmentReadiness",
    "BehavioralTrialSummary",
    "ClassifiedTrace",
    "LLMTurnClassifier",
    "StructuralScore",
    "TransitionMatrix",
    "TurnClassification",
    "build_behavioral_trial_summaries",
    "build_ideal_pattern",
    "build_ideal_sequence",
    "build_transition_matrix",
    "cohen_kappa",
    "judge_dimension",
    "judge_dimensions",
    "load_behavioral_trace",
    "mean",
    "score_rubric",
    "score_trace_structural",
    "assess_automated_judgment_readiness",
    "summarize_behavioral_confidence",
    "summarize_behavioral_records",
    "summarize_evaluation_records",
    "wilson_confidence_interval",
]
