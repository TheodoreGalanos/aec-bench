# ABOUTME: Pure analysis functions for evolution observations — discipline scoring and patterns.
# ABOUTME: Provides compute_discipline_scores, detect_behavioral_patterns, compute_graduated_scope.

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from aec_bench.contracts.evolution import DisciplineScore, EvolutionObservation


class GraduatedScope(StrEnum):
    """Level of analysis depth to apply for an evolution cycle."""

    SKIP = "skip"
    MINIMAL = "minimal"
    TARGETED = "targeted"
    COMPREHENSIVE = "comprehensive"


@dataclass(frozen=True)
class BehavioralPattern:
    """A recurring anti-pattern detected across failed evolution observations."""

    name: str
    count: int
    description: str
    affected_trial_ids: tuple[str, ...]


@dataclass(frozen=True)
class AnalysisResult:
    """Aggregate result of an analysis pass over a batch of observations."""

    discipline_scores: list[DisciplineScore]
    behavioral_patterns: list[BehavioralPattern]
    scope: GraduatedScope
    weakest_discipline: str | None
    batch_score: float


# ---------------------------------------------------------------------------
# Analysis functions
# ---------------------------------------------------------------------------


def compute_discipline_scores(
    observations: Sequence[EvolutionObservation],
) -> list[DisciplineScore]:
    """Compute aggregate performance metrics grouped by discipline.

    Returns a list of DisciplineScore entries, one per discipline, sorted
    alphabetically by discipline name. mean_structural_similarity is always
    None — structural similarity is not computed here.
    """
    if not observations:
        return []

    # Group observations by discipline
    groups: dict[str, list[EvolutionObservation]] = {}
    for obs in observations:
        groups.setdefault(obs.discipline, []).append(obs)

    scores: list[DisciplineScore] = []
    for discipline, obs_list in sorted(groups.items()):
        task_count = len(obs_list)
        mean_reward = sum(obs.trial.evaluation.reward for obs in obs_list) / task_count

        # field_pass_rate: proportion of all field_scores with reward >= 1.0
        all_field_scores = [fs for obs in obs_list for fs in obs.enrichment.field_scores]
        if all_field_scores:
            passing = sum(1 for fs in all_field_scores if fs.reward >= 1.0)
            field_pass_rate = passing / len(all_field_scores)
        else:
            field_pass_rate = 0.0

        scores.append(
            DisciplineScore(
                discipline=discipline,
                task_count=task_count,
                mean_reward=mean_reward,
                field_pass_rate=field_pass_rate,
                mean_structural_similarity=None,
            )
        )

    return scores


def detect_behavioral_patterns(
    observations: Sequence[EvolutionObservation],
    min_count: int = 2,
) -> list[BehavioralPattern]:
    """Detect recurring anti-patterns in failed observations (reward < 0.8).

    Five anti-patterns are checked:
    - blind_action: bond_sequence contains 4+ consecutive E bonds ("E-E-E-E")
    - no_verification: bond_sequence has no "V" character
    - analysis_paralysis: 3+ consecutive X or D bonds without an E
    - redundant_verification: 3+ consecutive V bonds — over-checking without progress
    - no_exploration: sequence starts with "E" and no "X" appears before the first "E"

    Only observations with a trace_digest are considered. Returns a list of
    BehavioralPattern instances for patterns that meet the min_count threshold.
    """
    failed = [
        obs for obs in observations if obs.trial.evaluation.reward < 0.8 and obs.enrichment.trace_digest is not None
    ]

    blind_action_ids: list[str] = []
    no_verification_ids: list[str] = []
    analysis_paralysis_ids: list[str] = []
    redundant_verification_ids: list[str] = []
    no_exploration_ids: list[str] = []

    for obs in failed:
        digest = obs.enrichment.trace_digest
        assert digest is not None  # guaranteed by filter above
        seq = digest.bond_sequence
        trial_id = obs.trial.trial_id

        # blind_action: 4+ consecutive E bonds
        if _has_consecutive_bonds(seq, "E", min_run=4):
            blind_action_ids.append(trial_id)

        # no_verification: no V in the sequence
        if "V" not in seq:
            no_verification_ids.append(trial_id)

        # analysis_paralysis: 3+ consecutive non-exec bonds (X or D) without E
        if _has_analysis_paralysis(seq, min_run=3):
            analysis_paralysis_ids.append(trial_id)

        # redundant_verification: 3+ consecutive V bonds
        if _has_redundant_verification(seq, min_run=3):
            redundant_verification_ids.append(trial_id)

        # no_exploration: starts with E and no X appears before the first E
        if _has_no_exploration(seq):
            no_exploration_ids.append(trial_id)

    patterns: list[BehavioralPattern] = []

    if len(blind_action_ids) >= min_count:
        patterns.append(
            BehavioralPattern(
                name="blind_action",
                count=len(blind_action_ids),
                description=("Agent executes 4+ consecutive actions without verification or reflection"),
                affected_trial_ids=tuple(blind_action_ids),
            )
        )

    if len(no_verification_ids) >= min_count:
        patterns.append(
            BehavioralPattern(
                name="no_verification",
                count=len(no_verification_ids),
                description="Agent never verifies its work — no V bond in trace",
                affected_trial_ids=tuple(no_verification_ids),
            )
        )

    if len(analysis_paralysis_ids) >= min_count:
        patterns.append(
            BehavioralPattern(
                name="analysis_paralysis",
                count=len(analysis_paralysis_ids),
                description=("Agent spends 3+ consecutive turns deliberating or exploring without acting"),
                affected_trial_ids=tuple(analysis_paralysis_ids),
            )
        )

    if len(redundant_verification_ids) >= min_count:
        patterns.append(
            BehavioralPattern(
                name="redundant_verification",
                count=len(redundant_verification_ids),
                description="Agent re-checks the same results 3+ times without making progress",
                affected_trial_ids=tuple(redundant_verification_ids),
            )
        )

    if len(no_exploration_ids) >= min_count:
        patterns.append(
            BehavioralPattern(
                name="no_exploration",
                count=len(no_exploration_ids),
                description=("Agent jumps straight to execution without first exploring or reading the task"),
                affected_trial_ids=tuple(no_exploration_ids),
            )
        )

    return patterns


def compute_graduated_scope(batch_score: float, improving: bool) -> GraduatedScope:
    """Map a batch score and improvement flag to the appropriate analysis scope.

    Decision table:
        batch_score >= 0.90 and not improving -> SKIP
        batch_score >= 0.90 and improving     -> MINIMAL
        batch_score >= 0.80                   -> TARGETED
        batch_score <  0.80                   -> COMPREHENSIVE
    """
    if batch_score >= 0.90:
        return GraduatedScope.MINIMAL if improving else GraduatedScope.SKIP
    if batch_score >= 0.80:
        return GraduatedScope.TARGETED
    return GraduatedScope.COMPREHENSIVE


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _has_consecutive_bonds(seq: str, bond: str, min_run: int) -> bool:
    """Return True if *bond* appears at least *min_run* times in a row in *seq*.

    The sequence is a hyphen-separated string like "E-E-E-V-D".
    """
    if not seq:
        return False
    bonds = seq.split("-")
    run = 0
    for b in bonds:
        if b == bond:
            run += 1
            if run >= min_run:
                return True
        else:
            run = 0
    return False


def _has_analysis_paralysis(seq: str, min_run: int) -> bool:
    """Return True if the sequence has *min_run* consecutive X or D bonds without E.

    Consecutive non-exec runs reset when an E bond appears.
    """
    if not seq:
        return False
    bonds = seq.split("-")
    run = 0
    for b in bonds:
        if b in ("X", "D"):
            run += 1
            if run >= min_run:
                return True
        else:
            run = 0
    return False


def _has_redundant_verification(seq: str, min_run: int) -> bool:
    """Return True if the sequence contains *min_run* or more consecutive V bonds.

    Detects over-checking behaviour where the agent re-verifies the same result
    repeatedly without making forward progress.
    """
    if not seq:
        return False
    # Build a regex that matches min_run consecutive V bonds: V(-V){min_run-1,}
    pattern = r"V(?:-V){" + str(min_run - 1) + r",}"
    return bool(re.search(pattern, seq))


def _has_no_exploration(seq: str) -> bool:
    """Return True if the agent starts executing without any prior exploration.

    Triggers when the bond sequence starts with "E" AND no "X" bond appears
    before the first "E". A leading X (or any non-E start) disqualifies the
    sequence.
    """
    if not seq:
        return False
    bonds = seq.split("-")
    if bonds[0] != "E":
        return False
    # Check whether X appears before the first E — since bonds[0] IS "E",
    # there is nothing before the first E, so the condition always holds here.
    # Any sequence starting with "E" qualifies unless X precedes it (impossible
    # since bonds[0] == "E" means nothing comes before it).
    return True
