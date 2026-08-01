# ABOUTME: Persists derived pump-station review cases as immutable private artifacts.
# ABOUTME: Provides idempotent publication, strict reload, and staged crash recovery.

from __future__ import annotations

import fcntl
import json
import os
import stat
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import NoReturn, TypeVar

from pydantic import BaseModel, field_validator, model_validator

from aec_bench.contracts.harness_kernel import (
    ContentAddressedModel,
    canonical_content_sha256,
    validate_sha256,
)
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review import (
    PreparedPumpStationReviewCase,
    PumpStationReviewCaseManifest,
    PumpStationReviewIssueSpecification,
    PumpStationReviewPack,
    PumpStationReviewPreparationReceipt,
    PumpStationReviewPreparationRequest,
    PumpStationReviewPublicCase,
    PumpStationReviewSubmission,
    PumpStationReviewSubmissionReceipt,
    PumpStationReviewTreatmentReceipt,
    PumpStationReviewVerifierTarget,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_verifier import (
    PumpStationVerificationReport,
)

ModelT = TypeVar("ModelT", bound=BaseModel)


class PumpStationReviewRepositoryError(ValueError):
    """Raised when durable review-case evidence violates its contract."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _fail(code: str, detail: str) -> NoReturn:
    raise PumpStationReviewRepositoryError(code, detail)


class PumpStationReviewCasePointer(ContentAddressedModel):
    """Small immutable index from a preparation request to its case manifest."""

    schema_version: str = "pump-station.review-case-pointer.v1"
    request_id: NonEmptyStr
    request_content_sha256: str
    case_id: NonEmptyStr
    manifest_content_sha256: str

    @field_validator("request_content_sha256", "manifest_content_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_pointer(self) -> PumpStationReviewCasePointer:
        if self.schema_version != "pump-station.review-case-pointer.v1":
            raise ValueError("unsupported review case pointer version")
        return self


class PumpStationReviewSubmissionPointer(ContentAddressedModel):
    """Immutable index from review identity to submission and receipt."""

    schema_version: str = "pump-station.review-submission-pointer.v1"
    review_id: NonEmptyStr
    review_content_sha256: str
    receipt_content_sha256: str
    case_id: NonEmptyStr

    @field_validator("review_content_sha256", "receipt_content_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_pointer(self) -> PumpStationReviewSubmissionPointer:
        if self.schema_version != "pump-station.review-submission-pointer.v1":
            raise ValueError("unsupported review submission pointer version")
        return self


@dataclass(frozen=True, slots=True)
class PumpStationStagedReviewCase:
    """Reference to one fully staged case not yet selected by request id."""

    request_id: str
    case_id: str
    pointer_content_sha256: str


def _ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(0o700)


def _model_bytes(value: BaseModel) -> bytes:
    return (
        json.dumps(
            value.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")


def _boolean(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        _fail("review-artifact-integrity", f"{label} is not boolean")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str):
        _fail("review-artifact-integrity", f"{label} is not text")
    return value


def _string_tuple(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        _fail(
            "review-artifact-integrity",
            f"{label} is not a string list",
        )
    return tuple(value)


class PumpStationReviewCaseRepository:
    """Confined durable repository for derived review cases and responses."""

    def __init__(self, root: Path) -> None:
        selected = Path(root)
        if selected.exists() and (selected.is_symlink() or not selected.is_dir()):
            _fail(
                "review-artifact-confinement",
                "review-case root must be a plain directory",
            )
        _ensure_directory(selected)
        self._root = selected.resolve(strict=True)
        self._lock_path = self._root / ".review-case.lock"

    @property
    def root(self) -> Path:
        """Return the exact host-selected review repository root."""
        return self._root

    @contextmanager
    def locked(self) -> Iterator[None]:
        """Serialize review-case selection across local processes."""
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(self._lock_path, flags, 0o600)
        try:
            details = os.fstat(descriptor)
            if not stat.S_ISREG(details.st_mode):
                _fail(
                    "review-artifact-confinement",
                    "review-case lock is not a regular file",
                )
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)

    def stage_case(
        self,
        prepared: PreparedPumpStationReviewCase,
    ) -> PumpStationStagedReviewCase:
        """Publish complete immutable content without selecting the request."""
        with self.locked():
            existing = self._pointer_if_present(
                "published-requests",
                prepared.request.request_id,
            ) or self._pointer_if_present(
                "staged-requests",
                prepared.request.request_id,
            )
            if existing is not None:
                self._require_same_request(existing, prepared.request)
                return PumpStationStagedReviewCase(
                    request_id=existing.request_id,
                    case_id=existing.case_id,
                    pointer_content_sha256=existing.content_sha256,
                )
            self._publish_model(
                "requests-content",
                prepared.request.content_sha256,
                prepared.request,
            )
            self._publish_model(
                "untreated-packs",
                prepared.untreated_pack.content_sha256,
                prepared.untreated_pack,
            )
            self._publish_model(
                "public-cases",
                prepared.public_case.content_sha256,
                prepared.public_case,
            )
            self._publish_model(
                "private-issues",
                prepared.issue.content_sha256,
                prepared.issue,
            )
            self._publish_model(
                "verifier-targets",
                prepared.verifier_target.content_sha256,
                prepared.verifier_target,
            )
            self._publish_model(
                "preparation-receipts",
                prepared.preparation_receipt.content_sha256,
                prepared.preparation_receipt,
            )
            self._publish_model(
                "treatment-receipts",
                prepared.treatment_receipt.content_sha256,
                prepared.treatment_receipt,
            )
            verification_payload = asdict(prepared.source_verification)
            verification_id = canonical_content_sha256(verification_payload)
            if verification_id != prepared.preparation_receipt.source_verification_sha256:
                _fail(
                    "review-artifact-integrity",
                    "source verification identity differs from the receipt",
                )
            self._publish_payload(
                "source-verifications",
                verification_id,
                _json_bytes(verification_payload),
            )
            self._publish_model(
                "manifests",
                prepared.manifest.content_sha256,
                prepared.manifest,
            )
            pointer = PumpStationReviewCasePointer(
                request_id=prepared.request.request_id,
                request_content_sha256=prepared.request.content_sha256,
                case_id=prepared.public_case.case_id,
                manifest_content_sha256=prepared.manifest.content_sha256,
            )
            self._publish_named_pointer(
                "staged-requests",
                prepared.request.request_id,
                pointer,
            )
            return PumpStationStagedReviewCase(
                request_id=pointer.request_id,
                case_id=pointer.case_id,
                pointer_content_sha256=pointer.content_sha256,
            )

    def publish_staged_case(
        self,
        staged: PumpStationStagedReviewCase,
    ) -> PreparedPumpStationReviewCase:
        """Atomically select one fully staged case by request identity."""
        with self.locked():
            published = self._pointer_if_present(
                "published-requests",
                staged.request_id,
            )
            if published is not None:
                if published.case_id != staged.case_id or published.content_sha256 != staged.pointer_content_sha256:
                    _fail(
                        "review-request-id-conflict",
                        staged.request_id,
                    )
                return self._load_case_from_pointer(published)
            pointer = self._load_named_pointer(
                "staged-requests",
                staged.request_id,
            )
            if pointer.case_id != staged.case_id or pointer.content_sha256 != staged.pointer_content_sha256:
                _fail(
                    "review-artifact-integrity",
                    "staged review pointer differs",
                )
            self._publish_named_pointer(
                "published-requests",
                staged.request_id,
                pointer,
            )
            return self._load_case_from_pointer(pointer)

    def publish_case(
        self,
        prepared: PreparedPumpStationReviewCase,
    ) -> PreparedPumpStationReviewCase:
        """Stage and select one case, returning exact retries unchanged."""
        published = self.find_published_case(prepared.request.request_id)
        if published is not None:
            if published.request != prepared.request:
                _fail(
                    "review-request-id-conflict",
                    prepared.request.request_id,
                )
            return published
        staged = self.stage_case(prepared)
        return self.publish_staged_case(staged)

    def recover_case(self, request_id: str) -> PreparedPumpStationReviewCase:
        """Recover a published or completely staged preparation after restart."""
        published = self.find_published_case(request_id)
        if published is not None:
            return published
        pointer = self._pointer_if_present("staged-requests", request_id)
        if pointer is None:
            _fail("review-request-not-found", request_id)
        return self.publish_staged_case(
            PumpStationStagedReviewCase(
                request_id=pointer.request_id,
                case_id=pointer.case_id,
                pointer_content_sha256=pointer.content_sha256,
            )
        )

    def find_published_case(
        self,
        request_id: str,
    ) -> PreparedPumpStationReviewCase | None:
        """Return one selected case by idempotent request identity."""
        pointer = self._pointer_if_present("published-requests", request_id)
        if pointer is None:
            return None
        return self._load_case_from_pointer(pointer)

    def load_case(self, case_id: str) -> PreparedPumpStationReviewCase:
        """Strictly reload one published case by public identity."""
        for request_id in self._published_request_ids():
            pointer = self._load_named_pointer(
                "published-requests",
                request_id,
            )
            if pointer.case_id == case_id:
                return self._load_case_from_pointer(pointer)
        _fail("review-case-not-found", case_id)

    def list_case_ids(self) -> tuple[str, ...]:
        """List every published case identity in stable order."""
        return tuple(
            sorted(
                self._load_named_pointer(
                    "published-requests",
                    request_id,
                ).case_id
                for request_id in self._published_request_ids()
            )
        )

    def publish_review(
        self,
        submission: PumpStationReviewSubmission,
    ) -> PumpStationReviewSubmissionReceipt:
        """Publish one visible-source-bound review and return exact retries."""
        with self.locked():
            existing = self._review_pointer_if_present(submission.review_id)
            if existing is not None:
                stored = self._load_model(
                    "review-submissions",
                    existing.review_content_sha256,
                    PumpStationReviewSubmission,
                )
                if stored != submission:
                    _fail(
                        "review-submission-id-conflict",
                        submission.review_id,
                    )
                return self._load_model(
                    "review-receipts",
                    existing.receipt_content_sha256,
                    PumpStationReviewSubmissionReceipt,
                )
            prepared = self.load_case(submission.case_id)
            public_case = prepared.public_case
            if (
                submission.public_case_content_sha256 != public_case.content_sha256
                or submission.pack_content_sha256 != public_case.pack.content_sha256
            ):
                raise ValueError("review submission differs from its visible case binding")
            record_ids = {item.record_id for item in public_case.pack.records}
            visible_source_ids = set(record_ids)
            for record in public_case.pack.records:
                visible_source_ids.update(record.source_record_ids)
                visible_source_ids.update(record.evidence_ids)
            if not set(submission.affected_record_ids).issubset(record_ids):
                raise ValueError("affected record is outside the visible pack")
            if not set(submission.unaffected_duty_ids).issubset(record_ids):
                raise ValueError("unaffected duty is outside the visible pack")
            if not set(submission.missing_evidence_ids).issubset(visible_source_ids):
                raise ValueError("missing evidence is outside the visible pack")
            if not set(submission.source_record_ids).issubset(visible_source_ids):
                raise ValueError("source reference is outside the visible pack")
            receipt = PumpStationReviewSubmissionReceipt(
                review_id=submission.review_id,
                review_content_sha256=submission.content_sha256,
                case_id=submission.case_id,
                public_case_content_sha256=(submission.public_case_content_sha256),
                reviewer_tenure_id=submission.reviewer_tenure_id,
            )
            self._publish_model(
                "review-submissions",
                submission.content_sha256,
                submission,
            )
            self._publish_model(
                "review-receipts",
                receipt.content_sha256,
                receipt,
            )
            pointer = PumpStationReviewSubmissionPointer(
                review_id=submission.review_id,
                review_content_sha256=submission.content_sha256,
                receipt_content_sha256=receipt.content_sha256,
                case_id=submission.case_id,
            )
            self._publish_path(
                self._root / "published-reviews" / f"{submission.review_id}.json",
                _model_bytes(pointer),
            )
            return receipt

    def load_review(self, review_id: str) -> PumpStationReviewSubmission:
        """Strictly reload one immutable reviewer submission."""
        pointer = self._load_review_pointer(review_id)
        return self._load_model(
            "review-submissions",
            pointer.review_content_sha256,
            PumpStationReviewSubmission,
        )

    def load_review_receipt(
        self,
        review_id: str,
    ) -> PumpStationReviewSubmissionReceipt:
        """Strictly reload the immutable receipt for one review."""
        pointer = self._load_review_pointer(review_id)
        return self._load_model(
            "review-receipts",
            pointer.receipt_content_sha256,
            PumpStationReviewSubmissionReceipt,
        )

    def list_review_ids(self, case_id: str) -> tuple[str, ...]:
        """List immutable reviews for one case in stable identity order."""
        directory = self._root / "published-reviews"
        if not directory.exists():
            return ()
        return tuple(
            sorted(
                path.stem
                for path in directory.glob("*.json")
                if self._load_review_pointer(path.stem).case_id == case_id
            )
        )

    def _load_case_from_pointer(
        self,
        pointer: PumpStationReviewCasePointer,
    ) -> PreparedPumpStationReviewCase:
        request = self._load_model(
            "requests-content",
            pointer.request_content_sha256,
            PumpStationReviewPreparationRequest,
        )
        manifest = self._load_model(
            "manifests",
            pointer.manifest_content_sha256,
            PumpStationReviewCaseManifest,
        )
        if (
            request.request_id != pointer.request_id
            or manifest.case_id != pointer.case_id
            or manifest.request_content_sha256 != request.content_sha256
        ):
            _fail(
                "review-artifact-integrity",
                "review pointer, request, and manifest differ",
            )
        public_case = self._load_model(
            "public-cases",
            manifest.public_case_content_sha256,
            PumpStationReviewPublicCase,
        )
        issue = self._load_model(
            "private-issues",
            manifest.issue_content_sha256,
            PumpStationReviewIssueSpecification,
        )
        target = self._load_model(
            "verifier-targets",
            manifest.verifier_target_content_sha256,
            PumpStationReviewVerifierTarget,
        )
        preparation_receipt = self._load_model(
            "preparation-receipts",
            manifest.preparation_receipt_content_sha256,
            PumpStationReviewPreparationReceipt,
        )
        treatment_receipt = self._load_model(
            "treatment-receipts",
            manifest.treatment_receipt_content_sha256,
            PumpStationReviewTreatmentReceipt,
        )
        untreated_pack = self._load_model(
            "untreated-packs",
            preparation_receipt.untreated_pack_content_sha256,
            PumpStationReviewPack,
        )
        verification_payload = self._read_json(
            "source-verifications",
            preparation_receipt.source_verification_sha256,
        )
        if canonical_content_sha256(verification_payload) != preparation_receipt.source_verification_sha256:
            _fail(
                "review-artifact-integrity",
                "source verification content identity differs",
            )
        verification = PumpStationVerificationReport(
            valid=_boolean(verification_payload["valid"], "verification.valid"),
            issues=_string_tuple(
                verification_payload["issues"],
                "verification.issues",
            ),
            replayed_transition_ids=_string_tuple(
                verification_payload["replayed_transition_ids"],
                "verification.replayed_transition_ids",
            ),
            final_state_id=_text(
                verification_payload["final_state_id"],
                "verification.final_state_id",
            ),
            active_restriction_ids=_string_tuple(
                verification_payload["active_restriction_ids"],
                "verification.active_restriction_ids",
            ),
            open_obligation_ids=_string_tuple(
                verification_payload["open_obligation_ids"],
                "verification.open_obligation_ids",
            ),
        )
        if (
            public_case.case_id != pointer.case_id
            or public_case.content_sha256 != manifest.public_case_content_sha256
            or issue.request_content_sha256 != request.content_sha256
            or treatment_receipt.issue_content_sha256 != issue.content_sha256
            or treatment_receipt.treated_pack_content_sha256 != public_case.pack.content_sha256
            or treatment_receipt.untreated_pack_content_sha256 != untreated_pack.content_sha256
            or preparation_receipt.request_content_sha256 != request.content_sha256
        ):
            _fail(
                "review-artifact-integrity",
                "review case evidence does not reconcile",
            )
        return PreparedPumpStationReviewCase(
            request=request,
            source_verification=verification,
            untreated_pack=untreated_pack,
            public_case=public_case,
            issue=issue,
            verifier_target=target,
            preparation_receipt=preparation_receipt,
            treatment_receipt=treatment_receipt,
            manifest=manifest,
        )

    def _require_same_request(
        self,
        pointer: PumpStationReviewCasePointer,
        request: PumpStationReviewPreparationRequest,
    ) -> None:
        stored = self._load_model(
            "requests-content",
            pointer.request_content_sha256,
            PumpStationReviewPreparationRequest,
        )
        if stored != request:
            _fail("review-request-id-conflict", request.request_id)

    def _published_request_ids(self) -> tuple[str, ...]:
        directory = self._root / "published-requests"
        if not directory.exists():
            return ()
        return tuple(sorted(path.stem for path in directory.glob("*.json")))

    def _pointer_if_present(
        self,
        collection: str,
        request_id: str,
    ) -> PumpStationReviewCasePointer | None:
        path = self._root / collection / f"{request_id}.json"
        if not path.exists():
            return None
        return PumpStationReviewCasePointer.model_validate_json(self._read(path, f"{collection}/{request_id}.json"))

    def _review_pointer_if_present(
        self,
        review_id: str,
    ) -> PumpStationReviewSubmissionPointer | None:
        path = self._root / "published-reviews" / f"{review_id}.json"
        if not path.exists():
            return None
        return PumpStationReviewSubmissionPointer.model_validate_json(
            self._read(path, f"published-reviews/{review_id}.json")
        )

    def _load_review_pointer(
        self,
        review_id: str,
    ) -> PumpStationReviewSubmissionPointer:
        pointer = self._review_pointer_if_present(review_id)
        if pointer is None:
            _fail("review-submission-not-found", review_id)
        return pointer

    def _load_named_pointer(
        self,
        collection: str,
        request_id: str,
    ) -> PumpStationReviewCasePointer:
        pointer = self._pointer_if_present(collection, request_id)
        if pointer is None:
            _fail("review-request-not-found", request_id)
        return pointer

    def _publish_named_pointer(
        self,
        collection: str,
        request_id: str,
        pointer: PumpStationReviewCasePointer,
    ) -> None:
        self._publish_path(
            self._root / collection / f"{request_id}.json",
            _model_bytes(pointer),
        )

    def _publish_model(
        self,
        collection: str,
        content_id: str,
        value: BaseModel,
    ) -> None:
        if value.content_sha256 != content_id:  # type: ignore[attr-defined]
            _fail(
                "review-artifact-integrity",
                f"{collection} content identity differs",
            )
        self._publish_payload(
            collection,
            content_id,
            _model_bytes(value),
        )

    def _publish_payload(
        self,
        collection: str,
        content_id: str,
        payload: bytes,
    ) -> None:
        validate_sha256(content_id)
        self._publish_path(
            self._root / collection / f"{content_id}.json",
            payload,
        )

    def _publish_path(self, path: Path, payload: bytes) -> None:
        if path.exists():
            observed = self._read(path, str(path.relative_to(self._root)))
            if observed != payload:
                _fail(
                    "review-artifact-collision",
                    str(path.relative_to(self._root)),
                )
            return
        _ensure_directory(path.parent)
        temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError:
                if (
                    self._read(
                        path,
                        str(path.relative_to(self._root)),
                    )
                    != payload
                ):
                    _fail(
                        "review-artifact-collision",
                        str(path.relative_to(self._root)),
                    )
        finally:
            temporary.unlink(missing_ok=True)

    def _load_model(
        self,
        collection: str,
        content_id: str,
        model_type: type[ModelT],
    ) -> ModelT:
        value = model_type.model_validate_json(
            self._read(
                self._root / collection / f"{content_id}.json",
                f"{collection}/{content_id}.json",
            )
        )
        if getattr(value, "content_sha256", None) != content_id:
            _fail(
                "review-artifact-integrity",
                f"{collection} content identity differs",
            )
        return value

    def _read_json(self, collection: str, content_id: str) -> dict[str, object]:
        payload = json.loads(
            self._read(
                self._root / collection / f"{content_id}.json",
                f"{collection}/{content_id}.json",
            )
        )
        if not isinstance(payload, dict):
            _fail(
                "review-artifact-integrity",
                f"{collection} artifact is not an object",
            )
        return payload

    def _read(self, path: Path, label: str) -> bytes:
        if path.is_symlink():
            _fail(
                "review-artifact-confinement",
                f"{label} is a symbolic link",
            )
        try:
            details = path.stat(follow_symlinks=False)
        except OSError as error:
            _fail(
                "review-artifact-integrity",
                f"{label} is unavailable: {error}",
            )
        if not stat.S_ISREG(details.st_mode):
            _fail(
                "review-artifact-integrity",
                f"{label} is not a regular file",
            )
        if stat.S_IMODE(details.st_mode) & 0o077:
            _fail(
                "review-artifact-confinement",
                f"{label} must be host-private",
            )
        return path.read_bytes()


__all__ = (
    "PumpStationReviewCaseRepository",
    "PumpStationReviewRepositoryError",
    "PumpStationStagedReviewCase",
)
