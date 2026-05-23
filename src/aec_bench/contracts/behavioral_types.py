# ABOUTME: Pure data types for behavioral trace classification.
# ABOUTME: Provides bond-type enums and frozen dataclasses used by both contracts and evaluation.

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum


class BondType(StrEnum):
    EXECUTION = "execution"
    VERIFICATION = "verification"
    DELIBERATION = "deliberation"
    EXPLORATION = "exploration"


@dataclass(frozen=True)
class TurnClassification:
    turn_index: int
    bond_type: BondType
    confidence: float
    rationale: str = ""


@dataclass(frozen=True)
class ClassifiedTrace:
    trace_id: str
    model_name: str
    classifications: tuple[TurnClassification, ...]
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class StructuralScore:
    trace_id: str
    cosine_similarity: float
    edit_distance: int
    normalized_edit_distance: float
    reward: float | None = None
