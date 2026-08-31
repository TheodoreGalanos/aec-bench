# ABOUTME: Root package for the Python implementation of aec-bench.
# ABOUTME: Exposes package metadata and shared top-level imports as the implementation grows.

import importlib

__all__ = ["__version__", "worlds"]

__version__ = "0.1.0"


def __getattr__(name: str) -> object:
    """Load the optional world facade only when a caller requests it."""
    if name != "worlds":
        raise AttributeError(name)
    module = importlib.import_module("aec_bench.worlds")
    globals()[name] = module
    return module
