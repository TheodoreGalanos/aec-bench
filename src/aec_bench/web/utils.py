# ABOUTME: Shared utility functions for web route handlers.
# ABOUTME: Centralises reward CSS mapping and task ID parsing used across multiple routes.

from __future__ import annotations


def reward_css_class(reward: float) -> str:
    """Map a reward value to the corresponding CSS utility class name."""
    if reward >= 1.0:
        return "reward-perfect"
    if reward >= 0.8:
        return "reward-good"
    if reward >= 0.5:
        return "reward-mid"
    if reward == 0.0:
        return "reward-zero"
    return "reward-poor"


def reward_bg_rgba(reward: float) -> str:
    """Map a reward value to a light rgba background tint string."""
    if reward >= 1.0:
        return "rgba(97, 170, 242, 0.10)"
    if reward >= 0.8:
        return "rgba(191, 191, 186, 0.10)"
    if reward >= 0.5:
        return "rgba(212, 162, 127, 0.10)"
    if reward == 0.0:
        return "rgba(191, 77, 67, 0.10)"
    return "rgba(204, 120, 92, 0.10)"


def extract_task_prefix(task_id: str) -> str:
    """Extract the task type prefix from a task_id (second path segment)."""
    parts = task_id.split("/")
    return parts[1] if len(parts) > 1 else task_id


def extract_discipline(task_id: str) -> str:
    """Extract the discipline prefix from a task_id like 'electrical/voltage-drop/...'."""
    parts = task_id.split("/")
    return parts[0] if parts else ""
