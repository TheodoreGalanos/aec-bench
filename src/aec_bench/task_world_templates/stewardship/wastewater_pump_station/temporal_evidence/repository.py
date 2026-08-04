# ABOUTME: Publishes and reloads one confined immutable temporal-evidence corpus.
# ABOUTME: Rejects artifact drift, lineage mismatch, unsafe paths, and prohibited source bytes.

from __future__ import annotations

import fcntl
import json
import os
import stat
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from aec_bench.contracts.harness_kernel import (
    canonical_content_sha256,
)
from aec_bench.ledger.durability import fsync_directory, mkdir_durable
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_package_models import (
    ReferencePackage,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence.access_models import (
    IssuedTemporalReference,
    TemporalAccessCommit,
    TemporalAccessContext,
    TemporalAccessDecision,
    TemporalAccessPublication,
    TemporalActorVisibleEvent,
    TemporalEvidenceAccessKind,
    TemporalEvidenceAccessReceipt,
    TemporalEvidenceAccessResult,
    TemporalEvidenceRelianceRecord,
    TemporalInformationSetManifest,
    TemporalInformationSetPointer,
    TemporalRetrievalHandoverInstallReceipt,
    TemporalRetrievalHandoverReceipt,
    TemporalRetrievalSessionManifest,
    TemporalRetrievalState,
    TemporalRetrievalStateCarrier,
    TemporalRetrievalStatePointer,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence.models import (
    TemporalAccessPolicy,
    TemporalBranchPolicy,
    TemporalCorpusManifest,
    TemporalCostPolicy,
    TemporalEvidenceAvailabilitySchedule,
    TemporalEvidenceBundle,
    TemporalEvidenceCapability,
    TemporalEvidenceIntegrityError,
    TemporalEvidenceLineage,
    TemporalEvidenceRightsClass,
    TemporalEvidenceVersion,
    TemporalRetrievalPolicy,
)

ModelT = TypeVar("ModelT", bound=BaseModel)


class TemporalEvidenceRepository:
    """Confined filesystem authority for one deterministic temporal corpus."""

    def __init__(self, root: Path) -> None:
        selected = Path(root)
        if selected.exists() and (selected.is_symlink() or not selected.is_dir()):
            raise TemporalEvidenceIntegrityError("temporal evidence root must be a plain directory")
        mkdir_durable(selected)
        selected.chmod(0o700)
        self._root = selected.resolve(strict=True)
        self._lock_path = self._root / ".temporal-evidence.lock"

    @property
    def root(self) -> Path:
        """Return the exact confined temporal-evidence root."""

        return self._root

    @staticmethod
    def is_enabled(root: Path) -> bool:
        """Return whether an existing run contains the capability declaration."""

        return (Path(root) / "temporal-evidence" / "capability.json").is_file()

    def initialize(
        self,
        bundle: TemporalEvidenceBundle,
        *,
        package: ReferencePackage,
    ) -> TemporalEvidenceBundle:
        """Publish one exact corpus or replay an identical prior publication."""

        self._validate_authority(bundle, package=package)
        validated = self._strict_bundle(bundle)
        self._publish_model("capability.json", validated.capability)
        self._publish_model("corpus/manifest.json", validated.corpus_manifest)
        self._publish_model("corpus/lineage.json", validated.lineage)
        self._publish_model("corpus/availability.json", validated.availability)
        self._publish_model("policies/retrieval.json", validated.retrieval_policy)
        self._publish_model("policies/access.json", validated.access_policy)
        self._publish_model("policies/branch.json", validated.branch_policy)
        self._publish_model("policies/cost.json", validated.cost_policy)
        for item in validated.versions:
            self._publish_model(f"corpus/versions/{item.version_id}.json", item)
        fsync_directory(self._root)
        return self.load_bundle(package=package)

    @contextmanager
    def locked(self) -> Iterator[None]:
        """Serialize corpus-independent access state across local processes."""

        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(self._lock_path, flags, 0o600)
        try:
            details = os.fstat(descriptor)
            if not stat.S_ISREG(details.st_mode):
                raise TemporalEvidenceIntegrityError("temporal evidence lock is not a regular file")
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)

    def open_retrieval_state(
        self,
        context: TemporalAccessContext,
    ) -> TemporalRetrievalState:
        """Create or reload the exact tenure-scoped retrieval state."""

        with self.locked():
            session_key = _session_key(context)
            root = f"private/sessions/{session_key}"
            manifest_path = f"{root}/manifest.json"
            if self._path(manifest_path).exists():
                return self._load_retrieval_state_unlocked(context)
            capability = self._load_model(
                "capability.json",
                TemporalEvidenceCapability,
                "capability",
            )
            reference_namespace_id = canonical_content_sha256(
                {
                    "policy": "opaque-reference-namespace.v1",
                    "run_id": context.run_id,
                    "session_id": context.session_id,
                    "agent_tenure_id": context.agent_tenure_id,
                }
            )
            state = TemporalRetrievalState(
                state_sequence=0,
                previous_state_id=None,
                reference_namespace_id=reference_namespace_id,
                remaining_budget=capability.initial_budget,
                issued_references=(),
                access_result_ids=(),
                actor_event_ids=(),
                fetched_content_ids=(),
                unresolved_search_ids=(),
                installed_carrier_id=None,
            )
            manifest = TemporalRetrievalSessionManifest(
                session_key=session_key,
                run_id=context.run_id,
                episode_id=context.episode_id,
                world_branch_id=context.world_branch_id,
                actor_id=context.actor_id,
                agent_tenure_id=context.agent_tenure_id,
                session_id=context.session_id,
                corpus_snapshot_id=capability.corpus_snapshot_id,
                initial_state_id=state.content_sha256,
            )
            self._publish_model(manifest_path, manifest)
            self._publish_model(
                f"{root}/states/{state.content_sha256}.json",
                state,
            )
            self._replace_model(
                f"{root}/current.json",
                TemporalRetrievalStatePointer(
                    session_key=session_key,
                    state_sequence=0,
                    state_id=state.content_sha256,
                ),
            )
            return state

    def load_retrieval_state(
        self,
        context: TemporalAccessContext,
    ) -> TemporalRetrievalState:
        """Reload the selected tenure state and verify its complete chain identity."""

        with self.locked():
            return self._load_retrieval_state_unlocked(context)

    def has_access(self, request_id: str) -> bool:
        """Return whether one request id already has a durable transaction."""

        return self._path(_transaction_path(request_id)).is_file()

    def record_evidence_reliance(
        self,
        context: TemporalAccessContext,
        *,
        action_request_id: str,
        action_name: str,
        relied_on_evidence_refs: tuple[str, ...],
    ) -> TemporalEvidenceRelianceRecord:
        """Validate and persist an explicit action-to-observed-evidence relation."""

        with self.locked():
            state = self._load_retrieval_state_unlocked(context)
            issued = {item.opaque_reference: item.evidence_version_id for item in state.issued_references}
            missing = tuple(reference for reference in relied_on_evidence_refs if reference not in issued)
            if missing:
                raise TemporalEvidenceIntegrityError("relied-on evidence was not supplied to this tenure")
            results = tuple(
                self._load_model(
                    f"public/results/{result_id}.json",
                    TemporalEvidenceAccessResult,
                    "relied-on access result",
                )
                for result_id in state.access_result_ids
            )
            observed_result_ids: list[str] = []
            for reference in relied_on_evidence_refs:
                result = next(
                    (
                        item
                        for item in results
                        if any(visible.opaque_reference == reference for visible in item.references)
                        or (item.fetched_content is not None and item.fetched_content.opaque_reference == reference)
                    ),
                    None,
                )
                if result is None:
                    raise TemporalEvidenceIntegrityError("relied-on evidence lacks an actor-visible result")
                if result.content_sha256 not in observed_result_ids:
                    observed_result_ids.append(result.content_sha256)
            record = TemporalEvidenceRelianceRecord(
                action_request_id=action_request_id,
                action_name=action_name,
                actor_id=context.actor_id,
                actor_role=context.actor_role,
                agent_tenure_id=context.agent_tenure_id,
                session_id=context.session_id,
                run_id=context.run_id,
                episode_id=context.episode_id,
                world_instance_id=context.world_instance_id,
                world_branch_id=context.world_branch_id,
                branch_ancestor_ids=context.branch_ancestor_ids,
                world_state_id=context.world_state_id,
                world_commit_id=context.world_commit_id,
                world_sequence=context.world_sequence,
                world_time_seconds=context.world_time_seconds,
                base_view_id=context.base_view_id,
                tool_contract_id=context.tool_contract_id,
                information_set_id=context.prior_information_set_id,
                relied_on_evidence_refs=relied_on_evidence_refs,
                evidence_version_ids=tuple(issued[reference] for reference in relied_on_evidence_refs),
                observed_access_result_ids=tuple(observed_result_ids),
                available_access_result_ids=state.access_result_ids,
            )
            self._publish_model(
                _reliance_path(action_request_id),
                record,
            )
            return record

    def load_evidence_reliance(
        self,
        action_request_id: str,
    ) -> TemporalEvidenceRelianceRecord:
        """Reload one exact action reliance record."""

        return self._load_model(
            _reliance_path(action_request_id),
            TemporalEvidenceRelianceRecord,
            "evidence reliance record",
        )

    def has_evidence_reliance(self, action_request_id: str) -> bool:
        """Return whether one action names a durable reliance record."""

        return self._path(_reliance_path(action_request_id)).is_file()

    def access_commits(self) -> tuple[TemporalAccessCommit, ...]:
        """Reload every immutable access commit in stable request order."""

        return tuple(
            sorted(
                self._load_models_in(
                    "private/transactions",
                    TemporalAccessCommit,
                    "temporal access commit",
                ),
                key=lambda item: (item.session_key, item.request_id),
            )
        )

    def load_access_publication(
        self,
        commit: TemporalAccessCommit,
    ) -> TemporalAccessPublication:
        """Reload and cross-bind one committed access publication."""

        publication = self._load_publication(commit)
        if publication.decision.result.content_sha256 != commit.result_id:
            raise TemporalEvidenceIntegrityError("access publication result identity differs")
        return publication

    def load_access_publication_for_request(
        self,
        request_id: str,
    ) -> TemporalAccessPublication:
        """Load one committed access result without changing its session pointer."""

        with self.locked():
            commit = self._load_model(
                _transaction_path(request_id),
                TemporalAccessCommit,
                "temporal access commit",
            )
            if commit.request_id != request_id:
                raise TemporalEvidenceIntegrityError("temporal access request identity differs")
            publication = self._load_publication(commit)
            receipt = publication.decision.receipt
            self._validate_commit_matches(
                commit,
                publication,
                context=TemporalAccessContext(
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
                ),
            )
            return publication

    def load_retrieval_state_artifact(
        self,
        *,
        session_key: str,
        state_id: str,
    ) -> TemporalRetrievalState:
        """Reload one immutable state from a known access commit."""

        state = self._load_model(
            f"private/sessions/{session_key}/states/{state_id}.json",
            TemporalRetrievalState,
            "retrieval state artifact",
        )
        if state.content_sha256 != state_id:
            raise TemporalEvidenceIntegrityError("retrieval state artifact identity differs")
        return state

    def evidence_reliance_records(self) -> tuple[TemporalEvidenceRelianceRecord, ...]:
        """Reload every explicit evidence-reliance record."""

        return tuple(
            sorted(
                self._load_models_in(
                    "public/reliance",
                    TemporalEvidenceRelianceRecord,
                    "evidence reliance record",
                ),
                key=lambda item: item.action_request_id,
            )
        )

    def load_access_result(self, result_id: str) -> TemporalEvidenceAccessResult:
        """Reload one actor-visible access result by content identity."""

        result = self._load_model(
            f"public/results/{result_id}.json",
            TemporalEvidenceAccessResult,
            "access result",
        )
        if result.content_sha256 != result_id:
            raise TemporalEvidenceIntegrityError("access result identity differs")
        return result

    def latest_access_information_set(
        self,
        context: TemporalAccessContext,
    ) -> TemporalInformationSetManifest | None:
        """Return the latest committed actor-visible context for one session."""

        session_key = _session_key(context)
        candidates = tuple(commit for commit in self.access_commits() if commit.session_key == session_key)
        if not candidates:
            return None
        latest = max(
            candidates,
            key=lambda commit: self.load_retrieval_state_artifact(
                session_key=commit.session_key,
                state_id=commit.next_state_id,
            ).state_sequence,
        )
        return self.load_access_publication(latest).information_set

    def publish_current_information_set(
        self,
        context: TemporalAccessContext,
        information_set: TemporalInformationSetManifest,
    ) -> None:
        """Select the latest immutable actor information set for one session."""

        if (
            information_set.agent_tenure_id != context.agent_tenure_id
            or information_set.base_view_id != context.base_view_id
        ):
            raise TemporalEvidenceIntegrityError("current temporal information set belongs to another actor context")
        session_key = _session_key(context)
        with self.locked():
            self._publish_model(
                f"private/information-sets/{information_set.content_sha256}.json",
                information_set,
            )
            self._replace_model(
                f"private/sessions/{session_key}/current-information-set.json",
                TemporalInformationSetPointer(
                    session_key=session_key,
                    information_set_id=information_set.information_set_id,
                    information_set_content_id=information_set.content_sha256,
                ),
            )

    def load_current_information_set(
        self,
        context: TemporalAccessContext,
    ) -> TemporalInformationSetManifest | None:
        """Reload the selected latest actor information set for one session."""

        session_key = _session_key(context)
        path = f"private/sessions/{session_key}/current-information-set.json"
        if not self._path(path).exists():
            return None
        pointer = self._load_model(
            path,
            TemporalInformationSetPointer,
            "current temporal information-set pointer",
        )
        information_set = self._load_model(
            f"private/information-sets/{pointer.information_set_content_id}.json",
            TemporalInformationSetManifest,
            "current temporal information set",
        )
        if (
            pointer.session_key != session_key
            or pointer.information_set_id != information_set.information_set_id
            or pointer.information_set_content_id != information_set.content_sha256
        ):
            raise TemporalEvidenceIntegrityError("current temporal information-set pointer differs")
        return information_set

    def load_current_information_set_for_session(
        self,
        *,
        run_id: str,
        session_id: str,
        agent_tenure_id: str,
    ) -> TemporalInformationSetManifest | None:
        """Reload current context before a resumed actor view is projected."""

        session_key = _session_identity_key(
            run_id=run_id,
            session_id=session_id,
            agent_tenure_id=agent_tenure_id,
        )
        path = f"private/sessions/{session_key}/current-information-set.json"
        if not self._path(path).exists():
            return None
        pointer = self._load_model(
            path,
            TemporalInformationSetPointer,
            "current temporal information-set pointer",
        )
        information_set = self._load_model(
            f"private/information-sets/{pointer.information_set_content_id}.json",
            TemporalInformationSetManifest,
            "current temporal information set",
        )
        if (
            pointer.session_key != session_key
            or pointer.information_set_id != information_set.information_set_id
            or pointer.information_set_content_id != information_set.content_sha256
        ):
            raise TemporalEvidenceIntegrityError("current temporal information-set pointer differs")
        return information_set

    def retrieval_carriers(self) -> tuple[TemporalRetrievalStateCarrier, ...]:
        """Reload every actor-visible retrieval carrier."""

        return self._load_models_in(
            "public/carriers",
            TemporalRetrievalStateCarrier,
            "retrieval carrier",
        )

    def retrieval_handover_receipts(self) -> tuple[TemporalRetrievalHandoverReceipt, ...]:
        """Reload every private retrieval-carrier projection receipt."""

        return self._load_models_in(
            "private/handover-receipts",
            TemporalRetrievalHandoverReceipt,
            "retrieval handover receipt",
        )

    def retrieval_handover_install_receipts(
        self,
    ) -> tuple[TemporalRetrievalHandoverInstallReceipt, ...]:
        """Reload every private retrieval-carrier installation receipt."""

        return self._load_models_in(
            "private/handover-install-receipts",
            TemporalRetrievalHandoverInstallReceipt,
            "retrieval handover install receipt",
        )

    def create_retrieval_handover(
        self,
        context: TemporalAccessContext,
        *,
        to_agent_tenure_id: str,
        to_session_id: str,
        include_fetched_content: bool,
    ) -> TemporalRetrievalStateCarrier:
        """Project one source tenure into a sanitized actor-visible carrier."""

        with self.locked():
            state = self._load_retrieval_state_unlocked(context)
            all_results = tuple(
                self._load_model(
                    f"public/results/{result_id}.json",
                    TemporalEvidenceAccessResult,
                    "carried access result",
                )
                for result_id in state.access_result_ids
            )
            results = tuple(
                item
                for item in all_results
                if include_fetched_content or item.operation is TemporalEvidenceAccessKind.SEARCH
            )
            result_ids = tuple(item.content_sha256 for item in results)
            carrier = TemporalRetrievalStateCarrier(
                run_id=context.run_id,
                episode_id=context.episode_id,
                world_branch_id=context.world_branch_id,
                from_agent_tenure_id=context.agent_tenure_id,
                from_session_id=context.session_id,
                to_agent_tenure_id=to_agent_tenure_id,
                to_session_id=to_session_id,
                created_at_seconds=context.world_time_seconds,
                include_fetched_content=include_fetched_content,
                access_results=results,
                unresolved_search_ids=tuple(item for item in state.unresolved_search_ids if item in result_ids),
                remaining_budget=state.remaining_budget,
            )
            references = {reference.opaque_reference for result in results for reference in result.references}
            self._publish_model(
                f"public/carriers/{carrier.content_sha256}.json",
                carrier,
            )
            receipt = TemporalRetrievalHandoverReceipt(
                carrier_id=carrier.content_sha256,
                source_state_id=state.content_sha256,
                from_agent_tenure_id=context.agent_tenure_id,
                from_session_id=context.session_id,
                to_agent_tenure_id=to_agent_tenure_id,
                to_session_id=to_session_id,
                carried_result_ids=result_ids,
                carried_reference_count=len(references),
                remaining_budget=state.remaining_budget,
            )
            self._publish_model(
                f"private/handover-receipts/{receipt.content_sha256}.json",
                receipt,
            )
            return carrier

    def install_retrieval_handover(
        self,
        carrier: TemporalRetrievalStateCarrier,
        *,
        context: TemporalAccessContext,
    ) -> TemporalRetrievalState:
        """Install one authorized carrier into an unused fresh-tenure state."""

        with self.locked():
            expected = (
                context.run_id,
                context.episode_id,
                context.world_branch_id,
                context.agent_tenure_id,
                context.session_id,
            )
            observed = (
                carrier.run_id,
                carrier.episode_id,
                carrier.world_branch_id,
                carrier.to_agent_tenure_id,
                carrier.to_session_id,
            )
            if observed != expected:
                raise TemporalEvidenceIntegrityError("retrieval carrier belongs to another world or recipient")
            current = self._load_retrieval_state_unlocked(context)
            if current.installed_carrier_id == carrier.content_sha256:
                return current
            if current.state_sequence != 0 or current.access_result_ids:
                raise TemporalEvidenceIntegrityError("retrieval carrier requires an unused fresh-tenure state")
            references: dict[str, IssuedTemporalReference] = {}
            fetched_content_ids: list[str] = []
            for result in carrier.access_results:
                self._publish_model(
                    f"public/results/{result.content_sha256}.json",
                    result,
                )
                for reference in result.references:
                    references[reference.opaque_reference] = IssuedTemporalReference(
                        opaque_reference=reference.opaque_reference,
                        evidence_version_id=reference.version_id,
                    )
                fetched = result.fetched_content
                if fetched is not None:
                    references[fetched.opaque_reference] = IssuedTemporalReference(
                        opaque_reference=fetched.opaque_reference,
                        evidence_version_id=fetched.version_id,
                    )
                    fetched_content_ids.append(fetched.content_sha256)
                    self._publish_model(
                        f"public/content/{fetched.content_sha256}.json",
                        fetched,
                    )
            next_state = TemporalRetrievalState(
                state_sequence=1,
                previous_state_id=current.content_sha256,
                reference_namespace_id=current.reference_namespace_id,
                remaining_budget=carrier.remaining_budget,
                issued_references=tuple(references[key] for key in sorted(references)),
                access_result_ids=tuple(item.content_sha256 for item in carrier.access_results),
                actor_event_ids=(),
                fetched_content_ids=tuple(fetched_content_ids),
                unresolved_search_ids=carrier.unresolved_search_ids,
                installed_carrier_id=carrier.content_sha256,
            )
            session_key = _session_key(context)
            self._publish_model(
                f"public/carriers/{carrier.content_sha256}.json",
                carrier,
            )
            self._publish_model(
                f"private/sessions/{session_key}/states/{next_state.content_sha256}.json",
                next_state,
            )
            receipt = TemporalRetrievalHandoverInstallReceipt(
                carrier_id=carrier.content_sha256,
                target_session_key=session_key,
                prior_state_id=current.content_sha256,
                next_state_id=next_state.content_sha256,
                to_agent_tenure_id=context.agent_tenure_id,
                to_session_id=context.session_id,
            )
            self._publish_model(
                f"private/handover-install-receipts/{receipt.content_sha256}.json",
                receipt,
            )
            self._replace_model(
                f"private/sessions/{session_key}/current.json",
                TemporalRetrievalStatePointer(
                    session_key=session_key,
                    state_sequence=next_state.state_sequence,
                    state_id=next_state.content_sha256,
                ),
            )
            return next_state

    def stage_access(
        self,
        publication: TemporalAccessPublication,
        *,
        context: TemporalAccessContext,
    ) -> TemporalAccessCommit:
        """Publish all immutable access artifacts without moving the tenure pointer."""

        with self.locked():
            canonical = publication.with_actor_event_bound()
            current = self._load_retrieval_state_unlocked(context)
            next_state = canonical.decision.next_state
            if next_state.previous_state_id != current.content_sha256:
                raise TemporalEvidenceIntegrityError("temporal access is based on stale retrieval state")
            receipt = canonical.decision.receipt
            if receipt.prior_information_set_id != context.prior_information_set_id:
                raise TemporalEvidenceIntegrityError("temporal access prior information set differs")
            transaction_path = _transaction_path(receipt.request_id)
            if self._path(transaction_path).exists():
                commit = self._load_model(
                    transaction_path,
                    TemporalAccessCommit,
                    "temporal access commit",
                )
                self._validate_commit_matches(commit, canonical, context=context)
                return commit
            self._publish_model(
                f"public/results/{canonical.decision.result.content_sha256}.json",
                canonical.decision.result,
            )
            self._publish_model(
                f"private/receipts/{receipt.content_sha256}.json",
                receipt,
            )
            self._publish_model(
                f"public/events/{canonical.event.event_id}.json",
                canonical.event,
            )
            self._publish_model(
                f"private/information-sets/{canonical.information_set.content_sha256}.json",
                canonical.information_set,
            )
            fetched = canonical.decision.result.fetched_content
            if fetched is not None:
                self._publish_model(
                    f"public/content/{fetched.content_sha256}.json",
                    fetched,
                )
            session_key = _session_key(context)
            self._publish_model(
                f"private/sessions/{session_key}/states/{next_state.content_sha256}.json",
                next_state,
            )
            commit = TemporalAccessCommit(
                session_key=session_key,
                request_id=receipt.request_id,
                request_content_id=receipt.request_content_id,
                prior_state_id=current.content_sha256,
                next_state_id=next_state.content_sha256,
                result_id=canonical.decision.result.content_sha256,
                receipt_id=receipt.content_sha256,
                event_id=canonical.event.event_id,
                event_content_id=canonical.event.content_sha256,
                information_set_id=canonical.information_set.information_set_id,
                information_set_content_id=canonical.information_set.content_sha256,
                fetched_content_id=fetched.content_sha256 if fetched is not None else None,
            )
            self._publish_model(transaction_path, commit)
            return commit

    def publish_staged_access(
        self,
        commit: TemporalAccessCommit,
        *,
        context: TemporalAccessContext,
    ) -> TemporalAccessPublication:
        """Atomically select one staged access state or recover its prior selection."""

        with self.locked():
            publication = self._load_publication(commit)
            self._validate_commit_matches(commit, publication, context=context)
            current = self._load_retrieval_state_unlocked(context)
            if current.content_sha256 == commit.next_state_id:
                return publication
            if current.content_sha256 != commit.prior_state_id:
                raise TemporalEvidenceIntegrityError("temporal access commit does not follow current state")
            next_state = publication.decision.next_state
            self._replace_model(
                f"private/sessions/{commit.session_key}/current.json",
                TemporalRetrievalStatePointer(
                    session_key=commit.session_key,
                    state_sequence=next_state.state_sequence,
                    state_id=next_state.content_sha256,
                ),
            )
            return publication

    def commit_access(
        self,
        publication: TemporalAccessPublication,
        *,
        context: TemporalAccessContext,
    ) -> TemporalAccessPublication:
        """Stage and atomically select one exact access publication."""

        transaction_path = _transaction_path(publication.decision.receipt.request_id)
        if self._path(transaction_path).exists():
            commit = self._load_model(
                transaction_path,
                TemporalAccessCommit,
                "temporal access commit",
            )
            self._validate_commit_matches(
                commit,
                publication.with_actor_event_bound(),
                context=context,
            )
        else:
            commit = self.stage_access(publication, context=context)
        return self.publish_staged_access(commit, context=context)

    def recover_access(
        self,
        request_id: str,
        *,
        context: TemporalAccessContext,
    ) -> TemporalAccessPublication:
        """Recover a committed or staged access without another retrieval operation."""

        commit = self._load_model(
            _transaction_path(request_id),
            TemporalAccessCommit,
            "temporal access commit",
        )
        if commit.request_id != request_id:
            raise TemporalEvidenceIntegrityError("temporal access request identity differs")
        return self.publish_staged_access(commit, context=context)

    def load_bundle(self, *, package: ReferencePackage) -> TemporalEvidenceBundle:
        """Reload the complete corpus and reject missing or drifted authority."""

        try:
            capability = self._load_model(
                "capability.json",
                TemporalEvidenceCapability,
                "capability",
            )
            manifest = self._load_model(
                "corpus/manifest.json",
                TemporalCorpusManifest,
                "corpus manifest",
            )
            lineage = self._load_model(
                "corpus/lineage.json",
                TemporalEvidenceLineage,
                "corpus lineage",
            )
            availability = self._load_model(
                "corpus/availability.json",
                TemporalEvidenceAvailabilitySchedule,
                "availability schedule",
            )
            retrieval_policy = self._load_model(
                "policies/retrieval.json",
                TemporalRetrievalPolicy,
                "retrieval policy",
            )
            access_policy = self._load_model(
                "policies/access.json",
                TemporalAccessPolicy,
                "access policy",
            )
            branch_policy = self._load_model(
                "policies/branch.json",
                TemporalBranchPolicy,
                "branch policy",
            )
            cost_policy = self._load_model(
                "policies/cost.json",
                TemporalCostPolicy,
                "cost policy",
            )
            versions = tuple(
                self._load_model(
                    f"corpus/versions/{item.version_id}.json",
                    TemporalEvidenceVersion,
                    f"evidence version {item.version_id}",
                )
                for item in manifest.versions
            )
            bundle = TemporalEvidenceBundle(
                capability=capability,
                corpus_manifest=manifest,
                lineage=lineage,
                availability=availability,
                retrieval_policy=retrieval_policy,
                access_policy=access_policy,
                branch_policy=branch_policy,
                cost_policy=cost_policy,
                versions=versions,
            )
        except (OSError, ValidationError, ValueError) as error:
            raise TemporalEvidenceIntegrityError(
                f"temporal corpus manifest or artifact is invalid: {error}",
            ) from error
        self._validate_authority(bundle, package=package)
        return bundle

    def _validate_authority(
        self,
        bundle: TemporalEvidenceBundle,
        *,
        package: ReferencePackage,
    ) -> None:
        manifest = bundle.corpus_manifest
        lineage = bundle.lineage
        expected_parent = (
            package.profile_id,
            package.generation_id,
            package.package_content_id,
            package.manifest_content_id,
        )
        if (
            manifest.parent_profile_id,
            manifest.parent_generation_id,
            manifest.parent_package_content_id,
            manifest.parent_certification_id,
        ) != expected_parent:
            raise TemporalEvidenceIntegrityError("temporal corpus parent package identity differs")
        if (
            lineage.parent_profile_id,
            lineage.parent_generation_id,
            lineage.parent_package_content_id,
            lineage.parent_certification_id,
        ) != expected_parent:
            raise TemporalEvidenceIntegrityError("temporal corpus parent package lineage differs")
        source_by_id = {item.source_id: item for item in lineage.sources}
        for version in bundle.versions:
            source = source_by_id.get(version.source_id)
            if source is None:
                raise TemporalEvidenceIntegrityError("temporal evidence source is absent from lineage")
            if version.content_text is not None and (
                source.rights_class is not TemporalEvidenceRightsClass.REDISTRIBUTABLE
                or not source.redistribution_permitted
            ):
                raise TemporalEvidenceIntegrityError("prohibited source bytes enter redistributable corpus")
            if (
                version.parent_profile_id,
                version.parent_generation_id,
                version.parent_package_content_id,
            ) != expected_parent[:3]:
                raise TemporalEvidenceIntegrityError("evidence version parent package identity differs")
            if version.source_class is not source.source_class or version.rights_class is not source.rights_class:
                raise TemporalEvidenceIntegrityError("evidence version source classification differs")
            if not set(version.derivation_ids).issubset(lineage.derivation_ids):
                raise TemporalEvidenceIntegrityError("evidence derivation is absent from lineage")
            if not set(version.assumption_ids).issubset(lineage.assumption_ids):
                raise TemporalEvidenceIntegrityError("evidence assumption is absent from lineage")
            if not set(version.transformation_ids).issubset(lineage.transformation_ids):
                raise TemporalEvidenceIntegrityError("evidence transformation is absent from lineage")
            if (
                version.constructed_treatment_id is not None
                and version.constructed_treatment_id not in lineage.constructed_treatment_ids
            ):
                raise TemporalEvidenceIntegrityError("constructed treatment is absent from lineage")

    def _load_retrieval_state_unlocked(
        self,
        context: TemporalAccessContext,
    ) -> TemporalRetrievalState:
        session_key = _session_key(context)
        root = f"private/sessions/{session_key}"
        manifest = self._load_model(
            f"{root}/manifest.json",
            TemporalRetrievalSessionManifest,
            "retrieval session manifest",
        )
        expected = (
            context.run_id,
            context.episode_id,
            context.world_branch_id,
            context.actor_id,
            context.agent_tenure_id,
            context.session_id,
        )
        if (
            manifest.run_id,
            manifest.episode_id,
            manifest.world_branch_id,
            manifest.actor_id,
            manifest.agent_tenure_id,
            manifest.session_id,
        ) != expected:
            raise TemporalEvidenceIntegrityError("retrieval session context differs")
        pointer = self._load_model(
            f"{root}/current.json",
            TemporalRetrievalStatePointer,
            "retrieval state pointer",
        )
        state = self._load_model(
            f"{root}/states/{pointer.state_id}.json",
            TemporalRetrievalState,
            "retrieval state",
        )
        if (
            state.content_sha256 != pointer.state_id
            or state.state_sequence != pointer.state_sequence
            or pointer.session_key != session_key
        ):
            raise TemporalEvidenceIntegrityError("retrieval state pointer differs")
        return state

    def _load_publication(
        self,
        commit: TemporalAccessCommit,
    ) -> TemporalAccessPublication:
        result = self._load_model(
            f"public/results/{commit.result_id}.json",
            TemporalEvidenceAccessResult,
            "access result",
        )
        receipt = self._load_model(
            f"private/receipts/{commit.receipt_id}.json",
            TemporalEvidenceAccessReceipt,
            "access receipt",
        )
        event = self._load_model(
            f"public/events/{commit.event_id}.json",
            TemporalActorVisibleEvent,
            "actor-visible access event",
        )
        information_set = self._load_model(
            f"private/information-sets/{commit.information_set_content_id}.json",
            TemporalInformationSetManifest,
            "temporal information set",
        )
        state = self._load_model(
            f"private/sessions/{commit.session_key}/states/{commit.next_state_id}.json",
            TemporalRetrievalState,
            "retrieval state",
        )
        return TemporalAccessPublication(
            decision=TemporalAccessDecision(
                result=result,
                receipt=receipt,
                next_state=state,
            ),
            event=event,
            information_set=information_set,
        )

    def _validate_commit_matches(
        self,
        commit: TemporalAccessCommit,
        publication: TemporalAccessPublication,
        *,
        context: TemporalAccessContext,
    ) -> None:
        canonical = publication.with_actor_event_bound()
        receipt = canonical.decision.receipt
        expected = (
            _session_key(context),
            receipt.request_id,
            receipt.request_content_id,
            canonical.decision.next_state.previous_state_id,
            canonical.decision.next_state.content_sha256,
            canonical.decision.result.content_sha256,
            receipt.content_sha256,
            canonical.event.event_id,
            canonical.event.content_sha256,
            canonical.information_set.information_set_id,
            canonical.information_set.content_sha256,
            (
                canonical.decision.result.fetched_content.content_sha256
                if canonical.decision.result.fetched_content is not None
                else None
            ),
        )
        observed = (
            commit.session_key,
            commit.request_id,
            commit.request_content_id,
            commit.prior_state_id,
            commit.next_state_id,
            commit.result_id,
            commit.receipt_id,
            commit.event_id,
            commit.event_content_id,
            commit.information_set_id,
            commit.information_set_content_id,
            commit.fetched_content_id,
        )
        if observed != expected:
            raise TemporalEvidenceIntegrityError("temporal access request identity conflict")

    def _strict_bundle(self, bundle: TemporalEvidenceBundle) -> TemporalEvidenceBundle:
        try:
            return TemporalEvidenceBundle.model_validate(bundle.model_dump(mode="json"))
        except ValidationError as error:
            raise TemporalEvidenceIntegrityError(f"temporal corpus contract is invalid: {error}") from error

    def _publish_model(self, relative_path: str, model: BaseModel) -> None:
        payload = _canonical_model_bytes(model)
        path = self._path(relative_path)
        if path.exists():
            if self._load_bytes(path, relative_path) != payload:
                raise TemporalEvidenceIntegrityError(f"immutable temporal artifact collision: {relative_path}")
            return
        mkdir_durable(path.parent)
        temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError:
                if self._load_bytes(path, relative_path) != payload:
                    raise TemporalEvidenceIntegrityError(
                        f"immutable temporal artifact collision: {relative_path}",
                    ) from None
            fsync_directory(path.parent)
        finally:
            temporary.unlink(missing_ok=True)

    def _replace_model(self, relative_path: str, model: BaseModel) -> None:
        payload = _canonical_model_bytes(model)
        path = self._path(relative_path)
        mkdir_durable(path.parent)
        temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            fsync_directory(path.parent)
        finally:
            temporary.unlink(missing_ok=True)

    def _load_model(
        self,
        relative_path: str,
        model_type: type[ModelT],
        label: str,
    ) -> ModelT:
        path = self._path(relative_path)
        try:
            return model_type.model_validate_json(self._load_bytes(path, relative_path))
        except (ValidationError, ValueError) as error:
            raise TemporalEvidenceIntegrityError(f"{label} is invalid: {error}") from error

    def _load_models_in(
        self,
        relative_directory: str,
        model_type: type[ModelT],
        label: str,
    ) -> tuple[ModelT, ...]:
        directory = self._path(relative_directory)
        if not directory.exists():
            return ()
        if directory.is_symlink() or not directory.is_dir():
            raise TemporalEvidenceIntegrityError(f"{label} directory is invalid")
        return tuple(
            self._load_model(
                str(path.relative_to(self._root)),
                model_type,
                label,
            )
            for path in sorted(directory.iterdir())
            if path.suffix == ".json"
        )

    def _load_bytes(self, path: Path, label: str) -> bytes:
        if path.is_symlink():
            raise TemporalEvidenceIntegrityError(f"temporal artifact is a symlink: {label}")
        try:
            details = path.stat(follow_symlinks=False)
        except OSError as error:
            raise TemporalEvidenceIntegrityError(f"temporal artifact is missing: {label}") from error
        if not stat.S_ISREG(details.st_mode):
            raise TemporalEvidenceIntegrityError(f"temporal artifact is not a file: {label}")
        return path.read_bytes()

    def _path(self, relative_path: str) -> Path:
        if not relative_path or relative_path.startswith("/"):
            raise TemporalEvidenceIntegrityError("temporal artifact path must be relative")
        parts = Path(relative_path).parts
        if any(part in {"", ".", ".."} for part in parts):
            raise TemporalEvidenceIntegrityError("temporal artifact path is not confined")
        path = self._root.joinpath(*parts)
        if not path.resolve(strict=False).is_relative_to(self._root):
            raise TemporalEvidenceIntegrityError("temporal artifact path escapes its root")
        cursor = self._root
        for part in parts:
            cursor /= part
            if cursor.is_symlink():
                raise TemporalEvidenceIntegrityError("temporal artifact path contains a symlink")
        return path


def _canonical_model_bytes(model: BaseModel) -> bytes:
    return (
        json.dumps(
            model.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _session_key(context: TemporalAccessContext) -> str:
    return _session_identity_key(
        run_id=context.run_id,
        session_id=context.session_id,
        agent_tenure_id=context.agent_tenure_id,
    )


def _session_identity_key(
    *,
    run_id: str,
    session_id: str,
    agent_tenure_id: str,
) -> str:
    return canonical_content_sha256(
        {
            "run_id": run_id,
            "session_id": session_id,
            "agent_tenure_id": agent_tenure_id,
        }
    )


def _transaction_path(request_id: str) -> str:
    identity = canonical_content_sha256({"request_id": request_id})
    return f"private/transactions/{identity}.json"


def _reliance_path(action_request_id: str) -> str:
    identity = canonical_content_sha256({"action_request_id": action_request_id})
    return f"public/reliance/{identity}.json"
