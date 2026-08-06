# ABOUTME: Exposes the canonical adaptive-cycle contracts, orchestration, and verification surface.
# ABOUTME: Provides the current adaptive-cycle implementation identity.

from aec_bench.meta_harness.adaptive_cycle_runtime.contracts import (
    AdaptiveCycleExecutors,
    AdaptiveCycleOutcome,
    AdaptiveCycleReport,
    AdaptiveCycleResult,
    AdaptiveCycleSpec,
    AdaptiveCycleTerminalReason,
    AdaptiveCycleTerminalStage,
    AdaptiveFactorialStageSpec,
)
from aec_bench.meta_harness.adaptive_cycle_runtime.materialization import (
    materialize_child_factorial_request,
)
from aec_bench.meta_harness.adaptive_cycle_runtime.orchestration import (
    run_adaptive_cycle,
)
from aec_bench.meta_harness.adaptive_cycle_runtime.verification import (
    load_adaptive_cycle_report,
    verify_adaptive_cycle_report,
)
from aec_bench.meta_harness.adaptive_diagnosis import (
    HarnessMaxTurnsDiagnosisRule,
    ProgramRetryDiagnosisRule,
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
    "verify_adaptive_cycle_report",
)
