# ABOUTME: Exposes the DeepSeek Harness adapter from its provider-integration package.
# ABOUTME: Keeps runtime, event, worker, and profile details behind one adapter owner.

from aec_bench.adapters.deepseek_harness.adapter import DeepSeekHarnessAdapter

__all__ = ["DeepSeekHarnessAdapter"]
