# ABOUTME: Tests for progressive scaffolding footer builder (Option C: quiet → active).
# ABOUTME: Validates phase detection and footer content across compaction states.

from aec_bench.agents.scaffolding import ScaffoldingState, build_scaffolding_footer


def test_freeform_mode_returns_empty_footer() -> None:
    state = ScaffoldingState(scaffolding_enabled=False, compacted=False)
    footer = build_scaffolding_footer(
        state=state,
        template_status={"total": 9, "completed": 0, "unlocked": ["background"]},
        scratchpad_keys=[],
        turns_since_progress=0,
    )
    assert footer == ""


def test_pre_compaction_no_fill_returns_empty() -> None:
    """Before compaction, no FILL has happened — stay quiet."""
    state = ScaffoldingState(scaffolding_enabled=True, compacted=False)
    footer = build_scaffolding_footer(
        state=state,
        template_status={"total": 9, "completed": 0, "unlocked": ["background"]},
        scratchpad_keys=[],
        turns_since_progress=0,
    )
    assert footer == ""


def test_pre_compaction_after_fill_shows_progress() -> None:
    """After a FILL call, show minimal progress line."""
    state = ScaffoldingState(scaffolding_enabled=True, compacted=False)
    footer = build_scaffolding_footer(
        state=state,
        template_status={"total": 9, "completed": 3, "unlocked": ["design"]},
        scratchpad_keys=["brief_facts"],
        turns_since_progress=0,
    )
    assert "3/9" in footer
    assert len(footer.splitlines()) <= 3  # minimal (including separator line)


def test_pre_compaction_stuck_shows_nudge() -> None:
    """3+ turns with no progress — gentle nudge."""
    state = ScaffoldingState(scaffolding_enabled=True, compacted=False)
    footer = build_scaffolding_footer(
        state=state,
        template_status={"total": 9, "completed": 1, "unlocked": ["scope"]},
        scratchpad_keys=[],
        turns_since_progress=3,
    )
    assert "scope" in footer.lower() or "START" in footer


def test_post_compaction_shows_full_orientation() -> None:
    """After compaction, full orientation with all guidance."""
    state = ScaffoldingState(scaffolding_enabled=True, compacted=True)
    footer = build_scaffolding_footer(
        state=state,
        template_status={
            "total": 9,
            "completed": 5,
            "unlocked": ["cost"],
            "pending": ["cost", "risk", "schedule", "appendix"],
        },
        scratchpad_keys=["brief_facts", "design_notes", "scope_data"],
        turns_since_progress=0,
    )
    assert "compacted" in footer.lower() or "summarised" in footer.lower()
    assert "5/9" in footer
    assert "RECALL" in footer or "scratchpad" in footer.lower()
    assert "cost" in footer.lower()


def test_post_compaction_ongoing_shows_progress_and_hint() -> None:
    """Post-compaction, ongoing turns keep showing guidance."""
    state = ScaffoldingState(scaffolding_enabled=True, compacted=True, first_post_compaction=False)
    footer = build_scaffolding_footer(
        state=state,
        template_status={"total": 9, "completed": 6, "unlocked": ["risk"]},
        scratchpad_keys=["brief_facts"],
        turns_since_progress=0,
    )
    assert "6/9" in footer
    assert "risk" in footer.lower()
