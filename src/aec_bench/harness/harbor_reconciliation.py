# ABOUTME: Defines the canonical Harbor trial-ID transport and import reconciliation boundary.
# ABOUTME: Keeps Harbor job and trial names as observed backend identifiers while binding records to RunPlan UUIDs.

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import field_validator, model_validator

from aec_bench.contracts.resolved_run import ResolvedRunSpec
from aec_bench.contracts.run_plan import PlannedTrial, RunPlan
from aec_bench.contracts.task_snapshot import ArtifactTaskSnapshotRef, RepositoryTaskSnapshotRef
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr
from aec_bench.trials import planned_trial_binding


class HarborTrialTransport(FrozenStrictModel):
    """Map one pre-effect Harbor job name to one canonical planned trial UUID."""

    schema_version: Literal[1] = 1
    harbor_job_name: NonEmptyStr
    planned_trial_id: UUID
    harbor_trial_name: NonEmptyStr | None = None

    @field_validator("harbor_job_name")
    @classmethod
    def validate_harbor_job_name(cls, value: str) -> str:
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value) is None:
            raise ValueError("Harbor job names must be safe single path components")
        return value


class HarborImportReconciliation(FrozenStrictModel):
    """Structured membership report for one exact Harbor import."""

    schema_version: Literal[1] = 1
    expected_trial_ids: tuple[UUID, ...]
    observed_trial_ids: tuple[UUID, ...] = ()
    observed_trial_names: tuple[NonEmptyStr, ...]
    missing_trial_ids: tuple[UUID, ...] = ()
    unexpected_trial_names: tuple[NonEmptyStr, ...] = ()
    duplicate_trial_ids: tuple[UUID, ...] = ()
    duplicate_trial_names: tuple[NonEmptyStr, ...] = ()
    accepted_trial_ids: tuple[UUID, ...] = ()

    @model_validator(mode="after")
    def validate_report_sets(self) -> HarborImportReconciliation:
        if len(self.expected_trial_ids) != len(set(self.expected_trial_ids)):
            raise ValueError("expected Harbor trial IDs must be unique")
        if any(trial_id not in self.expected_trial_ids for trial_id in self.observed_trial_ids):
            raise ValueError("observed Harbor trial IDs must belong to the expected subset")
        if len(self.accepted_trial_ids) != len(set(self.accepted_trial_ids)):
            raise ValueError("accepted Harbor trial IDs must be unique")
        if any(trial_id not in self.observed_trial_ids for trial_id in self.accepted_trial_ids):
            raise ValueError("accepted Harbor trial IDs must have been observed")
        return self


class HarborImportReconciliationError(ValueError):
    """Reject an import that cannot be bound to the exact planned trial set."""

    def __init__(self, report: HarborImportReconciliation) -> None:
        self.report = report
        super().__init__(
            "Harbor import does not match the exact planned trial set: "
            f"missing={len(report.missing_trial_ids)}, "
            f"unexpected={len(report.unexpected_trial_names)}, "
            f"duplicates={len(report.duplicate_trial_names)}"
        )


def build_harbor_trial_transport(
    trials: Sequence[PlannedTrial],
    harbor_trial_names: Sequence[str | None] = (),
) -> tuple[HarborTrialTransport, ...]:
    """Create pre-effect Harbor job names for selected planned trial UUIDs.

    Harbor currently generates backend trial names. The optional names are
    accepted only when a caller already has an observed name; otherwise the
    safe job name binds the one-job transport sidecar to its planned UUID.
    """

    selected = tuple(trials)
    if not selected:
        raise ValueError("Harbor trial transport requires at least one planned trial")
    names = tuple(harbor_trial_names)
    if names and len(names) != len(selected):
        raise ValueError("Harbor trial transport names must match the selected trial count")
    if len({trial.trial_identity.id for trial in selected}) != len(selected):
        raise ValueError("Harbor trial transport planned trial IDs must be unique")
    transport = tuple(
        HarborTrialTransport(
            harbor_job_name=f"aec-planned-{trial.trial_identity.id.hex}",
            planned_trial_id=trial.trial_identity.id,
            harbor_trial_name=(names[index] if names else None),
        )
        for index, trial in enumerate(selected)
    )
    observed_names = [item.harbor_trial_name for item in transport if item.harbor_trial_name is not None]
    if len(set(observed_names)) != len(observed_names):
        raise ValueError("Harbor trial transport names must be unique")
    return transport


def read_harbor_trial_transport(path: Path) -> tuple[HarborTrialTransport, ...]:
    """Read the pre-effect job mapping written beside one Harbor config."""

    selected_path = Path(path)
    if selected_path.is_symlink() or not selected_path.is_file():
        raise ValueError("Harbor trial transport must be a regular file")
    try:
        payload = json.loads(selected_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Harbor trial transport is not valid JSON") from error
    if not isinstance(payload, list) or not payload:
        raise ValueError("Harbor trial transport must contain a non-empty JSON list")
    return tuple(HarborTrialTransport.model_validate(item) for item in payload)


def reconcile_harbor_trial_records(
    *,
    records: Sequence[TrialRecord],
    run_spec: ResolvedRunSpec,
    run_plan: RunPlan,
    transport: Sequence[HarborTrialTransport],
) -> tuple[list[TrialRecord], HarborImportReconciliation]:
    """Bind imported Harbor records to the exact planned UUID subset."""

    planned_by_id = {trial.trial_identity.id: trial for trial in run_plan.trials}
    if run_spec.run_identity != run_plan.run_identity:
        raise ValueError("Harbor import run identity does not match the resolved run plan")
    if len(planned_by_id) != len(run_plan.trials):
        raise ValueError("run plan trial IDs must be unique")
    named_transport = tuple(item for item in transport if item.harbor_trial_name is not None)
    transport_by_name = {item.harbor_trial_name: item for item in named_transport}
    transport_ids = [item.planned_trial_id for item in transport]
    job_names = [item.harbor_job_name for item in transport]
    if len(set(job_names)) != len(transport) or len(set(transport_ids)) != len(transport):
        raise ValueError("Harbor trial transport mapping must have unique job names and planned IDs")
    if len(transport_by_name) != len(named_transport):
        raise ValueError("observed Harbor trial names must be unique")
    if any(item.planned_trial_id not in planned_by_id for item in transport):
        raise ValueError("Harbor trial transport references a trial outside the run plan")

    observed_names = tuple(record.trial_id for record in records)
    counts = Counter(observed_names)
    duplicate_names = tuple(sorted(name for name, count in counts.items() if count > 1))
    if not named_transport:
        if len(transport) != 1 or len(records) != 1:
            raise HarborImportReconciliationError(
                HarborImportReconciliation(
                    expected_trial_ids=tuple(transport_ids),
                    observed_trial_names=tuple(sorted(observed_names)),
                    missing_trial_ids=tuple(transport_ids),
                    unexpected_trial_names=tuple(sorted(observed_names)),
                    duplicate_trial_names=duplicate_names,
                )
            )
        transport_by_name[records[0].trial_id] = transport[0]
    unexpected_names = tuple(sorted(name for name in counts if name not in transport_by_name))
    observed_ids = {transport_by_name[name].planned_trial_id for name in counts if name in transport_by_name}
    duplicate_ids = {transport_by_name[name].planned_trial_id for name in duplicate_names if name in transport_by_name}
    expected_ids = tuple(item.planned_trial_id for item in transport)
    missing_ids = tuple(sorted(set(expected_ids) - observed_ids, key=str))
    report = HarborImportReconciliation(
        expected_trial_ids=expected_ids,
        observed_trial_ids=tuple(trial_id for trial_id in expected_ids if trial_id in observed_ids),
        observed_trial_names=tuple(sorted(observed_names)),
        missing_trial_ids=missing_ids,
        unexpected_trial_names=unexpected_names,
        duplicate_trial_ids=tuple(trial_id for trial_id in expected_ids if trial_id in duplicate_ids),
        duplicate_trial_names=duplicate_names,
    )
    if missing_ids or unexpected_names or duplicate_names:
        raise HarborImportReconciliationError(report)

    records_by_id: dict[UUID, TrialRecord] = {}
    for record in records:
        planned = planned_by_id[transport_by_name[record.trial_id].planned_trial_id]
        _validate_imported_record(record, planned)
        canonical = _bind_record(record, planned, run_spec)
        records_by_id[planned.trial_identity.id] = canonical
    ordered = [
        records_by_id[trial.trial_identity.id] for trial in run_plan.trials if trial.trial_identity.id in records_by_id
    ]
    accepted = report.model_copy(
        update={
            "accepted_trial_ids": tuple(
                record.planned_trial_binding.trial_identity.id
                for record in ordered
                if record.planned_trial_binding is not None
            )
        }
    )
    return ordered, accepted


def _validate_imported_record(record: TrialRecord, planned: PlannedTrial) -> None:
    if record.task_id != planned.task_release.task_id:
        raise ValueError("Harbor record task ID does not match the planned trial")
    if record.input.task_kind != planned.execution_family:
        raise ValueError("Harbor record execution family does not match the planned trial")
    if record.agent.adapter != planned.agent_condition.adapter or record.agent.model != planned.agent_condition.model:
        raise ValueError("Harbor record agent condition does not match the planned trial")
    if record.environment.compute_backend != planned.compute.backend:
        raise ValueError("Harbor record compute backend does not match the planned trial")
    if isinstance(planned.task_release, ArtifactTaskSnapshotRef):
        expected_revision = planned.task_release.artifact.sha256
    elif isinstance(planned.task_release, RepositoryTaskSnapshotRef):
        expected_revision = planned.task_release.source_revision
    else:
        expected_revision = None
    if expected_revision is not None and record.input.task_revision != expected_revision:
        raise ValueError("Harbor record task release does not match the planned snapshot")
    if record.attempt != 1:
        raise ValueError("Harbor records must contain one attempt receipt")


def _bind_record(record: TrialRecord, planned: PlannedTrial, run_spec: ResolvedRunSpec) -> TrialRecord:
    binding = planned_trial_binding(planned, run_spec)
    canonical_run_id = str(run_spec.run_identity.id)
    manifest = record.run_manifest.model_copy(
        update={
            "run_id": canonical_run_id,
            "experiment_id": str(run_spec.experiment_identity.id),
        }
    )
    output = record.output
    if output is not None:
        backend_ids = dict(output.agent_result or {})
        backend_ids.setdefault("harbor_trial_name", record.trial_id)
        output = output.model_copy(update={"agent_result": backend_ids})
    canonical = record.model_copy(
        update={
            "trial_id": str(planned.trial_identity.id),
            "run_id": canonical_run_id,
            "task_id": planned.task_release.task_id,
            "planned_trial_binding": binding,
            "output": output,
        }
    )
    return canonical.bind_run_manifest(manifest)


__all__ = (
    "HarborImportReconciliation",
    "HarborImportReconciliationError",
    "HarborTrialTransport",
    "build_harbor_trial_transport",
    "read_harbor_trial_transport",
    "reconcile_harbor_trial_records",
)
