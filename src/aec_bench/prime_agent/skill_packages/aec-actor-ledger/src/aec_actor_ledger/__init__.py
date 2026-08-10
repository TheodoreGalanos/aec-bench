# ABOUTME: Records exact Prime world actions while returning only compact actor-visible results.
# ABOUTME: Gives the actor bounded search and window access to its saved current observation.

from __future__ import annotations

import importlib
import json
import os
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

aec_world = importlib.import_module("aec_world")

_STORE_DIRECTORY = ".aec-actor-ledger"
_STATE_FILE = "state.json"
_LEDGER_FILE = "actions.jsonl"
_MAX_PAGE_ITEMS = 10
_MAX_OBJECT_FIELDS = 8
_MAX_TEXT_CHARS = 120
_MAX_PATH_CHARS = 160
_MAX_QUERY_CHARS = 120
_MAX_RESULT_CHARS = 4_000


class ActorLedgerError(RuntimeError):
    """Raised when local actor-ledger state is missing or malformed."""


async def observe() -> dict[str, Any]:
    """Observe the world, save the full actor-visible result, and return a compact summary."""
    observation = await aec_world.observe()
    _write_state(observation)
    return _compact_observation(observation)


async def invoke(
    action_name: str,
    arguments: dict[str, Any],
    *,
    expected_result: str,
    decision_id: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Invoke one actor action, record its exact outcome, and return a compact result."""
    if not expected_result.strip():
        raise ValueError("expected_result must be non-empty")
    current_decision_id = decision_id or _current_decision_id()
    current_request_id = request_id or str(uuid.uuid4())
    entry: dict[str, Any] = {
        "request_id": current_request_id,
        "decision_id": current_decision_id,
        "action": action_name,
        "arguments": arguments,
        "expected_result": expected_result,
    }
    try:
        json.dumps(entry)
    except (TypeError, ValueError) as error:
        raise ValueError("actor ledger input must be JSON serializable") from error
    try:
        result = await aec_world.invoke(
            action_name,
            arguments,
            decision_id=current_decision_id,
            request_id=current_request_id,
        )
    except aec_world.ActorError as error:
        entry.update(
            {
                "status": "failed",
                "error": {"code": error.code, "detail": error.detail},
            }
        )
        _append_entry(entry)
        return _compact_outcome(entry)

    entry.update({"status": result.get("status"), "result": result})
    next_observation = result.get("next_observation")
    if isinstance(next_observation, dict):
        _write_state(next_observation)
    _append_entry(entry)
    return _compact_outcome(entry)


def latest() -> dict[str, Any]:
    """Return a compact summary of the newest saved actor-visible observation."""
    return _compact_observation(_read_state())


def search(query: str, *, path: str = "view", limit: int = 8) -> dict[str, Any]:
    """Search saved actor-visible keys and scalar values with a fixed output bound."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be non-empty")
    if len(query) > _MAX_QUERY_CHARS:
        raise ValueError(f"query must contain at most {_MAX_QUERY_CHARS} characters")
    _validate_page(start=0, limit=limit)
    source = _resolve_path(_read_state(), path)
    matches: list[dict[str, Any]] = []
    wanted = query.casefold()
    for item_path, value in _walk(source, path):
        text = _scalar_text(value)
        if wanted not in item_path.casefold() and wanted not in text.casefold():
            continue
        if len(matches) == limit:
            return {
                "query": query,
                "path": path,
                "matches": matches,
                "returned": len(matches),
                "truncated": True,
            }
        matches.append({"path": _compact_path(item_path), "preview": _compact_scalar(value)})
    return {
        "query": query,
        "path": path,
        "matches": matches,
        "returned": len(matches),
        "truncated": False,
    }


def window(path: str, *, start: int = 0, limit: int = 5) -> dict[str, Any]:
    """Read one bounded window from the saved actor-visible observation."""
    _validate_page(start=start, limit=limit)
    value = _resolve_path(_read_state(), path)
    if isinstance(value, dict):
        source = [
            {"key": _compact_scalar(key), "value": _compact_value(item)}
            for key, item in sorted(value.items())[start : start + limit + 1]
        ]
        total = len(value)
    elif isinstance(value, list):
        source = [
            {"index": index, "value": _compact_value(value[index])}
            for index in range(start, min(len(value), start + limit + 1))
        ]
        total = len(value)
    else:
        if start != 0:
            raise ValueError("start must be zero for a scalar path")
        source = [{"value": _compact_scalar(value)}]
        total = 1
    items = _fit_items(
        source[:limit],
        base={"path": path, "start": start, "total": total},
    )
    return {
        "path": path,
        "start": start,
        "total": total,
        "items": items,
        "returned": len(items),
        "truncated": start + len(items) < total,
    }


def entries(*, start: int = 0, limit: int = 5) -> dict[str, Any]:
    """Return one bounded page of compact action-attempt summaries."""
    _validate_page(start=start, limit=limit)
    records = _read_entries()
    source = [_compact_entry(record) for record in records[start : start + limit]]
    items = _fit_items(
        source,
        base={"start": start, "total": len(records)},
    )
    return {
        "start": start,
        "total": len(records),
        "entries": items,
        "returned": len(items),
        "truncated": start + len(items) < len(records),
    }


def _compact_outcome(entry: dict[str, Any]) -> dict[str, Any]:
    result = entry.get("result")
    task_receipt = result.get("task_receipt") if isinstance(result, dict) else None
    next_observation = result.get("next_observation") if isinstance(result, dict) else None
    return {
        "request_id": _compact_scalar(entry["request_id"]),
        "action": _compact_scalar(entry["action"]),
        "status": _compact_scalar(entry["status"]),
        "reason_code": _compact_scalar(task_receipt.get("code")) if isinstance(task_receipt, dict) else None,
        "message": _optional_text(task_receipt.get("message")) if isinstance(task_receipt, dict) else None,
        "error": _compact_error(entry.get("error")),
        "terminated": result.get("terminated", False) if isinstance(result, dict) else False,
        "truncated": result.get("truncated", False) if isinstance(result, dict) else False,
        "reason": _optional_text(result.get("reason")) if isinstance(result, dict) else None,
        "observation": _compact_observation(next_observation) if isinstance(next_observation, dict) else None,
    }


def _compact_observation(observation: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision_id": _compact_scalar(observation.get("decision_id")),
        "view": _compact_value(observation.get("view")),
    }


def _compact_entry(entry: dict[str, Any]) -> dict[str, Any]:
    result = entry.get("result")
    receipt = result.get("task_receipt") if isinstance(result, dict) else None
    next_observation = result.get("next_observation") if isinstance(result, dict) else None
    return {
        "request_id": _compact_scalar(entry.get("request_id")),
        "decision_id": _compact_scalar(entry.get("decision_id")),
        "action": _compact_scalar(entry.get("action")),
        "arguments": _compact_value(entry.get("arguments")),
        "expected_result": _optional_text(entry.get("expected_result")),
        "status": _compact_scalar(entry.get("status")),
        "reason_code": _compact_scalar(receipt.get("code")) if isinstance(receipt, dict) else None,
        "error": _compact_error(entry.get("error")),
        "next_decision_id": (
            _compact_scalar(next_observation.get("decision_id")) if isinstance(next_observation, dict) else None
        ),
    }


def _compact_value(value: Any) -> Any:
    if isinstance(value, dict):
        keys = sorted(value)
        return {
            "type": "object",
            "fields": len(keys),
            "values": [
                {"key": _compact_scalar(key), "value": _describe_value(value[key])} for key in keys[:_MAX_OBJECT_FIELDS]
            ],
            "truncated": len(keys) > _MAX_OBJECT_FIELDS,
        }
    if isinstance(value, list):
        return {"type": "array", "items": len(value)}
    return _compact_scalar(value)


def _describe_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {"type": "object", "fields": len(value)}
    if isinstance(value, list):
        return {"type": "array", "items": len(value)}
    return _compact_scalar(value)


def _compact_scalar(value: Any) -> Any:
    if isinstance(value, str) and len(value) > _MAX_TEXT_CHARS:
        return value[:_MAX_TEXT_CHARS] + "..."
    return value


def _compact_error(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return {
        "code": _compact_scalar(value.get("code")),
        "detail": _optional_text(value.get("detail")),
    }


def _optional_text(value: Any) -> str | None:
    return _compact_scalar(value) if isinstance(value, str) else None


def _scalar_text(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def _compact_path(value: str) -> str:
    if len(value) <= _MAX_PATH_CHARS:
        return value
    return value[:_MAX_PATH_CHARS] + "..."


def _walk(value: Any, path: str) -> Iterator[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _walk(item, _join_path(path, key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk(item, _join_path(path, str(index)))
    else:
        yield path, value


def _join_path(prefix: str, part: str) -> str:
    return f"{prefix}.{part}" if prefix else part


def _resolve_path(source: Any, path: str) -> Any:
    if not isinstance(path, str) or len(path) > _MAX_PATH_CHARS:
        raise ValueError(f"path must contain at most {_MAX_PATH_CHARS} characters")
    value = source
    if not path:
        return value
    for part in path.split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
        elif isinstance(value, list) and part.isdecimal() and int(part) < len(value):
            value = value[int(part)]
        else:
            raise KeyError(path)
    return value


def _fit_items(items: list[dict[str, Any]], *, base: dict[str, Any]) -> list[dict[str, Any]]:
    fitted: list[dict[str, Any]] = []
    for item in items:
        candidate = [*fitted, item]
        if len(json.dumps({**base, "items": candidate}, sort_keys=True)) > _MAX_RESULT_CHARS:
            break
        fitted = candidate
    return fitted


def _validate_page(*, start: int, limit: int) -> None:
    if not isinstance(start, int) or start < 0:
        raise ValueError("start must be a non-negative integer")
    if not isinstance(limit, int) or not 1 <= limit <= _MAX_PAGE_ITEMS:
        raise ValueError(f"limit must be between 1 and {_MAX_PAGE_ITEMS}")


def _current_decision_id() -> str:
    decision_id = _read_state().get("decision_id")
    if not isinstance(decision_id, str) or not decision_id:
        raise ActorLedgerError("saved actor observation has no decision_id")
    return decision_id


def _read_state() -> dict[str, Any]:
    path = _store_directory() / _STATE_FILE
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ActorLedgerError("observe the world before using the actor ledger") from error
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ActorLedgerError("saved actor observation is malformed") from error
    if not isinstance(value, dict):
        raise ActorLedgerError("saved actor observation is not an object")
    return value


def _read_entries() -> list[dict[str, Any]]:
    path = _store_directory() / _LEDGER_FILE
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ActorLedgerError("actor ledger entry is not an object")
            records.append(value)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ActorLedgerError("actor ledger is malformed") from error
    return records


def _write_state(observation: dict[str, Any]) -> None:
    directory = _store_directory()
    directory.mkdir(exist_ok=True)
    destination = directory / _STATE_FILE
    temporary = directory / f".{_STATE_FILE}.{uuid.uuid4().hex}.tmp"
    try:
        temporary.write_text(json.dumps(observation, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def _append_entry(entry: dict[str, Any]) -> None:
    directory = _store_directory()
    directory.mkdir(exist_ok=True)
    with (directory / _LEDGER_FILE).open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(entry, sort_keys=True) + "\n")


def _store_directory() -> Path:
    return Path.cwd() / _STORE_DIRECTORY


__all__ = ["ActorLedgerError", "entries", "invoke", "latest", "observe", "search", "window"]
