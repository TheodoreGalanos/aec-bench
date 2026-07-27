# ABOUTME: Claims and terminates one ledger-global import for each proposal Harbor execution.
# ABOUTME: Makes import retries resume the first host-owned identity and rejects index drift.

from __future__ import annotations

import json
import os
import stat
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Self

from pydantic import field_validator, model_validator

from aec_bench.contracts.harness_kernel import ContentAddressedModel, validate_sha256
from aec_bench.contracts.trial_record import ArtifactReference
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.ledger.durability import fsync_directory, mkdir_durable


class ProposalImportConsumptionError(RuntimeError):
    """Reject a corrupt, conflicting, or unconfined import-consumption index."""


class ProposalImportConsumptionClaim(ContentAddressedModel):
    """First-writer claim fixing the one import identity for an execution receipt."""

    schema_version: Literal["aecbench.proposal-import-consumption-claim.v1"] = (
        "aecbench.proposal-import-consumption-claim.v1"
    )
    harbor_execution_receipt_sha256: str
    dispatch_sha256: str
    artifacts_root: NonEmptyStr
    import_id: NonEmptyStr
    requested_authority_event_id: NonEmptyStr

    @field_validator(
        "harbor_execution_receipt_sha256",
        "dispatch_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("artifacts_root")
    @classmethod
    def validate_artifacts_root(cls, value: str) -> str:
        path = Path(value)
        if not path.is_absolute() or str(path.resolve(strict=False)) != value:
            raise ValueError("proposal import artifacts root must be canonical and absolute")
        return value


class ProposalImportTerminalRecord(ContentAddressedModel):
    """Terminal index entry proving the execution was consumed exactly once."""

    schema_version: Literal["aecbench.proposal-import-terminal-record.v1"] = (
        "aecbench.proposal-import-terminal-record.v1"
    )
    harbor_execution_receipt_sha256: str
    dispatch_sha256: str
    import_id: NonEmptyStr
    outcome: Literal["scored", "candidate_failure"]
    terminal_artifact: ArtifactReference
    trial_record: ArtifactReference | None = None
    authority_event_id: NonEmptyStr | None = None
    authority_event_sha256: str | None = None

    @field_validator(
        "harbor_execution_receipt_sha256",
        "dispatch_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("authority_event_sha256")
    @classmethod
    def validate_optional_hash(cls, value: str | None) -> str | None:
        return validate_sha256(value) if value is not None else None

    @model_validator(mode="after")
    def validate_terminal_outcome(self) -> Self:
        scored_fields = (
            self.trial_record,
            self.authority_event_id,
            self.authority_event_sha256,
        )
        if self.outcome == "scored":
            if any(value is None for value in scored_fields):
                raise ValueError("scored proposal import terminal requires record and authority evidence")
            if self.terminal_artifact.kind != "proposal-trial-import-receipt":
                raise ValueError("scored proposal import terminal must bind the import receipt")
        elif any(value is not None for value in scored_fields):
            raise ValueError("candidate failure terminal cannot claim scored authority evidence")
        elif self.terminal_artifact.kind != "proposal-candidate-failure":
            raise ValueError("candidate failure terminal must bind the failure record")
        return self


@dataclass(frozen=True)
class StoredProposalImportConsumptionClaim:
    """One canonical claim and its ledger-global immutable path."""

    claim: ProposalImportConsumptionClaim
    path: Path


@dataclass(frozen=True)
class StoredProposalImportTerminalRecord:
    """One canonical terminal record and its ledger-global immutable path."""

    record: ProposalImportTerminalRecord
    path: Path


def claim_proposal_import_consumption(
    *,
    ledger_root: Path,
    proposed: ProposalImportConsumptionClaim,
) -> StoredProposalImportConsumptionClaim:
    """Atomically select or replay the first import identity for one execution."""

    root = _consumption_root(
        ledger_root=ledger_root,
        execution_sha256=proposed.harbor_execution_receipt_sha256,
    )
    path = root / "claim.json"
    selected = _publish_first_model(path=path, proposed=proposed)
    if (
        selected.harbor_execution_receipt_sha256 != proposed.harbor_execution_receipt_sha256
        or selected.dispatch_sha256 != proposed.dispatch_sha256
    ):
        raise ProposalImportConsumptionError(
            "proposal import consumption claim differs from its execution identity",
        )
    return StoredProposalImportConsumptionClaim(
        claim=selected,
        path=path,
    )


def load_proposal_import_terminal(
    *,
    ledger_root: Path,
    execution_sha256: str,
) -> StoredProposalImportTerminalRecord | None:
    """Load and verify the terminal record for one exact execution, when present."""

    root = _consumption_root(
        ledger_root=ledger_root,
        execution_sha256=execution_sha256,
    )
    path = root / "terminal.json"
    if not os.path.lexists(path):
        return None
    record = _load_canonical_model(
        path=path,
        model_type=ProposalImportTerminalRecord,
        label="proposal import terminal index",
    )
    if record.harbor_execution_receipt_sha256 != execution_sha256:
        raise ProposalImportConsumptionError(
            "proposal import terminal index differs from its execution identity",
        )
    return StoredProposalImportTerminalRecord(record=record, path=path)


def persist_proposal_import_terminal(
    *,
    ledger_root: Path,
    record: ProposalImportTerminalRecord,
) -> StoredProposalImportTerminalRecord:
    """Publish exactly one terminal outcome for an already claimed execution."""

    root = _consumption_root(
        ledger_root=ledger_root,
        execution_sha256=record.harbor_execution_receipt_sha256,
    )
    claim_path = root / "claim.json"
    claim = _load_canonical_model(
        path=claim_path,
        model_type=ProposalImportConsumptionClaim,
        label="proposal import consumption claim",
    )
    if record.dispatch_sha256 != claim.dispatch_sha256 or record.import_id != claim.import_id:
        raise ProposalImportConsumptionError(
            "proposal import terminal differs from its immutable consumption claim",
        )
    path = root / "terminal.json"
    selected = _publish_first_model(path=path, proposed=record)
    if selected != record:
        raise ProposalImportConsumptionError(
            "proposal execution is already bound to a different terminal import",
        )
    return StoredProposalImportTerminalRecord(record=selected, path=path)


def _consumption_root(
    *,
    ledger_root: Path,
    execution_sha256: str,
) -> Path:
    validate_sha256(execution_sha256)
    supplied = Path(ledger_root)
    _reject_symlink_components(supplied, label="authority ledger root")
    root = supplied.resolve(strict=False)
    target = root / "proposal-import-consumption" / execution_sha256
    if not target.is_relative_to(root):
        raise ProposalImportConsumptionError(
            "proposal import consumption index escapes the authority ledger",
        )
    _reject_symlink_components(target, label="proposal import consumption index")
    return target


def _publish_first_model[ModelT: ContentAddressedModel](
    *,
    path: Path,
    proposed: ModelT,
) -> ModelT:
    model_type = type(proposed)
    encoded = _canonical_model_bytes(proposed)
    mkdir_durable(path.parent)
    _reject_symlink_components(path, label="proposal import consumption index")
    if os.path.lexists(path):
        return _load_canonical_model(
            path=path,
            model_type=model_type,
            label="proposal import consumption index",
        )
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            pass
        fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)
    return _load_canonical_model(
        path=path,
        model_type=model_type,
        label="proposal import consumption index",
    )


def _load_canonical_model[ModelT: ContentAddressedModel](
    *,
    path: Path,
    model_type: type[ModelT],
    label: str,
) -> ModelT:
    encoded = _read_regular_file(path=path, label=label)
    try:
        model = model_type.model_validate_json(encoded)
    except ValueError as error:
        raise ProposalImportConsumptionError(
            f"{label} is corrupt or has the wrong schema",
        ) from error
    if _canonical_model_bytes(model) != encoded:
        raise ProposalImportConsumptionError(
            f"{label} is not canonical",
        )
    return model


def _read_regular_file(
    *,
    path: Path,
    label: str,
) -> bytes:
    _reject_symlink_components(path, label=label)
    try:
        mode = path.stat(follow_symlinks=False).st_mode
    except OSError as error:
        raise ProposalImportConsumptionError(
            f"{label} is missing or unreadable",
        ) from error
    if not stat.S_ISREG(mode):
        raise ProposalImportConsumptionError(
            f"{label} must be a regular file",
        )
    try:
        return path.read_bytes()
    except OSError as error:
        raise ProposalImportConsumptionError(
            f"{label} is unreadable",
        ) from error


def _reject_symlink_components(
    path: Path,
    *,
    label: str,
) -> None:
    candidate = Path(path)
    for parent in (candidate, *candidate.parents):
        if os.path.lexists(parent) and parent.is_symlink():
            raise ProposalImportConsumptionError(
                f"{label} must not pass through a symbolic link",
            )


def _canonical_model_bytes(model: ContentAddressedModel) -> bytes:
    return (
        json.dumps(
            model.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
