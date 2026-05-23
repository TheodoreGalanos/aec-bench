# ABOUTME: Tests for RLM guardrail tracking — token budget, iteration cap, depth limit.
# ABOUTME: Verifies all three protection layers behave correctly in isolation and together.

"""Tests for RLM guardrail tracking — token budget, iteration cap, and depth limit."""

from aec_bench.adapters.rlm.guardrails import GuardrailState


def test_initial_state_is_within_limits() -> None:
    gs = GuardrailState(token_budget=100_000, max_iterations=50, max_subcall_depth=1)
    verdict = gs.check()
    assert verdict.can_continue
    assert not verdict.budget_warning


def test_iteration_cap_triggers_stop() -> None:
    gs = GuardrailState(token_budget=100_000, max_iterations=3, max_subcall_depth=1)
    gs.record_iteration(input_tokens=100, output_tokens=50)
    gs.record_iteration(input_tokens=100, output_tokens=50)
    gs.record_iteration(input_tokens=100, output_tokens=50)
    verdict = gs.check()
    assert not verdict.can_continue
    assert "iteration" in verdict.stop_reason.lower()


def test_token_budget_triggers_stop() -> None:
    gs = GuardrailState(token_budget=500, max_iterations=100, max_subcall_depth=1)
    gs.record_iteration(input_tokens=300, output_tokens=250)
    verdict = gs.check()
    assert not verdict.can_continue
    assert "budget" in verdict.stop_reason.lower()


def test_budget_warning_fires_at_threshold() -> None:
    gs = GuardrailState(
        token_budget=1000,
        max_iterations=100,
        max_subcall_depth=1,
        budget_warning_pct=80.0,
    )
    gs.record_iteration(input_tokens=400, output_tokens=450)
    verdict = gs.check()
    assert verdict.can_continue
    assert verdict.budget_warning
    assert verdict.budget_consumed_pct >= 80.0


def test_budget_consumed_pct_is_accurate() -> None:
    gs = GuardrailState(token_budget=1000, max_iterations=100, max_subcall_depth=1)
    gs.record_iteration(input_tokens=200, output_tokens=100)
    verdict = gs.check()
    assert abs(verdict.budget_consumed_pct - 30.0) < 0.1


def test_subcall_depth_is_tracked() -> None:
    gs = GuardrailState(token_budget=100_000, max_iterations=100, max_subcall_depth=2)
    assert gs.can_subcall(current_depth=0)
    assert gs.can_subcall(current_depth=1)
    assert not gs.can_subcall(current_depth=2)


def test_subcall_tokens_count_toward_budget() -> None:
    gs = GuardrailState(token_budget=500, max_iterations=100, max_subcall_depth=1)
    gs.record_subcall_tokens(input_tokens=200, output_tokens=350)
    verdict = gs.check()
    assert not verdict.can_continue
    assert gs.total_tokens == 550


# ---- Global sub-call counter ----


def test_subcall_count_is_tracked() -> None:
    gs = GuardrailState(token_budget=100_000, max_iterations=100, max_subcall_depth=1)
    assert gs.subcall_count == 0
    gs.record_subcall_tokens(input_tokens=100, output_tokens=50)
    assert gs.subcall_count == 1
    gs.record_subcall_tokens(input_tokens=100, output_tokens=50)
    assert gs.subcall_count == 2


def test_max_subcalls_triggers_stop() -> None:
    gs = GuardrailState(
        token_budget=100_000,
        max_iterations=100,
        max_subcall_depth=1,
        max_subcalls=3,
    )
    gs.record_subcall_tokens(input_tokens=100, output_tokens=50)
    gs.record_subcall_tokens(input_tokens=100, output_tokens=50)
    gs.record_subcall_tokens(input_tokens=100, output_tokens=50)
    verdict = gs.check()
    assert not verdict.can_continue
    assert "subcall" in verdict.stop_reason.lower()


def test_max_subcalls_zero_means_unlimited() -> None:
    gs = GuardrailState(
        token_budget=100_000,
        max_iterations=100,
        max_subcall_depth=1,
        max_subcalls=0,
    )
    for _ in range(100):
        gs.record_subcall_tokens(input_tokens=10, output_tokens=5)
    verdict = gs.check()
    assert verdict.can_continue


# ---- USD cost budget ----


def test_cost_tracking_accumulates() -> None:
    gs = GuardrailState(
        token_budget=100_000,
        max_iterations=100,
        max_subcall_depth=1,
    )
    # Record with pricing: $3/M input, $15/M output (Sonnet-class)
    gs.record_iteration(input_tokens=10_000, output_tokens=2_000, cost_usd=0.06)
    assert abs(gs.total_cost_usd - 0.06) < 1e-9


def test_max_budget_usd_triggers_stop() -> None:
    gs = GuardrailState(
        token_budget=100_000,
        max_iterations=100,
        max_subcall_depth=1,
        max_budget_usd=0.10,
    )
    gs.record_iteration(input_tokens=10_000, output_tokens=2_000, cost_usd=0.06)
    verdict = gs.check()
    assert verdict.can_continue
    gs.record_iteration(input_tokens=10_000, output_tokens=2_000, cost_usd=0.06)
    verdict = gs.check()
    assert not verdict.can_continue
    assert "budget" in verdict.stop_reason.lower()
    assert "$" in verdict.stop_reason


def test_max_budget_usd_zero_means_unlimited() -> None:
    gs = GuardrailState(
        token_budget=100_000,
        max_iterations=100,
        max_subcall_depth=1,
        max_budget_usd=0.0,
    )
    gs.record_iteration(input_tokens=50_000, output_tokens=10_000, cost_usd=5.0)
    verdict = gs.check()
    assert verdict.can_continue


def test_subcall_cost_counts_toward_budget() -> None:
    gs = GuardrailState(
        token_budget=100_000,
        max_iterations=100,
        max_subcall_depth=1,
        max_budget_usd=0.05,
    )
    gs.record_subcall_tokens(input_tokens=5_000, output_tokens=1_000, cost_usd=0.03)
    gs.record_subcall_tokens(input_tokens=5_000, output_tokens=1_000, cost_usd=0.03)
    verdict = gs.check()
    assert not verdict.can_continue


# ---- Billable input budget ----


def test_billable_input_tracks_uncached_tokens() -> None:
    gs = GuardrailState(
        token_budget=10_000_000,
        max_iterations=100,
        max_subcall_depth=1,
        billable_input_budget=500_000,
    )
    gs.record_iteration(
        input_tokens=100_000,
        output_tokens=10_000,
        cache_read_tokens=80_000,
    )
    # Billable = 100K - 80K = 20K
    assert gs.billable_input_tokens == 20_000


def test_billable_input_budget_triggers_stop() -> None:
    gs = GuardrailState(
        token_budget=10_000_000,
        max_iterations=100,
        max_subcall_depth=1,
        billable_input_budget=50_000,
    )
    # 100K input, 90K cached → 10K billable
    gs.record_iteration(
        input_tokens=100_000,
        output_tokens=10_000,
        cache_read_tokens=90_000,
    )
    verdict = gs.check()
    assert verdict.can_continue  # 10K < 50K

    # Another 100K, only 50K cached → 50K billable, total 60K
    gs.record_iteration(
        input_tokens=100_000,
        output_tokens=10_000,
        cache_read_tokens=50_000,
    )
    verdict = gs.check()
    assert not verdict.can_continue
    assert "billable" in verdict.stop_reason.lower()


def test_billable_input_zero_means_unlimited() -> None:
    gs = GuardrailState(
        token_budget=10_000_000,
        max_iterations=100,
        max_subcall_depth=1,
        billable_input_budget=0,
    )
    gs.record_iteration(
        input_tokens=5_000_000,
        output_tokens=100_000,
        cache_read_tokens=0,
    )
    verdict = gs.check()
    assert verdict.can_continue  # only token_budget matters


def test_billable_input_subcalls_count() -> None:
    gs = GuardrailState(
        token_budget=10_000_000,
        max_iterations=100,
        max_subcall_depth=1,
        billable_input_budget=100_000,
    )
    gs.record_iteration(
        input_tokens=50_000,
        output_tokens=5_000,
        cache_read_tokens=40_000,
    )
    # 10K billable from iteration
    gs.record_subcall_tokens(
        input_tokens=200_000,
        output_tokens=10_000,
        cache_read_tokens=100_000,
    )
    # 100K billable from subcall, total 110K
    assert gs.billable_input_tokens == 110_000
    verdict = gs.check()
    assert not verdict.can_continue


def test_no_cache_means_all_input_is_billable() -> None:
    gs = GuardrailState(
        token_budget=10_000_000,
        max_iterations=100,
        max_subcall_depth=1,
        billable_input_budget=500_000,
    )
    gs.record_iteration(input_tokens=200_000, output_tokens=10_000)
    # No cache_read_tokens → all 200K is billable
    assert gs.billable_input_tokens == 200_000
