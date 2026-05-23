# ABOUTME: Pure combinators for the lambda-rlm adapter.
# ABOUTME: Deterministic text splitting and plan parameter computation (no LLM calls).

from __future__ import annotations

import math


def split_text(text: str, *, k_star: int, tau_star: int) -> list[str]:
    """Split text into up to k_star chunks, respecting word boundaries.

    If the text fits within tau_star characters, returns it as a single chunk.
    Otherwise, splits into k_star roughly equal chunks at word boundaries.
    """
    if len(text) <= tau_star or k_star <= 1:
        return [text]

    words = text.split()
    if not words:
        return [text]

    target_size = len(text) / k_star
    chunks: list[str] = []
    current_words: list[str] = []
    current_len = 0

    for word in words:
        word_len = len(word) + (1 if current_words else 0)
        if current_len + word_len > target_size and current_words and len(chunks) < k_star - 1:
            chunks.append(" ".join(current_words))
            current_words = [word]
            current_len = len(word)
        else:
            current_words.append(word)
            current_len += word_len

    if current_words:
        chunks.append(" ".join(current_words))

    return chunks


def compute_plan_params(
    *,
    source_size_chars: int,
    context_window_chars: int,
    max_branching_factor: int = 20,
) -> tuple[int, int, int]:
    """Compute optimal (k*, tau*, d) for a source using the lambda-RLM cost model.

    Returns:
        (k_star, tau_star, depth) where:
        - k_star: branching factor (1 means no splitting needed)
        - tau_star: max leaf chunk size in chars
        - depth: recursion depth (0 means single leaf call)
    """
    tau_star = context_window_chars

    if source_size_chars <= tau_star:
        return 1, tau_star, 0

    k_star = math.ceil(math.sqrt(source_size_chars / tau_star))
    k_star = min(k_star, max_branching_factor)
    k_star = max(k_star, 2)

    depth = math.ceil(math.log(source_size_chars / tau_star) / math.log(k_star))
    depth = max(depth, 1)

    return k_star, tau_star, depth
