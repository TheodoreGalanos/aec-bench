# ABOUTME: Exposes the DeepSeek Harness adapter from its provider-integration package.
# ABOUTME: Keeps runtime, event, worker, and profile details behind one adapter owner.

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from aec_bench.adapters.deepseek_harness.adapter import DeepSeekHarnessAdapter

__all__ = ["DeepSeekHarnessAdapter"]


def __getattr__(name: str) -> Any:
    """Load the optional adapter only when a caller selects it."""
    if name != "DeepSeekHarnessAdapter":
        raise AttributeError(name)
    from aec_bench.adapters.deepseek_harness.adapter import DeepSeekHarnessAdapter

    return DeepSeekHarnessAdapter
