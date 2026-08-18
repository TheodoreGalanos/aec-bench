# ABOUTME: Tests the fixed-kernel capability catalogue and content-addressed identity contracts.
# ABOUTME: Verifies immutable capability descriptions, deterministic hashes, and pinned references.

import pytest
from pydantic import ValidationError

from aec_bench.contracts.harness_kernel import (
    KernelCapabilityKind,
    KernelCapabilityRef,
    KernelCapabilitySpec,
    KernelExecutorImplementationIdentity,
    KernelImplementationIdentity,
    KernelManifest,
    KernelPortCardinality,
    KernelPortSpec,
    KernelRef,
    KernelSourceDigest,
)


def _adapter_capability(*, summary: str = "Execute one agent adapter.") -> KernelCapabilitySpec:
    return KernelCapabilitySpec(
        capability_id="aecbench.adapter.lambda-rlm",
        version="1.0.0",
        kind=KernelCapabilityKind.AGENT_ADAPTER,
        summary=summary,
        inputs=(KernelPortSpec(name="task", schema_ref="aecbench://task-definition/v1"),),
        outputs=(
            KernelPortSpec(
                name="agent_output",
                schema_ref="aecbench://agent-output/v1",
                cardinality=KernelPortCardinality.ONE,
            ),
        ),
        configuration_schema_ref="aecbench://harness-binding/agent/v1",
    )


def test_kernel_capability_is_plain_frozen_and_directly_referenced() -> None:
    first = _adapter_capability()
    second = _adapter_capability()
    changed = _adapter_capability(summary="Execute a different adapter contract.")

    assert first == second
    assert first != changed
    assert first.ref == KernelCapabilityRef(
        capability_id="aecbench.adapter.lambda-rlm",
        version="1.0.0",
    )
    assert "content_sha256" not in first.model_dump(mode="json")

    with pytest.raises(ValidationError, match="frozen"):
        first.summary = "mutated"


def test_kernel_capability_rejects_an_ambient_content_digest() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        KernelCapabilitySpec.model_validate(
            {
                **_adapter_capability().model_dump(mode="json"),
                "content_sha256": "0" * 64,
            }
        )


def test_kernel_manifest_pins_unique_capabilities() -> None:
    adapter = _adapter_capability()
    backend = KernelCapabilitySpec(
        capability_id="aecbench.backend.harbor",
        version="1.0.0",
        kind=KernelCapabilityKind.EXECUTION_BACKEND,
        summary="Execute a compiled batch through Harbor.",
        inputs=(KernelPortSpec(name="program", schema_ref="aecbench://compiled-program/v1"),),
        outputs=(
            KernelPortSpec(
                name="trials",
                schema_ref="aecbench://trial-record/v1",
                cardinality=KernelPortCardinality.MANY,
            ),
        ),
        configuration_schema_ref="aecbench://harness-binding/compute/v1",
    )

    manifest = KernelManifest(
        kernel_id="aec-bench",
        version="1.0.0",
        capabilities=(adapter, backend),
        implementation=KernelImplementationIdentity(
            sources=(KernelSourceDigest(path="kernel.py", sha256="a" * 64),),
        ),
    )

    assert manifest.ref == KernelRef(kernel_id="aec-bench", version="1.0.0")
    assert manifest.capability_refs == (adapter.ref, backend.ref)

    with pytest.raises(ValidationError, match="capability ids must be unique"):
        KernelManifest(
            kernel_id="aec-bench",
            version="1.0.0",
            capabilities=(adapter, adapter),
            implementation=manifest.implementation,
        )


def test_kernel_manifest_value_changes_with_executable_source_inventory() -> None:
    capability = _adapter_capability()
    first = KernelManifest(
        kernel_id="aec-bench",
        version="1.0.0",
        capabilities=(capability,),
        implementation=KernelImplementationIdentity(
            sources=(KernelSourceDigest(path="kernel.py", sha256="a" * 64),),
        ),
    )
    changed = KernelManifest(
        kernel_id="aec-bench",
        version="1.0.0",
        capabilities=(capability,),
        implementation=KernelImplementationIdentity(
            sources=(KernelSourceDigest(path="kernel.py", sha256="b" * 64),),
        ),
    )

    assert first.implementation != changed.implementation
    assert first != changed
    assert first.ref == changed.ref


def test_kernel_manifest_accepts_both_supported_implementation_identity_shapes() -> None:
    capability = _adapter_capability()
    legacy = KernelManifest(
        kernel_id="aec-bench",
        version="1.0.0",
        capabilities=(capability,),
        implementation=KernelImplementationIdentity(
            sources=(KernelSourceDigest(path="aec_bench/legacy.py", sha256="a" * 64),),
        ),
    )
    executor_surface = KernelManifest(
        kernel_id="aec-bench",
        version="1.0.0",
        capabilities=(capability,),
        implementation=KernelExecutorImplementationIdentity(
            sources=(KernelSourceDigest(path="aec_bench/executor.py", sha256="b" * 64),),
        ),
    )

    restored_legacy = KernelManifest.model_validate(legacy.model_dump(mode="json"))
    restored_executor_surface = KernelManifest.model_validate(executor_surface.model_dump(mode="json"))

    assert restored_legacy == legacy
    assert restored_legacy.implementation.kind == "python_source_inventory"
    assert restored_executor_surface == executor_surface
    assert restored_executor_surface.implementation.kind == "python_executor_surface"
    assert "content_sha256" not in restored_legacy.model_dump(mode="json")
    assert "content_sha256" not in restored_executor_surface.model_dump(mode="json")


def test_kernel_capability_rejects_duplicate_port_names() -> None:
    with pytest.raises(ValidationError, match="input port names must be unique"):
        KernelCapabilitySpec(
            capability_id="aecbench.adapter.invalid",
            version="1.0.0",
            kind=KernelCapabilityKind.AGENT_ADAPTER,
            summary="Invalid duplicate input surface.",
            inputs=(
                KernelPortSpec(name="task", schema_ref="aecbench://task/v1"),
                KernelPortSpec(name="task", schema_ref="aecbench://task/v1"),
            ),
            outputs=(KernelPortSpec(name="output", schema_ref="aecbench://output/v1"),),
        )


def test_kernel_catalogue_has_typed_tool_and_context_capabilities() -> None:
    assert KernelCapabilityKind.TOOL_PROVIDER.value == "tool_provider"
    assert KernelCapabilityKind.CONTEXT_PROVIDER.value == "context_provider"
