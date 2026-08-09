# ABOUTME: Tests the immutable RunBundle that binds fixed K, compiled Hx, and compiled px for Harbor.
# ABOUTME: Verifies cross-contract identity consistency, typed payload bindings, and pinned task snapshots.

import pytest
from pydantic import ValidationError

from aec_bench.contracts.execution_program import (
    ActionNode,
    CompiledExecutionProgram,
    ExecutionProgram,
    RetryPolicy,
    StopNode,
    StopOutcome,
)
from aec_bench.contracts.harness_instance import (
    AgentBindingConfig,
    CompiledHarnessBinding,
    CompiledHarnessInstance,
    ComputeBindingConfig,
    HarnessTopologyRole,
    ProgramOperationRef,
    ProgramOperationSpec,
    ProgramSurface,
    ResultImportBindingConfig,
    TaskSourceBindingConfig,
    VerificationBindingConfig,
    VerificationPlacement,
    VerificationStage,
)
from aec_bench.contracts.harness_kernel import (
    KernelCapabilityKind,
    KernelCapabilitySpec,
    KernelImplementationIdentity,
    KernelManifest,
    KernelPortSpec,
    KernelSourceDigest,
)
from aec_bench.contracts.run_bundle import (
    HarborRunPayload,
    RunBundle,
    RunTarget,
    TaskReviewSnapshotRef,
    TaskSnapshotRef,
)
from aec_bench.contracts.task_definition import Visibility


def _capability(capability_id: str, kind: KernelCapabilityKind) -> KernelCapabilitySpec:
    return KernelCapabilitySpec(
        capability_id=capability_id,
        version="1.0.0",
        kind=kind,
        summary=f"Capability {capability_id}.",
        outputs=(KernelPortSpec(name="result", schema_ref=f"aecbench://{kind.value}/v1"),),
    )


def _bundle_parts() -> tuple[KernelManifest, CompiledHarnessInstance, CompiledExecutionProgram, HarborRunPayload]:
    capabilities = {
        "tasks": _capability("aecbench.tasks.registry", KernelCapabilityKind.TASK_SOURCE),
        "agent": _capability("aecbench.adapter.lambda-rlm", KernelCapabilityKind.AGENT_ADAPTER),
        "compute": _capability("aecbench.backend.harbor", KernelCapabilityKind.EXECUTION_BACKEND),
        "verify": _capability("aecbench.verifier.harbor", KernelCapabilityKind.VERIFIER),
        "import": _capability("aecbench.results.trial-record", KernelCapabilityKind.RESULT_IMPORTER),
        "run": _capability("aecbench.operation.run-batch", KernelCapabilityKind.PROGRAM_OPERATION),
    }
    kernel = KernelManifest(
        kernel_id="aec-bench",
        version="1.0.0",
        capabilities=tuple(capabilities.values()),
        implementation=KernelImplementationIdentity(
            sources=(KernelSourceDigest(path="kernel.py", sha256="a" * 64),),
        ),
    )
    bindings = (
        CompiledHarnessBinding(
            binding_id="tasks",
            capability_ref=capabilities["tasks"].ref,
            capability_kind=capabilities["tasks"].kind,
            topology_role=HarnessTopologyRole.SOURCE,
            configuration=TaskSourceBindingConfig(task_refs=("civil/calculation/alpha",)),
        ),
        CompiledHarnessBinding(
            binding_id="agent",
            capability_ref=capabilities["agent"].ref,
            capability_kind=capabilities["agent"].kind,
            depends_on=("tasks",),
            topology_role=HarnessTopologyRole.ORCHESTRATOR,
            configuration=AgentBindingConfig(agent_name="lambda-rlm", model="claude-sonnet-4-6"),
        ),
        CompiledHarnessBinding(
            binding_id="compute",
            capability_ref=capabilities["compute"].ref,
            capability_kind=capabilities["compute"].kind,
            depends_on=("agent",),
            topology_role=HarnessTopologyRole.SERVICE,
            configuration=ComputeBindingConfig(max_concurrency=1),
        ),
        CompiledHarnessBinding(
            binding_id="verify",
            capability_ref=capabilities["verify"].ref,
            capability_kind=capabilities["verify"].kind,
            depends_on=("compute",),
            topology_role=HarnessTopologyRole.GATE,
            configuration=VerificationBindingConfig(enabled=True, required=True),
        ),
        CompiledHarnessBinding(
            binding_id="import",
            capability_ref=capabilities["import"].ref,
            capability_kind=capabilities["import"].kind,
            depends_on=("verify",),
            topology_role=HarnessTopologyRole.SINK,
            configuration=ResultImportBindingConfig(ledger_namespace="adaptive-harness"),
        ),
    )
    surface = ProgramSurface(
        surface_id="surface",
        operations=(
            ProgramOperationSpec(
                operation_id="run_batch.v1",
                capability_ref=capabilities["run"].ref,
                input_schema_ref="aecbench://run-batch-input/v1",
                output_schema_ref="aecbench://trial-record-set/v1",
                binding_ids=("tasks", "agent", "compute", "verify", "import"),
                allowed_task_refs=("civil/calculation/alpha",),
            ),
        ),
    )
    harness = CompiledHarnessInstance(
        instance_id="hx-alpha",
        kernel_ref=kernel.ref,
        source_recipe_sha256="c" * 64,
        bindings=bindings,
        program_surface=surface,
    )
    source_program = ExecutionProgram(
        program_id="px-alpha",
        version="1.0.0",
        harness_ref=harness.ref,
        nodes=(
            ActionNode(node_id="run", operation_id="run_batch.v1"),
            StopNode(node_id="stop", depends_on=("run",), outcome=StopOutcome.SUCCEEDED),
        ),
    )
    program = CompiledExecutionProgram(
        program_id=source_program.program_id,
        version=source_program.version,
        harness_ref=harness.ref,
        source_program_sha256=source_program.content_sha256,
        surface_sha256=surface.content_sha256,
        nodes=source_program.nodes,
        limits=source_program.limits,
        topological_order=("run", "stop"),
        operation_refs=(surface.operations[0].ref,),
    )
    payload = HarborRunPayload(
        experiment_id="adaptive-alpha",
        task_refs=("civil/calculation/alpha",),
        agent_binding_id="agent",
        compute_binding_id="compute",
        verification_binding_id="verify",
        result_import_binding_id="import",
        repetitions=1,
    )
    return kernel, harness, program, payload


def _compile_for_surface(
    harness: CompiledHarnessInstance,
    surface: ProgramSurface,
    *,
    retry: RetryPolicy | None = None,
) -> tuple[CompiledHarnessInstance, CompiledExecutionProgram]:
    compiled_harness = CompiledHarnessInstance(
        instance_id=harness.instance_id,
        kernel_ref=harness.kernel_ref,
        source_recipe_sha256=harness.source_recipe_sha256,
        contracts=harness.contracts,
        budget=harness.budget,
        recursion_policy=harness.recursion_policy,
        bindings=harness.bindings,
        program_surface=surface,
        compatibility_notes=harness.compatibility_notes,
    )
    source_program = ExecutionProgram(
        program_id="px-alpha",
        version="1.0.0",
        harness_ref=compiled_harness.ref,
        nodes=(
            ActionNode(node_id="run", operation_id="run_batch.v1", retry=retry),
            StopNode(node_id="stop", depends_on=("run",), outcome=StopOutcome.SUCCEEDED),
        ),
    )
    operation = surface.operation("run_batch.v1")
    assert operation is not None
    compiled_program = CompiledExecutionProgram(
        program_id=source_program.program_id,
        version=source_program.version,
        harness_ref=compiled_harness.ref,
        source_program_sha256=source_program.content_sha256,
        surface_sha256=surface.content_sha256,
        nodes=source_program.nodes,
        limits=source_program.limits,
        topological_order=("run", "stop"),
        operation_refs=(operation.ref,),
    )
    return compiled_harness, compiled_program


def test_run_bundle_binds_fixed_kernel_harness_program_and_task_snapshots() -> None:
    kernel, harness, program, payload = _bundle_parts()
    snapshot = TaskSnapshotRef(
        task_id="civil/calculation/alpha",
        definition_sha256="d" * 64,
        package_sha256="e" * 64,
    )
    bundle = RunBundle(
        bundle_id="run-adaptive-alpha",
        kernel_ref=kernel.ref,
        harness=harness,
        program=program,
        target=RunTarget.HARBOR,
        task_snapshots=(snapshot,),
        harbor=payload,
    )

    assert bundle.harness.ref == program.harness_ref
    assert bundle.program.surface_sha256 == harness.program_surface.content_sha256
    assert len(bundle.content_sha256) == 64

    with pytest.raises(ValidationError, match="frozen"):
        bundle.bundle_id = "mutated"

    with pytest.raises(ValidationError, match="target_settings"):
        RunBundle.model_validate(
            {
                **bundle.model_dump(mode="json", exclude={"content_sha256"}),
                "target_settings": {"agents": [{"adapter": "untrusted"}]},
            }
        )


def test_task_snapshot_can_pin_a_task_review_without_template_imports() -> None:
    task_review = TaskReviewSnapshotRef(
        profile_id="bridge-review-lifecycle",
        review_profile_sha256="1" * 64,
        review_sidecar_sha256="2" * 64,
        declared_surface_sha256="3" * 64,
        visibility=Visibility.PUBLIC,
    )
    snapshot = TaskSnapshotRef(
        task_id="civil/review/bridge-alpha",
        definition_sha256="4" * 64,
        package_sha256="5" * 64,
        task_review=task_review,
    )

    assert snapshot.task_review == task_review
    assert snapshot.task_review.visibility is Visibility.PUBLIC
    assert set(snapshot.task_review.model_dump(mode="json")) == {
        "profile_id",
        "review_profile_sha256",
        "review_sidecar_sha256",
        "declared_surface_sha256",
        "visibility",
    }
    assert "task_review" in snapshot.model_dump(mode="json")
    assert "world" not in snapshot.model_dump(mode="json")

    with pytest.raises(ValidationError, match="SHA-256"):
        TaskReviewSnapshotRef(
            profile_id="invalid-review",
            review_profile_sha256="not-a-hash",
            review_sidecar_sha256="2" * 64,
            declared_surface_sha256="3" * 64,
            visibility=Visibility.PUBLIC,
        )


def test_task_snapshot_rejects_pre_cutover_world_fields() -> None:
    with pytest.raises(ValidationError):
        TaskSnapshotRef.model_validate(
            {
                "task_id": "civil/review/bridge-alpha",
                "definition_sha256": "4" * 64,
                "package_sha256": "5" * 64,
                "world": {
                    "world_id": "bridge-review-lifecycle",
                    "world_envelope_sha256": "1" * 64,
                    "world_package_sha256": "2" * 64,
                    "topology_signature_sha256": "3" * 64,
                    "visibility": "public",
                },
            }
        )


def test_run_bundle_rejects_a_program_compiled_for_another_harness() -> None:
    kernel, harness, program, payload = _bundle_parts()
    mismatched_program = CompiledExecutionProgram.model_validate(
        {
            **program.model_dump(mode="json", exclude={"content_sha256", "harness_ref"}),
            "harness_ref": {
                "instance_id": program.harness_ref.instance_id,
                "content_sha256": "f" * 64,
            },
        }
    )

    with pytest.raises(ValidationError, match="program harness_ref does not match"):
        RunBundle(
            bundle_id="run-mismatch",
            kernel_ref=kernel.ref,
            harness=harness,
            program=mismatched_program,
            task_snapshots=(
                TaskSnapshotRef(
                    task_id="civil/calculation/alpha",
                    definition_sha256="d" * 64,
                    package_sha256="e" * 64,
                ),
            ),
            harbor=payload,
        )


def test_run_bundle_preserves_cross_contract_error_order() -> None:
    kernel, harness, program, payload = _bundle_parts()
    mismatched_kernel_ref = kernel.ref.model_copy(update={"content_sha256": "f" * 64})

    with pytest.raises(
        ValidationError,
        match="bundle kernel_ref does not match compiled harness kernel_ref",
    ):
        RunBundle(
            bundle_id="run-ordered-errors",
            kernel_ref=mismatched_kernel_ref,
            harness=harness,
            program=program,
            task_snapshots=(),
            harbor=payload,
        )


def test_run_bundle_rejects_an_operation_ref_not_pinned_to_its_surface() -> None:
    kernel, harness, program, payload = _bundle_parts()
    mismatched_program = CompiledExecutionProgram.model_validate(
        {
            **program.model_dump(mode="json", exclude={"content_sha256", "operation_refs"}),
            "operation_refs": (
                ProgramOperationRef(
                    operation_id="run_batch.v1",
                    content_sha256="f" * 64,
                ),
            ),
        }
    )

    with pytest.raises(ValidationError, match="does not resolve against the bundled harness surface"):
        RunBundle(
            bundle_id="run-operation-mismatch",
            kernel_ref=kernel.ref,
            harness=harness,
            program=mismatched_program,
            task_snapshots=(
                TaskSnapshotRef(
                    task_id="civil/calculation/alpha",
                    definition_sha256="d" * 64,
                    package_sha256="e" * 64,
                ),
            ),
            harbor=payload,
        )


def test_run_bundle_scopes_selected_bindings_to_invoked_operations() -> None:
    kernel, harness, _, payload = _bundle_parts()
    operation = harness.program_surface.operations[0]
    surface = ProgramSurface(
        surface_id="surface-with-unwired-agent",
        operations=(
            ProgramOperationSpec(
                operation_id=operation.operation_id,
                capability_ref=operation.capability_ref,
                input_schema_ref=operation.input_schema_ref,
                output_schema_ref=operation.output_schema_ref,
                binding_ids=("tasks", "compute", "verify", "import"),
                allowed_task_refs=operation.allowed_task_refs,
            ),
        ),
    )
    compiled_harness, compiled_program = _compile_for_surface(harness, surface)

    with pytest.raises(ValidationError, match="selected Harbor binding ids outside invoked operations: agent"):
        RunBundle(
            bundle_id="run-unwired-agent",
            kernel_ref=kernel.ref,
            harness=compiled_harness,
            program=compiled_program,
            task_snapshots=(
                TaskSnapshotRef(
                    task_id="civil/calculation/alpha",
                    definition_sha256="d" * 64,
                    package_sha256="e" * 64,
                ),
            ),
            harbor=payload,
        )


def test_run_bundle_enforces_required_verifier_placement_for_invoked_operations() -> None:
    kernel, harness, _, payload = _bundle_parts()
    operation = harness.program_surface.operations[0]
    surface = ProgramSurface(
        surface_id="surface-with-required-verifier",
        operations=(
            ProgramOperationSpec(
                operation_id=operation.operation_id,
                capability_ref=operation.capability_ref,
                input_schema_ref=operation.input_schema_ref,
                output_schema_ref=operation.output_schema_ref,
                binding_ids=operation.binding_ids,
                allowed_task_refs=operation.allowed_task_refs,
                verifier_placements=(
                    VerificationPlacement(
                        binding_id="verify",
                        stage=VerificationStage.AFTER_OPERATION,
                        required=True,
                    ),
                ),
            ),
        ),
    )
    compiled_harness, compiled_program = _compile_for_surface(harness, surface)
    payload_without_verifier = HarborRunPayload.model_validate(
        {
            **payload.model_dump(mode="json", exclude={"verification_binding_id"}),
            "verification_binding_id": None,
        }
    )

    with pytest.raises(ValidationError, match="required invoked verifier placements"):
        RunBundle(
            bundle_id="run-missing-required-verifier",
            kernel_ref=kernel.ref,
            harness=compiled_harness,
            program=compiled_program,
            task_snapshots=(
                TaskSnapshotRef(
                    task_id="civil/calculation/alpha",
                    definition_sha256="d" * 64,
                    package_sha256="e" * 64,
                ),
            ),
            harbor=payload_without_verifier,
        )


def test_run_bundle_rejects_retry_codes_outside_the_operation_safe_set() -> None:
    kernel, harness, _, payload = _bundle_parts()
    operation = harness.program_surface.operations[0]
    surface = ProgramSurface(
        surface_id="surface-with-retry-taxonomy",
        operations=(
            ProgramOperationSpec(
                operation_id=operation.operation_id,
                capability_ref=operation.capability_ref,
                input_schema_ref=operation.input_schema_ref,
                output_schema_ref=operation.output_schema_ref,
                binding_ids=operation.binding_ids,
                allowed_task_refs=operation.allowed_task_refs,
                supports_retry=True,
                retry_safe_error_codes=("pre_dispatch_capacity_timeout",),
            ),
        ),
    )
    compiled_harness, compiled_program = _compile_for_surface(
        harness,
        surface,
        retry=RetryPolicy(max_attempts=2, retry_on=("unknown_provider_failure",)),
    )

    with pytest.raises(ValidationError, match="outside the operation retry-safe error codes"):
        RunBundle(
            bundle_id="run-unsafe-retry-code",
            kernel_ref=kernel.ref,
            harness=compiled_harness,
            program=compiled_program,
            task_snapshots=(
                TaskSnapshotRef(
                    task_id="civil/calculation/alpha",
                    definition_sha256="d" * 64,
                    package_sha256="e" * 64,
                ),
            ),
            harbor=payload,
        )


def test_run_bundle_rejects_unpinned_or_out_of_surface_tasks() -> None:
    kernel, harness, program, payload = _bundle_parts()

    with pytest.raises(ValidationError, match="task snapshots must exactly match Harbor task_refs"):
        RunBundle(
            bundle_id="run-missing-snapshot",
            kernel_ref=kernel.ref,
            harness=harness,
            program=program,
            task_snapshots=(),
            harbor=payload,
        )

    invalid_payload = payload.model_copy(update={"task_refs": ("civil/calculation/not-allowed",)})
    with pytest.raises(ValidationError, match="outside the harness program surface"):
        RunBundle(
            bundle_id="run-task-outside-surface",
            kernel_ref=kernel.ref,
            harness=harness,
            program=program,
            task_snapshots=(
                TaskSnapshotRef(
                    task_id="civil/calculation/not-allowed",
                    definition_sha256="d" * 64,
                    package_sha256="e" * 64,
                ),
            ),
            harbor=invalid_payload,
        )


def test_run_bundle_rejects_binding_ids_with_the_wrong_typed_role() -> None:
    kernel, harness, program, payload = _bundle_parts()
    invalid_payload = payload.model_copy(update={"agent_binding_id": "compute"})

    with pytest.raises(ValidationError, match="agent_binding_id must reference an agent binding"):
        RunBundle(
            bundle_id="run-wrong-binding",
            kernel_ref=kernel.ref,
            harness=harness,
            program=program,
            task_snapshots=(
                TaskSnapshotRef(
                    task_id="civil/calculation/alpha",
                    definition_sha256="d" * 64,
                    package_sha256="e" * 64,
                ),
            ),
            harbor=invalid_payload,
        )
