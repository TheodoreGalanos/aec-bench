# ABOUTME: Persists phase-neutral governed batch designs, result prefixes, and terminals.
# ABOUTME: Uses canonical immutable evidence while preserving arbitrary batch cardinality.

from __future__ import annotations

from pathlib import Path

from pydantic import TypeAdapter

from aec_bench.meta_harness.immutable_artifact_store import (
    EvidenceRepository,
    ImmutableArtifactCollisionError,
    ImmutableArtifactConfinementError,
    ImmutableArtifactIntegrityError,
)

from .contracts import (
    GovernedBatchAssignmentTerminal,
    GovernedBatchDesign,
    GovernedBatchExecutionCollisionError,
    GovernedBatchExecutionConfinementError,
    GovernedBatchExecutionIntegrityError,
    GovernedBatchTerminal,
)


class GovernedBatchExecutionStore:
    """Immutable storage for one dynamically sized governed batch."""

    def __init__(
        self,
        *,
        repository: EvidenceRepository,
        design: GovernedBatchDesign,
    ) -> None:
        self._repository = repository
        self._design = design

    @property
    def design(self) -> GovernedBatchDesign:
        """Return the immutable batch design bound to this root."""

        return self._design

    @classmethod
    def open(
        cls,
        *,
        root: Path,
        design: GovernedBatchDesign,
        disjoint_roots: tuple[Path, ...] = (),
    ) -> GovernedBatchExecutionStore:
        """Bind a private evidence root to exactly one batch design."""

        try:
            repository = EvidenceRepository(
                Path(root),
                disjoint_roots=disjoint_roots,
                host_private=True,
            )
            repository.publish_canonical_model(
                "design.json",
                design,
                TypeAdapter(GovernedBatchDesign),
            )
            selected = repository.load_canonical_model(
                "design.json",
                TypeAdapter(GovernedBatchDesign),
            )
        except ImmutableArtifactCollisionError as error:
            raise GovernedBatchExecutionCollisionError(
                "governed batch root is bound to a different design",
            ) from error
        except ImmutableArtifactConfinementError as error:
            raise GovernedBatchExecutionConfinementError(str(error)) from error
        except ImmutableArtifactIntegrityError as error:
            raise GovernedBatchExecutionIntegrityError(str(error)) from error
        if selected != design:
            raise GovernedBatchExecutionCollisionError(
                "governed batch root selected a different design",
            )
        store = cls(repository=repository, design=selected)
        store.load_results()
        store.load_terminal()
        return store

    def load_results(self) -> tuple[GovernedBatchAssignmentTerminal, ...]:
        """Load the exact contiguous assignment-terminal prefix."""

        results: list[GovernedBatchAssignmentTerminal] = []
        missing_seen = False
        adapter = TypeAdapter(GovernedBatchAssignmentTerminal)
        try:
            for ordinal in range(1, self._design.assignment_count + 1):
                relative_path = f"assignments/{ordinal:02d}.json"
                if not self._repository.exists(relative_path):
                    missing_seen = True
                    continue
                if missing_seen:
                    raise GovernedBatchExecutionIntegrityError(
                        "governed batch assignment results are not a contiguous prefix",
                    )
                result = self._repository.load_canonical_model(
                    relative_path,
                    adapter,
                )
                self._validate_result(result, expected_ordinal=ordinal)
                results.append(result)
        except ImmutableArtifactIntegrityError as error:
            raise GovernedBatchExecutionIntegrityError(str(error)) from error
        return tuple(results)

    def record_result(
        self,
        result: GovernedBatchAssignmentTerminal,
    ) -> GovernedBatchAssignmentTerminal:
        """Append one exact assignment terminal to the durable prefix."""

        selected = GovernedBatchAssignmentTerminal.model_validate(
            result.model_dump(mode="python"),
        )
        prefix = self.load_results()
        expected_ordinal = len(prefix) + 1
        self._validate_result(
            selected,
            expected_ordinal=expected_ordinal,
        )
        try:
            self._repository.publish_canonical_model(
                f"assignments/{expected_ordinal:02d}.json",
                selected,
                TypeAdapter(GovernedBatchAssignmentTerminal),
            )
        except ImmutableArtifactCollisionError as error:
            raise GovernedBatchExecutionCollisionError(
                "governed batch assignment selected different immutable content",
            ) from error
        except ImmutableArtifactIntegrityError as error:
            raise GovernedBatchExecutionIntegrityError(str(error)) from error
        persisted = self.load_results()
        if len(persisted) != expected_ordinal or persisted[-1] != selected:
            raise GovernedBatchExecutionCollisionError(
                "governed batch assignment did not extend the exact prefix",
            )
        return persisted[-1]

    def load_terminal(self) -> GovernedBatchTerminal | None:
        """Load the immutable batch terminal when it exists."""

        if not self._repository.exists("terminal.json"):
            return None
        try:
            terminal = self._repository.load_canonical_model(
                "terminal.json",
                TypeAdapter(GovernedBatchTerminal),
            )
        except ImmutableArtifactIntegrityError as error:
            raise GovernedBatchExecutionIntegrityError(str(error)) from error
        self._validate_terminal(terminal)
        return terminal

    def record_terminal(
        self,
        terminal: GovernedBatchTerminal,
    ) -> GovernedBatchTerminal:
        """Persist one terminal over the exact current result prefix."""

        selected = GovernedBatchTerminal.model_validate(
            terminal.model_dump(mode="python"),
        )
        self._validate_terminal(selected)
        try:
            self._repository.publish_canonical_model(
                "terminal.json",
                selected,
                TypeAdapter(GovernedBatchTerminal),
            )
        except ImmutableArtifactCollisionError as error:
            raise GovernedBatchExecutionCollisionError(
                "governed batch terminal selected different immutable content",
            ) from error
        except ImmutableArtifactIntegrityError as error:
            raise GovernedBatchExecutionIntegrityError(str(error)) from error
        persisted = self.load_terminal()
        if persisted != selected:
            raise GovernedBatchExecutionCollisionError(
                "governed batch terminal did not retain exact immutable content",
            )
        return selected

    def _validate_result(
        self,
        result: GovernedBatchAssignmentTerminal,
        *,
        expected_ordinal: int,
    ) -> None:
        try:
            assignment = self._design.assignments[expected_ordinal - 1]
        except IndexError as error:
            raise GovernedBatchExecutionIntegrityError(
                "governed batch result exceeds the supplied cardinality",
            ) from error
        if (
            result.design_sha256 != self._design.content_sha256
            or result.ordinal != expected_ordinal
            or result.assignment_sha256 != assignment.assignment_sha256
            or result.dispatch_sha256 != assignment.dispatch_sha256
            or result.authorization_chain_sha256 != assignment.authorization_chain_sha256
        ):
            raise GovernedBatchExecutionIntegrityError(
                "governed batch result differs from its supplied assignment",
            )

    def _validate_terminal(
        self,
        terminal: GovernedBatchTerminal,
    ) -> None:
        results = self.load_results()
        if (
            terminal.design_sha256 != self._design.content_sha256
            or terminal.assignment_terminals != results
            or terminal.incomplete_assignment_sha256s != self._design.ordered_assignment_sha256s[len(results) :]
        ):
            raise GovernedBatchExecutionIntegrityError(
                "governed batch terminal differs from its design or result prefix",
            )
