# ABOUTME: Constitutional harness contract — typed parameter models for the five principles.
# ABOUTME: Governs context filtering, compaction, scaffolding, and anti-hallucination behaviour.

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class InformationMinimalityParams:
    """Parameters for the Information Minimality principle.

    Controls what the agent sees in conversation history vs what stays
    in REPL state. Governs context_filter.py behaviour.
    """

    default_threshold: int = 2000
    search_threshold: int = 10_000
    preview_length: int = 200
    truncation_strategy: Literal["metadata", "head", "tail"] = "metadata"


@dataclass(frozen=True)
class StatePersistenceParams:
    """Parameters for the State Persistence principle.

    Controls what survives compaction and how durable state is oriented.
    Governs compaction.py behaviour.
    """

    preserve_variables: bool = True
    preserve_scratchpad: bool = True
    compaction_strategy: Literal["llm_summary", "state_only", "full_reset"] = "llm_summary"


@dataclass(frozen=True)
class ProgressObligationParams:
    """Parameters for the Progress Obligation principle.

    Controls scaffolding nudges and stall detection.
    Governs scaffolding.py tier thresholds.
    """

    gentle_nudge_turns: int = 10
    strong_nudge_turns: int = 20
    stall_threshold_turns: int = 3


@dataclass(frozen=True)
class SourceFidelityParams:
    """Parameters for the Source Fidelity principle.

    Controls anti-hallucination enforcement in generation prompts.
    Governs system prompt anti-fabrication block and gap framing.
    """

    require_source_tracing: bool = True
    tbd_placeholder: str = "[TBD]"
    gap_framing: Literal["exclude", "tbd", "omit"] = "exclude"


@dataclass(frozen=True)
class EarnedAutonomyParams:
    """Parameters for the Earned Autonomy principle.

    Controls adaptive constraint relaxation during execution.
    Minimal in v1; affects starting scaffolding aggressiveness only.
    """

    initial_mode: Literal["constrained", "guided", "autonomous"] = "constrained"
    promotion_threshold: int = 2
    demotion_on_stall: bool = True


@dataclass(frozen=True)
class ConstitutionalPrinciple:
    """A single constitutional principle governing harness behaviour."""

    name: str
    description: str
    evaluation_criteria: str
    enabled: bool = True


@dataclass(frozen=True)
class ConstitutionManifest:
    """The complete constitution for an adapter run.

    Principles are always listed. Parameter models are None when the runtime uses its
    defaults, and populated when the user supplies explicit overrides.
    """

    version: str
    principles: list[ConstitutionalPrinciple] = field(default_factory=list)
    information_minimality: InformationMinimalityParams | None = None
    state_persistence: StatePersistenceParams | None = None
    progress_obligation: ProgressObligationParams | None = None
    source_fidelity: SourceFidelityParams | None = None
    earned_autonomy: EarnedAutonomyParams | None = None

    def enabled_principle_names(self) -> list[str]:
        """Return names of principles with enabled=True."""
        return [p.name for p in self.principles if p.enabled]


def parse_constitution(toml_str: str) -> ConstitutionManifest:
    """Parse a constitution TOML string into a ConstitutionManifest.

    Expected TOML schema:
      version = "0.1.0"
      [[principles]]
      name = "..."
      description = "..."
      evaluation_criteria = "..."
      enabled = true  # optional, default true

      [information_minimality]  # optional parameter overrides
      default_threshold = 3000
      ...

    Unspecified parameter tables leave the runtime defaults in place (None).
    """
    return parse_constitution_data(tomllib.loads(toml_str))


def parse_constitution_data(data: dict[str, Any]) -> ConstitutionManifest:
    """Validate a declared constitution without a TOML string round trip."""
    from dataclasses import fields

    from pydantic import TypeAdapter

    allowed = {f.name for f in fields(ConstitutionManifest)}
    if unknown := data.keys() - allowed:
        raise ValueError(f"Unknown constitution options: {sorted(unknown)}")
    parameter_types = {
        "information_minimality": InformationMinimalityParams,
        "state_persistence": StatePersistenceParams,
        "progress_obligation": ProgressObligationParams,
        "source_fidelity": SourceFidelityParams,
        "earned_autonomy": EarnedAutonomyParams,
    }
    for name, cls in parameter_types.items():
        value = data.get(name)
        if isinstance(value, dict) and (unknown := value.keys() - {f.name for f in fields(cls)}):
            raise ValueError(f"Unknown constitution.{name} options: {sorted(unknown)}")
    for principle in data.get("principles", []):
        if isinstance(principle, dict) and (
            unknown := principle.keys() - {f.name for f in fields(ConstitutionalPrinciple)}
        ):
            raise ValueError(f"Unknown principle options: {sorted(unknown)}")
    manifest = TypeAdapter(ConstitutionManifest).validate_python({"version": "0.1.0", **data})
    info = manifest.information_minimality
    if info and not all(
        0 < value <= 1_000_000 for value in (info.default_threshold, info.search_threshold, info.preview_length)
    ):
        raise ValueError("Information minimality limits must be in [1, 1000000]")
    progress = manifest.progress_obligation
    if progress and not (
        0 < progress.gentle_nudge_turns <= progress.strong_nudge_turns and progress.stall_threshold_turns > 0
    ):
        raise ValueError("Invalid progress obligation thresholds")
    if manifest.earned_autonomy and manifest.earned_autonomy.promotion_threshold <= 0:
        raise ValueError("Autonomy promotion_threshold must be positive")
    return manifest
