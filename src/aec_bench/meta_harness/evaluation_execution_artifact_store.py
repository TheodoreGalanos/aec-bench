# ABOUTME: Persists one evaluation execution binding, extensions, and claimed terminal evidence.
# ABOUTME: Provides the phase-neutral storage primitive used by experiment compatibility stores.

from __future__ import annotations

from collections.abc import Callable

from pydantic import TypeAdapter

from aec_bench.contracts.harness_kernel import ContentAddressedModel
from aec_bench.meta_harness.immutable_artifact_store import EvidenceRepository


class EvaluationExecutionArtifactStore[BindingT: ContentAddressedModel]:
    """Immutable storage mechanics for one bound evaluation execution."""

    def __init__(
        self,
        *,
        artifacts: EvidenceRepository,
        binding: BindingT,
    ) -> None:
        self._artifacts = artifacts
        self._binding = binding

    @property
    def artifacts(self) -> EvidenceRepository:
        """Return the confined repository used by this execution."""

        return self._artifacts

    @property
    def binding(self) -> BindingT:
        """Return the exact first-writer execution binding."""

        return self._binding

    @classmethod
    def bind(
        cls,
        *,
        artifacts: EvidenceRepository,
        binding: BindingT,
        binding_path: str,
        binding_adapter: TypeAdapter[BindingT],
    ) -> EvaluationExecutionArtifactStore[BindingT]:
        """Publish and replay the first immutable execution binding."""

        selected = artifacts.publish_canonical_model(
            binding_path,
            binding,
            binding_adapter,
        ).model
        return cls(
            artifacts=artifacts,
            binding=selected,
        )

    @classmethod
    def replay(
        cls,
        *,
        artifacts: EvidenceRepository,
        binding_path: str,
        binding_adapter: TypeAdapter[BindingT],
    ) -> EvaluationExecutionArtifactStore[BindingT]:
        """Replay an existing exact execution binding."""

        binding = artifacts.load_stored_canonical_model(
            binding_path,
            binding_adapter,
        ).model
        return cls(
            artifacts=artifacts,
            binding=binding,
        )

    def load_extension[ModelT: ContentAddressedModel](
        self,
        *,
        relative_path: str,
        adapter: TypeAdapter[ModelT],
    ) -> ModelT | None:
        """Load one optional typed extension from its fixed logical path."""

        stored = self._artifacts.load_optional_canonical_model(
            relative_path,
            adapter,
        )
        return None if stored is None else stored.model

    def persist_extension[ModelT: ContentAddressedModel](
        self,
        *,
        relative_path: str,
        model: ModelT,
        adapter: TypeAdapter[ModelT],
    ) -> ModelT:
        """Publish one typed extension at its fixed logical path."""

        return self._artifacts.publish_canonical_model(
            relative_path,
            model,
            adapter,
        ).model

    def load_claimed_terminal[
        TerminalT: ContentAddressedModel,
        ClaimT: ContentAddressedModel,
    ](
        self,
        *,
        terminal_adapter: TypeAdapter[TerminalT],
        object_collection: str,
        object_filename: str,
        claim_adapter: TypeAdapter[ClaimT],
        claim_collection: str,
        claim_identity: str,
        claim_filename: str,
        terminal_sha256: Callable[[ClaimT], str],
    ) -> TerminalT | None:
        """Resolve one optional first-writer claim to its terminal object."""

        claim = self.load_terminal_claim(
            claim_adapter=claim_adapter,
            claim_collection=claim_collection,
            claim_identity=claim_identity,
            claim_filename=claim_filename,
        )
        if claim is None:
            return None
        return self.load_terminal_object(
            terminal_adapter=terminal_adapter,
            object_collection=object_collection,
            object_filename=object_filename,
            content_sha256=terminal_sha256(claim),
        )

    def load_terminal_claim[ClaimT: ContentAddressedModel](
        self,
        *,
        claim_adapter: TypeAdapter[ClaimT],
        claim_collection: str,
        claim_identity: str,
        claim_filename: str,
    ) -> ClaimT | None:
        """Load one optional immutable logical terminal claim."""

        claim_path = self._artifacts.logical_model_path(
            collection=claim_collection,
            logical_identity=claim_identity,
            filename=claim_filename,
        )
        if not self._artifacts.exists(claim_path):
            return None
        return self._artifacts.load_logical_model(
            collection=claim_collection,
            logical_identity=claim_identity,
            filename=claim_filename,
            adapter=claim_adapter,
        ).model

    def load_terminal_object[TerminalT: ContentAddressedModel](
        self,
        *,
        terminal_adapter: TypeAdapter[TerminalT],
        object_collection: str,
        object_filename: str,
        content_sha256: str,
    ) -> TerminalT:
        """Load one terminal from its asserted content-addressed identity."""

        return self._artifacts.load_content_addressed_model(
            collection=object_collection,
            content_sha256=content_sha256,
            filename=object_filename,
            adapter=terminal_adapter,
        ).model

    def persist_claimed_terminal[
        TerminalT: ContentAddressedModel,
        ClaimT: ContentAddressedModel,
    ](
        self,
        *,
        terminal: TerminalT,
        terminal_adapter: TypeAdapter[TerminalT],
        object_collection: str,
        object_filename: str,
        claim: ClaimT,
        claim_adapter: TypeAdapter[ClaimT],
        claim_collection: str,
        claim_identity: str,
        claim_filename: str,
    ) -> TerminalT:
        """Publish a terminal object before binding its logical execution claim."""

        selected = self.persist_terminal_object(
            terminal=terminal,
            terminal_adapter=terminal_adapter,
            object_collection=object_collection,
            object_filename=object_filename,
        )
        self.persist_terminal_claim(
            claim=claim,
            claim_adapter=claim_adapter,
            claim_collection=claim_collection,
            claim_identity=claim_identity,
            claim_filename=claim_filename,
        )
        return selected

    def persist_terminal_object[TerminalT: ContentAddressedModel](
        self,
        *,
        terminal: TerminalT,
        terminal_adapter: TypeAdapter[TerminalT],
        object_collection: str,
        object_filename: str,
    ) -> TerminalT:
        """Publish one content-addressed terminal object."""

        return self._artifacts.publish_content_addressed_model(
            collection=object_collection,
            filename=object_filename,
            model=terminal,
            adapter=terminal_adapter,
        ).model

    def persist_terminal_claim[ClaimT: ContentAddressedModel](
        self,
        *,
        claim: ClaimT,
        claim_adapter: TypeAdapter[ClaimT],
        claim_collection: str,
        claim_identity: str,
        claim_filename: str,
    ) -> ClaimT:
        """Bind one logical execution identity to its terminal object."""

        return self._artifacts.publish_logical_model(
            collection=claim_collection,
            logical_identity=claim_identity,
            filename=claim_filename,
            model=claim,
            adapter=claim_adapter,
        ).model
