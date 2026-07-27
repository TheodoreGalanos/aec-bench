# ABOUTME: Characterizes the repair runtime package boundary and stable facade aliases.
# ABOUTME: Prevents decomposed modules from becoming duplicate or competing implementations.

from __future__ import annotations

from aec_bench.meta_harness import repair_runtime
from aec_bench.meta_harness.repair_runtime import (
    contracts,
    diagnosis,
    evidence,
    orchestration,
    patching,
    persistence,
)


def test_repair_runtime_facade_exports_each_canonical_implementation() -> None:
    assert repair_runtime.RepairPatchProposal is contracts.RepairPatchProposal
    assert repair_runtime.RepairRuntimeEvidence is contracts.RepairRuntimeEvidence
    assert repair_runtime.RepairAttemptPlan is contracts.RepairAttemptPlan
    assert repair_runtime.diagnose_harness_turn_limit is diagnosis.diagnose_harness_turn_limit
    assert repair_runtime._repair_output_artifact_evidence is evidence._repair_output_artifact_evidence
    assert repair_runtime.RepairRuntime is orchestration.RepairRuntime
    assert repair_runtime.materialize_program_declared_stage_graph is (
        patching.materialize_program_declared_stage_graph
    )
    assert repair_runtime._REPAIR_RULE_REGISTRY is patching._REPAIR_RULE_REGISTRY
    assert repair_runtime.StoredRepairArtifact is persistence.StoredRepairArtifact
    assert repair_runtime.RepairRuntimeExecution is persistence.RepairRuntimeExecution
