# ABOUTME: Exposes the canonical public API for deterministic adaptive-harness compilation.
# ABOUTME: Reexports each stable symbol from its single cohesive implementation module.

from .bundle import compile_run_plan
from .diagnostics import (
    CompilationDiagnostic,
    CompilationError,
    CompilationOwner,
)
from .harness import compile_harness_instance
from .operations import _operation_definition_for_compilation
from .profile import ProgramCompilationProfile
from .program import compile_execution_program

__all__ = (
    "CompilationDiagnostic",
    "CompilationError",
    "CompilationOwner",
    "ProgramCompilationProfile",
    "_operation_definition_for_compilation",
    "compile_execution_program",
    "compile_harness_instance",
    "compile_run_plan",
)
