# ABOUTME: Validates Prime ACP session artifacts and derives composite-principal accounting evidence.
# ABOUTME: Supports fail-closed model-call, token, and cost limits at completed-response boundaries.

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Protocol

from aec_bench.prime_agent.events import PRIME_EVENT_STREAM_VERSIONS

_USAGE_POLL_SECONDS = 0.05
_PRIME_AGENT_META_NAMESPACE = "ai.primeintellect.prime-agent"
_COST_QUANTUM_USD = Decimal("0.000000000001")


class PrimeSessionEvidenceError(ValueError):
    """Raised when Prime's session artifacts cannot support safe accounting."""


@dataclass(frozen=True, slots=True)
class PrimeAcpLimits:
    """Host limits for one Prime root session and its descendants."""

    max_model_calls: int
    max_tokens: int
    max_cost_usd: Decimal
    max_wall_seconds: float

    def __post_init__(self) -> None:
        if self.max_model_calls < 1:
            raise ValueError("Prime ACP max_model_calls must be positive")
        if self.max_tokens < 1:
            raise ValueError("Prime ACP max_tokens must be positive")
        if self.max_cost_usd <= 0:
            raise ValueError("Prime ACP max_cost_usd must be positive")
        if self.max_wall_seconds <= 0:
            raise ValueError("Prime ACP max_wall_seconds must be positive")


@dataclass(frozen=True, slots=True)
class PrimeAcpUsage:
    """Normalized provider accounting read from Prime's session artifacts."""

    complete: bool
    model_calls: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    total_tokens: int
    cost_usd: Decimal


class _PrimeAcpUsageValues(Protocol):
    @property
    def complete(self) -> bool: ...

    @property
    def model_calls(self) -> int: ...

    @property
    def input_tokens(self) -> int: ...

    @property
    def output_tokens(self) -> int: ...

    @property
    def cache_read_tokens(self) -> int: ...

    @property
    def cache_write_tokens(self) -> int: ...

    @property
    def total_tokens(self) -> int: ...

    @property
    def cost_usd(self) -> Decimal: ...


@dataclass(frozen=True, slots=True)
class PrimeAcpTopology:
    """Composite-principal topology observed in Prime's session artifacts."""

    root_sessions: int
    child_sessions: int


@dataclass(frozen=True, slots=True)
class PrimeAcpRefinement:
    """Normalized counts derived from preserved Prime ACP refinement metadata."""

    events: int
    completed: int
    failed: int
    unknown: int


async def wait_for_usage_limit(session_directory: Path, limits: PrimeAcpLimits) -> str:
    """Wait until persisted composite usage reaches one configured threshold."""
    previous_signature: tuple[tuple[str, int, int], ...] | None = None
    while True:
        signature = _session_artifact_signature(session_directory)
        if signature != previous_signature:
            previous_signature = signature
            evidence = read_session_evidence(session_directory, allow_partial=True, require_root=False)
            if evidence is not None:
                usage, _topology = evidence
                reason = usage_limit_reason(usage, limits)
                if reason is not None:
                    return reason
        await asyncio.sleep(_USAGE_POLL_SECONDS)


def read_session_evidence(
    session_directory: Path,
    *,
    allow_partial: bool,
    require_root: bool = True,
) -> tuple[PrimeAcpUsage, PrimeAcpTopology] | None:
    """Validate all Prime session streams and aggregate their assistant usage."""
    files = sorted(path for path in session_directory.rglob("*.jsonl") if path.is_file())
    if not files:
        if require_root:
            raise PrimeSessionEvidenceError("Prime ACP session produced no parseable session artifacts")
        return None

    model_calls = 0
    input_tokens = 0
    output_tokens = 0
    cache_read_tokens = 0
    cache_write_tokens = 0
    total_tokens = 0
    cost_usd = Decimal(0)
    root_sessions = 0
    child_sessions = 0
    seen_messages: set[str] = set()
    for path in files:
        events = _session_events(path, allow_partial=allow_partial)
        if not events:
            continue
        depth = _session_depth(events[0])
        if depth == 0:
            root_sessions += 1
        else:
            child_sessions += 1

        for event in events[1:]:
            message = event.get("message")
            if event.get("type") != "message" or not isinstance(message, dict) or message.get("role") != "assistant":
                continue
            message_id = event.get("id")
            if not isinstance(message_id, str) or not message_id.strip():
                raise PrimeSessionEvidenceError("Prime assistant session event has no identity")
            if message_id in seen_messages:
                continue
            seen_messages.add(message_id)
            usage = message.get("usage")
            if not isinstance(usage, dict):
                raise PrimeSessionEvidenceError("Prime assistant session event has no usage evidence")
            values = tuple(
                _required_non_negative_int(usage.get(name), name)
                for name in ("input", "output", "cacheRead", "cacheWrite", "totalTokens")
            )
            input_value, output_value, cache_read_value, cache_write_value, total_value = values
            if total_value != input_value + output_value + cache_read_value + cache_write_value:
                raise PrimeSessionEvidenceError("Prime assistant token totals are inconsistent")
            cost = usage.get("cost")
            if not isinstance(cost, dict):
                raise PrimeSessionEvidenceError("Prime assistant session event has no cost evidence")
            model_calls += 1
            input_tokens += input_value
            output_tokens += output_value
            cache_read_tokens += cache_read_value
            cache_write_tokens += cache_write_value
            total_tokens += total_value
            cost_usd += _required_non_negative_decimal(cost.get("total"), "cost.total")

    if require_root and root_sessions != 1:
        raise PrimeSessionEvidenceError("Prime ACP session artifacts must contain exactly one root session")
    return (
        PrimeAcpUsage(
            complete=True,
            model_calls=model_calls,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
        ),
        PrimeAcpTopology(root_sessions=root_sessions, child_sessions=child_sessions),
    )


def usage_limit_reason(usage: PrimeAcpUsage, limits: PrimeAcpLimits) -> str | None:
    if usage.model_calls >= limits.max_model_calls:
        return "max_model_calls"
    if usage.total_tokens >= limits.max_tokens:
        return "max_tokens"
    if usage.cost_usd >= limits.max_cost_usd:
        return "max_cost_usd"
    return None


def empty_usage() -> PrimeAcpUsage:
    return PrimeAcpUsage(
        complete=False,
        model_calls=0,
        input_tokens=0,
        output_tokens=0,
        cache_read_tokens=0,
        cache_write_tokens=0,
        total_tokens=0,
        cost_usd=Decimal(0),
    )


def aggregate_acp_usage(usages: Iterable[_PrimeAcpUsageValues]) -> PrimeAcpUsage:
    """Combine completed Prime-session accounting without changing its meaning."""
    items = tuple(usages)
    return PrimeAcpUsage(
        complete=bool(items) and all(item.complete for item in items),
        model_calls=sum(item.model_calls for item in items),
        input_tokens=sum(item.input_tokens for item in items),
        output_tokens=sum(item.output_tokens for item in items),
        cache_read_tokens=sum(item.cache_read_tokens for item in items),
        cache_write_tokens=sum(item.cache_write_tokens for item in items),
        total_tokens=sum(item.total_tokens for item in items),
        cost_usd=sum((item.cost_usd for item in items), start=Decimal(0)),
    )


def acp_usage_payload(usage: PrimeAcpUsage) -> dict[str, bool | int | str]:
    """Return the stable JSON values used by composed Prime-run evidence."""
    return {
        "complete": usage.complete,
        "model_calls": usage.model_calls,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cache_read_tokens": usage.cache_read_tokens,
        "cache_write_tokens": usage.cache_write_tokens,
        "total_tokens": usage.total_tokens,
        "cost_usd": str(usage.cost_usd),
    }


def refinement_evidence(updates: Sequence[dict[str, Any]]) -> PrimeAcpRefinement:
    statuses: list[str | None] = []
    for event in updates:
        update = event.get("update")
        metadata = event.get("_meta")
        candidates = [
            update.get("_meta") if isinstance(update, dict) else None,
            metadata,
        ]
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            namespaced = candidate.get(_PRIME_AGENT_META_NAMESPACE)
            if not isinstance(namespaced, dict) or "refinement" not in namespaced:
                continue
            refinement = namespaced["refinement"]
            statuses.append(refinement.get("status") if isinstance(refinement, dict) else None)
    return PrimeAcpRefinement(
        events=len(statuses),
        completed=statuses.count("complete"),
        failed=statuses.count("failed"),
        unknown=sum(status not in {"complete", "failed"} for status in statuses),
    )


def _session_artifact_signature(session_directory: Path) -> tuple[tuple[str, int, int], ...]:
    signature: list[tuple[str, int, int]] = []
    for path in sorted(session_directory.rglob("*.jsonl")):
        if path.is_file():
            stat = path.stat()
            signature.append((path.relative_to(session_directory).as_posix(), stat.st_size, stat.st_mtime_ns))
    return tuple(signature)


def _session_events(path: Path, *, allow_partial: bool) -> list[dict[str, Any]]:
    try:
        text = path.read_bytes().decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise PrimeSessionEvidenceError("Prime session artifact is not valid UTF-8") from exc
    if text and not text.endswith("\n"):
        if not allow_partial:
            raise PrimeSessionEvidenceError("Prime session artifact ended with an incomplete JSONL frame")
        last_newline = text.rfind("\n")
        text = "" if last_newline < 0 else text[: last_newline + 1]
    lines = text.splitlines()
    if not lines:
        if allow_partial:
            return []
        raise PrimeSessionEvidenceError("Prime session artifact is empty")
    events: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            raise PrimeSessionEvidenceError("Prime session artifact contains a blank frame")
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise PrimeSessionEvidenceError("Prime session artifact contains malformed JSON") from exc
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            raise PrimeSessionEvidenceError("Prime session artifact contains an unsupported event")
        events.append(event)
    return events


def _session_depth(header: dict[str, Any]) -> int:
    if header.get("type") != "session" or header.get("version") not in PRIME_EVENT_STREAM_VERSIONS:
        raise PrimeSessionEvidenceError("Prime session artifact has an unsupported session header")
    session_id = header.get("id")
    depth = header.get("rlmDepth")
    if not isinstance(session_id, str) or not session_id.strip():
        raise PrimeSessionEvidenceError("Prime session artifact has no session identity")
    if isinstance(depth, bool) or not isinstance(depth, int) or depth < 0:
        raise PrimeSessionEvidenceError("Prime session artifact has invalid topology metadata")
    return depth


def _required_non_negative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PrimeSessionEvidenceError(f"Prime assistant usage {name} must be a non-negative integer")
    return int(value)


def _required_non_negative_decimal(value: Any, name: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise PrimeSessionEvidenceError(f"Prime assistant usage {name} must be a non-negative number")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise PrimeSessionEvidenceError(f"Prime assistant usage {name} must be a non-negative number") from exc
    if not result.is_finite() or result < 0:
        raise PrimeSessionEvidenceError(f"Prime assistant usage {name} must be a non-negative number")
    try:
        return result.quantize(_COST_QUANTUM_USD).normalize()
    except InvalidOperation as exc:
        raise PrimeSessionEvidenceError(f"Prime assistant usage {name} is outside the supported range") from exc
