# ABOUTME: Preserves the stable adaptive-cycle import surface for existing callers.
# ABOUTME: Reexports canonical contracts and runtime behavior without duplicating ownership.

from aec_bench.meta_harness.adaptive_cycle_runtime import (
    AdaptiveCycleExecutors,
    AdaptiveCycleOutcome,
    AdaptiveCycleReport,
    AdaptiveCycleResult,
    AdaptiveCycleSpec,
    AdaptiveCycleTerminalReason,
    AdaptiveCycleTerminalStage,
    AdaptiveFactorialStageSpec,
    HarnessMaxTurnsDiagnosisRule,
    ProgramRetryDiagnosisRule,
    load_adaptive_cycle_report,
    materialize_child_factorial_request,
    run_adaptive_cycle,
    run_adaptive_cycle_v1_compatibility,
    verify_adaptive_cycle_report,
)

__all__ = (
    "AdaptiveCycleExecutors",
    "AdaptiveCycleOutcome",
    "AdaptiveCycleReport",
    "AdaptiveCycleResult",
    "AdaptiveCycleSpec",
    "AdaptiveCycleTerminalReason",
    "AdaptiveCycleTerminalStage",
    "AdaptiveFactorialStageSpec",
    "HarnessMaxTurnsDiagnosisRule",
    "ProgramRetryDiagnosisRule",
    "load_adaptive_cycle_report",
    "materialize_child_factorial_request",
    "run_adaptive_cycle",
    "run_adaptive_cycle_v1_compatibility",
    "verify_adaptive_cycle_report",
)
