# ABOUTME: Boundary type for the post-hoc grounding-check report.
# ABOUTME: Observability-only in v1; never affects reward.

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

FactCategory = Literal[
    "url",
    "document_ref",
    "number_with_unit",
    "date",
    "proper_noun_phrase",
]


@dataclass(frozen=True)
class FlaggedFact:
    """A fact in the output that did not trace to any accessed slice."""

    fact: str
    category: FactCategory
    block_index: int
    block_provenance: tuple[str, ...]
    matched_anchors: tuple[str, ...]


@dataclass(frozen=True)
class SectionGroundingResult:
    """Per-section result of the grounding check."""

    section_id: str
    facts_checked: int
    facts_grounded: int
    flagged: tuple[FlaggedFact, ...] = ()


@dataclass(frozen=True)
class GroundingReport:
    """Aggregate report across all sections of a run."""

    sections: tuple[SectionGroundingResult, ...]

    def total_facts_checked(self) -> int:
        return sum(s.facts_checked for s in self.sections)

    def total_facts_grounded(self) -> int:
        return sum(s.facts_grounded for s in self.sections)

    def to_dict(self) -> dict[str, Any]:
        return {"sections": [asdict(s) for s in self.sections]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GroundingReport:
        sections = tuple(
            SectionGroundingResult(
                section_id=s["section_id"],
                facts_checked=s["facts_checked"],
                facts_grounded=s["facts_grounded"],
                flagged=tuple(
                    FlaggedFact(
                        fact=f["fact"],
                        category=f["category"],
                        block_index=f["block_index"],
                        block_provenance=tuple(f["block_provenance"]),
                        matched_anchors=tuple(f["matched_anchors"]),
                    )
                    for f in s.get("flagged", [])
                ),
            )
            for s in data.get("sections", [])
        )
        return cls(sections=sections)


__all__ = [
    "FactCategory",
    "FlaggedFact",
    "GroundingReport",
    "SectionGroundingResult",
]
