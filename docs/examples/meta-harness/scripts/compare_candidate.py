# ABOUTME: Example script for comparing candidate and baseline meta-harness task runs.
# ABOUTME: Delegates to the shared library comparison CLI used by generated recipes.

from __future__ import annotations

from aec_bench.meta_harness.recipe import comparison_cli

if __name__ == "__main__":
    raise SystemExit(comparison_cli())
