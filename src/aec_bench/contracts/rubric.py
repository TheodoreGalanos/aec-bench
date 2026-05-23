# ABOUTME: Contract types for rubric-based evaluation of complex benchmark tasks.
# ABOUTME: Defines dimension scoring, weighted rollup, and mixed eval methods.

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import ConfigDict

from aec_bench.contracts.validators import StrictModel


class RubricCriterion(StrictModel):
    """A single binary criterion within a rubric dimension."""

    model_config = ConfigDict(frozen=True)

    text: str
    category: str  # "essential", "important", "optional"


# Category weights for binary scoring rollup
CATEGORY_WEIGHTS: dict[str, float] = {
    "essential": 1.0,
    "important": 0.7,
    "optional": 0.3,
}


class RubricDimension(StrictModel):
    """Definition of a single scoring dimension within a rubric."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    description: str
    weight: float
    max_score: float
    eval_method: str  # "automated" or "llm_judge"
    criteria: Sequence[RubricCriterion] = ()
    eval_sections: Sequence[str] = ()  # output sections to evaluate (empty = all)
    eval_references: Sequence[str] = ()  # reference doc keys to include (empty = all)
    expert_persona: str = ""  # specialised judge system prompt


class Rubric(StrictModel):
    """Evaluation rubric with multiple scoring dimensions and rollup strategy."""

    model_config = ConfigDict(frozen=True)

    dimensions: Sequence[RubricDimension]
    rollup_strategy: str = "weighted_mean"


class DimensionScore(StrictModel):
    """Actual score for a single rubric dimension."""

    model_config = ConfigDict(frozen=True)

    dimension_id: str
    score: float
    max_score: float
    evidence: str = ""
    eval_method_used: str = ""
    satisfied: Sequence[str] = ()
    unsatisfied: Sequence[str] = ()


class RubricResult(StrictModel):
    """Complete rubric evaluation result with per-dimension breakdown."""

    model_config = ConfigDict(frozen=True)

    dimension_scores: Sequence[DimensionScore]
    reward: float
    rollup_strategy: str = "weighted_mean"

    def to_details(self) -> dict[str, Any]:
        """Convert to a details dict for writing to details.json."""
        details: dict[str, Any] = {"reward": self.reward}
        for ds in self.dimension_scores:
            details[ds.dimension_id] = {
                "score": ds.score,
                "max_score": ds.max_score,
                "evidence": ds.evidence,
                "eval_method": ds.eval_method_used,
                "satisfied": list(ds.satisfied),
                "unsatisfied": list(ds.unsatisfied),
            }
        return details
