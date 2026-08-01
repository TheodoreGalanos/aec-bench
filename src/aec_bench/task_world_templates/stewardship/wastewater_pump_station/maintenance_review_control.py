# ABOUTME: Implements host-only preparation controls for pump-station review cases.
# ABOUTME: Keeps case derivation and session opening separate from reviewer actions.

from __future__ import annotations

from pathlib import Path
from typing import Literal, Self

from pydantic import model_validator

from aec_bench.contracts.harness_kernel import ContentAddressedModel
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review import (
    PumpStationReviewCaseManifest,
    PumpStationReviewPreparationReceipt,
    PumpStationReviewPreparationRequest,
    PumpStationReviewPublicCase,
    PumpStationReviewTreatmentReceipt,
    derive_pump_station_review_case,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review_repository import (
    PumpStationReviewCaseRepository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review_session import (
    PumpStationReviewHandover,
    PumpStationReviewObservation,
    PumpStationReviewSessionFactory,
    PumpStationReviewSessionOpenMode,
    PumpStationReviewSessionRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PumpStationStateSnapshotRef,
)

PUMP_STATION_REVIEW_TASK_ID = "wastewater-pump-station-maintenance-closeout-review.v1"
PUMP_STATION_REVIEW_CONTROL_OPERATIONS = (
    "prepare_case",
    "inspect_preparation",
    "recover_preparation",
    "open_review_session",
)


class PumpStationReviewControlOperation(ContentAddressedModel):
    """One declared host-only review control operation."""

    operation: NonEmptyStr
    changes_durable_state: bool


class PumpStationReviewControlCapabilities(ContentAddressedModel):
    """Closed operation catalogue for the review host."""

    schema_version: str = "pump-station.review-control-capabilities.v1"
    task_review_id: NonEmptyStr
    operations: tuple[PumpStationReviewControlOperation, ...]

    @model_validator(mode="after")
    def validate_capabilities(self) -> Self:
        if self.schema_version != "pump-station.review-control-capabilities.v1":
            raise ValueError("unsupported review control capabilities version")
        names = tuple(item.operation for item in self.operations)
        if names != PUMP_STATION_REVIEW_CONTROL_OPERATIONS:
            raise ValueError("review control operations differ")
        return self


class PumpStationReviewControlRequest(ContentAddressedModel):
    """Strict host request for one review-case control operation."""

    schema_version: str = "pump-station.review-control-request.v1"
    request_id: NonEmptyStr
    operation: Literal[
        "prepare_case",
        "inspect_preparation",
        "recover_preparation",
        "open_review_session",
    ]
    task_review_id: NonEmptyStr
    authority_id: NonEmptyStr
    preparation_request: PumpStationReviewPreparationRequest | None = None
    preparation_request_id: NonEmptyStr | None = None
    session_request: PumpStationReviewSessionRequest | None = None
    handover: PumpStationReviewHandover | None = None

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        if self.schema_version != "pump-station.review-control-request.v1":
            raise ValueError("unsupported review control request version")
        if self.task_review_id != PUMP_STATION_REVIEW_TASK_ID:
            raise ValueError("review control task identity differs")
        if self.operation == "prepare_case":
            if (
                self.preparation_request is None
                or self.preparation_request_id is not None
                or self.session_request is not None
                or self.handover is not None
            ):
                raise ValueError("prepare_case requires one preparation request")
            if self.request_id != self.preparation_request.request_id:
                raise ValueError("control and preparation request identities differ")
            return self
        if self.operation in {
            "inspect_preparation",
            "recover_preparation",
        }:
            if (
                self.preparation_request_id is None
                or self.preparation_request is not None
                or self.session_request is not None
                or self.handover is not None
            ):
                raise ValueError("inspection and recovery require one preparation identity")
            return self
        if (
            self.session_request is None
            or self.preparation_request is not None
            or self.preparation_request_id is not None
        ):
            raise ValueError("open_review_session requires one session request")
        expects_handover = self.session_request.open_mode is PumpStationReviewSessionOpenMode.RESUME
        if expects_handover != (self.handover is not None):
            raise ValueError("review session and handover requirements differ")
        return self


class PumpStationReviewControlReceipt(ContentAddressedModel):
    """Immutable result of one host review-control request."""

    schema_version: str = "pump-station.review-control-receipt.v1"
    request_content_sha256: str
    operation: NonEmptyStr
    authority_id: NonEmptyStr
    status: str = "completed"
    state_changed: bool
    case_id: NonEmptyStr
    source_snapshot_before: PumpStationStateSnapshotRef
    source_snapshot_after: PumpStationStateSnapshotRef

    @model_validator(mode="after")
    def validate_receipt(self) -> Self:
        if self.schema_version != "pump-station.review-control-receipt.v1":
            raise ValueError("unsupported review control receipt version")
        if self.status != "completed":
            raise ValueError("review control receipt must be completed")
        if self.source_snapshot_before != self.source_snapshot_after:
            raise ValueError("review control changed the source snapshot")
        return self


class PumpStationReviewControlResult(ContentAddressedModel):
    """Public case and immutable receipts returned to the review host."""

    schema_version: str = "pump-station.review-control-result.v1"
    request_content_sha256: str
    receipt: PumpStationReviewControlReceipt
    public_case: PumpStationReviewPublicCase
    manifest: PumpStationReviewCaseManifest
    preparation_receipt: PumpStationReviewPreparationReceipt
    treatment_receipt: PumpStationReviewTreatmentReceipt
    session_observation: PumpStationReviewObservation | None = None

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if self.schema_version != "pump-station.review-control-result.v1":
            raise ValueError("unsupported review control result version")
        if (
            self.request_content_sha256 != self.receipt.request_content_sha256
            or self.public_case.case_id != self.receipt.case_id
            or self.public_case.content_sha256 != self.manifest.public_case_content_sha256
        ):
            raise ValueError("review control result identities differ")
        return self


class PumpStationReviewControl:
    """Host-authorised preparation surface over one source and review root."""

    def __init__(
        self,
        *,
        source_run_root: Path,
        review_repository_root: Path,
        authorised_principal_ids: tuple[str, ...],
        package_root: Path | None = None,
    ) -> None:
        if (
            not authorised_principal_ids
            or any(not item.strip() for item in authorised_principal_ids)
            or len(authorised_principal_ids) != len(set(authorised_principal_ids))
        ):
            raise ValueError("review control requires distinct host principals")
        self._source_run_root = Path(source_run_root)
        self._review_repository_root = Path(review_repository_root)
        self._authorised_principals = frozenset(authorised_principal_ids)
        self._package_root = package_root

    def capabilities(
        self,
        authority_id: str,
    ) -> PumpStationReviewControlCapabilities:
        """Return the closed host catalogue after authority validation."""
        self._require_authority(authority_id)
        return PumpStationReviewControlCapabilities(
            task_review_id=PUMP_STATION_REVIEW_TASK_ID,
            operations=tuple(
                PumpStationReviewControlOperation(
                    operation=operation,
                    changes_durable_state=operation == "prepare_case",
                )
                for operation in PUMP_STATION_REVIEW_CONTROL_OPERATIONS
            ),
        )

    def execute(
        self,
        request: PumpStationReviewControlRequest,
    ) -> PumpStationReviewControlResult:
        """Execute one declared host operation without a record editor."""
        self._require_authority(request.authority_id)
        repository = PumpStationReviewCaseRepository(self._review_repository_root)
        observation: PumpStationReviewObservation | None = None
        if request.operation == "prepare_case":
            preparation = request.preparation_request
            if preparation is None:
                raise ValueError("prepare_case lacks its preparation request")
            prepared = repository.find_published_case(preparation.request_id)
            if prepared is None:
                prepared = repository.publish_case(
                    derive_pump_station_review_case(
                        source_run_root=self._source_run_root,
                        request=preparation,
                        package_root=self._package_root,
                    )
                )
            elif prepared.request != preparation:
                raise ValueError("review-request-id-conflict: " + preparation.request_id)
            state_changed = True
        elif request.operation == "inspect_preparation":
            if request.preparation_request_id is None:
                raise ValueError("inspection lacks preparation identity")
            prepared = repository.find_published_case(request.preparation_request_id)
            if prepared is None:
                raise ValueError("review-request-not-found: " + request.preparation_request_id)
            state_changed = False
        elif request.operation == "recover_preparation":
            if request.preparation_request_id is None:
                raise ValueError("recovery lacks preparation identity")
            prepared = repository.recover_case(request.preparation_request_id)
            state_changed = False
        else:
            session_request = request.session_request
            if session_request is None:
                raise ValueError("session open lacks its request")
            prepared = repository.load_case(session_request.case_id)
            session = PumpStationReviewSessionFactory(self._review_repository_root).open(
                session_request,
                handover=request.handover,
            )
            observation = session.observe()
            state_changed = False
        source_snapshot = prepared.public_case.source_snapshot
        receipt = PumpStationReviewControlReceipt(
            request_content_sha256=request.content_sha256,
            operation=request.operation,
            authority_id=request.authority_id,
            state_changed=state_changed,
            case_id=prepared.public_case.case_id,
            source_snapshot_before=source_snapshot,
            source_snapshot_after=source_snapshot,
        )
        return PumpStationReviewControlResult(
            request_content_sha256=request.content_sha256,
            receipt=receipt,
            public_case=prepared.public_case,
            manifest=prepared.manifest,
            preparation_receipt=prepared.preparation_receipt,
            treatment_receipt=prepared.treatment_receipt,
            session_observation=observation,
        )

    def _require_authority(self, authority_id: str) -> None:
        if authority_id not in self._authorised_principals:
            raise ValueError(f"review-control-unauthorised: {authority_id}")


__all__ = (
    "PUMP_STATION_REVIEW_CONTROL_OPERATIONS",
    "PUMP_STATION_REVIEW_TASK_ID",
    "PumpStationReviewControl",
    "PumpStationReviewControlCapabilities",
    "PumpStationReviewControlRequest",
    "PumpStationReviewControlResult",
)
