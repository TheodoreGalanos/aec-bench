# ABOUTME: Persists one phase-neutral evaluation generation as immutable lifecycle milestones.
# ABOUTME: Enforces exact preparation, batch, terminal, accounting, and retirement joins.

from __future__ import annotations

from pathlib import Path

from pydantic import TypeAdapter

from aec_bench.contracts.evaluation_generation.batch import EvaluationBatchPlan
from aec_bench.contracts.evaluation_generation.lifecycle import (
    CandidateBatchRejectionClosure,
    EvaluationGenerationClosure,
    EvaluationGenerationRetirementClosure,
    GovernedBatchExecutionClosure,
    GovernedBatchTerminalEvidence,
    ProposalGenerationClosure,
)
from aec_bench.contracts.evaluation_generation.preparation import PreparedEvaluationGeneration
from aec_bench.meta_harness.evaluation_generation_evidence import (
    EvaluationGenerationEvidenceError,
    verify_completed_governed_batch_evidence,
)
from aec_bench.meta_harness.immutable_artifact_store import (
    EvidenceRepository,
    ImmutableArtifactCollisionError,
    ImmutableArtifactConfinementError,
    ImmutableArtifactIntegrityError,
    validate_evidence_root,
)


class EvaluationGenerationStoreError(RuntimeError):
    """Base failure for immutable evaluation-generation persistence."""


class EvaluationGenerationStoreConfinementError(
    EvaluationGenerationStoreError,
):
    """The lifecycle root or one stored path is not confined."""


class EvaluationGenerationStoreIntegrityError(
    EvaluationGenerationStoreError,
):
    """Stored lifecycle evidence is missing, invalid, or incorrectly joined."""


class EvaluationGenerationStoreCollisionError(
    EvaluationGenerationStoreError,
):
    """One lifecycle milestone was rebound to different immutable content."""


_PREPARED_ADAPTER = TypeAdapter(PreparedEvaluationGeneration)
_BATCH_ADAPTER = TypeAdapter(EvaluationBatchPlan)
_CLOSURE_ADAPTER: TypeAdapter[EvaluationGenerationClosure] = TypeAdapter(
    EvaluationGenerationClosure,
)
_RETIREMENT_ADAPTER = TypeAdapter(EvaluationGenerationRetirementClosure)
_GOVERNED_BATCH_EVIDENCE_ADAPTER = TypeAdapter(
    GovernedBatchTerminalEvidence,
)

_PREPARED_PATH = "evaluation-generation/v2/prepared.json"
_BATCH_PATH = "evaluation-generation/v2/batch.json"
_CLOSURE_PATH = "evaluation-generation/v2/closure.json"
_RETIREMENT_PATH = "evaluation-generation/v2/retirement.json"
_GOVERNED_BATCH_EVIDENCE_PATH = "evaluation-generation/v2/governed-batch-evidence.json"


class EvaluationGenerationStore:
    """First-writer store for one complete phase-neutral generation lifecycle."""

    def __init__(
        self,
        *,
        artifacts: EvidenceRepository,
        prepared_generation: PreparedEvaluationGeneration,
    ) -> None:
        self._artifacts = artifacts
        self._prepared_generation = prepared_generation

    @property
    def root(self) -> Path:
        """Return the exact confined lifecycle root."""

        return self._artifacts.root

    @property
    def prepared_generation(self) -> PreparedEvaluationGeneration:
        """Return the immutable prepared-generation binding."""

        return self._prepared_generation

    @classmethod
    def open(
        cls,
        *,
        root: Path,
        prepared_generation: PreparedEvaluationGeneration,
    ) -> EvaluationGenerationStore:
        """Select one prepared generation as the immutable lifecycle root."""

        artifacts = _open_repository(Path(root))
        selected = _publish(
            artifacts=artifacts,
            relative_path=_PREPARED_PATH,
            model=prepared_generation,
            adapter=_PREPARED_ADAPTER,
            label="prepared evaluation generation",
        )
        if selected != prepared_generation:
            raise EvaluationGenerationStoreCollisionError(
                "evaluation-generation root is bound to a different prepared generation",
            )
        store = cls(
            artifacts=artifacts,
            prepared_generation=selected,
        )
        store.load_batch_plan()
        store.load_closure()
        store.load_retirement()
        return store

    @classmethod
    def for_existing(
        cls,
        *,
        root: Path,
        generation_id: str,
    ) -> EvaluationGenerationStore:
        """Open and verify an existing lifecycle by logical generation id."""

        store = cls.open_existing(root=root)
        prepared = store.prepared_generation
        if prepared.generation_id != generation_id:
            raise EvaluationGenerationStoreCollisionError(
                "evaluation-generation root belongs to a different generation",
            )
        return store

    @classmethod
    def open_existing(
        cls,
        *,
        root: Path,
    ) -> EvaluationGenerationStore:
        """Open an existing lifecycle from its exact immutable preparation."""

        artifacts = _open_existing_repository(Path(root))
        prepared = _load_required(
            artifacts=artifacts,
            relative_path=_PREPARED_PATH,
            adapter=_PREPARED_ADAPTER,
            label="prepared evaluation generation",
        )
        store = cls(
            artifacts=artifacts,
            prepared_generation=prepared,
        )
        store.load_batch_plan()
        store.load_closure()
        store.load_retirement()
        return store

    def load_batch_plan(self) -> EvaluationBatchPlan | None:
        """Load and validate the optional realized candidate batch."""

        batch = _load_optional(
            artifacts=self._artifacts,
            relative_path=_BATCH_PATH,
            adapter=_BATCH_ADAPTER,
            label="evaluation batch plan",
        )
        if batch is not None:
            _validate_batch_join(self._prepared_generation, batch)
        return batch

    def require_batch_plan(self) -> EvaluationBatchPlan:
        """Require a realized candidate batch."""

        batch = self.load_batch_plan()
        if batch is None:
            raise EvaluationGenerationStoreIntegrityError(
                "evaluation-generation lifecycle requires a batch plan",
            )
        return batch

    def persist_batch_plan(
        self,
        batch: EvaluationBatchPlan,
    ) -> EvaluationBatchPlan:
        """Publish the exact outcome-blind candidate batch."""

        _validate_batch_join(self._prepared_generation, batch)
        return _publish(
            artifacts=self._artifacts,
            relative_path=_BATCH_PATH,
            model=batch,
            adapter=_BATCH_ADAPTER,
            label="evaluation batch plan",
        )

    def load_governed_batch_evidence(
        self,
    ) -> GovernedBatchTerminalEvidence | None:
        """Load the optional phase-neutral completed-batch evidence projection."""

        evidence = _load_optional(
            artifacts=self._artifacts,
            relative_path=_GOVERNED_BATCH_EVIDENCE_PATH,
            adapter=_GOVERNED_BATCH_EVIDENCE_ADAPTER,
            label="governed batch terminal evidence",
        )
        if evidence is not None:
            batch = self.require_batch_plan()
            if evidence.batch_plan_sha256 != batch.content_sha256:
                raise EvaluationGenerationStoreIntegrityError(
                    "governed batch terminal evidence differs from its batch",
                )
        return evidence

    def require_governed_batch_evidence(
        self,
    ) -> GovernedBatchTerminalEvidence:
        """Require the phase-neutral evidence needed for a completed closure."""

        evidence = self.load_governed_batch_evidence()
        if evidence is None:
            raise EvaluationGenerationStoreIntegrityError(
                "completed governed batch closure requires terminal evidence",
            )
        return evidence

    def persist_governed_batch_evidence(
        self,
        evidence: GovernedBatchTerminalEvidence,
    ) -> GovernedBatchTerminalEvidence:
        """Publish exact execution and accounting joins before closure."""

        batch = self.require_batch_plan()
        if evidence.batch_plan_sha256 != batch.content_sha256:
            raise EvaluationGenerationStoreIntegrityError(
                "governed batch terminal evidence differs from its batch",
            )
        return _publish(
            artifacts=self._artifacts,
            relative_path=_GOVERNED_BATCH_EVIDENCE_PATH,
            model=evidence,
            adapter=_GOVERNED_BATCH_EVIDENCE_ADAPTER,
            label="governed batch terminal evidence",
        )

    def load_closure(self) -> EvaluationGenerationClosure | None:
        """Load and validate the explicit terminal variant."""

        closure = _load_optional(
            artifacts=self._artifacts,
            relative_path=_CLOSURE_PATH,
            adapter=_CLOSURE_ADAPTER,
            label="evaluation-generation closure",
        )
        if closure is not None:
            self._validate_closure(closure)
        return closure

    def require_closure(self) -> EvaluationGenerationClosure:
        """Require a terminal generation closure."""

        closure = self.load_closure()
        if closure is None:
            raise EvaluationGenerationStoreIntegrityError(
                "evaluation-generation lifecycle requires a terminal closure",
            )
        return closure

    def persist_closure(
        self,
        closure: EvaluationGenerationClosure,
    ) -> EvaluationGenerationClosure:
        """Publish one explicit terminal variant after its prerequisites."""

        self._validate_closure(closure)
        return _publish(
            artifacts=self._artifacts,
            relative_path=_CLOSURE_PATH,
            model=closure,
            adapter=_CLOSURE_ADAPTER,
            label="evaluation-generation closure",
        )

    def load_retirement(
        self,
    ) -> EvaluationGenerationRetirementClosure | None:
        """Load and validate the optional completed retirement join."""

        retirement = _load_optional(
            artifacts=self._artifacts,
            relative_path=_RETIREMENT_PATH,
            adapter=_RETIREMENT_ADAPTER,
            label="evaluation-generation retirement",
        )
        if retirement is not None:
            self._validate_retirement(retirement)
        return retirement

    def require_retirement(self) -> EvaluationGenerationRetirementClosure:
        """Require completed cohort, critic, and acceptance retirement."""

        retirement = self.load_retirement()
        if retirement is None:
            raise EvaluationGenerationStoreIntegrityError(
                "evaluation-generation lifecycle requires retirement",
            )
        return retirement

    def persist_retirement(
        self,
        retirement: EvaluationGenerationRetirementClosure,
    ) -> EvaluationGenerationRetirementClosure:
        """Publish the final retirement and acceptance-reveal join."""

        self._validate_retirement(retirement)
        return _publish(
            artifacts=self._artifacts,
            relative_path=_RETIREMENT_PATH,
            model=retirement,
            adapter=_RETIREMENT_ADAPTER,
            label="evaluation-generation retirement",
        )

    def _validate_closure(
        self,
        closure: EvaluationGenerationClosure,
    ) -> None:
        if closure.prepared_generation_sha256 != (self._prepared_generation.content_sha256):
            raise EvaluationGenerationStoreIntegrityError(
                "evaluation-generation closure differs from its prepared generation",
            )
        batch = self.load_batch_plan()
        if isinstance(closure, ProposalGenerationClosure):
            if batch is not None:
                raise EvaluationGenerationStoreIntegrityError(
                    "proposal-generation terminal cannot claim a realized batch",
                )
            return
        if batch is None or closure.batch_plan_sha256 != batch.content_sha256:
            raise EvaluationGenerationStoreIntegrityError(
                "evaluation-generation closure requires its exact batch",
            )
        if isinstance(closure, CandidateBatchRejectionClosure):
            _validate_rejected_assignments(batch, closure)
            return
        _validate_execution_prefix(batch, closure)
        if closure.status == "completed":
            self._validate_completed_execution_evidence(
                batch=batch,
                closure=closure,
            )

    def _validate_completed_execution_evidence(
        self,
        *,
        batch: EvaluationBatchPlan,
        closure: GovernedBatchExecutionClosure,
    ) -> None:
        evidence = self.require_governed_batch_evidence()
        try:
            verify_completed_governed_batch_evidence(
                batch=batch,
                closure=closure,
                evidence=evidence,
            )
        except EvaluationGenerationEvidenceError as error:
            raise EvaluationGenerationStoreIntegrityError(str(error)) from error

    def _validate_retirement(
        self,
        retirement: EvaluationGenerationRetirementClosure,
    ) -> None:
        closure = self.load_closure()
        if closure is None or retirement.generation_closure_sha256 != closure.content_sha256:
            raise EvaluationGenerationStoreIntegrityError(
                "evaluation-generation retirement requires its exact closure",
            )
        if retirement.cohort_retirement.cohort != (self._prepared_generation.cohort_binding):
            raise EvaluationGenerationStoreIntegrityError(
                "evaluation-generation retirement differs from its cohort",
            )


def _validate_batch_join(
    prepared: PreparedEvaluationGeneration,
    batch: EvaluationBatchPlan,
) -> None:
    if batch.prepared_generation_sha256 != prepared.content_sha256:
        raise EvaluationGenerationStoreIntegrityError(
            "evaluation batch differs from its prepared generation",
        )
    shared_bindings = (
        (batch.cohort, prepared.cohort),
        (batch.cohort_binding, prepared.cohort_binding),
        (batch.kernel_sha256, prepared.kernel_sha256),
        (batch.fixed_harness_sha256, prepared.fixed_harness_sha256),
        (batch.evaluation_plan_ref, prepared.evaluation_plan_ref),
        (
            batch.evaluation_authority_scope,
            prepared.evaluation_authority_scope,
        ),
        (batch.proposal_policy, prepared.proposal_policy),
        (
            batch.candidate_manifest_proposal_policy_sha256,
            prepared.candidate_manifest_proposal_policy_sha256,
        ),
        (
            batch.compilation_policies_sha256,
            prepared.compilation_policies_sha256,
        ),
        (batch.runtime_archive_sha256, prepared.runtime_archive_sha256),
        (batch.monitor_policy_sha256, prepared.monitor_policy_sha256),
        (
            batch.monitor_cycle_plan_sha256,
            prepared.monitor_cycle_plan_sha256,
        ),
        (
            batch.motif_assurance_snapshot_sha256,
            prepared.motif_assurance_snapshot_sha256,
        ),
        (batch.candidate_budget, prepared.candidate_budget),
        (batch.spec, prepared.spec),
    )
    if any(observed != expected for observed, expected in shared_bindings):
        raise EvaluationGenerationStoreIntegrityError(
            "evaluation batch shared bindings differ from its prepared generation",
        )


def _validate_rejected_assignments(
    batch: EvaluationBatchPlan,
    closure: CandidateBatchRejectionClosure,
) -> None:
    if not set(closure.rejected_assignment_sha256s).issubset(
        batch.ordered_assignment_sha256s,
    ):
        raise EvaluationGenerationStoreIntegrityError(
            "batch rejection contains an unknown assignment",
        )


def _validate_execution_prefix(
    batch: EvaluationBatchPlan,
    closure: GovernedBatchExecutionClosure,
) -> None:
    observed_count = len(closure.ordered_assignment_terminal_sha256s)
    expected_count = batch.spec.total_assignment_count
    if observed_count > expected_count or (closure.status == "completed" and observed_count != expected_count):
        raise EvaluationGenerationStoreIntegrityError(
            "governed batch terminal count differs from its batch",
        )


def _open_repository(root: Path) -> EvidenceRepository:
    try:
        return EvidenceRepository(root)
    except (
        ImmutableArtifactConfinementError,
        ImmutableArtifactIntegrityError,
    ) as error:
        raise _translate_store_error(
            error,
            label="evaluation-generation root",
        ) from error


def _open_existing_repository(root: Path) -> EvidenceRepository:
    try:
        selected = validate_evidence_root(root, must_exist=True)
        return EvidenceRepository(selected)
    except FileNotFoundError as error:
        raise EvaluationGenerationStoreIntegrityError(
            "evaluation-generation root is missing",
        ) from error
    except (
        ImmutableArtifactConfinementError,
        ImmutableArtifactIntegrityError,
    ) as error:
        raise _translate_store_error(
            error,
            label="evaluation-generation root",
        ) from error


def _publish[ModelT](
    *,
    artifacts: EvidenceRepository,
    relative_path: str,
    model: ModelT,
    adapter: TypeAdapter[ModelT],
    label: str,
) -> ModelT:
    try:
        return artifacts.publish_canonical_model(
            relative_path,
            model,
            adapter,
        ).model
    except (
        ImmutableArtifactCollisionError,
        ImmutableArtifactConfinementError,
        ImmutableArtifactIntegrityError,
    ) as error:
        raise _translate_store_error(error, label=label) from error


def _load_required[ModelT](
    *,
    artifacts: EvidenceRepository,
    relative_path: str,
    adapter: TypeAdapter[ModelT],
    label: str,
) -> ModelT:
    loaded = _load_optional(
        artifacts=artifacts,
        relative_path=relative_path,
        adapter=adapter,
        label=label,
    )
    if loaded is None:
        raise EvaluationGenerationStoreIntegrityError(f"{label} is missing")
    return loaded


def _load_optional[ModelT](
    *,
    artifacts: EvidenceRepository,
    relative_path: str,
    adapter: TypeAdapter[ModelT],
    label: str,
) -> ModelT | None:
    try:
        stored = artifacts.load_optional_canonical_model(
            relative_path,
            adapter,
        )
    except (
        ImmutableArtifactCollisionError,
        ImmutableArtifactConfinementError,
        ImmutableArtifactIntegrityError,
    ) as error:
        raise _translate_store_error(error, label=label) from error
    return None if stored is None else stored.model


def _translate_store_error(
    error: Exception,
    *,
    label: str,
) -> EvaluationGenerationStoreError:
    if isinstance(error, ImmutableArtifactCollisionError):
        return EvaluationGenerationStoreCollisionError(
            f"{label} already contains different immutable content",
        )
    if isinstance(error, ImmutableArtifactConfinementError):
        return EvaluationGenerationStoreConfinementError(
            f"{label} is not confined: {error}",
        )
    return EvaluationGenerationStoreIntegrityError(
        f"{label} cannot be replayed: {error}",
    )
