# ABOUTME: Constitutional harness contract — typed parameter models for the five principles.
# ABOUTME: Governs context filtering, compaction, scaffolding, and anti-hallucination behaviour.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


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

    Principles are always listed. Parameter models are None when they
    should be inferred by the LLM at adapter init, and populated when
    the user has provided explicit overrides.
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


try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]


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

    Unspecified parameter tables mean "infer at runtime" (None).
    """
    data = tomllib.loads(toml_str)

    version = data.get("version", "0.1.0")

    principles: list[ConstitutionalPrinciple] = []
    for p_data in data.get("principles", []):
        principles.append(
            ConstitutionalPrinciple(
                name=p_data["name"],
                description=p_data["description"],
                evaluation_criteria=p_data["evaluation_criteria"],
                enabled=p_data.get("enabled", True),
            )
        )

    information_minimality: InformationMinimalityParams | None = None
    im_data = data.get("information_minimality")
    if im_data is not None:
        information_minimality = InformationMinimalityParams(
            default_threshold=im_data.get("default_threshold", 2000),
            search_threshold=im_data.get("search_threshold", 10_000),
            preview_length=im_data.get("preview_length", 200),
            truncation_strategy=im_data.get("truncation_strategy", "metadata"),
        )

    state_persistence: StatePersistenceParams | None = None
    sp_data = data.get("state_persistence")
    if sp_data is not None:
        state_persistence = StatePersistenceParams(
            preserve_variables=sp_data.get("preserve_variables", True),
            preserve_scratchpad=sp_data.get("preserve_scratchpad", True),
            compaction_strategy=sp_data.get("compaction_strategy", "llm_summary"),
        )

    progress_obligation: ProgressObligationParams | None = None
    po_data = data.get("progress_obligation")
    if po_data is not None:
        progress_obligation = ProgressObligationParams(
            gentle_nudge_turns=po_data.get("gentle_nudge_turns", 10),
            strong_nudge_turns=po_data.get("strong_nudge_turns", 20),
            stall_threshold_turns=po_data.get("stall_threshold_turns", 3),
        )

    source_fidelity: SourceFidelityParams | None = None
    sf_data = data.get("source_fidelity")
    if sf_data is not None:
        source_fidelity = SourceFidelityParams(
            require_source_tracing=sf_data.get("require_source_tracing", True),
            tbd_placeholder=sf_data.get("tbd_placeholder", "[TBD]"),
            gap_framing=sf_data.get("gap_framing", "exclude"),
        )

    earned_autonomy: EarnedAutonomyParams | None = None
    ea_data = data.get("earned_autonomy")
    if ea_data is not None:
        earned_autonomy = EarnedAutonomyParams(
            initial_mode=ea_data.get("initial_mode", "constrained"),
            promotion_threshold=ea_data.get("promotion_threshold", 2),
            demotion_on_stall=ea_data.get("demotion_on_stall", True),
        )

    return ConstitutionManifest(
        version=version,
        principles=principles,
        information_minimality=information_minimality,
        state_persistence=state_persistence,
        progress_obligation=progress_obligation,
        source_fidelity=source_fidelity,
        earned_autonomy=earned_autonomy,
    )
