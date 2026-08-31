# ABOUTME: Provides provider-neutral metadata filters and stable cursor pagination over EvidenceIndex.
# ABOUTME: Keeps routine query pages independent from portable evidence body hydration.

from __future__ import annotations

import base64
import binascii
import json
from typing import NamedTuple

from aec_bench.ledger.index import EvidenceIndex, EvidenceIndexError, EvidenceIndexRow

_MAX_PAGE_SIZE = 1000
_CURSOR_VERSION = 1


class EvidenceQueryError(ValueError):
    """Reject an invalid, stale, or mismatched evidence query cursor."""


class EvidenceQueryPage(NamedTuple):
    """One bounded query page and the opaque cursor for its successor."""

    rows: tuple[EvidenceIndexRow, ...]
    next_cursor: str | None


class EvidenceQuery:
    """Run bounded metadata-only queries against one disposable EvidenceIndex."""

    def __init__(self, index: EvidenceIndex) -> None:
        self.index = index

    def page(
        self,
        *,
        page_size: int = 100,
        after_cursor: str | None = None,
        run_id: str | None = None,
        experiment_id: str | None = None,
        task_id: str | None = None,
        task_revision: str | None = None,
        task_prefix: str | None = None,
        task_kind: str | None = None,
        dataset_id: str | None = None,
        adapter: str | None = None,
        model: str | None = None,
        world_profile_id: str | None = None,
        execution_status: str | None = None,
        evaluation_status: str | None = None,
        evidence_status: str | None = None,
        provider_evidence_missing: bool | None = None,
        trial_id: str | None = None,
        attempt: int | None = None,
    ) -> EvidenceQueryPage:
        if not 1 <= page_size <= _MAX_PAGE_SIZE:
            raise EvidenceQueryError(f"page_size must be between 1 and {_MAX_PAGE_SIZE}")
        filters = {
            "run_id": run_id,
            "experiment_id": experiment_id,
            "task_id": task_id,
            "task_revision": task_revision,
            "task_prefix": task_prefix,
            "task_kind": task_kind,
            "dataset_id": dataset_id,
            "adapter": adapter,
            "model": model,
            "world_profile_id": world_profile_id,
            "execution_status": _value(execution_status),
            "evaluation_status": _value(evaluation_status),
            "evidence_status": _value(evidence_status),
            "provider_evidence_missing": provider_evidence_missing,
            "trial_id": trial_id,
            "attempt": attempt,
        }
        clauses = ["1 = 1"]
        parameters: list[object] = []
        columns = (
            "run_id",
            "experiment_id",
            "task_id",
            "task_revision",
            "task_kind",
            "dataset_id",
            "adapter",
            "model",
            "world_profile_id",
            "execution_status",
            "evaluation_status",
            "evidence_status",
            "trial_id",
            "attempt",
        )
        for column in columns:
            value = filters[column]
            if value is not None:
                clauses.append(f"{column} = ?")
                parameters.append(value)
        if task_prefix is not None:
            clauses.append("task_id LIKE ? ESCAPE '\\'")
            parameters.append(_like_prefix(task_prefix))
        if provider_evidence_missing is not None:
            clauses.append("provider_evidence_present = ?")
            parameters.append(int(provider_evidence_missing is False))

        generation = self.index.generation
        if after_cursor is not None:
            position = _decode_cursor(after_cursor, generation, filters)
            clauses.append("(started_at > ? OR (started_at = ? AND trial_id > ?))")
            parameters.extend(position)
        try:
            rows = self.index._select_rows(
                " AND ".join(clauses),
                tuple(parameters),
                page_size + 1,
                generation,
            )
        except EvidenceIndexError as error:
            raise EvidenceQueryError("evidence index changed while the query was starting") from error
        visible = rows[:page_size]
        next_cursor = None
        if len(rows) > page_size:
            last = visible[-1]
            next_cursor = _encode_cursor(generation, filters, last)
        return EvidenceQueryPage(visible, next_cursor)

    query = page


def _value(value: object) -> object:
    return getattr(value, "value", value)


def _like_prefix(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"{escaped}%"


def _encode_cursor(generation: int, filters: dict[str, object], row: EvidenceIndexRow) -> str:
    payload = [_CURSOR_VERSION, generation, filters, row.started_at.isoformat(), row.trial_id]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(encoded).decode("ascii")


def _decode_cursor(cursor: str, generation: int, filters: dict[str, object]) -> tuple[str, str, str]:
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode("ascii")))
    except (ValueError, UnicodeError, binascii.Error, json.JSONDecodeError) as error:
        raise EvidenceQueryError("invalid evidence query cursor") from error
    if (
        not isinstance(payload, list)
        or len(payload) != 5
        or payload[0] != _CURSOR_VERSION
        or payload[1] != generation
        or payload[2] != filters
    ):
        raise EvidenceQueryError("evidence query cursor is stale or does not match the query")
    if not isinstance(payload[3], str) or not isinstance(payload[4], str):
        raise EvidenceQueryError("invalid evidence query cursor position")
    return payload[3], payload[3], payload[4]


__all__ = ("EvidenceQuery", "EvidenceQueryError", "EvidenceQueryPage")
