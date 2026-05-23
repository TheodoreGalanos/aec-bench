# ABOUTME: Dataclasses for the lambda-rlm execution plan, operations, and runtime state.
# ABOUTME: All plan types are frozen; PlanState is mutable for tracking execution progress.

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from aec_bench.adapters.lambda_rlm.structure_validator import (
    StructureValidationResult,
)


class CompositionOp(StrEnum):
    """Composition operator applied after leaf extraction for a section."""

    MERGE_EXTRACTIONS = "merge_extractions"
    COMBINE_ANALYSIS = "combine_analysis"
    CONCATENATE = "concatenate"
    SKIP = "skip"

    @classmethod
    def from_generation_mode(cls, mode: str) -> CompositionOp:
        """Map a template generation_mode to a composition operator."""
        mapping = {
            "transform": cls.MERGE_EXTRACTIONS,
            "creative": cls.COMBINE_ANALYSIS,
            "guided": cls.MERGE_EXTRACTIONS,
            "boilerplate": cls.CONCATENATE,
            "external": cls.SKIP,
        }
        return mapping.get(mode, cls.MERGE_EXTRACTIONS)


@dataclass(frozen=True)
class LeafOp:
    """A single leaf extraction call on a (possibly chunked) source."""

    source: str
    chunk_index: int
    total_chunks: int


@dataclass(frozen=True)
class ReduceOp:
    """A reduce call that merges chunked extractions for one source."""

    source: str
    inputs_count: int


@dataclass(frozen=True)
class SectionPlan:
    """Execution plan for a single template section."""

    section_id: str
    generation_mode: str
    sources: list[str]
    leaf_ops: list[LeafOp]
    reduce_ops: list[ReduceOp]
    composition_op: CompositionOp
    estimated_leaf_calls: int
    estimated_reduce_calls: int

    @property
    def estimated_total_calls(self) -> int:
        """Leaf + reduce calls for extraction only (excludes review and generate)."""
        return self.estimated_leaf_calls + self.estimated_reduce_calls


@dataclass(frozen=True)
class ExecutionPlan:
    """Complete execution plan across all sections."""

    section_order: list[str]
    section_plans: dict[str, SectionPlan]
    skipped_sections: list[str]

    @property
    def total_estimated_leaf_calls(self) -> int:
        return sum(p.estimated_leaf_calls for p in self.section_plans.values())

    @property
    def total_estimated_reduce_calls(self) -> int:
        return sum(p.estimated_reduce_calls for p in self.section_plans.values())

    @property
    def active_section_count(self) -> int:
        return len(self.section_order)

    @property
    def total_estimated_calls(self) -> int:
        """All LLM calls: leaf + reduce + review (1 per section) + generate (1 per section)."""
        extraction = self.total_estimated_leaf_calls + self.total_estimated_reduce_calls
        review = self.active_section_count
        generate = self.active_section_count
        return extraction + review + generate


@dataclass(frozen=True)
class ReviewResult:
    """Outcome of a contract review check for one section."""

    status: str
    gaps: list[str]
    risks: list[str]
    reextract_sources: list[str]
    supplement_guidance: str | None

    @property
    def needs_action(self) -> bool:
        return self.status != "pass"


@dataclass
class PlanState:
    """Mutable runtime state tracking execution progress."""

    extractions: dict[str, dict[str, Any]] = field(default_factory=dict)
    reviews: dict[str, ReviewResult] = field(default_factory=dict)
    sections: dict[str, str] = field(default_factory=dict)
    # Per-section composition traces for compose-mode sections. Keys are
    # section IDs; values are lists of BlockTrace-shaped dicts ready for
    # JSON serialisation (see compose_bridge / adapter for the write path).
    composition_traces: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    phase: str = "init"
    current_section: str | None = None
    llm_calls: int = 0
    estimated_calls: int = 0
    tokens_used: int = 0
    estimated_tokens: int = 0
    # Trajectory events from synthesis mode (one per synthesised section). The
    # adapter callback reads the latest entry when event_type=="synthesise".
    synthesis_events: list[dict[str, Any]] = field(default_factory=list)

    # ── Idea 3a: Verbalized confidence ──
    extraction_confidence: dict[str, dict[str, float]] = field(default_factory=dict)
    extraction_confidence_chunks: dict[str, dict[str, list[float]]] = field(
        default_factory=dict,
    )
    extraction_confidence_missing: dict[str, dict[str, str]] = field(
        default_factory=dict,
    )

    # ── Idea 3b: Self-consistency ──
    extraction_consistency: dict[str, dict[str, float]] = field(default_factory=dict)
    extraction_candidates: dict[str, dict[str, list[dict[str, Any]]]] | None = None

    # ── Idea 3c: Trace length / uncertainty ──
    leaf_output_tokens: dict[str, dict[str, list[int]]] = field(default_factory=dict)
    uncertainty_scores: dict[str, dict[str, float]] = field(default_factory=dict)

    # Shared slot store for agentic compose-mode — populated by the
    # planning-phase turn and read by scratchpad-aware SlotResolvers
    # so recurring slots (project_name, site, client_pm, ...) resolve
    # via zero-LLM lookups across compose sections.
    #
    # Reserved keys:
    #   "_back_brief": dict[str, str] — per-topic digest produced by
    #     the back-brief sub-phase; consumed by _format_sources when it
    #     sees a label of the form `references/*:<topic>`.
    #   "_scope_evolution": str — narrative summary of how the client's
    #     ask narrowed across the primary source (typically an email
    #     thread). Surfaced at the top of compose-mode generation
    #     prompts when present.
    compose_scratchpad: dict[str, str | dict[str, str]] = field(default_factory=dict)

    # Whether uncertainty scoring is active (set by executor from config).
    _uncertainty_scoring_active: bool = False
    _uncertainty_population_stats: dict[str, float | int] = field(
        default_factory=lambda: {"mean": 0.0, "stdev": 0.0, "n": 0},
    )

    # ── Idea A: Structure enforcement ──
    structure_retries: dict[str, int] = field(default_factory=dict)
    structure_unresolved: dict[str, StructureValidationResult] = field(
        default_factory=dict,
    )

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-serializable snapshot for trajectory metadata."""
        # Derive by_section confidence as mean of valid source confidences.
        by_section: dict[str, float] = {}
        for sid, sources in self.extraction_confidence.items():
            vals = list(sources.values())
            if vals:
                by_section[sid] = sum(vals) / len(vals)

        return {
            "phase": self.phase,
            "current_section": self.current_section,
            "llm_calls": self.llm_calls,
            "estimated_calls": self.estimated_calls,
            "tokens_used": self.tokens_used,
            "estimated_tokens": self.estimated_tokens,
            "extractions": {
                section_id: {source: _safe_serialize(data) for source, data in sources.items()}
                for section_id, sources in self.extractions.items()
            },
            "reviews": {
                section_id: {
                    "status": review.status,
                    "gaps": review.gaps,
                    "risks": review.risks,
                }
                for section_id, review in self.reviews.items()
            },
            "sections": {
                section_id: content[:200] + "..." if len(content) > 200 else content
                for section_id, content in self.sections.items()
            },
            "confidence": {
                "by_source": dict(self.extraction_confidence),
                "by_section": by_section,
                "chunks": dict(self.extraction_confidence_chunks),
                "missing": dict(self.extraction_confidence_missing),
            },
            "uncertainty": {
                "scoring_active": self._uncertainty_scoring_active,
                "leaf_output_tokens": dict(self.leaf_output_tokens),
                "scores": dict(self.uncertainty_scores),
                "population_stats": dict(self._uncertainty_population_stats),
            },
            "consistency": dict(self.extraction_consistency),
            "compose_scratchpad": dict(self.compose_scratchpad),
            "structure_retries": dict(self.structure_retries),
            "structure_unresolved_count": len(self.structure_unresolved),
        }


def _safe_serialize(obj: Any) -> Any:
    """Best-effort JSON-safe conversion."""
    if isinstance(obj, dict):
        return {k: _safe_serialize(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [_safe_serialize(v) for v in obj]
    if isinstance(obj, str | int | float | bool | type(None)):
        return obj
    return str(obj)
