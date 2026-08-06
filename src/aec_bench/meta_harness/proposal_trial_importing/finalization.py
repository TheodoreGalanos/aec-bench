# ABOUTME: Finalizes one authorized proposal Harbor execution into immutable terminal evidence.
# ABOUTME: Orchestrates scored and candidate-failure paths through focused package boundaries.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from aec_bench.contracts.evaluation_plane import EvaluationPlan
from aec_bench.contracts.proposal_execution_types import ProposalSessionStatus
from aec_bench.contracts.trial_record import (
    ArtifactReference,
    Completeness,
    MetaHarnessTrialProvenance,
    ProposalSessionTrialProvenance,
    TrialRecord,
)
from aec_bench.harness.harbor_importing.contracts import HarborImportError
from aec_bench.harness.harbor_importing.core import import_harbor_trial
from aec_bench.harness.harbor_importing.proposal_evidence import (
    ProposalHarborImportEvidence,
    load_proposal_harbor_import_evidence,
)
from aec_bench.meta_harness.authority_ledger import (
    AuthorityLedger,
    AuthorityLedgerError,
)
from aec_bench.meta_harness.immutable_artifact_store import EvidenceRepository
from aec_bench.meta_harness.proposal_dispatch import (
    GovernedProposalDispatchAuthorization,
    ProposalDispatchGovernanceError,
    replay_governed_proposal_dispatch,
)
from aec_bench.meta_harness.proposal_harbor_runtime import (
    ProposalHarborExecutionReceipt,
    load_proposal_harbor_execution,
)
from aec_bench.meta_harness.proposal_import_consumption import (
    ProposalImportConsumptionClaim,
    ProposalImportConsumptionError,
    ProposalImportTerminalRecord,
    StoredProposalImportConsumptionClaim,
    claim_proposal_import_consumption,
    load_proposal_import_terminal,
    persist_proposal_import_terminal,
)
from aec_bench.meta_harness.proposal_trial_importing.authority import (
    record_import_authority,
    resolve_unique_event_model,
)
from aec_bench.meta_harness.proposal_trial_importing.candidate_failure import (
    TerminalPersister,
    preserve_candidate_failure,
)
from aec_bench.meta_harness.proposal_trial_importing.contracts import (
    GovernedProposalTrialImport,
    PersistedProposalArtifacts,
    ProposalTrialImportAuthority,
    ProposalTrialImportError,
    ProposalTrialImportReceipt,
    ProposalTrialImportResult,
    ProposalVerifierEvidence,
    WorldLineage,
)
from aec_bench.meta_harness.proposal_trial_importing.persistence import (
    copied_artifact,
    merge_artifacts,
    object_root,
    persist_model_artifact,
    persist_model_path,
    physical_reference,
    prepare_host_artifacts_repository,
    repository_reference,
    snapshot_evidence_artifacts,
    snapshot_file,
    snapshot_raw_output,
    validate_host_artifacts_root,
    write_or_load_exact_trial_record,
)
from aec_bench.meta_harness.proposal_trial_importing.replay import (
    replay_governed_proposal_trial_import,
)
from aec_bench.meta_harness.proposal_trial_importing.validation import (
    bound_tool_versions,
    meta_split,
    program_generator_sha256,
    proposal_terminal_status,
    resolve_world_lineage,
    revalidate_physical_dispatch,
    sole_trial_dir,
    validate_exact_import,
)


class ImportAuthorityRecorder(Protocol):
    """Callable boundary for recording one scored import's authority graph."""

    def __call__(
        self,
        *,
        repository: EvidenceRepository,
        ledger: AuthorityLedger,
        authorization: GovernedProposalDispatchAuthorization,
        execution: ProposalHarborExecutionReceipt,
        execution_artifact: ArtifactReference,
        evidence: ProposalHarborImportEvidence,
        verifier_evidence: ProposalVerifierEvidence,
        record: TrialRecord,
        record_path: Path,
        import_receipt: ProposalTrialImportReceipt,
        import_receipt_path: Path,
        import_id: str,
        authority_event_id: str,
    ) -> ProposalTrialImportAuthority: ...


@dataclass(frozen=True)
class FinalizationServices:
    """Host mutation boundaries used by resumable finalization."""

    record_authority: ImportAuthorityRecorder
    persist_terminal: TerminalPersister


@dataclass(frozen=True)
class CompletedEvidenceArtifacts:
    """Immutable artifacts created from one completed Harbor trial."""

    copied_by_identity: dict[tuple[str, str, str], ArtifactReference]
    reward: ArtifactReference
    details: ArtifactReference
    verifier_evidence: ProposalVerifierEvidence
    verifier: ArtifactReference
    raw_output: ArtifactReference
    all_artifacts: list[ArtifactReference]


DEFAULT_FINALIZATION_SERVICES = FinalizationServices(
    record_authority=record_import_authority,
    persist_terminal=persist_proposal_import_terminal,
)


def finalize_governed_proposal_trial_import(
    *,
    ledger: AuthorityLedger,
    authorization: GovernedProposalDispatchAuthorization,
    harbor_execution_receipt_path: Path,
    repo_root: Path,
    artifacts_root: Path,
    import_id: str,
    authority_event_id: str,
    services: FinalizationServices = DEFAULT_FINALIZATION_SERVICES,
) -> ProposalTrialImportResult:
    """Finalize the sole trial from an exact governed proposal Harbor execution."""
    try:
        replayed = replay_governed_proposal_dispatch(
            ledger=ledger,
            authorization=authorization,
        )
        execution = load_proposal_harbor_execution(
            receipt_path=Path(harbor_execution_receipt_path),
            ledger=ledger,
            authorization=replayed,
        )
        trial_dir = sole_trial_dir(execution)
        revalidate_physical_dispatch(replayed)
        forbidden_roots = (
            Path(replayed.dispatch.host_config.source_task_dir),
            Path(replayed.dispatch.derived_task_path),
            trial_dir,
        )
        proposed_root = validate_host_artifacts_root(
            Path(artifacts_root),
            forbidden_roots=forbidden_roots,
        )
        consumption = claim_proposal_import_consumption(
            ledger_root=ledger.root,
            proposed=ProposalImportConsumptionClaim(
                harbor_execution_receipt_sha256=execution.content_sha256,
                dispatch_sha256=replayed.dispatch.content_sha256,
                artifacts_root=str(proposed_root),
                import_id=import_id,
                requested_authority_event_id=authority_event_id,
            ),
        )
        terminal = load_proposal_import_terminal(
            ledger_root=ledger.root,
            execution_sha256=execution.content_sha256,
        )
        if terminal is not None and terminal.record.dispatch_sha256 != replayed.dispatch.content_sha256:
            raise ProposalTrialImportError(
                "proposal import terminal index differs from the authorized dispatch",
            )
        repository = prepare_host_artifacts_repository(
            Path(consumption.claim.artifacts_root),
            forbidden_roots=forbidden_roots,
        )
        root = repository.root
        world = resolve_world_lineage(
            ledger=ledger,
            authorization=replayed,
        )
        execution_artifact = snapshot_file(
            repository=repository,
            reference=physical_reference(
                kind="proposal_harbor_execution_receipt",
                path=Path(harbor_execution_receipt_path),
                media_type="application/json",
            ),
            repo_root=Path(repo_root),
            object_root=object_root(root, replayed),
        )
        persisted = _persist_static_proposal_artifacts(
            repository=repository,
            ledger=ledger,
            authorization=replayed,
            object_root=object_root(root, replayed),
        )
        terminal_status = proposal_terminal_status(trial_dir)
        if terminal_status is ProposalSessionStatus.CANDIDATE_FAILURE:
            return preserve_candidate_failure(
                ledger=ledger,
                authorization=replayed,
                execution=execution,
                execution_artifact=execution_artifact,
                trial_dir=trial_dir,
                repo_root=Path(repo_root),
                repository=repository,
                artifacts_root=root,
                persisted=persisted,
                consumption=consumption,
                receipt_path=Path(harbor_execution_receipt_path),
                persist_terminal=services.persist_terminal,
            )
        if terminal_status is not ProposalSessionStatus.COMPLETED:
            raise ProposalTrialImportError(
                "proposal Harbor result has no supported terminal session status",
            )
        evidence = load_proposal_harbor_import_evidence(
            trial_dir=trial_dir,
            repo_root=Path(repo_root),
        )
        if evidence is None:
            raise ProposalTrialImportError(
                "authorized proposal execution produced an ordinary Harbor trial",
            )
        imported = import_harbor_trial(
            trial_dir=trial_dir,
            repo_root=Path(repo_root),
        )
        validate_exact_import(
            authorization=replayed,
            execution=execution,
            evidence=evidence,
            record=imported,
        )
        return _finalize_completed_import(
            ledger=ledger,
            authorization=replayed,
            execution=execution,
            execution_artifact=execution_artifact,
            evidence=evidence,
            imported=imported,
            trial_dir=trial_dir,
            repo_root=Path(repo_root),
            repository=repository,
            artifacts_root=root,
            persisted=persisted,
            world=world,
            consumption=consumption,
            receipt_path=Path(harbor_execution_receipt_path),
            services=services,
        )
    except ProposalTrialImportError:
        raise
    except (
        AuthorityLedgerError,
        HarborImportError,
        OSError,
        ProposalImportConsumptionError,
        ProposalDispatchGovernanceError,
        RuntimeError,
        ValueError,
    ) as error:
        raise ProposalTrialImportError(
            f"governed proposal TrialRecord import failed: {error}",
        ) from error


def _persist_static_proposal_artifacts(
    *,
    repository: EvidenceRepository,
    ledger: AuthorityLedger,
    authorization: GovernedProposalDispatchAuthorization,
    object_root: Path,
) -> PersistedProposalArtifacts:
    bundle = authorization.dispatch.bundle
    compilation = bundle.compilation
    freeze = compilation.proposal_freeze
    resolve_unique_event_model(
        ledger=ledger,
        event=authorization.freeze_authority_event,
        model_type=EvaluationPlan,
        expected_content_sha256=freeze.evaluation_plan_ref.content_sha256,
        label="evaluation plan",
    )
    return PersistedProposalArtifacts(
        candidate_manifest=persist_model_artifact(
            repository=repository,
            model=freeze.candidate_manifest,
            kind="candidate-manifest",
            filename="candidate-generation-manifest.json",
            object_root=object_root,
        ),
        graph=persist_model_artifact(
            repository=repository,
            model=compilation.proposal_graph,
            kind="proposal-decomposition-graph",
            filename="proposal-decomposition-graph.json",
            object_root=object_root,
        ),
        freeze=persist_model_artifact(
            repository=repository,
            model=freeze,
            kind="proposal-freeze",
            filename="proposal-freeze.json",
            object_root=object_root,
        ),
        compilation=persist_model_artifact(
            repository=repository,
            model=compilation,
            kind="proposal-compilation",
            filename="proposal-compilation.json",
            object_root=object_root,
        ),
        session_plan=persist_model_artifact(
            repository=repository,
            model=bundle.session_plan,
            kind="proposal-session-plan",
            filename="proposal-session-plan.json",
            object_root=object_root,
        ),
        bundle=persist_model_artifact(
            repository=repository,
            model=bundle,
            kind="proposal-run-session-bundle",
            filename="proposal-run-session-bundle.json",
            object_root=object_root,
        ),
        fixed_harness=persist_model_artifact(
            repository=repository,
            model=bundle.fixed_harness,
            kind="proposal-fixed-harness",
            filename="proposal-fixed-harness.json",
            object_root=object_root,
        ),
        dispatch=persist_model_artifact(
            repository=repository,
            model=authorization.dispatch,
            kind="governed-proposal-dispatch",
            filename="governed-proposal-dispatch.json",
            object_root=object_root,
        ),
    )


def _finalize_completed_import(
    *,
    ledger: AuthorityLedger,
    authorization: GovernedProposalDispatchAuthorization,
    execution: ProposalHarborExecutionReceipt,
    execution_artifact: ArtifactReference,
    evidence: ProposalHarborImportEvidence,
    imported: TrialRecord,
    trial_dir: Path,
    repo_root: Path,
    repository: EvidenceRepository,
    artifacts_root: Path,
    persisted: PersistedProposalArtifacts,
    world: WorldLineage,
    consumption: StoredProposalImportConsumptionClaim,
    receipt_path: Path,
    services: FinalizationServices,
) -> GovernedProposalTrialImport:
    completed = _preserve_completed_evidence(
        authorization=authorization,
        execution_artifact=execution_artifact,
        evidence=evidence,
        imported=imported,
        trial_dir=trial_dir,
        repo_root=repo_root,
        repository=repository,
        artifacts_root=artifacts_root,
        persisted=persisted,
    )
    record = _build_complete_trial_record(
        authorization=authorization,
        evidence=evidence,
        imported=imported,
        persisted=persisted,
        world=world,
        completed=completed,
    )
    return _persist_scored_result(
        ledger=ledger,
        authorization=authorization,
        execution=execution,
        execution_artifact=execution_artifact,
        evidence=evidence,
        record=record,
        repository=repository,
        artifacts_root=artifacts_root,
        world=world,
        completed=completed,
        consumption=consumption,
        receipt_path=receipt_path,
        services=services,
    )


def _preserve_completed_evidence(
    *,
    authorization: GovernedProposalDispatchAuthorization,
    execution_artifact: ArtifactReference,
    evidence: ProposalHarborImportEvidence,
    imported: TrialRecord,
    trial_dir: Path,
    repo_root: Path,
    repository: EvidenceRepository,
    artifacts_root: Path,
    persisted: PersistedProposalArtifacts,
) -> CompletedEvidenceArtifacts:
    destination = object_root(artifacts_root, authorization)
    copied_evidence, copied_by_identity = snapshot_evidence_artifacts(
        repository=repository,
        evidence=evidence,
        repo_root=repo_root,
        object_root=destination,
    )
    reward = snapshot_file(
        repository=repository,
        reference=physical_reference(
            kind="proposal-verifier-reward",
            path=trial_dir / "verifier" / "reward.json",
            media_type="application/json",
        ),
        repo_root=repo_root,
        object_root=destination,
    )
    details = snapshot_file(
        repository=repository,
        reference=physical_reference(
            kind="proposal-verifier-details",
            path=trial_dir / "verifier" / "details.json",
            media_type="application/json",
        ),
        repo_root=repo_root,
        object_root=destination,
    )
    verifier_evidence = ProposalVerifierEvidence(
        trial_id=imported.trial_id,
        task_id=imported.task.task_id,
        session_id=evidence.session_id,
        reward_artifact=reward,
        details_artifact=details,
        evaluation=imported.evaluation,
    )
    verifier = persist_model_artifact(
        repository=repository,
        model=verifier_evidence,
        kind="proposal-verifier-evidence",
        filename="proposal-verifier-evidence.json",
        object_root=destination,
    )
    raw_output = snapshot_raw_output(
        repository=repository,
        record=imported,
        repo_root=repo_root,
        object_root=destination,
    )
    all_artifacts = merge_artifacts(
        copied_evidence,
        list(persisted.all),
        [
            execution_artifact,
            reward,
            details,
            verifier,
            raw_output,
        ],
    )
    return CompletedEvidenceArtifacts(
        copied_by_identity=copied_by_identity,
        reward=reward,
        details=details,
        verifier_evidence=verifier_evidence,
        verifier=verifier,
        raw_output=raw_output,
        all_artifacts=all_artifacts,
    )


def _build_complete_trial_record(
    *,
    authorization: GovernedProposalDispatchAuthorization,
    evidence: ProposalHarborImportEvidence,
    imported: TrialRecord,
    persisted: PersistedProposalArtifacts,
    world: WorldLineage,
    completed: CompletedEvidenceArtifacts,
) -> TrialRecord:
    proposal_provenance = ProposalSessionTrialProvenance(
        session_id=evidence.session_id,
        candidate_id=evidence.candidate_id,
        candidate_artifact_sha256=evidence.candidate_artifact_sha256,
        proposal_graph_sha256=evidence.proposal_graph_sha256,
        compilation_sha256=evidence.compilation_sha256,
        session_plan_sha256=evidence.session_plan_sha256,
        session_receipt=copied_artifact(
            evidence.session_receipt_artifact,
            completed.copied_by_identity,
        ),
        cleanup_receipt=copied_artifact(
            evidence.cleanup_receipt_artifact,
            completed.copied_by_identity,
        ),
        task_package_manifest=copied_artifact(
            evidence.task_package_manifest_artifact,
            completed.copied_by_identity,
        ),
        runtime_archive_manifest=copied_artifact(
            evidence.runtime_archive_artifact,
            completed.copied_by_identity,
        ),
        expected_trial_records=1,
        trial_ordinal=1,
    )
    bundle = authorization.dispatch.bundle
    freeze = bundle.compilation.proposal_freeze
    provenance = MetaHarnessTrialProvenance(
        run_id=authorization.dispatch.dispatch_id,
        policy_id=freeze.candidate_manifest.manifest_id,
        kernel_id=bundle.fixed_harness.kernel_ref.kernel_id,
        kernel_sha256=bundle.fixed_harness.kernel_ref.content_sha256,
        harness_id=bundle.fixed_harness.instance_id,
        harness_sha256=bundle.fixed_harness.content_sha256,
        program_id=bundle.compilation.compiled_program.program_id,
        program_sha256=bundle.compilation.compiled_program.content_sha256,
        bundle_id=bundle.bundle_id,
        bundle_sha256=bundle.content_sha256,
        world_package_sha256=world.package_sha256,
        topology_signature_sha256=world.topology_sha256,
        harness_generator_sha256=bundle.fixed_harness.source_recipe_sha256,
        program_generator_sha256=program_generator_sha256(authorization),
        split=meta_split(freeze.split),
        repetition=authorization.dispatch.evaluation_coordinate.repetition,
        execution_seed=authorization.dispatch.evaluation_coordinate.seed,
        candidate_manifest=persisted.candidate_manifest,
        evaluation_plan_ref=freeze.evaluation_plan_ref,
        proposal_session=proposal_provenance,
    )
    transformed = imported.model_copy(
        update={
            "environment": imported.environment.model_copy(
                update={
                    "tool_versions": bound_tool_versions(
                        record=imported,
                        authorization=authorization,
                    ),
                },
            ),
            "outputs": imported.outputs.model_copy(
                update={
                    "raw_output_path": completed.raw_output.path,
                    "artifacts": completed.all_artifacts,
                },
            ),
            "meta_harness_provenance": provenance,
            "completeness": Completeness.COMPLETE,
        },
    )
    return TrialRecord.model_validate(
        transformed.model_dump(mode="python"),
    )


def _persist_scored_result(
    *,
    ledger: AuthorityLedger,
    authorization: GovernedProposalDispatchAuthorization,
    execution: ProposalHarborExecutionReceipt,
    execution_artifact: ArtifactReference,
    evidence: ProposalHarborImportEvidence,
    record: TrialRecord,
    repository: EvidenceRepository,
    artifacts_root: Path,
    world: WorldLineage,
    completed: CompletedEvidenceArtifacts,
    consumption: StoredProposalImportConsumptionClaim,
    receipt_path: Path,
    services: FinalizationServices,
) -> GovernedProposalTrialImport:
    import_id = consumption.claim.import_id
    record_path = write_or_load_exact_trial_record(
        repository=repository,
        ledger_root=artifacts_root / "proposal-trial-records",
        record=record,
    )
    record_artifact = repository_reference(
        repository=repository,
        kind="proposal-trial-record",
        path=record_path,
        media_type="application/json",
    )
    import_receipt = ProposalTrialImportReceipt(
        import_id=import_id,
        dispatch_id=authorization.dispatch.dispatch_id,
        dispatch_sha256=authorization.dispatch.content_sha256,
        provider_dispatch_event_sha256=(authorization.provider_dispatch_event.content_sha256),
        harbor_execution_receipt_sha256=execution.content_sha256,
        trial_id=record.trial_id,
        trial_record=record_artifact,
        session_id=evidence.session_id,
        candidate_id=evidence.candidate_id,
        candidate_artifact_sha256=evidence.candidate_artifact_sha256,
        proposal_graph_sha256=evidence.proposal_graph_sha256,
        compilation_sha256=evidence.compilation_sha256,
        session_plan_sha256=evidence.session_plan_sha256,
        world_package_sha256=world.package_sha256,
        topology_signature_sha256=world.topology_sha256,
        verifier_evidence_sha256=completed.verifier_evidence.content_sha256,
        node_receipt_sha256s=tuple(node.content_sha256 for node in evidence.session_receipt.node_receipts),
    )
    destination = object_root(artifacts_root, authorization)
    import_receipt_path = persist_model_path(
        repository=repository,
        model=import_receipt,
        filename="proposal-trial-import-receipt.json",
        object_root=destination,
    )
    import_receipt_artifact = repository_reference(
        repository=repository,
        kind="proposal-trial-import-receipt",
        path=import_receipt_path,
        media_type="application/json",
    )
    authority = services.record_authority(
        repository=repository,
        ledger=ledger,
        authorization=authorization,
        execution=execution,
        execution_artifact=execution_artifact,
        evidence=evidence,
        verifier_evidence=completed.verifier_evidence,
        record=record,
        record_path=record_path,
        import_receipt=import_receipt,
        import_receipt_path=import_receipt_path,
        import_id=import_id,
        authority_event_id=consumption.claim.requested_authority_event_id,
    )
    terminal = services.persist_terminal(
        ledger_root=ledger.root,
        record=ProposalImportTerminalRecord(
            harbor_execution_receipt_sha256=execution.content_sha256,
            dispatch_sha256=authorization.dispatch.content_sha256,
            import_id=import_id,
            outcome="scored",
            terminal_artifact=import_receipt_artifact,
            trial_record=record_artifact,
            authority_event_id=authority.authority_event.event.event_id,
            authority_event_sha256=authority.authority_event.event.content_sha256,
        ),
    )
    result = GovernedProposalTrialImport(
        record=record,
        record_path=record_path,
        record_artifact=record_artifact,
        import_receipt=import_receipt,
        import_receipt_path=import_receipt_path,
        import_receipt_artifact=import_receipt_artifact,
        harbor_execution_receipt_path=receipt_path,
        authority=authority,
        consumption_claim=consumption.claim,
        consumption_claim_path=consumption.path,
        terminal_record=terminal.record,
        terminal_record_path=terminal.path,
    )
    return replay_governed_proposal_trial_import(
        ledger=AuthorityLedger(ledger.root),
        authorization=authorization,
        result=result,
    )
