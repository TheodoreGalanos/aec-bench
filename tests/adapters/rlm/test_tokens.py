# ABOUTME: Tests for per-call token tracking and compaction threshold detection.
# ABOUTME: Validates turn metrics, subcall accounting, compaction triggers, and cross-compaction.

from __future__ import annotations

from aec_bench.adapters.rlm.tokens import TokenTracker, TurnMetrics


class TestTurnMetrics:
    """TurnMetrics is a frozen dataclass with the right fields."""

    def test_turn_metrics_fields(self) -> None:
        m = TurnMetrics(
            call_input_tokens=100,
            call_output_tokens=50,
            cumulative_input_tokens=500,
            cumulative_output_tokens=200,
            grand_total_tokens=1000,
            subcall_tokens=80,
        )
        assert m.call_input_tokens == 100
        assert m.grand_total_tokens == 1000


class TestRecordTurn:
    """Tests for TokenTracker.record_turn()."""

    def test_first_turn_metrics(self) -> None:
        tracker = TokenTracker(context_limit=1_000_000)
        metrics = tracker.record_turn(input_tokens=500, output_tokens=100)
        assert metrics.call_input_tokens == 500
        assert metrics.call_output_tokens == 100
        assert metrics.cumulative_input_tokens == 500
        assert metrics.cumulative_output_tokens == 100
        assert metrics.grand_total_tokens == 600
        assert metrics.subcall_tokens == 0

    def test_second_turn_accumulates(self) -> None:
        tracker = TokenTracker(context_limit=1_000_000)
        tracker.record_turn(input_tokens=500, output_tokens=100)
        metrics = tracker.record_turn(input_tokens=800, output_tokens=150)
        assert metrics.call_input_tokens == 800
        assert metrics.call_output_tokens == 150
        assert metrics.cumulative_input_tokens == 1300
        assert metrics.cumulative_output_tokens == 250
        assert metrics.grand_total_tokens == 1550

    def test_subcall_tokens_included_in_grand_total(self) -> None:
        tracker = TokenTracker(context_limit=1_000_000)
        tracker.record_turn(input_tokens=500, output_tokens=100)
        tracker.record_subcall(input_tokens=200, output_tokens=50)
        metrics = tracker.record_turn(input_tokens=600, output_tokens=120)
        assert metrics.subcall_tokens == 250
        assert metrics.grand_total_tokens == 500 + 100 + 250 + 600 + 120


class TestRecordSubcall:
    """Tests for TokenTracker.record_subcall()."""

    def test_subcall_adds_to_subcall_total(self) -> None:
        tracker = TokenTracker(context_limit=1_000_000)
        tracker.record_subcall(input_tokens=100, output_tokens=50)
        tracker.record_subcall(input_tokens=200, output_tokens=80)
        metrics = tracker.record_turn(input_tokens=500, output_tokens=100)
        assert metrics.subcall_tokens == 430


class TestCompactionThreshold:
    """Tests for needs_compaction() and hit_hard_ceiling()."""

    def test_below_threshold_no_compaction(self) -> None:
        tracker = TokenTracker(context_limit=1_000_000)
        assert not tracker.needs_compaction(call_input=800_000, threshold_pct=0.85)

    def test_above_threshold_triggers_compaction(self) -> None:
        tracker = TokenTracker(context_limit=1_000_000)
        assert tracker.needs_compaction(call_input=860_000, threshold_pct=0.85)

    def test_exact_threshold_triggers_compaction(self) -> None:
        tracker = TokenTracker(context_limit=1_000_000)
        # 850_000 is exactly 0.85 * 1M — "exceeds" means strictly greater
        assert not tracker.needs_compaction(call_input=850_000, threshold_pct=0.85)
        assert tracker.needs_compaction(call_input=850_001, threshold_pct=0.85)

    def test_below_hard_ceiling(self) -> None:
        tracker = TokenTracker(context_limit=1_000_000)
        assert not tracker.hit_hard_ceiling(call_input=940_000, ceiling_pct=0.95)

    def test_above_hard_ceiling(self) -> None:
        tracker = TokenTracker(context_limit=1_000_000)
        assert tracker.hit_hard_ceiling(call_input=960_000, ceiling_pct=0.95)


class TestResetForCompaction:
    """Tests for reset_for_compaction() — preserving grand total."""

    def test_reset_accumulates_grand_total(self) -> None:
        tracker = TokenTracker(context_limit=1_000_000)
        tracker.record_turn(input_tokens=500, output_tokens=100)
        tracker.record_subcall(input_tokens=200, output_tokens=50)
        # grand total before reset: 500 + 100 + 250 = 850
        tracker.reset_for_compaction()

        # After reset, run counters are zero, grand total preserved
        metrics = tracker.record_turn(input_tokens=300, output_tokens=80)
        assert metrics.call_input_tokens == 300
        assert metrics.cumulative_input_tokens == 300
        assert metrics.cumulative_output_tokens == 80
        assert metrics.subcall_tokens == 0
        # Grand total = 850 (previous) + 300 + 80 (new run)
        assert metrics.grand_total_tokens == 850 + 380

    def test_multiple_compactions(self) -> None:
        tracker = TokenTracker(context_limit=1_000_000)
        tracker.record_turn(input_tokens=1000, output_tokens=200)
        tracker.reset_for_compaction()  # grand: 1200
        tracker.record_turn(input_tokens=800, output_tokens=150)
        tracker.reset_for_compaction()  # grand: 1200 + 950 = 2150
        metrics = tracker.record_turn(input_tokens=500, output_tokens=100)
        assert metrics.grand_total_tokens == 2150 + 600


class TestDepthSummary:
    """Tests for depth-level aggregation."""

    def test_depth_summary_tracks_main_and_subcalls(self) -> None:
        tracker = TokenTracker(context_limit=1_000_000)
        tracker.record_turn(input_tokens=500, output_tokens=100)
        tracker.record_turn(input_tokens=800, output_tokens=150)
        tracker.record_subcall(input_tokens=200, output_tokens=50)
        tracker.record_subcall(input_tokens=100, output_tokens=30)

        summary = tracker.depth_summary()
        assert summary["main"]["calls"] == 2
        assert summary["main"]["input_tokens"] == 1300
        assert summary["main"]["output_tokens"] == 250
        assert summary["subcalls"]["calls"] == 2
        assert summary["subcalls"]["input_tokens"] == 300
        assert summary["subcalls"]["output_tokens"] == 80

    def test_depth_summary_tracks_compaction(self) -> None:
        tracker = TokenTracker(context_limit=1_000_000)
        tracker.record_turn(input_tokens=500, output_tokens=100)
        tracker.record_compaction(input_tokens=300, output_tokens=50)

        summary = tracker.depth_summary()
        assert summary["compaction"]["calls"] == 1
        assert summary["compaction"]["input_tokens"] == 300
        assert summary["compaction"]["output_tokens"] == 50

    def test_depth_summary_with_cost(self) -> None:
        tracker = TokenTracker(context_limit=1_000_000)
        tracker.record_turn(input_tokens=500, output_tokens=100, cost_usd=0.05)
        tracker.record_subcall(input_tokens=200, output_tokens=50, cost_usd=0.01)
        tracker.record_compaction(input_tokens=300, output_tokens=50, cost_usd=0.02)

        summary = tracker.depth_summary()
        assert abs(summary["main"]["cost_usd"] - 0.05) < 1e-9
        assert abs(summary["subcalls"]["cost_usd"] - 0.01) < 1e-9
        assert abs(summary["compaction"]["cost_usd"] - 0.02) < 1e-9
        assert abs(summary["total"]["cost_usd"] - 0.08) < 1e-9


class TestGrandTotal:
    """Tests for the grand_total property."""

    def test_grand_total_without_compaction(self) -> None:
        tracker = TokenTracker(context_limit=1_000_000)
        tracker.record_turn(input_tokens=500, output_tokens=100)
        assert tracker.grand_total == 600

    def test_grand_total_after_compaction(self) -> None:
        tracker = TokenTracker(context_limit=1_000_000)
        tracker.record_turn(input_tokens=500, output_tokens=100)
        tracker.reset_for_compaction()
        tracker.record_turn(input_tokens=300, output_tokens=80)
        assert tracker.grand_total == 600 + 380


class TestCacheTokenTracking:
    """Tests for cache read/write token tracking through TokenTracker."""

    def test_record_turn_with_cache_tokens(self) -> None:
        tracker = TokenTracker(context_limit=1_000_000)
        metrics = tracker.record_turn(
            input_tokens=1000,
            output_tokens=200,
            cache_read_tokens=800,
            cache_write_tokens=150,
        )
        assert metrics.cache_read_tokens == 800
        assert metrics.cache_write_tokens == 150

    def test_cache_tokens_accumulate_across_turns(self) -> None:
        tracker = TokenTracker(context_limit=1_000_000)
        tracker.record_turn(
            input_tokens=1000,
            output_tokens=200,
            cache_read_tokens=800,
            cache_write_tokens=150,
        )
        metrics = tracker.record_turn(
            input_tokens=1500,
            output_tokens=300,
            cache_read_tokens=1200,
            cache_write_tokens=0,
        )
        assert metrics.cache_read_tokens == 1200  # per-call
        summary = tracker.depth_summary()
        assert summary["main"]["cache_read_tokens"] == 2000
        assert summary["main"]["cache_write_tokens"] == 150

    def test_subcall_cache_tokens_in_depth_summary(self) -> None:
        tracker = TokenTracker(context_limit=1_000_000)
        tracker.record_subcall(
            input_tokens=500,
            output_tokens=100,
            cache_read_tokens=400,
            cache_write_tokens=50,
        )
        summary = tracker.depth_summary()
        assert summary["subcalls"]["cache_read_tokens"] == 400
        assert summary["subcalls"]["cache_write_tokens"] == 50

    def test_compaction_cache_tokens_in_depth_summary(self) -> None:
        tracker = TokenTracker(context_limit=1_000_000)
        tracker.record_compaction(
            input_tokens=300,
            output_tokens=50,
            cache_read_tokens=200,
            cache_write_tokens=30,
        )
        summary = tracker.depth_summary()
        assert summary["compaction"]["cache_read_tokens"] == 200
        assert summary["compaction"]["cache_write_tokens"] == 30

    def test_total_cache_tokens_in_depth_summary(self) -> None:
        tracker = TokenTracker(context_limit=1_000_000)
        tracker.record_turn(
            input_tokens=1000,
            output_tokens=200,
            cache_read_tokens=800,
            cache_write_tokens=100,
        )
        tracker.record_subcall(
            input_tokens=500,
            output_tokens=100,
            cache_read_tokens=300,
            cache_write_tokens=50,
        )
        tracker.record_compaction(
            input_tokens=300,
            output_tokens=50,
            cache_read_tokens=200,
            cache_write_tokens=30,
        )
        summary = tracker.depth_summary()
        assert summary["total"]["cache_read_tokens"] == 1300
        assert summary["total"]["cache_write_tokens"] == 180

    def test_turn_metrics_default_cache_zero(self) -> None:
        tracker = TokenTracker(context_limit=1_000_000)
        metrics = tracker.record_turn(input_tokens=500, output_tokens=100)
        assert metrics.cache_read_tokens == 0
        assert metrics.cache_write_tokens == 0
