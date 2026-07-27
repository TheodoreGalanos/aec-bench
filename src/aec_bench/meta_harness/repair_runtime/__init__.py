# ABOUTME: Preserves the stable repair-runtime import surface across cohesive package modules.
# ABOUTME: Re-exports canonical contracts, diagnosis, patching, evidence, persistence, and orchestration symbols.

from aec_bench.meta_harness.repair_runtime import (
    contracts,
    diagnosis,
    evidence,
    orchestration,
    patching,
    persistence,
)
from aec_bench.meta_harness.repair_runtime.contracts import (
    HarnessAgentCapabilityPatch,
    HarnessAgentMaxTurnsPatch,
    ProgramCoalesceTaskBatchPatch,
    ProgramMaterializeDeclaredStageGraphPatch,
    ProgramMaxTotalAttemptsPatch,
    ProgramNodeRetryPatch,
    RepairAgentExecutionEvidence,
    RepairAttemptPlan,
    RepairDeclaredStageGraphEvidence,
    RepairEvidenceUsePolicy,
    RepairMonolithicRunBatchEvidence,
    RepairNoPatchProposal,
    RepairOutputArtifactEvidence,
    RepairPatchProposal,
    RepairProgramExecutionEvidence,
    RepairProgramNodeFailureEvidence,
    RepairRunArtifactManifest,
    RepairRuntimeEvidence,
    RepairRuntimePatch,
    RepairSeedExecution,
    RepairTerminalRecord,
    RepairTrialEvidence,
    RepairVerifierEvidence,
    RepairVerifierPolicy,
)
from aec_bench.meta_harness.repair_runtime.diagnosis import (
    CONFLICTING_MUTABLE_FAILURE_ATTRIBUTION_CODE,
    DiagnosisFunction,
    conflicting_mutable_failure_attribution,
    diagnose_harness_agent_capability,
    diagnose_harness_turn_limit,
    diagnose_program_attempt_limit,
    diagnose_program_batch_coalescing,
    diagnose_program_declared_stage_graph_materialization,
    diagnose_program_retry,
)
from aec_bench.meta_harness.repair_runtime.evidence import (
    _has_output_commit_attestation as _has_output_commit_attestation,
)
from aec_bench.meta_harness.repair_runtime.evidence import (
    _repair_output_artifact_evidence as _repair_output_artifact_evidence,
)
from aec_bench.meta_harness.repair_runtime.orchestration import RepairRuntime
from aec_bench.meta_harness.repair_runtime.patching import (
    _REPAIR_RULE_REGISTRY as _REPAIR_RULE_REGISTRY,
)
from aec_bench.meta_harness.repair_runtime.patching import (
    _patch_agent_capability as _patch_agent_capability,
)
from aec_bench.meta_harness.repair_runtime.patching import (
    _patch_program_retry as _patch_program_retry,
)
from aec_bench.meta_harness.repair_runtime.patching import (
    materialize_program_declared_stage_graph,
    validate_program_batch_coalescing_source,
    validate_program_declared_stage_graph_source,
)
from aec_bench.meta_harness.repair_runtime.persistence import (
    RepairRuntimeExecution,
    StoredRepairArtifact,
    StoredRepairRunArtifact,
)

__all__ = [
    "CONFLICTING_MUTABLE_FAILURE_ATTRIBUTION_CODE",
    "DiagnosisFunction",
    "HarnessAgentCapabilityPatch",
    "HarnessAgentMaxTurnsPatch",
    "ProgramCoalesceTaskBatchPatch",
    "ProgramMaterializeDeclaredStageGraphPatch",
    "ProgramMaxTotalAttemptsPatch",
    "ProgramNodeRetryPatch",
    "RepairAgentExecutionEvidence",
    "RepairAttemptPlan",
    "RepairDeclaredStageGraphEvidence",
    "RepairEvidenceUsePolicy",
    "RepairMonolithicRunBatchEvidence",
    "RepairNoPatchProposal",
    "RepairOutputArtifactEvidence",
    "RepairPatchProposal",
    "RepairProgramExecutionEvidence",
    "RepairProgramNodeFailureEvidence",
    "RepairRunArtifactManifest",
    "RepairRuntime",
    "RepairRuntimeEvidence",
    "RepairRuntimeExecution",
    "RepairRuntimePatch",
    "RepairSeedExecution",
    "RepairTerminalRecord",
    "RepairTrialEvidence",
    "RepairVerifierEvidence",
    "RepairVerifierPolicy",
    "StoredRepairArtifact",
    "StoredRepairRunArtifact",
    "conflicting_mutable_failure_attribution",
    "contracts",
    "diagnose_harness_agent_capability",
    "diagnose_harness_turn_limit",
    "diagnose_program_attempt_limit",
    "diagnose_program_batch_coalescing",
    "diagnose_program_declared_stage_graph_materialization",
    "diagnose_program_retry",
    "diagnosis",
    "evidence",
    "materialize_program_declared_stage_graph",
    "orchestration",
    "patching",
    "persistence",
    "validate_program_batch_coalescing_source",
    "validate_program_declared_stage_graph_source",
]
