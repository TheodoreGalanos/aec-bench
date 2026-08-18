# ABOUTME: Captures and content-binds Prime continual-harness changes without sharing them across runs.
# ABOUTME: Installs one fixed candidate for controlled Prime discovery and comparison sessions.

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import JsonValue, field_validator, model_validator

from aec_bench.contracts.harness_kernel import validate_sha256
from aec_bench.contracts.legacy_content_address import LegacyContentAddressedModel
from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr
from aec_bench.prime_agent.batch import redact_prime_bytes

HARNESS_STATE_NAME = "harness_state.json"
REFINEMENT_CHANGE_NAME = "prime-refinement-change.json"
PRIME_HARNESS_SCHEMA = 1
_ABSOLUTE_PATH = re.compile(r"(?:^|[\s\"'(])(?:/[^\s\"')]+|[A-Za-z]:[\\/][^\s\"')]+)")
_REFINE_COMMAND = re.compile(r"(?<![\w/])/refine(?=$|[\s\"'),.;:])")


class PrimeRefinementMode(StrEnum):
    """AECBench policy for Prime's continual-harness state in one run."""

    CAPTURE = "capture"
    DISCOVER = "discover"
    CANDIDATE = "candidate"


class PrimeRefinementKind(StrEnum):
    """Kinds currently defined by Prime's continual-harness contract."""

    PROMPT = "prompt"
    MEMORY = "memory"
    SKILL = "skill"
    SUBAGENT = "subagent"


class PrimeRefinementScope(StrEnum):
    """Scope requested by Prime when it created one harness entry."""

    LOCAL = "local"
    GLOBAL = "global"


class PrimeRefinementEntry(FrozenStrictModel):
    """One normalized Prime harness entry with its requested scope preserved."""

    id: NonEmptyStr
    kind: PrimeRefinementKind
    title: NonEmptyStr
    content: NonEmptyStr
    path: str
    scope: PrimeRefinementScope
    reference: dict[str, JsonValue]
    arguments: dict[str, JsonValue]
    metadata: dict[str, JsonValue]
    source: str
    created_at: str
    updated_at: str
    version: int

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: int) -> int:
        if isinstance(value, bool) or value < 1:
            raise ValueError("Prime refinement entry version must be positive")
        return value


class PrimeRefinementCandidate(LegacyContentAddressedModel):
    """One exact, isolated continual-harness treatment that can be installed again."""

    schema_version: Literal["aecbench.prime-refinement-candidate.v1"] = "aecbench.prime-refinement-candidate.v1"
    prime_harness_schema: int
    entries: tuple[PrimeRefinementEntry, ...]

    @field_validator("prime_harness_schema")
    @classmethod
    def validate_harness_schema(cls, value: int) -> int:
        if isinstance(value, bool) or value != PRIME_HARNESS_SCHEMA:
            raise ValueError(f"Prime harness schema must be {PRIME_HARNESS_SCHEMA}")
        return value

    @field_validator("entries")
    @classmethod
    def canonicalize_entries(
        cls,
        value: tuple[PrimeRefinementEntry, ...],
    ) -> tuple[PrimeRefinementEntry, ...]:
        return tuple(sorted(value, key=lambda entry: (entry.kind.value, entry.id, entry.scope.value)))

    @model_validator(mode="after")
    def validate_unique_entries(self) -> Self:
        identities = tuple((entry.scope, entry.kind, entry.id) for entry in self.entries)
        if len(identities) != len(set(identities)):
            raise ValueError("Prime refinement candidate entry identities must be unique")
        return self


class PrimeRefinementSource(FrozenStrictModel):
    """Content-bound raw harness evidence copied into the host evidence directory."""

    path: NonEmptyStr
    sha256: str
    scope: PrimeRefinementScope
    session_id: str | None = None

    @field_validator("sha256")
    @classmethod
    def validate_digest(cls, value: str) -> str:
        return validate_sha256(value)


class PrimeRefinementChange(LegacyContentAddressedModel):
    """A proposed candidate derived from one closed Prime session."""

    schema_version: Literal["aecbench.prime-refinement-change.v1"] = "aecbench.prime-refinement-change.v1"
    base_sha256: str
    candidate: PrimeRefinementCandidate
    sources: tuple[PrimeRefinementSource, ...]
    portable: bool
    issues: tuple[NonEmptyStr, ...]

    @field_validator("base_sha256")
    @classmethod
    def validate_base_digest(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_portability(self) -> Self:
        if self.portable == bool(self.issues):
            raise ValueError("Prime refinement change is portable exactly when it has no issues")
        return self


class PrimeRefinementEvidence(FrozenStrictModel):
    """Safe normalized evidence from one Prime process."""

    mode: PrimeRefinementMode
    candidate: PrimeRefinementCandidate
    global_candidate: PrimeRefinementCandidate
    sources: tuple[PrimeRefinementSource, ...]
    portable: bool
    issues: tuple[NonEmptyStr, ...]
    changed: bool
    drifted: bool
    change_file: str | None = None

    @model_validator(mode="after")
    def validate_state(self) -> Self:
        if self.portable == bool(self.issues):
            raise ValueError("Prime refinement evidence is portable exactly when it has no issues")
        if self.drifted and self.mode is not PrimeRefinementMode.CANDIDATE:
            raise ValueError("only a fixed candidate run can report treatment drift")
        return self


def empty_refinement_candidate() -> PrimeRefinementCandidate:
    """Return the canonical empty Prime harness treatment."""

    return PrimeRefinementCandidate(prime_harness_schema=PRIME_HARNESS_SCHEMA, entries=())


def validate_refinement_request(
    mode: PrimeRefinementMode,
    candidate: PrimeRefinementCandidate | None,
) -> None:
    """Reject ambiguous refinement configuration before any process starts."""

    if mode is PrimeRefinementMode.CANDIDATE and candidate is None:
        raise ValueError("Prime candidate refinement mode requires an exact candidate")
    if mode is PrimeRefinementMode.CAPTURE and candidate is not None:
        raise ValueError("Prime capture refinement mode does not accept a candidate")
    if candidate is not None:
        issues = candidate_portability_issues(candidate)
        if issues:
            raise ValueError(f"Prime refinement candidate is not portable: {', '.join(issues)}")


def candidate_portability_issues(candidate: PrimeRefinementCandidate) -> tuple[str, ...]:
    """Return deterministic reasons why a candidate cannot be installed safely."""

    issues: set[str] = set()
    for entry in candidate.entries:
        if _entry_contains_nonportable_path(entry):
            issues.add("harness_entry_contains_nonportable_path")
        if entry.kind is PrimeRefinementKind.SKILL and not _valid_skill_reference(entry.reference):
            issues.add("skill_reference_is_not_portable")
    return tuple(sorted(issues))


def install_refinement_candidate(
    state_directory: Path,
    candidate: PrimeRefinementCandidate,
) -> Path:
    """Install one candidate in the run-local Prime store before Prime starts."""

    harness_directory = state_directory / "harness"
    harness_directory.mkdir(parents=True, exist_ok=False)
    destination = harness_directory / HARNESS_STATE_NAME
    entries: dict[str, dict[str, dict[str, JsonValue]]] = {kind.value: {} for kind in PrimeRefinementKind}
    for entry in candidate.entries:
        storage_id = entry.id
        if storage_id in entries[entry.kind.value]:
            storage_id = f"{entry.scope.value}:{entry.id}"
        if storage_id in entries[entry.kind.value]:
            raise ValueError(f"Prime refinement candidate has duplicate {entry.kind.value} entry: {entry.id}")
        entries[entry.kind.value][storage_id] = entry.model_dump(mode="json")
    payload: dict[str, Any] = {
        "schema": candidate.prime_harness_schema,
        "entries": entries,
        "refinements": [],
    }
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def capture_refinement_evidence(
    *,
    mode: PrimeRefinementMode,
    state_directory: Path,
    session_directory: Path,
    evidence_directory: Path,
    base: PrimeRefinementCandidate | None,
    environment: Mapping[str, str],
    redact_values: Sequence[str],
) -> PrimeRefinementEvidence:
    """Preserve all harness files and derive one strict, content-bound candidate."""

    raw_sources = _harness_sources(state_directory, session_directory)
    normalized_entries: list[PrimeRefinementEntry] = []
    global_entries: list[PrimeRefinementEntry] = []
    evidence_sources: list[PrimeRefinementSource] = []
    issues: set[str] = set()
    harness_schemas: set[int] = set()

    for index, (scope, session_id, source) in enumerate(raw_sources):
        suffix = "global" if scope is PrimeRefinementScope.GLOBAL else f"local-{index:03d}"
        destination = evidence_directory / f"prime-harness-{suffix}.json"
        sanitized = redact_prime_bytes(
            source.read_bytes(),
            environment,
            additional_values=tuple(redact_values),
        )
        destination.write_bytes(sanitized)
        evidence_sources.append(
            PrimeRefinementSource(
                path=destination.relative_to(evidence_directory).as_posix(),
                sha256=hashlib.sha256(sanitized).hexdigest(),
                scope=scope,
                session_id=session_id,
            )
        )
        parsed_entries, schema, source_issues = _parse_harness_state(sanitized, default_scope=scope)
        normalized_entries.extend(parsed_entries)
        if scope is PrimeRefinementScope.GLOBAL:
            global_entries.extend(parsed_entries)
        harness_schemas.add(schema)
        issues.update(source_issues)

    schema = max(harness_schemas, default=(base.prime_harness_schema if base is not None else 1))
    candidate_entries, merge_issues = _merge_entries(normalized_entries)
    global_candidate_entries, global_merge_issues = _merge_entries(global_entries)
    issues.update(merge_issues)
    issues.update(global_merge_issues)
    candidate = PrimeRefinementCandidate(prime_harness_schema=schema, entries=candidate_entries)
    global_candidate = PrimeRefinementCandidate(prime_harness_schema=schema, entries=global_candidate_entries)
    base_candidate = base or empty_refinement_candidate()
    changed = candidate.content_sha256 != base_candidate.content_sha256
    drifted = mode is PrimeRefinementMode.CANDIDATE and changed
    if drifted:
        issues.add("fixed_candidate_changed")
    ordered_issues = tuple(sorted(issues))
    portable = not ordered_issues
    change_file: str | None = None
    if mode is PrimeRefinementMode.DISCOVER:
        change = PrimeRefinementChange(
            base_sha256=base_candidate.content_sha256,
            candidate=candidate,
            sources=tuple(evidence_sources),
            portable=portable,
            issues=ordered_issues,
        )
        destination = evidence_directory / REFINEMENT_CHANGE_NAME
        destination.write_text(change.model_dump_json(indent=2) + "\n", encoding="utf-8")
        change_file = destination.relative_to(evidence_directory).as_posix()
    return PrimeRefinementEvidence(
        mode=mode,
        candidate=candidate,
        global_candidate=global_candidate,
        sources=tuple(evidence_sources),
        portable=portable,
        issues=ordered_issues,
        changed=changed,
        drifted=drifted,
        change_file=change_file,
    )


def _harness_sources(
    state_directory: Path,
    session_directory: Path,
) -> tuple[tuple[PrimeRefinementScope, str | None, Path], ...]:
    sources: list[tuple[PrimeRefinementScope, str | None, Path]] = []
    global_state = state_directory / "harness" / HARNESS_STATE_NAME
    if global_state.is_file():
        sources.append((PrimeRefinementScope.GLOBAL, None, global_state))
    artifact_root = session_directory.parent / "session-artifacts"
    if artifact_root.is_dir():
        for state in sorted(artifact_root.glob(f"*/harness/{HARNESS_STATE_NAME}")):
            session_id = state.parents[1].name
            sources.append((PrimeRefinementScope.LOCAL, session_id, state))
    return tuple(sources)


def _parse_harness_state(
    raw: bytes,
    *,
    default_scope: PrimeRefinementScope,
) -> tuple[tuple[PrimeRefinementEntry, ...], int, tuple[str, ...]]:
    issues: set[str] = set()
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return (), 1, ("malformed_harness_state",)
    if not isinstance(payload, dict):
        return (), 1, ("malformed_harness_state",)
    schema = payload.get("schema", PRIME_HARNESS_SCHEMA)
    if isinstance(schema, bool) or not isinstance(schema, int) or schema != PRIME_HARNESS_SCHEMA:
        issues.add("unsupported_harness_schema")
        schema = PRIME_HARNESS_SCHEMA
    entries = payload.get("entries")
    if not isinstance(entries, dict):
        return (), schema, tuple(sorted({*issues, "malformed_harness_entries"}))
    unknown_kinds = set(entries) - {kind.value for kind in PrimeRefinementKind}
    if unknown_kinds:
        issues.add("unknown_harness_kind")
    normalized: list[PrimeRefinementEntry] = []
    for kind in PrimeRefinementKind:
        records = entries.get(kind.value, {})
        if not isinstance(records, dict):
            issues.add(f"malformed_{kind.value}_entries")
            continue
        for storage_id, raw_entry in records.items():
            entry, entry_issues = _parse_entry(
                raw_entry,
                storage_id=storage_id,
                kind=kind,
                default_scope=default_scope,
            )
            issues.update(entry_issues)
            if entry is not None:
                normalized.append(entry)
    return tuple(normalized), schema, tuple(sorted(issues))


def _parse_entry(
    raw: Any,
    *,
    storage_id: Any,
    kind: PrimeRefinementKind,
    default_scope: PrimeRefinementScope,
) -> tuple[PrimeRefinementEntry | None, tuple[str, ...]]:
    if not isinstance(storage_id, str) or not storage_id or not isinstance(raw, dict):
        return None, (f"malformed_{kind.value}_entry",)
    expected = {
        "id",
        "kind",
        "title",
        "content",
        "path",
        "scope",
        "reference",
        "arguments",
        "metadata",
        "source",
        "created_at",
        "updated_at",
        "version",
    }
    issues: set[str] = set()
    if set(raw) - expected:
        issues.add("unknown_harness_entry_field")
    payload = dict(raw)
    payload.setdefault("id", storage_id)
    payload.setdefault("kind", kind.value)
    payload.setdefault("path", "")
    payload.setdefault("scope", default_scope.value)
    payload.setdefault("reference", {})
    payload.setdefault("arguments", {})
    payload.setdefault("metadata", {})
    payload.setdefault("source", "")
    payload.setdefault("created_at", "")
    payload.setdefault("updated_at", "")
    payload_id = payload.get("id")
    payload_scope = payload.get("scope")
    storage_identity_matches = storage_id == payload_id or (
        isinstance(payload_id, str) and isinstance(payload_scope, str) and storage_id == f"{payload_scope}:{payload_id}"
    )
    if not storage_identity_matches or payload.get("kind") != kind.value:
        issues.add("harness_entry_identity_mismatch")
    try:
        entry = PrimeRefinementEntry.model_validate(payload)
    except ValueError:
        return None, tuple(sorted({*issues, f"malformed_{kind.value}_entry"}))
    if _entry_contains_nonportable_path(entry):
        issues.add("harness_entry_contains_nonportable_path")
    if kind is PrimeRefinementKind.SKILL and not _valid_skill_reference(entry.reference):
        issues.add("skill_reference_is_not_portable")
    return entry, tuple(sorted(issues))


def _valid_skill_reference(reference: Mapping[str, JsonValue]) -> bool:
    if reference.get("type") != "python":
        return False
    module = reference.get("import") or reference.get("python_import")
    callable_name = reference.get("callable")
    call_pattern = reference.get("call_pattern")
    return (
        isinstance(module, str)
        and bool(module.strip())
        and (
            (isinstance(callable_name, str) and bool(callable_name.strip()))
            or (isinstance(call_pattern, str) and bool(call_pattern.strip()))
        )
    )


def _merge_entries(
    entries: Sequence[PrimeRefinementEntry],
) -> tuple[tuple[PrimeRefinementEntry, ...], tuple[str, ...]]:
    by_identity: dict[tuple[PrimeRefinementScope, PrimeRefinementKind, str], PrimeRefinementEntry] = {}
    issues: set[str] = set()
    for entry in entries:
        identity = (entry.scope, entry.kind, entry.id)
        previous = by_identity.get(identity)
        if previous is not None and previous != entry:
            issues.add("conflicting_harness_entry")
            continue
        by_identity[identity] = entry
    return tuple(by_identity.values()), tuple(sorted(issues))


def _entry_contains_nonportable_path(entry: PrimeRefinementEntry) -> bool:
    payload = entry.model_dump(mode="json")
    content = payload.get("content")
    if isinstance(content, str):
        payload["content"] = _REFINE_COMMAND.sub("refine-command", content)
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return "<redacted>" in encoded or _ABSOLUTE_PATH.search(encoded) is not None
