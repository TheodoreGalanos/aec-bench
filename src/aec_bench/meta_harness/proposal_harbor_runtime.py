# ABOUTME: Executes one exact authority-approved proposal Harbor job and preserves its attempt evidence.
# ABOUTME: Replays governance before effects, prevents duplicate billing, and fails closed before import.

from __future__ import annotations

import hashlib
import json
import os
import stat
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Literal, Self

import yaml
from pydantic import Field, field_validator, model_validator

from aec_bench.contracts.authority import BasisKind, TaintLabel
from aec_bench.contracts.harness_kernel import (
    ContentAddressedModel,
    FrozenStrictModel,
    canonical_content_sha256,
    validate_sha256,
)
from aec_bench.contracts.trial_record import ArtifactReference
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.harness.harbor_dispatch import (
    HarborCommandExecutor,
    execute_harbor_config,
)
from aec_bench.meta_harness.authority_ledger import AuthorityLedger, StoredBasis
from aec_bench.meta_harness.proposal_dispatch_governance import (
    GovernedProposalDispatchAuthorization,
    replay_governed_proposal_dispatch,
)
from aec_bench.meta_harness.proposal_harbor_paths import (
    paths_overlap as _paths_overlap,
)
from aec_bench.meta_harness.proposal_harbor_paths import (
    reject_symlink_components as _reject_symlink_components,
)
from aec_bench.meta_harness.proposal_harbor_paths import (
    safe_segment as _safe_segment,
)


class ProposalHarborExecutionStatus(StrEnum):
    """Terminal host observation for one authorized Harbor process attempt."""

    COMPLETED = "completed"
    FAILED = "failed"


class ProposalHarborJobFile(FrozenStrictModel):
    """One regular file observed below the exact Harbor job directory."""

    relative_path: NonEmptyStr
    sha256: str
    size_bytes: int = Field(ge=0)

    @field_validator("sha256")
    @classmethod
    def validate_digest(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("relative_path")
    @classmethod
    def validate_relative_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
            raise ValueError("Harbor job file path must remain contained and relative")
        return value


ProposalHarborFailureCode = Literal[
    "executor_exception",
    "harbor_exit_nonzero",
    "job_directory_missing",
    "job_directory_ambiguous",
    "result_evidence_missing",
    "result_evidence_ambiguous",
]


class ProposalHarborExecutionReceipt(ContentAddressedModel):
    """Immutable observation of one and only one authorized Harbor dispatch attempt."""

    schema_version: Literal["aecbench.proposal-harbor-execution-receipt.v1"] = (
        "aecbench.proposal-harbor-execution-receipt.v1"
    )
    dispatch_id: NonEmptyStr
    dispatch_sha256: str
    provider_dispatch_event_sha256: str
    harbor_job_config_sha256: str
    config_path: NonEmptyStr
    config_file_sha256: str
    command: tuple[NonEmptyStr, ...]
    started_at: datetime
    finished_at: datetime
    total_seconds: float = Field(ge=0)
    exit_code: int | None
    status: ProposalHarborExecutionStatus
    failure_code: ProposalHarborFailureCode | None
    observed_new_job_dirs: tuple[NonEmptyStr, ...] = ()
    job_dir: NonEmptyStr | None
    job_files: tuple[ProposalHarborJobFile, ...] = ()
    result_paths: tuple[NonEmptyStr, ...] = ()
    trial_record_import_permitted: bool

    @field_validator(
        "dispatch_sha256",
        "provider_dispatch_event_sha256",
        "harbor_job_config_sha256",
        "config_file_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("observed_new_job_dirs", "result_paths")
    @classmethod
    def validate_sorted_unique_strings(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("Harbor execution paths must be sorted and unique")
        return value

    @field_validator("started_at", "finished_at")
    @classmethod
    def validate_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("proposal Harbor execution timestamps must be timezone-aware")
        return value

    @field_validator("job_files")
    @classmethod
    def validate_job_file_inventory(
        cls,
        value: tuple[ProposalHarborJobFile, ...],
    ) -> tuple[ProposalHarborJobFile, ...]:
        paths = tuple(item.relative_path for item in value)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("Harbor job file inventory must be sorted and unique")
        return value

    @model_validator(mode="after")
    def validate_terminal_shape(self) -> Self:
        expected_command_prefix = ("uv", "run", "harbor", "run", "-c")
        if self.command[:5] != expected_command_prefix or len(self.command) != 6:
            raise ValueError("proposal Harbor receipt requires the closed Harbor command")
        if self.command[5] != self.config_path:
            raise ValueError("proposal Harbor command must use the exact persisted config")
        if self.finished_at < self.started_at:
            raise ValueError("proposal Harbor execution cannot finish before it starts")
        file_paths = {item.relative_path for item in self.job_files}
        if any(
            result_path not in file_paths
            or PurePosixPath(result_path).name != "result.json"
            or len(PurePosixPath(result_path).parts) != 2
            for result_path in self.result_paths
        ):
            raise ValueError(
                "proposal Harbor result paths must identify immediate trial results in the file inventory",
            )
        if self.status is ProposalHarborExecutionStatus.COMPLETED:
            if (
                self.exit_code != 0
                or self.failure_code is not None
                or len(self.observed_new_job_dirs) != 1
                or self.job_dir != self.observed_new_job_dirs[0]
                or len(self.result_paths) != 1
                or not self.job_files
                or not self.trial_record_import_permitted
            ):
                raise ValueError(
                    "completed proposal Harbor execution requires one job, one result, "
                    "zero exit, complete file evidence, and import permission",
                )
        elif self.trial_record_import_permitted or self.failure_code is None:
            raise ValueError(
                "failed proposal Harbor execution requires a failure code and forbids import",
            )
        return self


@dataclass(frozen=True)
class ProposalHarborExecution:
    """Physical receipt handle returned by an executed or safely replayed dispatch."""

    receipt: ProposalHarborExecutionReceipt
    receipt_path: Path
    receipt_artifact: ArtifactReference
    replayed: bool


class ProposalProviderOperationCoordinate(ContentAddressedModel):
    """Ledger-global identity of one exact authority-approved provider operation."""

    schema_version: Literal["aecbench.proposal-provider-operation-coordinate.v1"] = (
        "aecbench.proposal-provider-operation-coordinate.v1"
    )
    dispatch_id: NonEmptyStr
    dispatch_sha256: str
    provider_dispatch_event_id: NonEmptyStr
    provider_dispatch_event_sha256: str

    @field_validator(
        "dispatch_sha256",
        "provider_dispatch_event_sha256",
    )
    @classmethod
    def validate_coordinate_hashes(cls, value: str) -> str:
        return validate_sha256(value)


class ProposalProviderOperationStart(ContentAddressedModel):
    """Durable consumed-operation evidence published before provider execution."""

    schema_version: Literal["aecbench.proposal-provider-operation-start.v1"] = (
        "aecbench.proposal-provider-operation-start.v1"
    )
    coordinate: ProposalProviderOperationCoordinate
    project_root: NonEmptyStr
    jobs_root: NonEmptyStr
    artifacts_root: NonEmptyStr
    execution_root: NonEmptyStr
    config_path: NonEmptyStr
    receipt_path: NonEmptyStr
    config_file_sha256: str
    command: tuple[NonEmptyStr, ...]
    started_at: datetime

    @field_validator("config_file_sha256")
    @classmethod
    def validate_config_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("started_at")
    @classmethod
    def validate_start_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("proposal provider operation start must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_paths_and_command(self) -> Self:
        paths = tuple(
            Path(value)
            for value in (
                self.project_root,
                self.jobs_root,
                self.artifacts_root,
                self.execution_root,
                self.config_path,
                self.receipt_path,
            )
        )
        if any(not path.is_absolute() for path in paths):
            raise ValueError("proposal provider operation paths must be absolute")
        project_root, jobs_root, artifacts_root, execution_root, config_path, receipt_path = paths
        del project_root, jobs_root
        if (
            execution_root.parent.parent != artifacts_root
            or execution_root.name != _safe_segment(self.coordinate.dispatch_id)
            or execution_root.parent.name != "proposal-harbor-executions"
            or config_path != execution_root / "harbor.yaml"
            or receipt_path != execution_root / "proposal-harbor-execution.json"
        ):
            raise ValueError("proposal provider operation paths are not canonically related")
        if (
            self.command[:5] != ("uv", "run", "harbor", "run", "-c")
            or len(self.command) != 6
            or self.command[5] != self.config_path
        ):
            raise ValueError("proposal provider operation start requires the closed Harbor command")
        return self


class ProposalProviderOperationTerminal(ContentAddressedModel):
    """Ledger-global terminal pointer for a completed or failed provider attempt."""

    schema_version: Literal["aecbench.proposal-provider-operation-terminal.v1"] = (
        "aecbench.proposal-provider-operation-terminal.v1"
    )
    coordinate: ProposalProviderOperationCoordinate
    start_sha256: str
    receipt_path: NonEmptyStr
    receipt_file_sha256: str
    receipt_content_sha256: str
    status: ProposalHarborExecutionStatus
    finished_at: datetime

    @field_validator(
        "start_sha256",
        "receipt_file_sha256",
        "receipt_content_sha256",
    )
    @classmethod
    def validate_terminal_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("finished_at")
    @classmethod
    def validate_terminal_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("proposal provider operation terminal must be timezone-aware")
        return value

    @field_validator("receipt_path")
    @classmethod
    def validate_terminal_receipt_path(cls, value: str) -> str:
        if not Path(value).is_absolute():
            raise ValueError("proposal provider operation receipt path must be absolute")
        return value


@dataclass(frozen=True)
class _ProposalProviderOperationState:
    coordinate: ProposalProviderOperationCoordinate
    start: ProposalProviderOperationStart | None
    start_basis: StoredBasis | None
    terminal: ProposalProviderOperationTerminal | None


def run_governed_proposal_harbor(
    *,
    ledger: AuthorityLedger,
    authorization: GovernedProposalDispatchAuthorization,
    project_root: Path,
    jobs_root: Path,
    artifacts_root: Path,
    executor: HarborCommandExecutor | None = None,
) -> ProposalHarborExecution:
    """Execute one canonical authorized job, or replay its immutable prior attempt."""

    replayed_authorization = replay_governed_proposal_dispatch(
        ledger=ledger,
        authorization=authorization,
    )
    project = _required_directory(Path(project_root), label="project root")
    dispatch_id = replayed_authorization.dispatch.dispatch_id
    dispatch_segment = _safe_segment(dispatch_id)
    jobs = _authorized_jobs_root(
        project_root=project,
        jobs_root=Path(jobs_root),
        authorization=replayed_authorization,
    )
    operation_state = _load_provider_operation_state(
        ledger=ledger,
        authorization=replayed_authorization,
    )
    if operation_state.start is not None:
        _validate_operation_start_context(
            start=operation_state.start,
            project_root=project,
            jobs_root=jobs,
        )
        if operation_state.terminal is not None:
            return _replay_terminal_operation(
                ledger=ledger,
                authorization=replayed_authorization,
                state=operation_state,
            )
        recorded_receipt_path = Path(operation_state.start.receipt_path)
        if recorded_receipt_path.exists():
            receipt = load_proposal_harbor_execution(
                receipt_path=recorded_receipt_path,
                ledger=ledger,
                authorization=replayed_authorization,
            )
            _persist_provider_operation_terminal(
                ledger=ledger,
                authorization=replayed_authorization,
                state=operation_state,
                receipt=receipt,
                receipt_path=recorded_receipt_path,
            )
            return _execution_result(
                receipt=receipt,
                receipt_path=recorded_receipt_path,
                replayed=True,
            )
        raise ValueError(
            "proposal Harbor dispatch has incomplete prior attempt evidence; automatic redispatch is forbidden",
        )

    artifact_root = _prepare_artifact_root(
        Path(artifacts_root),
        forbidden_roots=(
            Path(replayed_authorization.dispatch.derived_task_path),
            Path(replayed_authorization.dispatch.host_config.source_task_dir),
            jobs,
        ),
    )
    execution_root = artifact_root / "proposal-harbor-executions" / dispatch_segment
    receipt_path = execution_root / "proposal-harbor-execution.json"
    config_path = execution_root / "harbor.yaml"
    if receipt_path.exists() or config_path.exists() or execution_root.exists():
        raise ValueError(
            "proposal Harbor dispatch has unregistered prior attempt evidence; automatic redispatch is forbidden",
        )

    config = json.loads(replayed_authorization.dispatch.harbor_job_config_json)
    if not isinstance(config, dict):
        raise ValueError("authorized proposal Harbor job must decode to an object")
    config_bytes = yaml.safe_dump(config, sort_keys=False).encode("utf-8")
    if yaml.safe_load(config_bytes) != config:
        raise ValueError("persisted proposal Harbor YAML does not preserve the authorized job")
    command = (
        "uv",
        "run",
        "harbor",
        "run",
        "-c",
        str(config_path.resolve()),
    )
    started_at = datetime.now(UTC)
    started_monotonic = time.monotonic()
    start = ProposalProviderOperationStart(
        coordinate=operation_state.coordinate,
        project_root=str(project),
        jobs_root=str(jobs),
        artifacts_root=str(artifact_root),
        execution_root=str(execution_root),
        config_path=str(config_path),
        receipt_path=str(receipt_path),
        config_file_sha256=hashlib.sha256(config_bytes).hexdigest(),
        command=command,
        started_at=started_at,
    )
    start_basis = _persist_provider_operation_start(
        ledger=ledger,
        authorization=replayed_authorization,
        start=start,
    )
    operation_state = _ProposalProviderOperationState(
        coordinate=operation_state.coordinate,
        start=start,
        start_basis=start_basis,
        terminal=None,
    )

    execution_root.mkdir(parents=True)
    _write_new_file(config_path, config_bytes)
    before = _job_directories(jobs)
    exit_code: int | None
    executor_failed = False
    try:
        observed_command, exit_code = execute_harbor_config(
            config_path=config_path,
            project_root=project,
            executor=executor,
        )
        if tuple(observed_command) != command:
            raise RuntimeError("Harbor dispatcher changed the authorized proposal command")
    except Exception:
        exit_code = None
        executor_failed = True

    after = _job_directories(jobs)
    new_jobs = tuple(sorted(after - before, key=str))
    observed_job_dirs = tuple(str(path) for path in new_jobs)
    job_dir = new_jobs[0] if len(new_jobs) == 1 else None
    job_files = _job_file_inventory(job_dir) if job_dir is not None else ()
    result_paths = (
        tuple(
            item.relative_path
            for item in job_files
            if (
                PurePosixPath(item.relative_path).name == "result.json"
                and len(PurePosixPath(item.relative_path).parts) == 2
            )
        )
        if job_dir is not None
        else ()
    )
    finished_at = datetime.now(UTC)
    total_seconds = time.monotonic() - started_monotonic
    failure_code = _failure_code(
        executor_failed=executor_failed,
        exit_code=exit_code,
        new_job_count=len(new_jobs),
        result_count=len(result_paths),
    )
    status = ProposalHarborExecutionStatus.COMPLETED if failure_code is None else ProposalHarborExecutionStatus.FAILED
    receipt = ProposalHarborExecutionReceipt(
        dispatch_id=dispatch_id,
        dispatch_sha256=replayed_authorization.dispatch.content_sha256,
        provider_dispatch_event_sha256=(replayed_authorization.provider_dispatch_event.content_sha256),
        harbor_job_config_sha256=(replayed_authorization.dispatch.harbor_job_config_sha256),
        config_path=str(config_path.resolve()),
        config_file_sha256=hashlib.sha256(config_bytes).hexdigest(),
        command=command,
        started_at=started_at,
        finished_at=finished_at,
        total_seconds=total_seconds,
        exit_code=exit_code,
        status=status,
        failure_code=failure_code,
        observed_new_job_dirs=observed_job_dirs,
        job_dir=None if job_dir is None else str(job_dir),
        job_files=job_files,
        result_paths=result_paths,
        trial_record_import_permitted=(status is ProposalHarborExecutionStatus.COMPLETED),
    )
    _write_new_file(receipt_path, _canonical_model_bytes(receipt))
    loaded = load_proposal_harbor_execution(
        receipt_path=receipt_path,
        ledger=ledger,
        authorization=replayed_authorization,
    )
    _persist_provider_operation_terminal(
        ledger=ledger,
        authorization=replayed_authorization,
        state=operation_state,
        receipt=loaded,
        receipt_path=receipt_path,
    )
    return _execution_result(
        receipt=loaded,
        receipt_path=receipt_path,
        replayed=False,
    )


def _load_provider_operation_state(
    *,
    ledger: AuthorityLedger,
    authorization: GovernedProposalDispatchAuthorization,
) -> _ProposalProviderOperationState:
    coordinate = _provider_operation_coordinate(authorization)
    start_basis = ledger.basis_for_id(
        kind=BasisKind.EVIDENCE,
        artifact_id=_provider_operation_start_id(coordinate),
    )
    terminal_basis = ledger.basis_for_id(
        kind=BasisKind.EVIDENCE,
        artifact_id=_provider_operation_terminal_id(coordinate),
    )
    if start_basis is None:
        if terminal_basis is not None:
            raise ValueError(
                "proposal provider operation terminal exists without consumed start evidence",
            )
        return _ProposalProviderOperationState(
            coordinate=coordinate,
            start=None,
            start_basis=None,
            terminal=None,
        )

    start = _load_ledger_model(
        basis=start_basis,
        model_type=ProposalProviderOperationStart,
        label="proposal provider operation start",
    )
    if start.coordinate != coordinate or start_basis.origin.parent_origin_sha256s != (
        authorization.dispatch_origin.content_sha256,
    ):
        raise ValueError(
            "proposal provider operation start differs from its exact dispatch authority",
        )
    terminal: ProposalProviderOperationTerminal | None = None
    if terminal_basis is not None:
        terminal = _load_ledger_model(
            basis=terminal_basis,
            model_type=ProposalProviderOperationTerminal,
            label="proposal provider operation terminal",
        )
        if (
            terminal.coordinate != coordinate
            or terminal.start_sha256 != start.content_sha256
            or terminal.receipt_path != start.receipt_path
            or terminal_basis.origin.parent_origin_sha256s != (start_basis.origin.content_sha256,)
        ):
            raise ValueError(
                "proposal provider operation terminal differs from its consumed start",
            )
    return _ProposalProviderOperationState(
        coordinate=coordinate,
        start=start,
        start_basis=start_basis,
        terminal=terminal,
    )


def _persist_provider_operation_start(
    *,
    ledger: AuthorityLedger,
    authorization: GovernedProposalDispatchAuthorization,
    start: ProposalProviderOperationStart,
) -> StoredBasis:
    return ledger.observe_model_basis(
        kind=BasisKind.EVIDENCE,
        artifact_id=_provider_operation_start_id(start.coordinate),
        model=start,
        producer=authorization.provider_dispatch_event.principal,
        producer_process_id="aecbench.proposal-harbor-runtime",
        observed_by=authorization.provider_dispatch_event.principal,
        channel="proposal-provider-operation",
        operation_id="proposal-provider-operation.consume",
        invocation_id=start.coordinate.content_sha256,
        parent_origin_sha256s=(authorization.dispatch_origin.content_sha256,),
        operation_taint=(TaintLabel.RUNTIME_OBSERVED,),
    )


def _persist_provider_operation_terminal(
    *,
    ledger: AuthorityLedger,
    authorization: GovernedProposalDispatchAuthorization,
    state: _ProposalProviderOperationState,
    receipt: ProposalHarborExecutionReceipt,
    receipt_path: Path,
) -> StoredBasis:
    if state.start is None or state.start_basis is None:
        raise ValueError(
            "proposal provider operation cannot terminate without consumed start evidence",
        )
    resolved_receipt_path = _required_regular_file(
        receipt_path,
        label="proposal Harbor execution receipt",
    )
    if str(resolved_receipt_path) != state.start.receipt_path:
        raise ValueError(
            "proposal provider operation receipt differs from its consumed start",
        )
    _validate_receipt_against_start(
        receipt=receipt,
        start=state.start,
    )
    encoded = resolved_receipt_path.read_bytes()
    terminal = ProposalProviderOperationTerminal(
        coordinate=state.coordinate,
        start_sha256=state.start.content_sha256,
        receipt_path=str(resolved_receipt_path),
        receipt_file_sha256=hashlib.sha256(encoded).hexdigest(),
        receipt_content_sha256=receipt.content_sha256,
        status=receipt.status,
        finished_at=receipt.finished_at,
    )
    return ledger.observe_model_basis(
        kind=BasisKind.EVIDENCE,
        artifact_id=_provider_operation_terminal_id(state.coordinate),
        model=terminal,
        producer=authorization.provider_dispatch_event.principal,
        producer_process_id="aecbench.proposal-harbor-runtime",
        observed_by=authorization.provider_dispatch_event.principal,
        channel="proposal-provider-operation",
        operation_id="proposal-provider-operation.terminate",
        invocation_id=state.coordinate.content_sha256,
        parent_origin_sha256s=(state.start_basis.origin.content_sha256,),
        operation_taint=(TaintLabel.RUNTIME_OBSERVED,),
    )


def _replay_terminal_operation(
    *,
    ledger: AuthorityLedger,
    authorization: GovernedProposalDispatchAuthorization,
    state: _ProposalProviderOperationState,
) -> ProposalHarborExecution:
    if state.start is None or state.terminal is None:
        raise ValueError("proposal provider operation has no terminal evidence to replay")
    receipt_path = Path(state.terminal.receipt_path)
    receipt = load_proposal_harbor_execution(
        receipt_path=receipt_path,
        ledger=ledger,
        authorization=authorization,
    )
    _validate_receipt_against_start(
        receipt=receipt,
        start=state.start,
    )
    encoded = receipt_path.read_bytes()
    if (
        hashlib.sha256(encoded).hexdigest() != state.terminal.receipt_file_sha256
        or receipt.content_sha256 != state.terminal.receipt_content_sha256
        or receipt.status is not state.terminal.status
    ):
        raise ValueError(
            "proposal Harbor receipt differs from its ledger-global terminal evidence",
        )
    return _execution_result(
        receipt=receipt,
        receipt_path=receipt_path,
        replayed=True,
    )


def _validate_receipt_against_start(
    *,
    receipt: ProposalHarborExecutionReceipt,
    start: ProposalProviderOperationStart,
) -> None:
    if (
        receipt.dispatch_id != start.coordinate.dispatch_id
        or receipt.dispatch_sha256 != start.coordinate.dispatch_sha256
        or receipt.provider_dispatch_event_sha256 != start.coordinate.provider_dispatch_event_sha256
        or receipt.config_path != start.config_path
        or receipt.config_file_sha256 != start.config_file_sha256
        or receipt.command != start.command
        or receipt.started_at != start.started_at
    ):
        raise ValueError(
            "proposal Harbor receipt differs from its ledger-global consumed start",
        )


def _validate_operation_start_context(
    *,
    start: ProposalProviderOperationStart,
    project_root: Path,
    jobs_root: Path,
) -> None:
    if start.project_root != str(project_root) or start.jobs_root != str(jobs_root):
        raise ValueError(
            "proposal provider operation runtime roots differ from its consumed start",
        )


def _provider_operation_coordinate(
    authorization: GovernedProposalDispatchAuthorization,
) -> ProposalProviderOperationCoordinate:
    return ProposalProviderOperationCoordinate(
        dispatch_id=authorization.dispatch.dispatch_id,
        dispatch_sha256=authorization.dispatch.content_sha256,
        provider_dispatch_event_id=authorization.provider_dispatch_event.event_id,
        provider_dispatch_event_sha256=(authorization.provider_dispatch_event.content_sha256),
    )


def _provider_operation_start_id(
    coordinate: ProposalProviderOperationCoordinate,
) -> str:
    return f"proposal-provider-operation.{coordinate.content_sha256}.start"


def _provider_operation_terminal_id(
    coordinate: ProposalProviderOperationCoordinate,
) -> str:
    return f"proposal-provider-operation.{coordinate.content_sha256}.terminal"


def _load_ledger_model[ModelT: ContentAddressedModel](
    *,
    basis: StoredBasis,
    model_type: type[ModelT],
    label: str,
) -> ModelT:
    encoded = basis.content_path.read_bytes()
    try:
        model = model_type.model_validate_json(encoded)
    except ValueError as error:
        raise ValueError(f"{label} has the wrong typed schema: {error}") from error
    if _ledger_model_bytes(model) != encoded:
        raise ValueError(f"{label} is not canonically serialized")
    return model


def load_proposal_harbor_execution(
    *,
    receipt_path: Path,
    ledger: AuthorityLedger,
    authorization: GovernedProposalDispatchAuthorization,
) -> ProposalHarborExecutionReceipt:
    """Replay governance and verify every persisted dispatch-attempt byte."""

    replayed_authorization = replay_governed_proposal_dispatch(
        ledger=ledger,
        authorization=authorization,
    )
    path = _required_regular_file(
        Path(receipt_path),
        label="proposal Harbor execution receipt",
    )
    try:
        receipt = ProposalHarborExecutionReceipt.model_validate_json(
            path.read_bytes(),
        )
    except ValueError as error:
        raise ValueError(f"proposal Harbor execution receipt is invalid: {error}") from error
    if (
        receipt.dispatch_id != replayed_authorization.dispatch.dispatch_id
        or receipt.dispatch_sha256 != replayed_authorization.dispatch.content_sha256
        or receipt.provider_dispatch_event_sha256 != replayed_authorization.provider_dispatch_event.content_sha256
        or receipt.harbor_job_config_sha256 != replayed_authorization.dispatch.harbor_job_config_sha256
    ):
        raise ValueError(
            "proposal Harbor execution receipt differs from its exact dispatch authority",
        )
    config_path = _required_regular_file(
        Path(receipt.config_path),
        label="proposal Harbor config",
    )
    config_bytes = config_path.read_bytes()
    if hashlib.sha256(config_bytes).hexdigest() != receipt.config_file_sha256:
        raise ValueError("proposal Harbor config bytes changed after execution")
    config = yaml.safe_load(config_bytes)
    if (
        not isinstance(config, dict)
        or canonical_content_sha256(config) != receipt.harbor_job_config_sha256
        or config
        != json.loads(
            replayed_authorization.dispatch.harbor_job_config_json,
        )
    ):
        raise ValueError("proposal Harbor config differs from its authorized canonical job")
    if receipt.job_dir is not None:
        job_dir = _required_directory(
            Path(receipt.job_dir),
            label="proposal Harbor job directory",
        )
        if _job_file_inventory(job_dir) != receipt.job_files:
            raise ValueError("proposal Harbor job files changed after execution")
    elif receipt.job_files or receipt.result_paths:
        raise ValueError("proposal Harbor receipt without a job cannot claim job evidence")
    return receipt


def _execution_result(
    *,
    receipt: ProposalHarborExecutionReceipt,
    receipt_path: Path,
    replayed: bool,
) -> ProposalHarborExecution:
    encoded = receipt_path.read_bytes()
    return ProposalHarborExecution(
        receipt=receipt,
        receipt_path=receipt_path.resolve(),
        receipt_artifact=ArtifactReference(
            kind="proposal_harbor_execution_receipt",
            path=str(receipt_path.resolve()),
            sha256=hashlib.sha256(encoded).hexdigest(),
            media_type="application/json",
        ),
        replayed=replayed,
    )


def _authorized_jobs_root(
    *,
    project_root: Path,
    jobs_root: Path,
    authorization: GovernedProposalDispatchAuthorization,
) -> Path:
    config = json.loads(authorization.dispatch.harbor_job_config_json)
    configured = config.get("jobs_dir") if isinstance(config, dict) else None
    if not isinstance(configured, str) or not configured.strip():
        raise ValueError("authorized proposal Harbor job has no jobs root")
    configured_path = Path(configured)
    expected = (
        configured_path.resolve() if configured_path.is_absolute() else (project_root / configured_path).resolve()
    )
    observed = jobs_root.resolve()
    if observed != expected:
        raise ValueError("proposal Harbor jobs root differs from the authorized job config")
    _reject_symlink_components(jobs_root, label="proposal Harbor jobs root")
    observed.mkdir(parents=True, exist_ok=True)
    return observed


def _prepare_artifact_root(
    path: Path,
    *,
    forbidden_roots: tuple[Path, ...],
) -> Path:
    _reject_symlink_components(path, label="proposal Harbor artifacts root")
    resolved = path.resolve()
    if any(_paths_overlap(resolved, forbidden.resolve()) for forbidden in forbidden_roots):
        raise ValueError(
            "proposal Harbor artifacts root must remain outside task and job evidence roots",
        )
    path.mkdir(parents=True, exist_ok=True)
    return resolved


def _job_directories(jobs_root: Path) -> set[Path]:
    return {child.resolve() for child in jobs_root.iterdir() if child.is_dir() and not child.is_symlink()}


def _job_file_inventory(
    job_dir: Path,
) -> tuple[ProposalHarborJobFile, ...]:
    root = _required_directory(job_dir, label="proposal Harbor job directory")
    inventory: list[ProposalHarborJobFile] = []
    for path in sorted(root.rglob("*")):
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise ValueError("proposal Harbor job evidence cannot traverse symlinks")
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise ValueError("proposal Harbor job evidence must contain only regular files")
        encoded = path.read_bytes()
        inventory.append(
            ProposalHarborJobFile(
                relative_path=path.relative_to(root).as_posix(),
                sha256=hashlib.sha256(encoded).hexdigest(),
                size_bytes=len(encoded),
            )
        )
    return tuple(inventory)


def _failure_code(
    *,
    executor_failed: bool,
    exit_code: int | None,
    new_job_count: int,
    result_count: int,
) -> ProposalHarborFailureCode | None:
    if executor_failed:
        return "executor_exception"
    if exit_code != 0:
        return "harbor_exit_nonzero"
    if new_job_count == 0:
        return "job_directory_missing"
    if new_job_count != 1:
        return "job_directory_ambiguous"
    if result_count == 0:
        return "result_evidence_missing"
    if result_count != 1:
        return "result_evidence_ambiguous"
    return None


def _required_directory(path: Path, *, label: str) -> Path:
    _reject_symlink_components(path, label=label)
    if not path.is_dir() or path.is_symlink():
        raise ValueError(f"{label} must be an existing non-symlink directory")
    return path.resolve()


def _required_regular_file(path: Path, *, label: str) -> Path:
    _reject_symlink_components(path, label=label)
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"{label} must be an existing regular non-symlink file")
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError(f"{label} must be a regular file")
    return path.resolve()


def _write_new_file(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)
    directory_descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_descriptor)
    finally:
        os.close(directory_descriptor)


def _canonical_model_bytes(model: ContentAddressedModel) -> bytes:
    return (
        json.dumps(
            model.model_dump(mode="json"),
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _ledger_model_bytes(model: ContentAddressedModel) -> bytes:
    return (
        json.dumps(
            model.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
