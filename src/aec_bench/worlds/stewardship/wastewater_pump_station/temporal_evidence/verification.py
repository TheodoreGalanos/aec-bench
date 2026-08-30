# ABOUTME: Independently replays temporal access, handover, and reliance evidence.
# ABOUTME: Reports accessible, observed, relied-on, recorded, and accepted sets separately.

from __future__ import annotations

from collections.abc import Mapping

from pydantic import model_validator

from aec_bench.contracts.content_address import ContentAddressedModel
from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr
from aec_bench.worlds.stewardship.wastewater_pump_station.reference_package_models import (
    ReferencePackage,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.temporal_evidence.access_models import (
    TemporalAccessContext,
    TemporalAccessPublication,
    TemporalActorVisibleEvent,
    TemporalEvidenceAccessKind,
    TemporalEvidenceRelianceRecord,
    temporal_actor_event_id,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.temporal_evidence.gateway import (
    TemporalEvidenceGateway,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.temporal_evidence.models import (
    TemporalEvidenceIntegrityError,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.temporal_evidence.repository import (
    TemporalEvidenceRepository,
)


class TemporalEvidenceVerificationIssue(FrozenStrictModel):
    """One stable fail-closed verification issue."""

    code: NonEmptyStr
    detail: NonEmptyStr
    artifact_id: str | None = None


class TemporalActionEvidenceSets(FrozenStrictModel):
    """Distinct evidence-authority sets at one consequential action."""

    action_request_id: NonEmptyStr
    information_set_id: NonEmptyStr
    accessible_version_ids: tuple[NonEmptyStr, ...]
    observed_version_ids: tuple[NonEmptyStr, ...]
    relied_on_version_ids: tuple[NonEmptyStr, ...]
    recorded_evidence_refs: tuple[NonEmptyStr, ...]
    accepted_evidence_refs: tuple[NonEmptyStr, ...]


class TemporalEvidenceVerificationReport(ContentAddressedModel):
    """Independent result over one complete local temporal-evidence ledger."""

    valid: bool
    issues: tuple[TemporalEvidenceVerificationIssue, ...]
    access_count: int
    reliance_count: int
    carrier_count: int
    verified_access_result_ids: tuple[NonEmptyStr, ...]
    action_evidence_sets: tuple[TemporalActionEvidenceSets, ...]

    @model_validator(mode="after")
    def validate_report(self) -> TemporalEvidenceVerificationReport:
        if min(self.access_count, self.reliance_count, self.carrier_count) < 0:
            raise ValueError("temporal verification counts must be non-negative")
        if self.valid == bool(self.issues):
            raise ValueError("temporal verification validity and issues differ")
        return self


def verify_temporal_evidence_repository(
    repository: TemporalEvidenceRepository,
    *,
    package: ReferencePackage,
    actor_bindings: Mapping[str, tuple[str, str]] | None = None,
) -> TemporalEvidenceVerificationReport:
    """Recompute every deterministic access and cross-check all continuing state."""

    issues: list[TemporalEvidenceVerificationIssue] = []
    verified_results: list[str] = []
    action_sets: list[TemporalActionEvidenceSets] = []
    access_count = 0
    reliance_count = 0
    carrier_count = 0
    try:
        bundle = repository.load_bundle(package=package)
        gateway = TemporalEvidenceGateway(bundle)
        commits = repository.access_commits()
        access_count = len(commits)
        for commit in commits:
            try:
                publication = repository.load_access_publication(commit)
                access_receipt = publication.decision.receipt
                context = _context_from_receipt(access_receipt)
                prior_state = repository.load_retrieval_state_artifact(
                    session_key=commit.session_key,
                    state_id=commit.prior_state_id,
                )
                if prior_state.remaining_budget != access_receipt.budget_before:
                    issues.append(
                        TemporalEvidenceVerificationIssue(
                            code="budget-chain",
                            detail="access budget before does not match its prior state",
                            artifact_id=access_receipt.request_id,
                        )
                    )
                decision = (
                    gateway.search(
                        request_id=access_receipt.request_id,
                        query=access_receipt.original_query or "",
                        scope=access_receipt.requested_scope or "",
                        limit=access_receipt.requested_limit or 0,
                        context=context,
                        state=prior_state,
                        resulting_information_set_id=access_receipt.resulting_information_set_id,
                    )
                    if publication.decision.result.operation is TemporalEvidenceAccessKind.SEARCH
                    else gateway.fetch(
                        request_id=access_receipt.request_id,
                        reference=access_receipt.requested_reference or "",
                        context=context,
                        state=prior_state,
                        resulting_information_set_id=access_receipt.resulting_information_set_id,
                    )
                )
                expected = TemporalAccessPublication(
                    decision=decision,
                    event=TemporalActorVisibleEvent(
                        event_id=temporal_actor_event_id(
                            request_id=access_receipt.request_id,
                            access_sequence=decision.result.access_sequence,
                            context=context,
                        ),
                        event_sequence=decision.result.access_sequence,
                        actor_id=context.actor_id,
                        agent_tenure_id=context.agent_tenure_id,
                        session_id=context.session_id,
                        operation=decision.result.operation,
                        access_result_id=decision.result.content_sha256,
                        public_status=decision.result.public_status,
                        information_set_id=access_receipt.resulting_information_set_id,
                    ),
                    information_set=publication.information_set,
                ).with_actor_event_bound()
                if expected != publication:
                    issues.append(
                        TemporalEvidenceVerificationIssue(
                            code="access-replay",
                            detail="stored access differs from deterministic replay",
                            artifact_id=access_receipt.request_id,
                        )
                    )
                else:
                    verified_results.append(decision.result.content_sha256)
            except (OSError, ValueError, TemporalEvidenceIntegrityError) as error:
                issues.append(
                    TemporalEvidenceVerificationIssue(
                        code="artifact-integrity",
                        detail=str(error),
                        artifact_id=commit.request_id,
                    )
                )

        reliance_records = repository.evidence_reliance_records()
        reliance_count = len(reliance_records)
        for record in reliance_records:
            _verify_reliance(
                repository,
                gateway,
                record,
                actor_bindings=actor_bindings,
                issues=issues,
                action_sets=action_sets,
            )

        carriers = repository.retrieval_carriers()
        carrier_count = len(carriers)
        carriers_by_id = {item.content_sha256: item for item in carriers}
        handover_receipts = repository.retrieval_handover_receipts()
        for handover_receipt in handover_receipts:
            carrier = carriers_by_id.get(handover_receipt.carrier_id)
            if carrier is None or (
                handover_receipt.carried_result_ids != tuple(item.content_sha256 for item in carrier.access_results)
                or handover_receipt.remaining_budget != carrier.remaining_budget
            ):
                issues.append(
                    TemporalEvidenceVerificationIssue(
                        code="handover-projection",
                        detail="retrieval carrier and private projection receipt differ",
                        artifact_id=handover_receipt.carrier_id,
                    )
                )
        install_receipts = repository.retrieval_handover_install_receipts()
        for install_receipt in install_receipts:
            carrier = carriers_by_id.get(install_receipt.carrier_id)
            state = repository.load_retrieval_state_artifact(
                session_key=install_receipt.target_session_key,
                state_id=install_receipt.next_state_id,
            )
            if (
                carrier is None
                or state.installed_carrier_id != install_receipt.carrier_id
                or state.remaining_budget != carrier.remaining_budget
            ):
                issues.append(
                    TemporalEvidenceVerificationIssue(
                        code="handover-install",
                        detail="installed retrieval state differs from its carrier",
                        artifact_id=install_receipt.carrier_id,
                    )
                )
    except (OSError, ValueError, TemporalEvidenceIntegrityError) as error:
        issues.append(
            TemporalEvidenceVerificationIssue(
                code="artifact-integrity",
                detail=str(error),
            )
        )
    return TemporalEvidenceVerificationReport(
        valid=not issues,
        issues=tuple(issues),
        access_count=access_count,
        reliance_count=reliance_count,
        carrier_count=carrier_count,
        verified_access_result_ids=tuple(verified_results),
        action_evidence_sets=tuple(action_sets),
    )


def _context_from_receipt(receipt: object) -> TemporalAccessContext:
    from aec_bench.worlds.stewardship.wastewater_pump_station.temporal_evidence.access_models import (
        TemporalEvidenceAccessReceipt,
    )

    if not isinstance(receipt, TemporalEvidenceAccessReceipt):
        raise TypeError("temporal verifier received an invalid access receipt")
    return TemporalAccessContext(
        run_id=receipt.run_id,
        episode_id=receipt.episode_id,
        world_instance_id=receipt.world_instance_id,
        world_branch_id=receipt.world_branch_id,
        world_state_id=receipt.world_state_id,
        world_commit_id=receipt.world_commit_id,
        world_sequence=receipt.world_sequence,
        world_time_seconds=receipt.world_time_seconds,
        actor_id=receipt.actor_id,
        actor_role=receipt.actor_role,
        agent_tenure_id=receipt.agent_tenure_id,
        session_id=receipt.session_id,
        base_view_id=receipt.base_view_id,
        prior_information_set_id=receipt.prior_information_set_id,
        tool_contract_id=receipt.tool_contract_id,
        branch_ancestor_ids=receipt.branch_ancestor_ids,
    )


def _verify_reliance(
    repository: TemporalEvidenceRepository,
    gateway: TemporalEvidenceGateway,
    record: TemporalEvidenceRelianceRecord,
    *,
    actor_bindings: Mapping[str, tuple[str, str]] | None,
    issues: list[TemporalEvidenceVerificationIssue],
    action_sets: list[TemporalActionEvidenceSets],
) -> None:
    context = TemporalAccessContext(
        run_id=record.run_id,
        episode_id=record.episode_id,
        world_instance_id=record.world_instance_id,
        world_branch_id=record.world_branch_id,
        world_state_id=record.world_state_id,
        world_commit_id=record.world_commit_id,
        world_sequence=record.world_sequence,
        world_time_seconds=record.world_time_seconds,
        actor_id=record.actor_id,
        actor_role=record.actor_role,
        agent_tenure_id=record.agent_tenure_id,
        session_id=record.session_id,
        base_view_id=record.base_view_id,
        prior_information_set_id=record.information_set_id,
        tool_contract_id=record.tool_contract_id,
        branch_ancestor_ids=record.branch_ancestor_ids,
    )
    observed_versions: list[str] = []
    for result_id in record.available_access_result_ids:
        result = repository.load_access_result(result_id)
        for item in result.references:
            if item.version_id not in observed_versions:
                observed_versions.append(item.version_id)
        if result.fetched_content is not None and result.fetched_content.version_id not in observed_versions:
            observed_versions.append(result.fetched_content.version_id)
    if not set(record.evidence_version_ids).issubset(observed_versions):
        issues.append(
            TemporalEvidenceVerificationIssue(
                code="reliance-not-observed",
                detail="relied-on evidence was not in the actor-visible result history",
                artifact_id=record.action_request_id,
            )
        )
    if actor_bindings is not None:
        binding = actor_bindings.get(record.action_request_id)
        if binding != (record.information_set_id, record.base_view_id):
            issues.append(
                TemporalEvidenceVerificationIssue(
                    code="reliance-action-binding",
                    detail="reliance record and durable actor binding differ",
                    artifact_id=record.action_request_id,
                )
            )
    action_sets.append(
        TemporalActionEvidenceSets(
            action_request_id=record.action_request_id,
            information_set_id=record.information_set_id,
            accessible_version_ids=tuple(item.version_id for item in gateway.accessible_versions(context)),
            observed_version_ids=tuple(observed_versions),
            relied_on_version_ids=record.evidence_version_ids,
            recorded_evidence_refs=record.recorded_evidence_refs,
            accepted_evidence_refs=record.accepted_evidence_refs,
        )
    )
