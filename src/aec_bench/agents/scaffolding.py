# ABOUTME: Progressive scaffolding footer builder for RLM tool output enrichment.
# ABOUTME: Implements Option C: quiet pre-compaction, active post-compaction.

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


@dataclass
class ScaffoldingState:
    """Tracks scaffolding phase across the iter() loop."""

    scaffolding_enabled: bool = True
    compacted: bool = False
    first_post_compaction: bool = True  # first tool call after compaction


def build_scaffolding_footer(
    state: ScaffoldingState,
    template_status: dict[str, Any] | None,
    scratchpad_keys: Sequence[str],
    turns_since_progress: int,
) -> str:
    """Build a contextual footer to append to REPL tool output.

    Option C: Start quiet, ramp up after compaction.
    """
    if not state.scaffolding_enabled:
        return ""

    if template_status is None:
        return ""

    completed = template_status.get("completed", 0)
    total = template_status.get("total", 0)
    unlocked = template_status.get("unlocked", [])
    next_section = unlocked[0] if unlocked else None

    # Post-compaction: full orientation
    if state.compacted:
        lines: list[str] = ["\n---"]
        if state.first_post_compaction:
            lines.append("[Context was compacted. Your conversation history has been summarised.]")
            state.first_post_compaction = False
        lines.append(f"[Template progress: {completed}/{total} sections filled]")
        if scratchpad_keys:
            lines.append(f"[Scratchpad has {len(scratchpad_keys)} keys — use RECALL() to retrieve extracted data]")
        if next_section:
            lines.append(f"[Next unlocked: '{next_section}'. Use START('{next_section}') for guidance.]")
        return "\n".join(lines)

    # Pre-compaction, agent stuck: gentle nudge
    if turns_since_progress >= 3 and next_section:
        return f"\n---\n[Hint: '{next_section}' is unlocked. Use START('{next_section}') to continue.]"

    # Pre-compaction, after a FILL: minimal progress
    if completed > 0:
        return f"\n---\n[{completed}/{total} sections filled]"

    # Pre-compaction, no fills yet: stay quiet
    return ""
