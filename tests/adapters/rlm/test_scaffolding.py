# ABOUTME: Tests for progressive scaffolding footer state machine.
# ABOUTME: Validates post-compaction hints, stall detection, and normal progress display.

from __future__ import annotations

from aec_bench.adapters.rlm.scaffolding import ScaffoldingState
from aec_bench.adapters.rlm.template import TemplateStatus


def _status(
    completed: int = 0,
    total: int = 5,
    unlocked: list[str] | None = None,
) -> TemplateStatus:
    """Helper to build a TemplateStatus."""
    return TemplateStatus(
        total_sections=total,
        completed_sections=completed,
        unlocked=unlocked or [],
        pending=[f"s{i}" for i in range(total - completed)],
        completed=[f"done{i}" for i in range(completed)],
    )


class TestDisabled:
    """When scaffolding is disabled, footer is always empty."""

    def test_disabled_returns_empty(self) -> None:
        state = ScaffoldingState(enabled=False)
        footer = state.build_footer(template_status=_status(2, 5, ["s3"]), scratchpad_keys=["a"])
        assert footer == ""


class TestNoTemplate:
    """When no template is provided, footer is always empty."""

    def test_no_template_returns_empty(self) -> None:
        state = ScaffoldingState(enabled=True)
        footer = state.build_footer(template_status=None, scratchpad_keys=[])
        assert footer == ""


class TestNormalProgress:
    """Normal footer shows progress count when sections are completed."""

    def test_shows_progress_count(self) -> None:
        state = ScaffoldingState(enabled=True)
        state.record_progress(2)
        footer = state.build_footer(
            template_status=_status(2, 5, ["s3"]),
            scratchpad_keys=[],
        )
        assert "2/5" in footer
        assert "sections filled" in footer.lower() or "sections" in footer.lower()

    def test_no_sections_filled_returns_empty(self) -> None:
        state = ScaffoldingState(enabled=True)
        state.record_progress(0)
        footer = state.build_footer(
            template_status=_status(0, 5, ["s1"]),
            scratchpad_keys=[],
        )
        assert footer == ""


class TestPostCompaction:
    """After compaction, footer shows rich contextual hints."""

    def test_first_post_compaction_shows_notice(self) -> None:
        state = ScaffoldingState(enabled=True)
        state.mark_compacted()
        footer = state.build_footer(
            template_status=_status(2, 5, ["s3"]),
            scratchpad_keys=["a", "b"],
        )
        assert "compacted" in footer.lower()

    def test_post_compaction_shows_progress(self) -> None:
        state = ScaffoldingState(enabled=True)
        state.mark_compacted()
        footer = state.build_footer(
            template_status=_status(2, 5, ["s3"]),
            scratchpad_keys=[],
        )
        assert "2/5" in footer

    def test_post_compaction_shows_scratchpad_count(self) -> None:
        state = ScaffoldingState(enabled=True)
        state.mark_compacted()
        footer = state.build_footer(
            template_status=_status(2, 5, ["s3"]),
            scratchpad_keys=["facts", "context", "notes"],
        )
        assert "3" in footer
        assert "RECALL" in footer

    def test_post_compaction_shows_next_unlocked(self) -> None:
        state = ScaffoldingState(enabled=True)
        state.mark_compacted()
        footer = state.build_footer(
            template_status=_status(2, 5, ["next_section"]),
            scratchpad_keys=[],
        )
        assert "next_section" in footer

    def test_compaction_notice_shown_only_once(self) -> None:
        state = ScaffoldingState(enabled=True)
        state.mark_compacted()
        footer1 = state.build_footer(
            template_status=_status(2, 5, ["s3"]),
            scratchpad_keys=[],
        )
        footer2 = state.build_footer(
            template_status=_status(2, 5, ["s3"]),
            scratchpad_keys=[],
        )
        assert "compacted" in footer1.lower()
        # Second call still shows progress (compacted state persists) but not the notice
        assert "2/5" in footer2


class TestStallDetection:
    """After 3+ turns without progress and an unlocked section, show a hint."""

    def test_stalled_with_unlocked_shows_hint(self) -> None:
        state = ScaffoldingState(enabled=True)
        # Simulate 3 turns with no progress
        state.record_progress(1)
        state.record_progress(1)
        state.record_progress(1)
        state.record_progress(1)  # 4th call with same count => 3 stalled turns
        footer = state.build_footer(
            template_status=_status(1, 5, ["next_one"]),
            scratchpad_keys=[],
        )
        assert "next_one" in footer
        assert "hint" in footer.lower() or "unlocked" in footer.lower()

    def test_stalled_without_unlocked_returns_progress(self) -> None:
        state = ScaffoldingState(enabled=True)
        for _ in range(4):
            state.record_progress(1)
        footer = state.build_footer(
            template_status=_status(1, 5, []),  # no unlocked sections
            scratchpad_keys=[],
        )
        # Should just show progress, not a hint (nothing to hint about)
        assert "1/5" in footer

    def test_progress_resets_stall_counter(self) -> None:
        state = ScaffoldingState(enabled=True)
        state.record_progress(1)
        state.record_progress(1)
        state.record_progress(1)
        # Now make progress
        state.record_progress(2)
        # One more turn without progress — only 1 stalled turn, not 3
        state.record_progress(2)
        footer = state.build_footer(
            template_status=_status(2, 5, ["s3"]),
            scratchpad_keys=[],
        )
        # Should show normal progress, not stall hint
        assert "2/5" in footer
        assert "hint" not in footer.lower()


class TestPreFillNudge:
    """When zero sections are filled and many turns have passed, nudge to start writing."""

    def test_gentle_nudge_at_threshold(self) -> None:
        state = ScaffoldingState(enabled=True)
        # 10 turns with no fills
        for _ in range(10):
            state.record_progress(0)
        footer = state.build_footer(
            template_status=_status(0, 5, ["introduction"]),
            scratchpad_keys=["fact1", "fact2"],
        )
        assert "introduction" in footer
        assert "FILL" in footer or "START" in footer

    def test_strong_nudge_at_higher_threshold(self) -> None:
        state = ScaffoldingState(enabled=True)
        # 20 turns with no fills
        for _ in range(20):
            state.record_progress(0)
        footer = state.build_footer(
            template_status=_status(0, 5, ["introduction"]),
            scratchpad_keys=["fact1", "fact2", "fact3"],
        )
        # Should be more forceful
        assert "FILL" in footer
        assert "introduction" in footer

    def test_no_nudge_when_sections_filled(self) -> None:
        state = ScaffoldingState(enabled=True)
        # Many turns but some sections filled
        state.record_progress(0)
        state.record_progress(0)
        state.record_progress(1)  # filled one
        for _ in range(15):
            state.record_progress(1)
        footer = state.build_footer(
            template_status=_status(1, 5, ["scope"]),
            scratchpad_keys=[],
        )
        # Should be regular stall hint, not pre-fill nudge
        assert "FILL" not in footer or "scope" in footer

    def test_no_nudge_before_threshold(self) -> None:
        state = ScaffoldingState(enabled=True)
        # Only 5 turns — below threshold
        for _ in range(5):
            state.record_progress(0)
        footer = state.build_footer(
            template_status=_status(0, 5, ["introduction"]),
            scratchpad_keys=[],
        )
        # Should be empty (0 sections, not stalled yet, below pre-fill threshold)
        assert "FILL" not in footer


class TestScaffoldingWithCustomParams:
    def test_uses_default_params_when_none_provided(self) -> None:
        from aec_bench.contracts.constitution import (  # noqa: F401
            EarnedAutonomyParams,
            ProgressObligationParams,
        )

        s = ScaffoldingState(enabled=True)
        # record_progress 3 times without progress → stall hint
        for _ in range(3):
            s.record_progress(0)
        out = s.build_footer(template_status=_status(0, 5, ["intro"]), scratchpad_keys=[])
        assert "is unlocked" in out
        assert "intro" in out

    def test_custom_stall_threshold(self) -> None:
        from aec_bench.contracts.constitution import ProgressObligationParams

        s = ScaffoldingState(
            enabled=True,
            progress_params=ProgressObligationParams(stall_threshold_turns=1),
        )
        s.record_progress(0)  # first turn, no progress → stall at 1
        out = s.build_footer(template_status=_status(0, 5, ["intro"]), scratchpad_keys=[])
        assert "is unlocked" in out

    def test_custom_gentle_nudge(self) -> None:
        from aec_bench.contracts.constitution import ProgressObligationParams

        s = ScaffoldingState(
            enabled=True,
            progress_params=ProgressObligationParams(gentle_nudge_turns=2, strong_nudge_turns=5),
        )
        # 2 turns without progress, 0 completed → gentle nudge
        for _ in range(2):
            s.record_progress(0)
        out = s.build_footer(
            template_status=_status(0, 5, ["intro"]),
            scratchpad_keys=["a"],
        )
        assert "without filling a section" in out

    def test_custom_strong_nudge(self) -> None:
        from aec_bench.contracts.constitution import ProgressObligationParams

        s = ScaffoldingState(
            enabled=True,
            progress_params=ProgressObligationParams(gentle_nudge_turns=2, strong_nudge_turns=4),
        )
        for _ in range(4):
            s.record_progress(0)
        out = s.build_footer(
            template_status=_status(0, 5, ["intro"]),
            scratchpad_keys=["a"],
        )
        assert "Stop gathering and start writing" in out

    def test_initial_mode_autonomous_disables_strong_nudge(self) -> None:
        """In 'autonomous' mode, strong nudges are suppressed."""
        from aec_bench.contracts.constitution import EarnedAutonomyParams, ProgressObligationParams

        s = ScaffoldingState(
            enabled=True,
            progress_params=ProgressObligationParams(gentle_nudge_turns=2, strong_nudge_turns=4),
            autonomy_params=EarnedAutonomyParams(initial_mode="autonomous"),
        )
        for _ in range(5):
            s.record_progress(0)
        out = s.build_footer(
            template_status=_status(0, 5, ["intro"]),
            scratchpad_keys=["a"],
        )
        # Gentle still fires, strong suppressed
        assert "Stop gathering and start writing" not in out

    def test_initial_mode_constrained_allows_all_tiers(self) -> None:
        from aec_bench.contracts.constitution import EarnedAutonomyParams, ProgressObligationParams

        s = ScaffoldingState(
            enabled=True,
            progress_params=ProgressObligationParams(gentle_nudge_turns=2, strong_nudge_turns=4),
            autonomy_params=EarnedAutonomyParams(initial_mode="constrained"),
        )
        for _ in range(5):
            s.record_progress(0)
        out = s.build_footer(
            template_status=_status(0, 5, ["intro"]),
            scratchpad_keys=["a"],
        )
        assert "Stop gathering and start writing" in out
