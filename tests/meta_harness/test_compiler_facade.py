# ABOUTME: Characterizes the stable compiler facade across the cohesive compilation package.
# ABOUTME: Guards public and compatibility symbol identity under either import order.

from __future__ import annotations

import importlib
import subprocess
import sys


def test_compiler_facade_reexports_canonical_symbols_by_identity() -> None:
    facade = importlib.import_module("aec_bench.meta_harness.compiler")
    compilation = importlib.import_module("aec_bench.meta_harness.compilation")
    diagnostics = importlib.import_module("aec_bench.meta_harness.compilation.diagnostics")
    profile = importlib.import_module("aec_bench.meta_harness.compilation.profile")
    harness = importlib.import_module("aec_bench.meta_harness.compilation.harness")
    program = importlib.import_module("aec_bench.meta_harness.compilation.program")
    bundle = importlib.import_module("aec_bench.meta_harness.compilation.bundle")
    operations = importlib.import_module("aec_bench.meta_harness.compilation.operations")

    expected = {
        "CompilationOwner": diagnostics.CompilationOwner,
        "ProgramCompilationProfile": profile.ProgramCompilationProfile,
        "CompilationDiagnostic": diagnostics.CompilationDiagnostic,
        "CompilationError": diagnostics.CompilationError,
        "compile_harness_instance": harness.compile_harness_instance,
        "compile_execution_program": program.compile_execution_program,
        "compile_run_bundle": bundle.compile_run_bundle,
        "_operation_definition_for_compilation": operations._operation_definition_for_compilation,
    }
    for name, canonical in expected.items():
        assert getattr(facade, name) is canonical
        assert getattr(compilation, name) is canonical


def test_compiler_facade_is_stable_under_both_import_orders() -> None:
    programs = (
        """
import aec_bench.meta_harness.compiler as facade
import aec_bench.meta_harness.compilation as canonical
assert facade.CompilationError is canonical.CompilationError
assert facade.compile_run_bundle is canonical.compile_run_bundle
""",
        """
import aec_bench.meta_harness.compilation as canonical
import aec_bench.meta_harness.compiler as facade
assert facade.CompilationError is canonical.CompilationError
assert facade.compile_run_bundle is canonical.compile_run_bundle
""",
    )

    for program in programs:
        subprocess.run(
            [sys.executable, "-c", program],
            check=True,
        )
