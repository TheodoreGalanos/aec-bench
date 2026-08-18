# ABOUTME: Defines the fixed execution-kernel capability catalogue for adaptive harness compilation.
# ABOUTME: Provides immutable capability contracts and stable kernel references without executable import hooks.

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import field_validator, model_validator

from aec_bench.contracts.commitments import canonical_json_sha256 as canonical_json_sha256
from aec_bench.contracts.commitments import validate_sha256 as validate_sha256
from aec_bench.contracts.validators import FrozenStrictModel as FrozenStrictModel
from aec_bench.contracts.validators import NonEmptyStr


class KernelCapabilityKind(StrEnum):
    """Trusted primitive categories exposed by the fixed kernel."""

    TASK_SOURCE = "task_source"
    AGENT_ADAPTER = "agent_adapter"
    EXECUTION_BACKEND = "execution_backend"
    CONTEXT_PROVIDER = "context_provider"
    TOOL_PROVIDER = "tool_provider"
    VERIFIER = "verifier"
    RESULT_IMPORTER = "result_importer"
    PROGRAM_OPERATION = "program_operation"
    PROFILER = "profiler"


class KernelPortCardinality(StrEnum):
    """Cardinality declared by a kernel capability port."""

    ONE = "one"
    OPTIONAL = "optional"
    MANY = "many"


class KernelPortSpec(FrozenStrictModel):
    """Typed input or output port on a fixed kernel capability."""

    name: NonEmptyStr
    schema_ref: NonEmptyStr
    cardinality: KernelPortCardinality = KernelPortCardinality.ONE


class KernelCapabilityRef(FrozenStrictModel):
    """Stable reference to one trusted kernel capability version."""

    capability_id: NonEmptyStr
    version: NonEmptyStr


class KernelCapabilitySpec(FrozenStrictModel):
    """Serializable descriptor for one capability implemented by trusted kernel code."""

    capability_id: NonEmptyStr
    version: NonEmptyStr
    kind: KernelCapabilityKind
    summary: NonEmptyStr
    inputs: tuple[KernelPortSpec, ...] = ()
    outputs: tuple[KernelPortSpec, ...] = ()
    configuration_schema_ref: NonEmptyStr | None = None

    @model_validator(mode="after")
    def validate_ports(self) -> Self:
        _validate_unique_names(self.inputs, label="input")
        _validate_unique_names(self.outputs, label="output")
        return self

    @property
    def ref(self) -> KernelCapabilityRef:
        return KernelCapabilityRef(
            capability_id=self.capability_id,
            version=self.version,
        )


class KernelSourceDigest(FrozenStrictModel):
    """One executable source file bound into the fixed-kernel implementation identity."""

    path: NonEmptyStr
    sha256: str

    @field_validator("sha256")
    @classmethod
    def validate_source_hash(cls, value: str) -> str:
        return validate_sha256(value)


class KernelImplementationIdentity(FrozenStrictModel):
    """Legacy whole-package source inventory used by fixed-K manifests."""

    kind: Literal["python_source_inventory"] = "python_source_inventory"
    sources: tuple[KernelSourceDigest, ...]

    @field_validator("sources")
    @classmethod
    def validate_sources(
        cls,
        value: tuple[KernelSourceDigest, ...],
    ) -> tuple[KernelSourceDigest, ...]:
        if not value:
            raise ValueError("kernel implementation source inventory must not be empty")
        paths = tuple(source.path for source in value)
        if len(paths) != len(set(paths)):
            raise ValueError("kernel implementation source paths must be unique")
        if paths != tuple(sorted(paths)):
            raise ValueError("kernel implementation sources must be sorted by path")
        return value


class KernelExecutorImplementationIdentity(FrozenStrictModel):
    """Explicit allowlist of executable source bytes owned by fixed K."""

    kind: Literal["python_executor_surface"] = "python_executor_surface"
    sources: tuple[KernelSourceDigest, ...]

    @field_validator("sources")
    @classmethod
    def validate_sources(
        cls,
        value: tuple[KernelSourceDigest, ...],
    ) -> tuple[KernelSourceDigest, ...]:
        if not value:
            raise ValueError("kernel executor source inventory must not be empty")
        paths = tuple(source.path for source in value)
        if len(paths) != len(set(paths)):
            raise ValueError("kernel executor source paths must be unique")
        if paths != tuple(sorted(paths)):
            raise ValueError("kernel executor sources must be sorted by path")
        return value


class KernelRef(FrozenStrictModel):
    """Stable reference to one fixed-kernel manifest version."""

    kernel_id: NonEmptyStr
    version: NonEmptyStr


def kernel_abi_commitment(ref: KernelRef) -> str:
    """Return the named compatibility commitment used by harness-program studies."""

    return canonical_json_sha256(
        {
            "domain": "aecbench.kernel-abi.v1",
            "kernel_ref": ref.model_dump(mode="json"),
        }
    )


class KernelManifest(FrozenStrictModel):
    """Versioned fixed-kernel surface available to harness compilation."""

    kernel_id: NonEmptyStr
    version: NonEmptyStr
    capabilities: tuple[KernelCapabilitySpec, ...]
    implementation: KernelImplementationIdentity | KernelExecutorImplementationIdentity

    @model_validator(mode="after")
    def validate_capabilities(self) -> Self:
        if not self.capabilities:
            raise ValueError("kernel manifest must include at least one capability")
        capability_ids = [capability.capability_id for capability in self.capabilities]
        if len(capability_ids) != len(set(capability_ids)):
            raise ValueError("kernel manifest capability ids must be unique")
        return self

    @property
    def ref(self) -> KernelRef:
        return KernelRef(
            kernel_id=self.kernel_id,
            version=self.version,
        )

    @property
    def capability_refs(self) -> tuple[KernelCapabilityRef, ...]:
        return tuple(capability.ref for capability in self.capabilities)


def _validate_unique_names(ports: tuple[KernelPortSpec, ...], *, label: str) -> None:
    names = [port.name for port in ports]
    if len(names) != len(set(names)):
        raise ValueError(f"kernel capability {label} port names must be unique")
