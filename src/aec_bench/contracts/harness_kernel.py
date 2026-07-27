# ABOUTME: Defines the fixed execution-kernel capability catalogue for adaptive harness compilation.
# ABOUTME: Provides immutable content-addressed capability and kernel references without executable import hooks.

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import Field, field_validator, model_validator

from aec_bench.contracts.validators import (
    FrozenStrictModel as FrozenStrictModel,
)
from aec_bench.contracts.validators import NonEmptyStr


def validate_sha256(value: str) -> str:
    """Validate a lowercase hexadecimal SHA-256 digest."""
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError("SHA-256 digest must contain 64 lowercase hexadecimal characters")
    return value


def canonical_content_sha256(payload: Any) -> str:
    """Return a deterministic SHA-256 digest for JSON-compatible contract content."""
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class ContentAddressedModel(FrozenStrictModel):
    """Frozen model whose identity is the canonical digest of all other fields."""

    content_sha256: str = Field(default="", repr=False)

    @model_validator(mode="after")
    def validate_content_address(self) -> Self:
        payload = self.model_dump(mode="json", exclude={"content_sha256"})
        expected = canonical_content_sha256(payload)
        if self.content_sha256:
            validate_sha256(self.content_sha256)
            if self.content_sha256 != expected:
                raise ValueError("content_sha256 does not match canonical model content")
        object.__setattr__(self, "content_sha256", expected)
        return self


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
    """Content-pinned reference to one trusted kernel capability."""

    capability_id: NonEmptyStr
    version: NonEmptyStr
    content_sha256: str

    @field_validator("content_sha256")
    @classmethod
    def validate_content_sha256(cls, value: str) -> str:
        return validate_sha256(value)


class KernelCapabilitySpec(ContentAddressedModel):
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
            content_sha256=self.content_sha256,
        )


class KernelSourceDigest(FrozenStrictModel):
    """One executable source file bound into the fixed-kernel implementation identity."""

    path: NonEmptyStr
    sha256: str

    @field_validator("sha256")
    @classmethod
    def validate_source_hash(cls, value: str) -> str:
        return validate_sha256(value)


class KernelImplementationIdentity(ContentAddressedModel):
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


class KernelExecutorImplementationIdentity(ContentAddressedModel):
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
    """Content-pinned reference to a complete fixed-kernel manifest."""

    kernel_id: NonEmptyStr
    version: NonEmptyStr
    content_sha256: str

    @field_validator("content_sha256")
    @classmethod
    def validate_content_sha256(cls, value: str) -> str:
        return validate_sha256(value)


class KernelManifest(ContentAddressedModel):
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
            content_sha256=self.content_sha256,
        )

    @property
    def capability_refs(self) -> tuple[KernelCapabilityRef, ...]:
        return tuple(capability.ref for capability in self.capabilities)


def _validate_unique_names(ports: tuple[KernelPortSpec, ...], *, label: str) -> None:
    names = [port.name for port in ports]
    if len(names) != len(set(names)):
        raise ValueError(f"kernel capability {label} port names must be unique")
