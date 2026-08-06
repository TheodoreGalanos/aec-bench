# ABOUTME: Tests missing-primitive evidence capture and fixed-kernel change governance.
# ABOUTME: Proves recurrence, approval, regression, version, and holdout gates without mutating K.

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from aec_bench.contracts.execution_program import ActionNode, ExecutionProgram, StopNode, StopOutcome
from aec_bench.contracts.harness_instance import CompiledHarnessInstance
from aec_bench.contracts.harness_kernel import (
    KernelCapabilityKind,
    KernelCapabilitySpec,
    KernelPortSpec,
)
from aec_bench.meta_harness.compilation import CompilationError, compile_execution_program
from aec_bench.meta_harness.kernel_catalogue import default_kernel_registry
from aec_bench.meta_harness.kernel_evolution import (
    EvidenceSelectionBasis,
    HumanApprovalArtifact,
    KernelChangeRejectionCode,
    KernelChangeRequest,
    KernelRegressionEvidence,
    KernelVersionBump,
    MissingPrimitiveEvidence,
    MissingPrimitiveEvidenceSet,
    MissingPrimitiveFailure,
    MissingPrimitiveObservationBoundary,
    MissingPrimitiveSource,
    PromotionEvidenceSplit,
    RuntimeMissingPrimitiveDiagnostic,
    capture_compiler_missing_primitive,
    capture_runtime_missing_primitive,
    decide_kernel_change,
)
from tests.support.adaptive_harness import build_adaptive_bundle, write_adaptive_task


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _target_kernel_version(*, minor_steps: int = 1) -> str:
    major, minor, _patch = (int(part) for part in default_kernel_registry().manifest.version.split("."))
    return f"{major}.{minor + minor_steps}.0"


def _requested_capability() -> KernelCapabilitySpec:
    return KernelCapabilitySpec(
        capability_id="aecbench.operation.distributed-join",
        version="1.0.0",
        kind=KernelCapabilityKind.PROGRAM_OPERATION,
        summary="Join independently executed branches with an evidence-completeness gate.",
        inputs=(KernelPortSpec(name="branches", schema_ref="aecbench://branch-results/v1"),),
        outputs=(KernelPortSpec(name="joined", schema_ref="aecbench://joined-result/v1"),),
        configuration_schema_ref="aecbench://kernel/program-operation/distributed-join/v1",
    )


def _source(
    family: str,
    *,
    split: PromotionEvidenceSplit = PromotionEvidenceSplit.OPTIMIZATION,
) -> MissingPrimitiveSource:
    return MissingPrimitiveSource(
        task_family_id=family,
        task_id=f"{family}/case-01",
        bundle_id=f"bundle-{family}",
        world_id=f"world-{family}",
        split=split,
    )


def _runtime_evidence(
    family: str,
    *,
    evidence_id: str | None = None,
    split: PromotionEvidenceSplit = PromotionEvidenceSplit.OPTIMIZATION,
) -> MissingPrimitiveEvidence:
    registry = default_kernel_registry()
    return capture_runtime_missing_primitive(
        evidence_id=evidence_id or f"missing-{family}",
        kernel_ref=registry.manifest.ref,
        requested_capability=_requested_capability(),
        source=_source(family, split=split),
        diagnostic=RuntimeMissingPrimitiveDiagnostic(
            code="operation_handler_missing",
            message="No trusted runtime handler implements distributed join.",
            subject_ids=("distributed-join",),
        ),
    )


def _evidence_set(
    evidence: tuple[MissingPrimitiveEvidence, ...],
) -> MissingPrimitiveEvidenceSet:
    registry = default_kernel_registry()
    return MissingPrimitiveEvidenceSet(
        evidence_set_id="distributed-join-recurrence",
        source_kernel_ref=registry.manifest.ref,
        requested_capability_sha256=_requested_capability().content_sha256,
        selection_basis=EvidenceSelectionBasis.CAPABILITY_RECURRENCE,
        minimum_distinct_task_families=2,
        evidence_refs=tuple(item.ref for item in evidence),
    )


def _approval(
    evidence_set: MissingPrimitiveEvidenceSet,
    *,
    approved: bool = True,
    target_version: str | None = None,
) -> HumanApprovalArtifact:
    registry = default_kernel_registry()
    resolved_target_version = target_version or _target_kernel_version()
    return HumanApprovalArtifact(
        approval_id="kernel-change-approval",
        approved_by="aec-bench-kernel-owner",
        approved=approved,
        source_kernel_ref=registry.manifest.ref,
        requested_capability_sha256=_requested_capability().content_sha256,
        evidence_set_sha256=evidence_set.content_sha256,
        target_kernel_version=resolved_target_version,
        artifact_sha256=_sha("signed-human-approval"),
    )


def _regression(
    evidence_set: MissingPrimitiveEvidenceSet,
    *,
    passed: bool = True,
    target_version: str | None = None,
) -> KernelRegressionEvidence:
    registry = default_kernel_registry()
    resolved_target_version = target_version or _target_kernel_version()
    return KernelRegressionEvidence(
        regression_id="kernel-regression-suite",
        suite_id="adaptive-kernel-regression",
        source_kernel_ref=registry.manifest.ref,
        requested_capability_sha256=_requested_capability().content_sha256,
        evidence_set_sha256=evidence_set.content_sha256,
        target_kernel_version=resolved_target_version,
        passed=passed,
        artifact_sha256=_sha("regression-results"),
    )


def _request(
    evidence: tuple[MissingPrimitiveEvidence, ...],
    *,
    approval: HumanApprovalArtifact | None = None,
    regressions: tuple[KernelRegressionEvidence, ...] | None = None,
    target_version: str | None = None,
    version_bump: KernelVersionBump = KernelVersionBump.MINOR,
) -> KernelChangeRequest:
    registry = default_kernel_registry()
    evidence_set = _evidence_set(evidence)
    resolved_target_version = target_version or _target_kernel_version()
    return KernelChangeRequest(
        request_id="add-distributed-join",
        source_kernel_ref=registry.manifest.ref,
        requested_capability=_requested_capability(),
        evidence_set=evidence_set,
        target_kernel_version=resolved_target_version,
        version_bump=version_bump,
        approval=approval,
        regression_evidence=regressions or (),
    )


def _approved_request(
    evidence: tuple[MissingPrimitiveEvidence, ...],
    *,
    target_version: str | None = None,
    version_bump: KernelVersionBump = KernelVersionBump.MINOR,
) -> KernelChangeRequest:
    evidence_set = _evidence_set(evidence)
    resolved_target_version = target_version or _target_kernel_version()
    return _request(
        evidence,
        approval=_approval(evidence_set, target_version=resolved_target_version),
        regressions=(_regression(evidence_set, target_version=resolved_target_version),),
        target_version=resolved_target_version,
        version_bump=version_bump,
    )


def _compile_failure(harness: CompiledHarnessInstance, program_id: str) -> CompilationError:
    registry = default_kernel_registry()
    program = ExecutionProgram(
        program_id=program_id,
        version="1.0.0",
        harness_ref=harness.ref,
        nodes=(
            ActionNode(node_id="join", operation_id="distributed_join.v1"),
            StopNode(node_id="stop", depends_on=("join",), outcome=StopOutcome.SUCCEEDED),
        ),
    )
    with pytest.raises(CompilationError) as captured:
        compile_execution_program(program, harness=harness, registry=registry)
    return captured.value


def test_missing_primitive_evidence_is_content_addressed_and_records_complete_source() -> None:
    evidence = _runtime_evidence("stormwater")
    rebuilt = MissingPrimitiveEvidence.model_validate(evidence.model_dump(mode="json"))

    assert rebuilt == evidence
    assert rebuilt.ref.content_sha256 == evidence.content_sha256
    assert rebuilt.requested_capability.capability_id == "aecbench.operation.distributed-join"
    assert rebuilt.source == _source("stormwater")
    assert rebuilt.failure.boundary is MissingPrimitiveObservationBoundary.RUNTIME
    assert rebuilt.failure.code == "operation_handler_missing"


def test_capture_of_compiler_and_runtime_observations_never_mutates_fixed_kernel(tmp_path: Path) -> None:
    registry = default_kernel_registry()
    before = registry.manifest
    write_adaptive_task(tmp_path / "tasks")
    bundle = build_adaptive_bundle(tasks_root=tmp_path / "tasks", registry=registry)
    failure = _compile_failure(bundle.harness, "needs-join")

    compiler_evidence = capture_compiler_missing_primitive(
        evidence_id="compiler-missing-join",
        kernel_ref=registry.manifest.ref,
        requested_capability=_requested_capability(),
        source=_source("stormwater"),
        error=failure,
    )
    runtime_evidence = _runtime_evidence("road-visual")

    assert compiler_evidence.failure == MissingPrimitiveFailure(
        boundary=MissingPrimitiveObservationBoundary.COMPILER,
        owner="program",
        code="operation_outside_harness_surface",
        message="program operation is not exported by Hx: distributed_join.v1",
        subject_ids=("distributed_join.v1", "needs-join"),
    )
    assert runtime_evidence.failure.boundary is MissingPrimitiveObservationBoundary.RUNTIME
    assert registry.manifest == before
    assert registry.manifest.ref == before.ref
    with pytest.raises(ValueError, match="unknown kernel capability"):
        registry.capability(_requested_capability().capability_id)


def test_frozen_evidence_set_rejects_duplicate_references_and_reward_selection_fields() -> None:
    evidence = _runtime_evidence("stormwater")
    registry = default_kernel_registry()

    with pytest.raises(ValidationError, match="evidence references must be unique"):
        MissingPrimitiveEvidenceSet(
            evidence_set_id="duplicates",
            source_kernel_ref=registry.manifest.ref,
            requested_capability_sha256=_requested_capability().content_sha256,
            evidence_refs=(evidence.ref, evidence.ref),
        )

    payload = _evidence_set((evidence,)).model_dump(mode="json")
    payload["objective_reward"] = 1.0
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        MissingPrimitiveEvidenceSet.model_validate(payload)


def test_repeated_observations_from_one_task_family_do_not_count_as_recurrence() -> None:
    evidence = (
        _runtime_evidence("stormwater", evidence_id="stormwater-a"),
        _runtime_evidence("stormwater", evidence_id="stormwater-b"),
    )
    request = _approved_request(evidence)

    decision = decide_kernel_change(
        request,
        evidence_records=evidence,
        installed_registry=default_kernel_registry(),
    )

    assert decision.eligible is False
    assert decision.distinct_task_family_ids == ("stormwater",)
    assert decision.rejection_codes == (KernelChangeRejectionCode.INSUFFICIENT_DISTINCT_TASK_FAMILIES,)
    assert decision.proposal is None


def test_holdout_observations_cannot_enter_kernel_change_selection() -> None:
    evidence = (
        _runtime_evidence("stormwater"),
        _runtime_evidence(
            "road-visual",
            split=PromotionEvidenceSplit.STRUCTURAL_HOLDOUT,
        ),
    )
    request = _approved_request(evidence)

    decision = decide_kernel_change(
        request,
        evidence_records=evidence,
        installed_registry=default_kernel_registry(),
    )

    assert decision.rejection_codes == (KernelChangeRejectionCode.SELECTION_SPLIT_NOT_ALLOWED,)
    assert decision.proposal is None


def test_missing_and_tampered_evidence_are_rejected_against_frozen_set() -> None:
    first = _runtime_evidence("stormwater")
    second = _runtime_evidence("road-visual")
    request = _approved_request((first, second))

    missing = decide_kernel_change(
        request,
        evidence_records=(first,),
        installed_registry=default_kernel_registry(),
    )
    tampered_second = second.model_copy(
        update={"source": _source("coastal-flood")},
    )
    tampered = decide_kernel_change(
        request,
        evidence_records=(first, tampered_second),
        installed_registry=default_kernel_registry(),
    )

    assert missing.rejection_codes == (KernelChangeRejectionCode.EVIDENCE_MISSING,)
    assert tampered.rejection_codes == (KernelChangeRejectionCode.EVIDENCE_TAMPERED,)


def test_tampered_approval_and_regression_artifacts_fail_closed() -> None:
    evidence = (_runtime_evidence("stormwater"), _runtime_evidence("road-visual"))
    evidence_set = _evidence_set(evidence)
    approval = _approval(evidence_set)
    regression = _regression(evidence_set)
    tampered_approval = approval.model_copy(update={"approved_by": "unbound-approver"})
    tampered_regression = regression.model_copy(update={"suite_id": "unbound-suite"})

    with pytest.raises(ValidationError, match="content_sha256 does not match"):
        _request(
            evidence,
            approval=tampered_approval,
            regressions=(regression,),
        )
    with pytest.raises(ValidationError, match="content_sha256 does not match"):
        _request(
            evidence,
            approval=approval,
            regressions=(tampered_regression,),
        )


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        ("approval-missing", KernelChangeRejectionCode.APPROVAL_MISSING),
        ("approval-rejected", KernelChangeRejectionCode.APPROVAL_NOT_GRANTED),
        ("regression-missing", KernelChangeRejectionCode.REGRESSION_EVIDENCE_MISSING),
        ("regression-failed", KernelChangeRejectionCode.REGRESSION_TESTS_FAILED),
        ("invalid-version", KernelChangeRejectionCode.INVALID_VERSION_PROGRESSION),
    ],
)
def test_governance_artifacts_and_version_progression_are_mandatory(case: str, expected: str) -> None:
    evidence = (_runtime_evidence("stormwater"), _runtime_evidence("road-visual"))
    evidence_set = _evidence_set(evidence)
    approval: HumanApprovalArtifact | None = _approval(evidence_set)
    regressions: tuple[KernelRegressionEvidence, ...] = (_regression(evidence_set),)
    target_version = _target_kernel_version()
    version_bump = KernelVersionBump.MINOR
    if case == "approval-missing":
        approval = None
    elif case == "approval-rejected":
        approval = _approval(evidence_set, approved=False)
    elif case == "regression-missing":
        regressions = ()
    elif case == "regression-failed":
        regressions = (_regression(evidence_set, passed=False),)
    else:
        target_version = _target_kernel_version(minor_steps=2)
        approval = _approval(evidence_set, target_version=target_version)
        regressions = (_regression(evidence_set, target_version=target_version),)
    request = _request(
        evidence,
        approval=approval,
        regressions=regressions,
        target_version=target_version,
        version_bump=version_bump,
    )

    decision = decide_kernel_change(
        request,
        evidence_records=evidence,
        installed_registry=default_kernel_registry(),
    )

    assert expected in decision.rejection_codes
    assert decision.proposal is None


def test_several_real_compile_failures_form_governed_proposal_while_k_remains_fixed(tmp_path: Path) -> None:
    registry = default_kernel_registry()
    before_ref = registry.manifest.ref
    write_adaptive_task(tmp_path / "tasks")
    bundle = build_adaptive_bundle(tasks_root=tmp_path / "tasks", registry=registry)
    evidence = tuple(
        capture_compiler_missing_primitive(
            evidence_id=f"missing-join-{family}",
            kernel_ref=registry.manifest.ref,
            requested_capability=_requested_capability(),
            source=_source(family),
            error=_compile_failure(bundle.harness, f"needs-join-{family}"),
        )
        for family in ("stormwater", "road-visual", "fire-water")
    )
    request = _approved_request(evidence)

    first = decide_kernel_change(
        request,
        evidence_records=evidence,
        installed_registry=registry,
    )
    second = decide_kernel_change(
        request,
        evidence_records=tuple(reversed(evidence)),
        installed_registry=registry,
    )

    assert first == second
    assert first.eligible is True
    assert first.rejection_codes == ()
    assert first.distinct_task_family_ids == ("fire-water", "road-visual", "stormwater")
    assert first.proposal is not None
    assert first.proposal.status == "governed_for_implementation"
    assert first.proposal.source_evidence_set == request.evidence_set
    assert first.proposal.target_kernel_version == _target_kernel_version()
    assert registry.manifest.ref == before_ref
    assert request.source_kernel_ref == before_ref
    assert first.proposal.source_kernel_ref == before_ref
    with pytest.raises(ValueError, match="unknown kernel capability"):
        registry.capability(_requested_capability().capability_id)
