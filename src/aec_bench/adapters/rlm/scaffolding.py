# ABOUTME: Progressive scaffolding footer state machine for the RLM adapter.
# ABOUTME: Appends contextual hints based on constitutional progress + autonomy params.

from __future__ import annotations

from typing import TYPE_CHECKING

from aec_bench.contracts.constitution import (
    EarnedAutonomyParams,
    ProgressObligationParams,
)

if TYPE_CHECKING:
    from aec_bench.adapters.rlm.template import TemplateStatus


class ScaffoldingState:
    """Tracks compaction state and stall detection for progressive scaffolding.

    The footer evolves through tiers:
    1. **Post-compaction** — compaction notice, progress, scratchpad key count.
    2. **Pre-fill strong** — turns >= strong_nudge_turns with 0 sections filled
       (suppressed in 'autonomous' autonomy mode).
    3. **Pre-fill gentle** — turns >= gentle_nudge_turns with 0 sections filled.
    4. **Stalled** — turns >= stall_threshold_turns with no new section.
    5. **Normal** — simple progress count ``[X/Y sections filled]``.

    All thresholds and autonomy mode come from the constitution.
    """

    def __init__(
        self,
        *,
        enabled: bool = True,
        progress_params: ProgressObligationParams | None = None,
        autonomy_params: EarnedAutonomyParams | None = None,
    ) -> None:
        self._enabled = enabled
        self._progress = progress_params or ProgressObligationParams()
        self._autonomy = autonomy_params or EarnedAutonomyParams()
        self._compacted = False
        self._first_post_compaction = True
        self._turns_since_progress = 0
        self._last_completed_count = 0

    def mark_compacted(self) -> None:
        """Signal that a context compaction just happened."""
        self._compacted = True
        self._first_post_compaction = True

    def record_progress(self, completed_count: int) -> None:
        """Update progress tracking after each turn."""
        if completed_count > self._last_completed_count:
            self._turns_since_progress = 0
            self._last_completed_count = completed_count
        else:
            self._turns_since_progress += 1

    def build_footer(
        self,
        *,
        template_status: TemplateStatus | None,
        scratchpad_keys: list[str],
    ) -> str:
        """Build the progressive scaffolding footer string."""
        if not self._enabled or template_status is None:
            return ""

        completed = template_status.completed_sections
        total = template_status.total_sections
        unlocked = template_status.unlocked
        next_section = unlocked[0] if unlocked else None

        # Tier 1: Post-compaction — rich contextual hints
        if self._compacted:
            return self._post_compaction_footer(
                completed,
                total,
                next_section,
                scratchpad_keys,
            )

        # Tier 2/3: Pre-fill nudges — when 0 sections filled after many turns
        if completed == 0 and next_section:
            strong_allowed = self._autonomy.initial_mode != "autonomous"
            if strong_allowed and self._turns_since_progress >= self._progress.strong_nudge_turns:
                return (
                    f"\n[You have spent {self._turns_since_progress} turns gathering data "
                    f"without filling any sections. "
                    f"Stop gathering and start writing NOW. "
                    f"Use START('{next_section}') then FILL('{next_section}', ...) immediately. "
                    f"You have {len(scratchpad_keys)} scratchpad keys "
                    f"— that is enough data to begin.]"
                )
            if self._turns_since_progress >= self._progress.gentle_nudge_turns:
                return (
                    f"\n[{self._turns_since_progress} turns without filling a section. "
                    f"'{next_section}' is unlocked — use START('{next_section}') "
                    f"then FILL with your extracted data.]"
                )

        # Tier 4: Stalled — nudge toward next section
        if self._turns_since_progress >= self._progress.stall_threshold_turns and next_section:
            return f"\n[Hint: '{next_section}' is unlocked. Use START('{next_section}') to continue.]"

        # Tier 5: Normal — simple progress
        if completed > 0:
            return f"\n[{completed}/{total} sections filled]"

        return ""

    def _post_compaction_footer(
        self,
        completed: int,
        total: int,
        next_section: str | None,
        scratchpad_keys: list[str],
    ) -> str:
        """Build the rich post-compaction footer."""
        lines: list[str] = []

        if self._first_post_compaction:
            lines.append(
                "[Context was compacted. Your REPL variables and scratchpad are intact. "
                "Use RECALL() to retrieve stored data.]"
            )
            self._first_post_compaction = False

        lines.append(f"[Template progress: {completed}/{total} sections filled]")

        if scratchpad_keys:
            lines.append(
                f"[Scratchpad has {len(scratchpad_keys)} keys — use RECALL() to retrieve your extracted data.]"
            )

        if next_section:
            lines.append(f"[Next unlocked: '{next_section}'. Use START('{next_section}') for guidance.]")

        return "\n" + "\n".join(lines)
