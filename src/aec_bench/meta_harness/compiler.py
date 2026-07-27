# ABOUTME: Preserves the historical import surface for deterministic harness compilation.
# ABOUTME: Reexports canonical compilation symbols without owning implementation behavior.

from aec_bench.meta_harness.compilation import (
    CompilationDiagnostic,
    CompilationError,
    CompilationOwner,
    ProgramCompilationProfile,
    _operation_definition_for_compilation,
    compile_execution_program,
    compile_harness_instance,
    compile_run_bundle,
)

__all__ = (
    "CompilationDiagnostic",
    "CompilationError",
    "CompilationOwner",
    "ProgramCompilationProfile",
    "_operation_definition_for_compilation",
    "compile_execution_program",
    "compile_harness_instance",
    "compile_run_bundle",
)
