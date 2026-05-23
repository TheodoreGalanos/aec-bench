# ABOUTME: Tests for lambda-rlm pure combinators (split, merge).
# ABOUTME: Validates word-boundary splitting, chunk sizing, and merge assembly.

from aec_bench.adapters.lambda_rlm.combinators import compute_plan_params, split_text


def test_split_text_single_chunk():
    """Text smaller than tau_star returns a single chunk."""
    text = "Short text that fits."
    chunks = split_text(text, k_star=2, tau_star=1000)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_split_text_two_chunks():
    """Text split into k_star=2 chunks at word boundary."""
    words = ["word"] * 100
    text = " ".join(words)  # 499 chars
    chunks = split_text(text, k_star=2, tau_star=200)
    assert len(chunks) == 2
    for chunk in chunks:
        assert len(chunk) > 0
    reassembled = " ".join(chunks)
    assert reassembled.split() == text.split()


def test_split_text_respects_word_boundaries():
    """Splits should not cut words in half."""
    text = "alpha bravo charlie delta echo foxtrot golf hotel"
    chunks = split_text(text, k_star=2, tau_star=20)
    for chunk in chunks:
        for word in chunk.split():
            assert word in text.split()


def test_split_text_k_star_three():
    words = ["hello"] * 90
    text = " ".join(words)  # 539 chars
    chunks = split_text(text, k_star=3, tau_star=100)
    assert len(chunks) == 3
    reassembled = " ".join(chunks)
    assert reassembled.split() == text.split()


def test_compute_plan_params_small_source():
    """Source smaller than context window needs no splitting."""
    k, tau, d = compute_plan_params(
        source_size_chars=5_000,
        context_window_chars=100_000,
        max_branching_factor=20,
    )
    assert k == 1
    assert tau == 100_000
    assert d == 0


def test_compute_plan_params_large_source():
    """Source larger than context window triggers splitting."""
    k, tau, d = compute_plan_params(
        source_size_chars=400_000,
        context_window_chars=100_000,
        max_branching_factor=20,
    )
    assert k >= 2
    assert tau == 100_000
    assert d >= 1
    assert k**d * tau >= 400_000


def test_compute_plan_params_respects_max_branching():
    k, tau, d = compute_plan_params(
        source_size_chars=10_000_000,
        context_window_chars=100_000,
        max_branching_factor=5,
    )
    assert k <= 5
