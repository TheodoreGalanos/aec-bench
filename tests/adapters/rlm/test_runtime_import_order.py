# ABOUTME: Guards the RLM lifecycle against advisor and tool-loop import cycles.
# ABOUTME: Exercises both package initialization orders in isolated Python processes.

from __future__ import annotations

import json
import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    "module_order",
    (
        (
            "aec_bench.adapters.advisor",
            "aec_bench.adapters.rlm.adapter",
        ),
        (
            "aec_bench.adapters.rlm.adapter",
            "aec_bench.adapters.advisor",
        ),
        (
            "aec_bench.adapters.tool_loop",
            "aec_bench.adapters.rlm.adapter",
        ),
    ),
)
def test_rlm_runtime_import_order_is_acyclic(module_order: tuple[str, ...]) -> None:
    script = (
        "import importlib\n"
        f"modules = {json.dumps(module_order)}\n"
        "for module in modules:\n"
        "    importlib.import_module(module)\n"
    )

    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
