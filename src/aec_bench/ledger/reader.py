# ABOUTME: Reads current trials through their shared run manifests.
# ABOUTME: Verifies every retained ArtifactRef before returning a resolved trial to callers.

import json
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel

from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.trial_extensions import VerifierExecutionReceipt
from aec_bench.contracts.trial_record import (
    AdaptationProvenance,
    LifecycleExecutionRecord,
    LifecycleTrialProvenance,
    MetaHarnessTrialProvenance,
    RunManifest,
    TrialRecord,
)
from aec_bench.ledger.artifact_repository import ArtifactRepository
from aec_bench.ledger.writer import run_manifest_path


def read_trial_record(path: Path, *, ledger_root: Path | None = None) -> TrialRecord:
    selected_ledger_root = path.parent.parent if ledger_root is None else ledger_root
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("trial record must contain a JSON object")
    if payload.get("schema_version") != 2:
        raise ValueError(f"unsupported TrialRecord schema_version: {payload.get('schema_version')!r}")
    record = TrialRecord.model_validate(payload)
    experiment_id = path.parent.name
    standard_manifest_path = run_manifest_path(
        ledger_root=selected_ledger_root,
        experiment_id=experiment_id,
        run_id=record.run_id,
    )
    portable_manifest_path = path.parent / "_runs" / standard_manifest_path.name
    manifest_path = next(
        (candidate for candidate in (standard_manifest_path, portable_manifest_path) if candidate.is_file()),
        standard_manifest_path,
    )
    manifest = RunManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    repository = _artifact_repository(record, selected_ledger_root, path)
    if repository is not None:
        _hydrate_extensions(record, repository)
        artifact_root = repository.root
    else:
        artifact_root = selected_ledger_root / "_artifacts"
    return record.bind_run_manifest(manifest).bind_artifact_root(artifact_root)


def _read_trial_record(path: Path, *, ledger_root: Path | None = None) -> TrialRecord:
    return read_trial_record(path, ledger_root=ledger_root)


def _verify_references(record: TrialRecord, repository: ArtifactRepository) -> None:
    for reference in _references(record):
        repository.read_bytes(reference)


def _references(record: TrialRecord) -> tuple[ArtifactRef, ...]:
    references = [
        *(item.artifact for item in record.extension_refs),
        *(item.artifact for item in record.authority_evidence),
        *(file.artifact for file in record.input.input_files or ()),
        *((item.artifact for item in record.output.artifacts) if record.output is not None else ()),
    ]
    if record.provider_evidence is not None:
        references.append(record.provider_evidence)
    return tuple(references)


def _artifact_repository(
    record: TrialRecord,
    ledger_root: Path,
    record_path: Path,
) -> ArtifactRepository | None:
    references = _references(record)
    if not references:
        return None
    roots = (ledger_root / "_artifacts", record_path.parent / "_artifacts")
    first_error: Exception | None = None
    for root in dict.fromkeys(roots):
        if not root.is_dir():
            continue
        repository = ArtifactRepository(root)
        try:
            _verify_references(record, repository)
        except (OSError, RuntimeError, ValueError) as error:
            first_error = first_error or error
            continue
        return repository
    if first_error is not None:
        raise first_error
    raise FileNotFoundError("trial artifact repository is unavailable")


def _hydrate_extensions(record: TrialRecord, repository: ArtifactRepository) -> None:
    known: dict[str, type[BaseModel]] = {
        "adaptation": AdaptationProvenance,
        "lifecycle_execution": LifecycleExecutionRecord,
        "lifecycle_provenance": LifecycleTrialProvenance,
        "meta_harness_provenance": MetaHarnessTrialProvenance,
        "verifier_execution": VerifierExecutionReceipt,
    }
    for extension in record.extension_refs:
        model_type = known.get(extension.extension_kind)
        if model_type is None:
            continue
        value = model_type.model_validate_json(repository.read_bytes(extension.artifact))
        record.attach_extension(extension.extension_kind, value)


def _iter_trial_record_paths(
    ledger_root: Path,
    *,
    experiment_id: str | None = None,
) -> list[Path]:
    if experiment_id is not None:
        scoped_root = ledger_root / experiment_id
    else:
        scoped_root = ledger_root
    if not scoped_root.exists():
        return []
    # Skip directories prefixed with _ (e.g., _evaluations/) to avoid
    # picking up non-trial artifacts stored alongside trial records.
    return sorted(
        p
        for p in scoped_root.rglob("*.json")
        if not any(part.startswith("_") for part in p.relative_to(scoped_root).parts)
    )


def read_trial_records(
    ledger_root: Path,
    *,
    experiment_id: str | None = None,
) -> list[TrialRecord]:
    return [
        _read_trial_record(p, ledger_root=ledger_root)
        for p in _iter_trial_record_paths(ledger_root, experiment_id=experiment_id)
    ]


def query_trial_records(
    ledger_root: Path,
    *,
    experiment_id: str | None = None,
    dataset_id: str | None = None,
    task_ids: Sequence[str] | None = None,
    task_prefix: str | None = None,
    adapter: str | None = None,
    model: str | None = None,
) -> list[TrialRecord]:
    records = read_trial_records(ledger_root, experiment_id=experiment_id)
    if dataset_id is not None:
        records = [record for record in records if record.dataset_id == dataset_id]
    if task_ids is not None:
        task_id_set = set(task_ids)
        records = [record for record in records if record.task.task_id in task_id_set]
    if task_prefix is not None:
        records = [record for record in records if record.task.task_id.startswith(task_prefix)]
    if adapter is not None:
        records = [record for record in records if record.agent.adapter == adapter]
    if model is not None:
        records = [record for record in records if record.agent.model == model]
    return records
