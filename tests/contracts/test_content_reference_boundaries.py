# ABOUTME: Tests the boundary between ordinary strict contracts and content references.
# ABOUTME: Proves kernel domain models do not inherit the current content-addressed base.

from __future__ import annotations

import pytest

from aec_bench.contracts.content_address import ContentAddressedModel
from aec_bench.contracts.evaluation_outcome import EvaluationOutcome
from aec_bench.contracts.evaluation_plane import Critic, EvaluationRegime
from aec_bench.contracts.execution_program import CompiledExecutionProgram, ExecutionProgram
from aec_bench.contracts.harness_instance import CompiledHarnessInstance, HarnessSpec
from aec_bench.contracts.harness_kernel import KernelCapabilitySpec, KernelManifest
from aec_bench.contracts.run_bundle import RunPlan
from aec_bench.contracts.stage_execution import (
    DeclaredStageGraph,
    StageContextManifest,
    StageExecutionReceipt,
    StageOutput,
)
from aec_bench.contracts.task_review_snapshot import ReviewSnapshot, TaskReviewSnapshot
from aec_bench.contracts.task_snapshot import ArtifactTaskSnapshotRef, RepositoryTaskSnapshotRef
from aec_bench.contracts.validators import FrozenStrictModel
from aec_bench.harness.program_execution.contracts import ProgramExecutionResult


@pytest.mark.parametrize(
    "contract_type",
    [
        KernelCapabilitySpec,
        KernelManifest,
        HarnessSpec,
        CompiledHarnessInstance,
        ExecutionProgram,
        CompiledExecutionProgram,
        Critic,
        EvaluationRegime,
        EvaluationOutcome,
        RunPlan,
        ReviewSnapshot,
        TaskReviewSnapshot,
        ArtifactTaskSnapshotRef,
        RepositoryTaskSnapshotRef,
        DeclaredStageGraph,
        StageContextManifest,
        StageOutput,
        StageExecutionReceipt,
        ProgramExecutionResult,
    ],
)
def test_ordinary_execution_contract_has_no_content_reference(contract_type: type[FrozenStrictModel]) -> None:
    assert not issubclass(contract_type, ContentAddressedModel)
    assert "content_sha256" not in contract_type.model_fields
