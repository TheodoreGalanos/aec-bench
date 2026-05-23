# ABOUTME: Read and query helpers for append-only TrialRecord storage in the Python ledger.
# ABOUTME: Provides deterministic discovery and basic filtering over persisted trial records.

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from aec_bench.contracts.trial_record import TrialRecord


@dataclass(frozen=True)
class _LedgerCache:
    """In-memory snapshot of unscoped ledger reads, keyed by latest mtime."""

    snapshot_mtime: float
    records: list[TrialRecord]


_cache: _LedgerCache | None = None


def _read_trial_record(path: Path) -> TrialRecord:
    return TrialRecord.model_validate_json(path.read_text(encoding="utf-8"))


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


def _latest_mtime(paths: list[Path]) -> float:
    """Cheapest cache key: the newest mtime across trial JSON files."""
    if not paths:
        return 0.0
    return max(p.stat().st_mtime for p in paths)


def read_trial_records(
    ledger_root: Path,
    *,
    experiment_id: str | None = None,
) -> list[TrialRecord]:
    # Scoped reads bypass the cache — they're rare and already cheap.
    if experiment_id is not None:
        return [_read_trial_record(p) for p in _iter_trial_record_paths(ledger_root, experiment_id=experiment_id)]

    global _cache
    paths = _iter_trial_record_paths(ledger_root)
    latest = _latest_mtime(paths)
    if _cache is not None and _cache.snapshot_mtime == latest:
        return list(_cache.records)

    records = [_read_trial_record(p) for p in paths]
    _cache = _LedgerCache(snapshot_mtime=latest, records=records)
    return list(_cache.records)


def _reset_cache_for_testing() -> None:
    """Clear the module-level cache. Tests should call this between cases."""
    global _cache
    _cache = None


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
