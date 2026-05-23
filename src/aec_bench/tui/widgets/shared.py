# ABOUTME: Shared TUI utilities for colour mapping and styling.
# ABOUTME: Provides reward_color() and reward_style() used across all screens.

from __future__ import annotations


def reward_color(reward: float) -> str:
    """Return a hex colour string for a reward value."""
    if reward >= 1.0:
        return "#61AAF2"  # Focus blue — perfect
    if reward >= 0.8:
        return "#BFBFBA"  # Cloud Light — good
    if reward >= 0.5:
        return "#D4A27F"  # Kraft — mediocre
    if reward == 0.0:
        return "#BF4D43"  # Error red — zero
    return "#CC785C"  # Book Cloth — poor


def reward_style(mean: float) -> str:
    """Return a hex colour string for an aggregate mean reward."""
    if mean >= 0.8:
        return "#61AAF2"
    return "#D4A27F" if mean >= 0.5 else "#BF4D43"
