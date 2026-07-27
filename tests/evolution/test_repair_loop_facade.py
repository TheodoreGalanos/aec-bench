# ABOUTME: Guards the stable repair-loop import surface while implementation ownership is decomposed.
# ABOUTME: Proves public contracts and orchestration retain exact object identity across the facade.

from __future__ import annotations

from aec_bench.evolution import repair_loop
from aec_bench.evolution.repair_lifecycle import contracts, orchestration


def test_repair_loop_contract_facade_preserves_object_identity() -> None:
    public_contracts = (
        "RepairOwner",
        "RepairFailureDomain",
        "RepairLoopStage",
        "RepairLoopStatus",
        "RepairRewardCoverage",
        "RepairExecutionStatus",
        "RepairPairingSpec",
        "RepairProgramTemplate",
        "RepairCandidate",
        "CompiledRepairCandidate",
        "RepairRunResult",
        "RepairRunObservation",
        "RepairExecutionObservation",
        "VerifiedRepairRun",
        "RepairExecutionRecoveryAttempt",
        "RepairExecutionRecoveryDecision",
        "RepairDiagnosis",
        "RepairPatchRequest",
        "RepairLoopRequest",
        "RepairLoopResult",
        "RepairLoopDiagnostic",
        "RepairLoopError",
    )

    for name in public_contracts:
        assert getattr(repair_loop, name) is getattr(contracts, name)


def test_repair_loop_orchestration_facade_preserves_object_identity() -> None:
    public_orchestration = ("RepairLoopDependencies", "run_repair_loop")

    for name in public_orchestration:
        assert getattr(repair_loop, name) is getattr(orchestration, name)
