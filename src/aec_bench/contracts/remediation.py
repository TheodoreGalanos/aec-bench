# ABOUTME: Contracts for verifier-driven remediation — patches, HITL items, iteration records.
# ABOUTME: Surgical edits with locator-based addressing; structured review queue for unfixable defects.

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal


class PatchStatus(StrEnum):
    """What the applier should do with a proposal."""

    APPLY = "apply"
    REVIEW = "review"
    DEFER = "defer"


@dataclass(frozen=True)
class Patch:
    """A surgical edit located by a unique phrase within a named section."""

    section_id: str
    locator_phrase: str
    replacement: str
    occurrence: int = 1


@dataclass(frozen=True)
class PatchProposal:
    """A patch candidate with the verifier-sourced context that produced it."""

    patch: Patch
    criterion: str
    evidence: str
    rationale: str
    confidence: Literal["high", "medium", "low"]
    status: PatchStatus


@dataclass(frozen=True)
class HitlItem:
    """A structured review-queue entry for a defect that couldn't be auto-fixed."""

    section_id: str
    criterion: str
    evidence: str
    suggested_resolution: str
    attempt_count: int


@dataclass(frozen=True)
class RemediationIteration:
    """Per-iteration record of patches applied and reward change."""

    iteration: int
    patches_applied: int
    patches_rejected: int
    reward_before: float
    reward_after: float

    @property
    def reward_delta(self) -> float:
        return self.reward_after - self.reward_before


@dataclass(frozen=True)
class RemediationResult:
    """Top-level summary of a remediation run."""

    iterations: tuple[RemediationIteration, ...]
    hitl_items: tuple[HitlItem, ...]
    stop_reason: str
    final_reward: float
    final_output_text: str = ""

    @property
    def total_patches_applied(self) -> int:
        return sum(it.patches_applied for it in self.iterations)
