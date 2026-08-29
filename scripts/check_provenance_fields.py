#!/usr/bin/env python3
# ABOUTME: Audits persisted and public provenance-shaped fields without importing AEC-Bench modules.
# ABOUTME: Enforces the provenance registry and a deletion-only migration baseline for maintained Python code.

from __future__ import annotations

import argparse
import ast
import importlib.util
import io
import json
import re
import subprocess
import sys
import tarfile
import tomllib
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BASELINE_SCHEMA = "aec-bench/provenance-baseline/1"
REGISTRY_SCHEMA = 1

_PROVENANCE_TOKENS = {
    "checksum",
    "commit",
    "commitment",
    "digest",
    "fingerprint",
    "hash",
    "protocol",
    "revision",
    "schema",
    "semantics",
    "sha",
    "sha256",
    "timestamp",
    "version",
}
_MODEL_BASE_NAMES = {
    "BaseModel",
    "FrozenStrictModel",
    "LenientModel",
    "StrictModel",
}
_CATEGORY_NAMES = {
    "artifact_integrity",
    "compatibility",
    "domain_identity",
    "event_time",
    "operational_commitment",
    "qualification_attestation",
    "semantic_commitment",
    "source_identity",
}
_COMMON_FIELD_KEYS = {
    "aliases",
    "authority",
    "authoritative",
    "canonicalization",
    "category",
    "consumer",
    "domain_owner",
    "duplication",
    "exposure",
    "mismatch_behavior",
    "payload_contract",
    "rationale",
    "retention",
    "status",
    "surface",
    "symbol",
    "validation_behavior",
    "wire_name",
}
_COMMON_REQUIRED_KEYS = _COMMON_FIELD_KEYS - {"aliases", "symbol"}
_CATEGORY_KEYS = {
    "artifact_integrity": {"algorithm", "artifact_boundary", "fail_closed", "read_verification"},
    "compatibility": {"compatibility_behavior", "compatibility_kind"},
    "domain_identity": set(),
    "event_time": {"event"},
    "operational_commitment": {"algorithm", "canonicalizer", "identity_scope", "purpose"},
    "qualification_attestation": {
        "evidence_levels",
        "missing_evidence_behavior",
        "provider_route_scope",
        "qualification_state_behavior",
        "version_scope",
    },
    "semantic_commitment": {"algorithm", "canonicalizer", "fail_closed"},
    "source_identity": {"format"},
}
_EXCEPTION_REQUIRED_KEYS = {"exception_reason", "removal_milestone"}
_EXCEPTION_TARGET_KEYS = {"duplicate_of", "exception_scope"}
_EXCEPTION_KEYS = _EXCEPTION_REQUIRED_KEYS | _EXCEPTION_TARGET_KEYS
_ALL_FIELD_KEYS = _COMMON_FIELD_KEYS | set().union(*_CATEGORY_KEYS.values()) | _EXCEPTION_KEYS
_MANIFEST_KEYS = {"contract", "sink"}
_LEGACY_RELOCATION_KEYS = {"from_prefix", "to_prefix"}
_PERSISTENCE_CALL_PARTS = {
    "dump",
    "dumps",
    "emit",
    "export",
    "persist",
    "publish",
    "record",
    "respond",
    "save",
    "serialize",
    "store",
    "write",
    "write_bytes",
    "write_text",
}
_HASH_KEY_PARTS = {"checksum", "digest", "hash", "sha", "sha256"}
_CONTRACT_KEY_PRIORITY = (
    "schema",
    "schema_id",
    "schema_version",
    "protocol",
    "protocol_version",
    "semantics",
    "semantics_version",
)
_IGNORED_PATH_PARTS = {"__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache", "node_modules"}
_COMPATIBILITY_KINDS = {
    "entity_revision",
    "external_schema",
    "package_distribution",
    "protocol",
    "qualification_matrix",
}
_FIELD_STATUSES = {"current", "temporary_exception"}
_ACTOR_REQUEST_FINGERPRINT_KEYS = {
    "action_name",
    "actor_principal_id",
    "arguments",
    "decision_id",
    "semantics",
}
_ACTOR_REQUEST_FINGERPRINT_EXPRESSIONS = {
    "action_name": "request.action_name",
    "actor_principal_id": "actor_principal_id",
    "arguments": "request.arguments",
    "decision_id": "request.decision_id",
    "semantics": "ACTOR_INVOCATION_SEMANTICS",
}
_CONTENT_ADDRESSED_BASE_NAMES = {"ContentAddressedModel", "LegacyContentAddressedModel"}
_SELF_PATH = "scripts/check_provenance_fields.py"


class ProvenanceInputError(ValueError):
    """Report a malformed registry, baseline, source tree, or Git input."""


class ProvenanceBaselineGrowthError(ProvenanceInputError):
    """Reject an update that would add current fields to the legacy baseline."""


@dataclass(frozen=True, order=True)
class Occurrence:
    """One exact source occurrence for a discovered field."""

    path: str
    line: int
    kind: str

    def as_dict(self) -> dict[str, object]:
        return {"kind": self.kind, "line": self.line, "path": self.path}


@dataclass(frozen=True)
class Candidate:
    """One provenance-shaped public or persisted field definition."""

    symbol: str
    wire_name: str
    surface: str
    occurrences: tuple[Occurrence, ...]
    owner: str
    field_name: str
    annotation: str = ""
    inherited: bool = False
    sibling_fields: tuple[str, ...] = ()
    artifact_ref_fields: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "annotation": self.annotation,
            "artifact_ref_fields": list(self.artifact_ref_fields),
            "field_name": self.field_name,
            "inherited": self.inherited,
            "occurrences": [occurrence.as_dict() for occurrence in self.occurrences],
            "owner": self.owner,
            "sibling_fields": list(self.sibling_fields),
            "surface": self.surface,
            "symbol": self.symbol,
            "wire_name": self.wire_name,
        }


@dataclass(frozen=True)
class RegistryManifest:
    contract: str
    sink: str


@dataclass(frozen=True)
class RegistryLegacyRelocation:
    """One reviewed module-prefix move for fields already in the legacy baseline."""

    from_prefix: str
    to_prefix: str


@dataclass(frozen=True)
class RegistryField:
    symbol: str
    aliases: tuple[str, ...]
    metadata: Mapping[str, object]

    @property
    def category(self) -> str:
        return str(self.metadata["category"])

    @property
    def is_exception(self) -> bool:
        return str(self.metadata["status"]) == "temporary_exception"


@dataclass(frozen=True)
class Registry:
    manifests: tuple[RegistryManifest, ...]
    legacy_relocations: tuple[RegistryLegacyRelocation, ...]
    fields: tuple[RegistryField, ...]

    @property
    def by_locator(self) -> dict[str, RegistryField]:
        result: dict[str, RegistryField] = {}
        for item in self.fields:
            result[item.symbol] = item
            result.update((alias, item) for alias in item.aliases)
        return result


@dataclass(frozen=True)
class Baseline:
    source_ref: str
    symbols: tuple[str, ...]


@dataclass(frozen=True)
class Violation:
    code: str
    message: str
    remediation: str
    symbols: tuple[str, ...] = ()
    occurrences: tuple[Occurrence, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "occurrences": [occurrence.as_dict() for occurrence in self.occurrences],
            "remediation": self.remediation,
            "symbol": self.symbols[0] if len(self.symbols) == 1 else None,
            "symbols": list(self.symbols),
        }


@dataclass(frozen=True)
class Finding:
    candidate: Candidate
    state: str
    registry_symbol: str | None
    metadata: Mapping[str, object]

    def as_dict(self) -> dict[str, object]:
        return {
            **self.candidate.as_dict(),
            "metadata": dict(sorted(self.metadata.items())),
            "registry_symbol": self.registry_symbol,
            "state": self.state,
        }


@dataclass(frozen=True)
class AuditReport:
    findings: tuple[Finding, ...]
    violations: tuple[Violation, ...]
    groups: Mapping[str, Mapping[str, tuple[str, ...]]]
    baseline_count: int
    registered_count: int
    base_ref: str | None = None

    @property
    def passed(self) -> bool:
        return not self.violations

    def as_dict(self) -> dict[str, object]:
        return {
            "base_revision": self.base_ref,
            "findings": [finding.as_dict() for finding in self.findings],
            "groups": {
                group: {name: list(symbols) for name, symbols in sorted(values.items())}
                for group, values in sorted(self.groups.items())
            },
            "summary": {
                "baseline": self.baseline_count,
                "discovered": len(self.findings),
                "passed": self.passed,
                "registered": self.registered_count,
                "violations": len(self.violations),
            },
            "violations": [violation.as_dict() for violation in self.violations],
        }


@dataclass(frozen=True)
class _SourceUnit:
    relative_path: str
    module: str
    text: str


@dataclass
class _ClassInfo:
    unit: _SourceUnit
    node: ast.ClassDef
    qualified_name: str
    bases: tuple[str, ...]
    decorators: tuple[str, ...]
    kind: str | None = None
    content_addressed: bool = False

    @property
    def symbol(self) -> str:
        return f"{self.unit.module}.{self.qualified_name}"


@dataclass(frozen=True)
class _RawField:
    owner: str
    name: str
    wire_name: str
    surface: str
    annotation: str
    occurrence: Occurrence
    inherited: bool = False


@dataclass(frozen=True)
class _ModelShape:
    owner: str
    fields: tuple[_RawField, ...]
    artifact_ref_fields: tuple[str, ...]
    occurrence: Occurrence


@dataclass(frozen=True)
class _Discovery:
    candidates: tuple[Candidate, ...]
    model_shapes: tuple[_ModelShape, ...]
    boundary_violations: tuple[Violation, ...] = ()


@dataclass(frozen=True)
class _MappingEntry:
    key: str | None
    value: ast.AST
    line: int


@dataclass
class _MappingBuilder:
    variable: str | None
    entries: list[_MappingEntry]
    node: ast.AST
    surface: bool = False
    forced_contract: str | None = None


@dataclass(frozen=True)
class _ModuleInfo:
    unit: _SourceUnit
    tree: ast.Module
    imports: Mapping[str, str]
    constants: Mapping[str, ast.AST]


def _split_words(name: str) -> tuple[str, ...]:
    expanded = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name)
    return tuple(part for part in re.split(r"[^a-zA-Z0-9]+", expanded.lower()) if part)


def is_candidate_name(name: str) -> bool:
    """Return true when a field or wire name has a provenance-shaped token."""
    words = _split_words(name)
    if not words:
        return False
    normalized = "_".join(words)
    if normalized.endswith("_at") or normalized.endswith("_date"):
        return True
    return any(word in _PROVENANCE_TOKENS or word.removesuffix("s") in _PROVENANCE_TOKENS for word in words)


def _is_version_field_name(name: str) -> bool:
    return "version" in _split_words(name)


def _hash_shaped_name(name: str) -> bool:
    return bool(set(_split_words(name)) & _HASH_KEY_PARTS)


def _node_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _node_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    if isinstance(node, ast.Subscript):
        return _node_name(node.value)
    if isinstance(node, ast.Call):
        return _node_name(node.func)
    return ""


def _resolve_name(name: str, module: _ModuleInfo) -> str:
    first, separator, rest = name.partition(".")
    resolved = module.imports.get(first)
    if resolved is not None:
        return f"{resolved}.{rest}" if separator else resolved
    if "." not in name:
        return f"{module.unit.module}.{name}"
    return name


def _literal_string(
    node: ast.AST | None, constants: Mapping[str, ast.AST], seen: frozenset[str] = frozenset()
) -> str | None:
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str | int) and not isinstance(node.value, bool):
        return str(node.value)
    if isinstance(node, ast.Name) and node.id in constants and node.id not in seen:
        return _literal_string(constants[node.id], constants, seen | {node.id})
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _literal_string(node.left, constants, seen)
        right = _literal_string(node.right, constants, seen)
        return left + right if left is not None and right is not None else None
    if isinstance(node, ast.JoinedStr):
        pieces: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                pieces.append(value.value)
            elif isinstance(value, ast.FormattedValue):
                part = _literal_string(value.value, constants, seen)
                if part is None:
                    return None
                pieces.append(part)
            else:
                return None
        return "".join(pieces)
    return None


def _module_name(relative_path: str) -> str:
    path = Path(relative_path).with_suffix("")
    parts = path.parts
    if parts[:2] == ("src", "aec_bench"):
        module_parts = parts[1:]
    elif parts and parts[0] == "scripts":
        module_parts = parts
    else:
        raise ProvenanceInputError(f"Source path is outside maintained roots: {relative_path}")
    if module_parts[-1] == "__init__":
        module_parts = module_parts[:-1]
    return ".".join(module_parts)


def _source_units(repository_root: Path) -> tuple[_SourceUnit, ...]:
    units: list[_SourceUnit] = []
    for root in (repository_root / "src" / "aec_bench", repository_root / "scripts"):
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            relative = path.relative_to(repository_root)
            if relative.as_posix() == _SELF_PATH or set(relative.parts) & _IGNORED_PATH_PARTS:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as error:
                raise ProvenanceInputError(f"Cannot read maintained Python source {relative}: {error}") from error
            units.append(_SourceUnit(relative.as_posix(), _module_name(relative.as_posix()), text))
    if not units:
        raise ProvenanceInputError(f"No maintained Python source was found under {repository_root}")
    return tuple(units)


def _parse_modules(units: Iterable[_SourceUnit]) -> tuple[_ModuleInfo, ...]:
    result: list[_ModuleInfo] = []
    for unit in sorted(units, key=lambda item: item.relative_path):
        try:
            tree = ast.parse(unit.text, filename=unit.relative_path)
        except SyntaxError as error:
            raise ProvenanceInputError(
                f"Cannot parse maintained Python source {unit.relative_path}:{error.lineno}: {error.msg}"
            ) from error
        imports: dict[str, str] = {}
        constants: dict[str, ast.AST] = {}
        package = unit.module if unit.relative_path.endswith("/__init__.py") else unit.module.rpartition(".")[0]
        for statement in tree.body:
            if isinstance(statement, ast.Import):
                for alias in statement.names:
                    imports[alias.asname or alias.name.split(".", maxsplit=1)[0]] = alias.name
            elif isinstance(statement, ast.ImportFrom):
                imported_module = statement.module or ""
                if statement.level:
                    relative = "." * statement.level + imported_module
                    try:
                        imported_module = importlib.util.resolve_name(relative, package)
                    except (ImportError, ValueError):
                        imported_module = ""
                for alias in statement.names:
                    if alias.name != "*" and imported_module:
                        imports[alias.asname or alias.name] = f"{imported_module}.{alias.name}"
            elif isinstance(statement, ast.Assign):
                for target in statement.targets:
                    if isinstance(target, ast.Name):
                        constants[target.id] = statement.value
            elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name) and statement.value:
                constants[statement.target.id] = statement.value
        result.append(_ModuleInfo(unit=unit, tree=tree, imports=imports, constants=constants))
    return tuple(result)


def _resolve_project_constants(modules: Iterable[_ModuleInfo]) -> tuple[_ModuleInfo, ...]:
    module_list = tuple(modules)
    resolved: dict[str, str] = {}
    changed = True
    while changed:
        changed = False
        for module in module_list:
            context = dict(module.constants)
            for alias, imported in module.imports.items():
                if imported in resolved:
                    context[alias] = ast.Constant(resolved[imported])
            for name, node in module.constants.items():
                value = _literal_string(node, context)
                locator = f"{module.unit.module}.{name}"
                if value is not None and resolved.get(locator) != value:
                    resolved[locator] = value
                    context[name] = ast.Constant(value)
                    changed = True

    result: list[_ModuleInfo] = []
    for module in module_list:
        constants = dict(module.constants)
        for alias, imported in module.imports.items():
            if imported in resolved:
                constants[alias] = ast.Constant(resolved[imported])
        for name in module.constants:
            if value := resolved.get(f"{module.unit.module}.{name}"):
                constants[name] = ast.Constant(value)
        result.append(_ModuleInfo(module.unit, module.tree, module.imports, constants))
    return tuple(result)


def _forbidden_actor_identity_name(name: str) -> bool:
    words = _split_words(name)
    normalized = "_".join(words)
    return (
        normalized == "request_id"
        or normalized.endswith("_request_id")
        or bool(set(words) & {"correlation", "provider", "transport"})
    )


def _request_value_uses_forbidden_identity(node: ast.AST, constants: Mapping[str, ast.AST]) -> str | None:
    for child in ast.walk(node):
        name = _node_name(child)
        if name.startswith("request."):
            request_field = name.split(".", maxsplit=2)[1]
            if _forbidden_actor_identity_name(request_field):
                return name
        if isinstance(child, ast.Subscript) and _node_name(child.value).startswith("request"):
            key = _literal_string(child.slice, constants)
            if key is not None and _forbidden_actor_identity_name(key):
                return f"request[{key!r}]"
    return None


def _direct_expression_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _direct_expression_name(node.value)
        return f"{prefix}.{node.attr}" if prefix is not None else None
    return None


def _actor_request_fingerprint_violations(modules: Iterable[_ModuleInfo]) -> tuple[Violation, ...]:
    boundary = "aec_bench.harness.world_actor.authority._request_fingerprint"
    violations: list[Violation] = []
    for module in modules:
        if module.unit.module != "aec_bench.harness.world_actor.authority":
            continue
        function = next(
            (
                statement
                for statement in module.tree.body
                if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef)
                and statement.name == "_request_fingerprint"
            ),
            None,
        )
        if function is None:
            return (
                Violation(
                    code="PROV008",
                    message="Actor request fingerprint canonicalizer is missing from its authority module.",
                    remediation=(
                        "Restore `_request_fingerprint` with one statically visible transport-neutral canonical "
                        "payload."
                    ),
                    symbols=(boundary,),
                    occurrences=(Occurrence(module.unit.relative_path, 1, "actor_request_fingerprint"),),
                ),
            )
        payloads = [
            call.args[0]
            for call in ast.walk(function)
            if isinstance(call, ast.Call)
            and _tail(_node_name(call.func)) == "_json_sha256"
            and call.args
            and isinstance(call.args[0], ast.Dict)
        ]
        if len(payloads) != 1:
            return (
                Violation(
                    code="PROV008",
                    message=(
                        "Actor request fingerprint must have exactly one statically visible canonical dictionary; "
                        f"found {len(payloads)}."
                    ),
                    remediation=(
                        "Pass one literal canonical payload to `_json_sha256` so policy can verify its exact reviewed "
                        "field set and excluded identity fields."
                    ),
                    symbols=(boundary,),
                    occurrences=(Occurrence(module.unit.relative_path, function.lineno, "actor_request_fingerprint"),),
                ),
            )
        for payload in payloads:
            payload_keys = [_literal_string(key_node, module.constants) for key_node in payload.keys]
            if len(payload_keys) != len(_ACTOR_REQUEST_FINGERPRINT_KEYS) or set(payload_keys) != (
                _ACTOR_REQUEST_FINGERPRINT_KEYS
            ):
                rendered_keys = ", ".join(sorted(key or "<dynamic>" for key in payload_keys))
                expected_keys = ", ".join(sorted(_ACTOR_REQUEST_FINGERPRINT_KEYS))
                violations.append(
                    Violation(
                        code="PROV008",
                        message=(
                            "Actor request fingerprint canonical keys differ from the reviewed boundary: "
                            f"found [{rendered_keys}], expected [{expected_keys}]."
                        ),
                        remediation=(
                            "Keep the canonical payload limited to semantics, actor_principal_id, decision_id, "
                            "action_name, and arguments. Update the provenance policy and its tests before changing "
                            "this identity boundary."
                        ),
                        symbols=(boundary,),
                        occurrences=(
                            Occurrence(module.unit.relative_path, payload.lineno, "actor_request_fingerprint"),
                        ),
                    )
                )
            for key_node, value_node in zip(payload.keys, payload.values, strict=True):
                key = _literal_string(key_node, module.constants)
                expected_expression = _ACTOR_REQUEST_FINGERPRINT_EXPRESSIONS.get(key or "")
                actual_expression = _direct_expression_name(value_node)
                if expected_expression is not None and actual_expression != expected_expression:
                    violations.append(
                        Violation(
                            code="PROV008",
                            message=(
                                f"Actor request fingerprint key {key!r} uses expression "
                                f"{actual_expression or '<computed>'!r}; expected {expected_expression!r}."
                            ),
                            remediation=(
                                "Use the exact reviewed canonical expression. Do not route actor identity through "
                                "aliases, helpers, correlation data, provider data, or transport data."
                            ),
                            symbols=(boundary,),
                            occurrences=(
                                Occurrence(
                                    module.unit.relative_path,
                                    getattr(value_node, "lineno", payload.lineno),
                                    "actor_request_fingerprint",
                                ),
                            ),
                        )
                    )
                if key is not None and _forbidden_actor_identity_name(key):
                    violations.append(
                        Violation(
                            code="PROV008",
                            message=f"Actor request fingerprint payload includes forbidden identity key {key!r}.",
                            remediation=(
                                "Remove request IDs, provider data, correlation data, and transport data from the "
                                "logical actor-request fingerprint."
                            ),
                            symbols=(boundary,),
                            occurrences=(
                                Occurrence(
                                    module.unit.relative_path,
                                    getattr(key_node, "lineno", payload.lineno),
                                    "actor_request_fingerprint",
                                ),
                            ),
                        )
                    )
                forbidden_value = _request_value_uses_forbidden_identity(value_node, module.constants)
                if forbidden_value is not None:
                    violations.append(
                        Violation(
                            code="PROV008",
                            message=(
                                "Actor request fingerprint payload includes forbidden request member "
                                f"{forbidden_value}."
                            ),
                            remediation=(
                                "Use only transport-neutral logical request members in the canonical fingerprint "
                                "payload."
                            ),
                            symbols=(boundary,),
                            occurrences=(
                                Occurrence(
                                    module.unit.relative_path,
                                    getattr(value_node, "lineno", payload.lineno),
                                    "actor_request_fingerprint",
                                ),
                            ),
                        )
                    )
        return tuple(sorted(violations, key=lambda item: (item.occurrences, item.message)))
    return ()


def inspect_actor_request_fingerprint(repository_root: Path) -> tuple[Violation, ...]:
    """Inspect the production actor request fingerprint without importing repository modules."""
    units = tuple(
        unit
        for unit in _source_units(Path(repository_root).resolve())
        if unit.module == "aec_bench.harness.world_actor.authority"
    )
    if not units:
        return ()
    modules = _resolve_project_constants(_parse_modules(units))
    return _actor_request_fingerprint_violations(modules)


def _class_qualnames(tree: ast.Module) -> list[tuple[ast.ClassDef, str]]:
    result: list[tuple[ast.ClassDef, str]] = []

    def visit(statements: Iterable[ast.stmt], prefix: str = "") -> None:
        for statement in statements:
            if isinstance(statement, ast.ClassDef):
                qualified = f"{prefix}.{statement.name}" if prefix else statement.name
                result.append((statement, qualified))
                visit(statement.body, qualified)
            elif isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef):
                qualified = f"{prefix}.{statement.name}" if prefix else statement.name
                visit(statement.body, f"{qualified}.<locals>")

    visit(tree.body)
    return result


def _decorator_name(decorator: ast.AST) -> str:
    return _node_name(decorator.func if isinstance(decorator, ast.Call) else decorator)


def _collect_classes(modules: Iterable[_ModuleInfo]) -> dict[str, _ClassInfo]:
    result: dict[str, _ClassInfo] = {}
    for module in modules:
        for node, qualified_name in _class_qualnames(module.tree):
            bases = tuple(_resolve_name(_node_name(base), module) for base in node.bases if _node_name(base))
            decorators = tuple(_resolve_name(_decorator_name(decorator), module) for decorator in node.decorator_list)
            info = _ClassInfo(module.unit, node, qualified_name, bases, decorators)
            result[info.symbol] = info
    return result


def _tail(name: str) -> str:
    return name.rsplit(".", maxsplit=1)[-1]


def _resolve_class_kinds(classes: Mapping[str, _ClassInfo]) -> None:
    for item in classes.values():
        base_tails = {_tail(base) for base in item.bases}
        decorator_tails = {_tail(decorator) for decorator in item.decorators}
        if "TypedDict" in base_tails:
            item.kind = "typed_dict"
        elif "dataclass" in decorator_tails:
            item.kind = "dataclass"
        elif base_tails & (_MODEL_BASE_NAMES | _CONTENT_ADDRESSED_BASE_NAMES):
            item.kind = "pydantic"
        item.content_addressed = bool(base_tails & _CONTENT_ADDRESSED_BASE_NAMES) and (
            item.node.name not in _CONTENT_ADDRESSED_BASE_NAMES
        )

    changed = True
    while changed:
        changed = False
        for item in classes.values():
            for base in item.bases:
                parent = classes.get(base)
                if parent is None:
                    continue
                if item.kind is None and parent.kind is not None:
                    item.kind = parent.kind
                    changed = True
                if not item.content_addressed and (
                    parent.content_addressed or parent.node.name in _CONTENT_ADDRESSED_BASE_NAMES
                ):
                    item.content_addressed = item.node.name not in _CONTENT_ADDRESSED_BASE_NAMES
                    changed = True


def _literal_aliases(node: ast.AST | None, module: _ModuleInfo) -> tuple[str, ...]:
    if node is None:
        return ()
    result: list[str] = []
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        call_name = _tail(_resolve_name(_node_name(child.func), module))
        if call_name not in {
            "AliasChoices",
            "AliasPath",
            "Field",
            "computed_field",
        }:
            continue
        if call_name in {"AliasChoices", "AliasPath"}:
            values = (_literal_string(argument, module.constants) for argument in child.args)
            result.extend(value for value in values if value is not None)
            continue
        keyword_order = ("serialization_alias", "alias", "validation_alias")
        keywords = {keyword.arg: keyword.value for keyword in child.keywords if keyword.arg is not None}
        for keyword in keyword_order:
            value = _literal_string(keywords.get(keyword), module.constants)
            if value is not None:
                result.append(value)
    return tuple(dict.fromkeys(result))


def _annotation_text(node: ast.AST | None) -> str:
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except (AttributeError, ValueError):
        return ""


def _class_fields(item: _ClassInfo, module: _ModuleInfo) -> tuple[_RawField, ...]:
    fields: list[_RawField] = []
    if item.kind is None:
        return ()
    for statement in item.node.body:
        if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            name = statement.target.id
            if name.startswith("_") or "ClassVar" in _annotation_text(statement.annotation):
                continue
            aliases = _literal_aliases(statement.annotation, module) + _literal_aliases(statement.value, module)
            wire_name = aliases[0] if aliases else name
            fields.append(
                _RawField(
                    owner=item.symbol,
                    name=name,
                    wire_name=wire_name,
                    surface=item.kind,
                    annotation=_annotation_text(statement.annotation),
                    occurrence=Occurrence(item.unit.relative_path, statement.lineno, item.kind),
                )
            )
        elif isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef):
            computed = next(
                (
                    decorator
                    for decorator in statement.decorator_list
                    if _tail(_resolve_name(_decorator_name(decorator), module)) == "computed_field"
                ),
                None,
            )
            if computed is None:
                continue
            aliases = _literal_aliases(computed, module)
            wire_name = aliases[0] if aliases else statement.name
            fields.append(
                _RawField(
                    owner=item.symbol,
                    name=statement.name,
                    wire_name=wire_name,
                    surface="pydantic_computed_field",
                    annotation=_annotation_text(statement.returns),
                    occurrence=Occurrence(item.unit.relative_path, statement.lineno, "pydantic_computed_field"),
                )
            )
    if item.content_addressed and not any(model_field.name == "content_sha256" for model_field in fields):
        fields.append(
            _RawField(
                owner=item.symbol,
                name="content_sha256",
                wire_name="content_sha256",
                surface="pydantic_inherited",
                annotation="str",
                occurrence=Occurrence(item.unit.relative_path, item.node.lineno, "inherited_content_address"),
                inherited=True,
            )
        )
    return tuple(fields)


def _functional_typed_dict_fields(module: _ModuleInfo) -> tuple[_RawField, ...]:
    fields: list[_RawField] = []
    for statement in module.tree.body:
        target: ast.Name | None = None
        value: ast.AST | None = None
        if (
            isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name)
        ):
            target = statement.targets[0]
            value = statement.value
        elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            target = statement.target
            value = statement.value
        if target is None or not isinstance(value, ast.Call):
            continue
        if _tail(_resolve_name(_node_name(value.func), module)) != "TypedDict":
            continue
        owner = f"{module.unit.module}.{target.id}"
        if len(value.args) >= 2 and isinstance(value.args[1], ast.Dict):
            for key, annotation in zip(value.args[1].keys, value.args[1].values, strict=True):
                name = _literal_string(key, module.constants)
                if name is None:
                    continue
                fields.append(
                    _RawField(
                        owner=owner,
                        name=name,
                        wire_name=name,
                        surface="typed_dict",
                        annotation=_annotation_text(annotation),
                        occurrence=Occurrence(
                            module.unit.relative_path, getattr(key, "lineno", statement.lineno), "typed_dict"
                        ),
                    )
                )
        for keyword in value.keywords:
            keyword_name = keyword.arg
            if keyword_name not in {None, "total", "closed"}:
                assert keyword_name is not None
                fields.append(
                    _RawField(
                        owner=owner,
                        name=keyword_name,
                        wire_name=keyword_name,
                        surface="typed_dict",
                        annotation=_annotation_text(keyword.value),
                        occurrence=Occurrence(module.unit.relative_path, keyword.value.lineno, "typed_dict"),
                    )
                )
    return tuple(fields)


def _mapping_entries(node: ast.AST, module: _ModuleInfo) -> list[_MappingEntry] | None:
    if isinstance(node, ast.Dict):
        result: list[_MappingEntry] = []
        for key, value in zip(node.keys, node.values, strict=True):
            if key is None:
                result.append(_MappingEntry(None, value, getattr(value, "lineno", node.lineno)))
                continue
            name = _literal_string(key, module.constants)
            if name is None:
                return None
            result.append(_MappingEntry(name, value, getattr(key, "lineno", node.lineno)))
        return result
    if isinstance(node, ast.Call) and _tail(_node_name(node.func)) == "dict" and not node.args:
        if any(keyword.arg is None for keyword in node.keywords):
            return None
        return [_MappingEntry(keyword.arg or "", keyword.value, keyword.value.lineno) for keyword in node.keywords]
    return None


def _direct_scopes(tree: ast.Module) -> list[tuple[str, list[ast.stmt], ast.AST]]:
    result: list[tuple[str, list[ast.stmt], ast.AST]] = [("<module>", tree.body, tree)]

    def visit(statements: Iterable[ast.stmt], prefix: str = "") -> None:
        for statement in statements:
            if isinstance(statement, ast.ClassDef):
                qualified = f"{prefix}.{statement.name}" if prefix else statement.name
                visit(statement.body, qualified)
            elif isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef):
                qualified = f"{prefix}.{statement.name}" if prefix else statement.name
                result.append((qualified, statement.body, statement))
                visit(statement.body, f"{qualified}.<locals>")

    visit(tree.body)
    return result


def _scope_nodes(statements: Iterable[ast.stmt]) -> Iterable[ast.AST]:
    """Yield nodes in one lexical scope without entering nested definitions."""
    stack: list[ast.AST] = list(reversed(tuple(statements)))
    while stack:
        node = stack.pop()
        yield node
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
            continue
        stack.extend(reversed(list(ast.iter_child_nodes(node))))


def _assigned_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    return None


def _subscript_key(node: ast.Subscript, module: _ModuleInfo) -> tuple[str, str] | None:
    if not isinstance(node.value, ast.Name):
        return None
    key = _literal_string(node.slice, module.constants)
    return (node.value.id, key) if key is not None else None


def _call_matches_sink(call_name: str, sink: str, *, caller_owner: str) -> bool:
    normalized_sink = sink.replace(":", ".")
    if (
        call_name == normalized_sink
        or call_name.endswith(f".{normalized_sink}")
        or normalized_sink.endswith(f".{call_name}")
    ):
        return True
    receiver, separator, method = call_name.rpartition(".")
    sink_owner, sink_separator, sink_method = normalized_sink.rpartition(".")
    if not separator or not sink_separator or method != sink_method:
        return False
    if receiver in {"self", "cls"}:
        return caller_owner == sink_owner
    sink_owner_name = sink_owner.rsplit(".", maxsplit=1)[-1]
    return receiver in {sink_owner, sink_owner_name} and caller_owner == sink_owner


def _matching_manifest_contracts(
    rules: Iterable[RegistryManifest],
    *,
    scope_name: str,
    module_name: str,
    call_name: str | None = None,
) -> tuple[str, ...]:
    full_scope = module_name if scope_name == "<module>" else f"{module_name}.{scope_name}"
    scope_owner, separator, _scope_leaf = full_scope.rpartition(".")
    caller_owner = scope_owner if separator else module_name
    matches: list[str] = []
    for rule in rules:
        if _call_matches_sink(full_scope, rule.sink, caller_owner=caller_owner) or (
            call_name is not None and _call_matches_sink(call_name, rule.sink, caller_owner=caller_owner)
        ):
            matches.append(rule.contract)
    return tuple(sorted(set(matches)))


def _persistence_call(name: str) -> bool:
    words = set(_split_words(name))
    return bool(words & _PERSISTENCE_CALL_PARTS) and not words & {"hash", "sha", "sha256"}


def _literal_parameter_bindings(module: _ModuleInfo) -> dict[str, dict[str, ast.AST]]:
    scopes = _direct_scopes(module.tree)
    definitions = {
        scope_name: scope_node
        for scope_name, _statements, scope_node in scopes
        if isinstance(scope_node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    observed: dict[tuple[str, str], list[str | None]] = defaultdict(list)
    for caller_scope, statements, _scope_node in scopes:
        caller_owner, _separator, _leaf = caller_scope.rpartition(".")
        for node in _scope_nodes(statements):
            if not isinstance(node, ast.Call):
                continue
            call_name = _node_name(node.func)
            receiver, separator, method = call_name.rpartition(".")
            if separator and receiver in {"self", "cls"} and caller_owner:
                target_name = f"{caller_owner}.{method}"
            elif not separator:
                target_name = call_name
            else:
                continue
            target = definitions.get(target_name)
            if target is None:
                continue
            parameters = [*target.args.posonlyargs, *target.args.args]
            if parameters and parameters[0].arg in {"self", "cls"}:
                parameters = parameters[1:]
            for parameter, argument in zip(parameters, node.args, strict=False):
                observed[(target_name, parameter.arg)].append(_literal_string(argument, module.constants))
            keyword_arguments = {keyword.arg: keyword.value for keyword in node.keywords if keyword.arg is not None}
            for parameter in parameters[len(node.args) :]:
                if keyword_argument := keyword_arguments.get(parameter.arg):
                    observed[(target_name, parameter.arg)].append(_literal_string(keyword_argument, module.constants))

    bindings: dict[str, dict[str, ast.AST]] = defaultdict(dict)
    for (scope_name, parameter_name), values in observed.items():
        if values and None not in values and len(set(values)) == 1:
            bindings[scope_name][parameter_name] = ast.Constant(values[0])
    return dict(bindings)


def _mapping_builders(
    module: _ModuleInfo,
    scope_name: str,
    statements: list[ast.stmt],
    rules: tuple[RegistryManifest, ...],
) -> tuple[_MappingBuilder, ...]:
    builders: list[_MappingBuilder] = []
    by_variable: dict[str, _MappingBuilder] = {}
    anonymous_by_node: dict[int, _MappingBuilder] = {}
    scope_contracts = _matching_manifest_contracts(
        rules,
        scope_name=scope_name,
        module_name=module.unit.module,
    )

    for node in _scope_nodes(statements):
        value: ast.AST | None = None
        target: ast.AST | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        elif isinstance(node, ast.AnnAssign):
            target, value = node.target, node.value
        if value is not None and target is not None:
            entries = _mapping_entries(value, module)
            variable = _assigned_name(target)
            copied_from: _MappingBuilder | None = None
            if isinstance(value, ast.Name):
                copied_from = by_variable.get(value.id)
            elif (
                isinstance(value, ast.Call)
                and _tail(_node_name(value.func)) == "dict"
                and len(value.args) == 1
                and isinstance(value.args[0], ast.Name)
                and not value.keywords
            ):
                copied_from = by_variable.get(value.args[0].id)
            if variable is not None and (entries is not None or copied_from is not None):
                if entries is not None:
                    selected_entries = entries
                else:
                    assert copied_from is not None
                    selected_entries = list(copied_from.entries)
                builder = _MappingBuilder(variable=variable, entries=selected_entries, node=value)
                builders.append(builder)
                by_variable[variable] = builder
            elif isinstance(target, ast.Subscript) and (key := _subscript_key(target, module)) is not None:
                variable_name, field_name = key
                existing_builder = by_variable.get(variable_name)
                if existing_builder is not None:
                    existing_builder.entries.append(_MappingEntry(field_name, value, target.lineno))

        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "update":
            if isinstance(node.func.value, ast.Name) and len(node.args) == 1:
                updated_builder = by_variable.get(node.func.value.id)
                entries = _mapping_entries(node.args[0], module)
                if updated_builder is not None and entries is not None:
                    updated_builder.entries.extend(entries)

    def expand_entries(
        entries: Iterable[_MappingEntry],
        seen_variables: frozenset[str] = frozenset(),
    ) -> list[_MappingEntry]:
        expanded: list[_MappingEntry] = []
        for entry in entries:
            if entry.key is not None:
                expanded.append(entry)
                continue
            nested_entries = _mapping_entries(entry.value, module)
            if nested_entries is not None:
                expanded.extend(expand_entries(nested_entries, seen_variables))
                continue
            if isinstance(entry.value, ast.Name) and entry.value.id not in seen_variables:
                source = by_variable.get(entry.value.id)
                if source is not None:
                    expanded.extend(expand_entries(source.entries, seen_variables | {entry.value.id}))
        return expanded

    for builder in builders:
        initial_seen = frozenset({builder.variable}) if builder.variable is not None else frozenset()
        builder.entries = expand_entries(builder.entries, initial_seen)

    def anonymous(node: ast.AST) -> _MappingBuilder | None:
        entries = _mapping_entries(node, module)
        if entries is None:
            return None
        entries = expand_entries(entries)
        identifier = id(node)
        if identifier not in anonymous_by_node:
            anonymous_by_node[identifier] = _MappingBuilder(variable=None, entries=entries, node=node)
            builders.append(anonymous_by_node[identifier])
        return anonymous_by_node[identifier]

    def selected_builder(node: ast.AST) -> _MappingBuilder | None:
        if isinstance(node, ast.Name):
            return by_variable.get(node.id)
        if (
            isinstance(node, ast.Call)
            and _tail(_node_name(node.func)) == "dict"
            and len(node.args) == 1
            and isinstance(node.args[0], ast.Name)
            and not node.keywords
        ):
            return by_variable.get(node.args[0].id)
        return anonymous(node)

    for node in _scope_nodes(statements):
        if isinstance(node, ast.Return) and node.value is not None:
            selected = selected_builder(node.value)
            if selected is not None:
                selected.surface = True
                if scope_contracts:
                    selected.forced_contract = scope_contracts[0]
        elif isinstance(node, ast.Call):
            call_name = _resolve_name(_node_name(node.func), module)
            contracts = _matching_manifest_contracts(
                rules,
                scope_name=scope_name,
                module_name=module.unit.module,
                call_name=call_name,
            )
            is_sink = _persistence_call(call_name) or bool(contracts)
            if not is_sink:
                continue
            for argument in (*node.args, *(keyword.value for keyword in node.keywords)):
                selected = selected_builder(argument)
                if selected is not None:
                    selected.surface = True
                    if contracts:
                        selected.forced_contract = contracts[0]

    for builder in builders:
        if _manifest_contract(builder.entries, module) is not None:
            builder.surface = True
        if scope_contracts and builder.surface:
            builder.forced_contract = builder.forced_contract or scope_contracts[0]
    return tuple(builders)


def _entry_value(entries: Iterable[_MappingEntry], names: set[str], module: _ModuleInfo) -> str | None:
    for entry in reversed(tuple(entries)):
        if entry.key in names:
            value = _literal_string(entry.value, module.constants)
            if value is not None:
                return value
    return None


def _manifest_contract(entries: Iterable[_MappingEntry], module: _ModuleInfo) -> str | None:
    entry_list = tuple(entries)
    for key in _CONTRACT_KEY_PRIORITY:
        if value := _entry_value(entry_list, {key}, module):
            return value
    return None


def _manifest_candidates(
    modules: Iterable[_ModuleInfo],
    rules: tuple[RegistryManifest, ...],
    declared_locators: frozenset[str],
) -> tuple[Candidate, ...]:
    occurrences: dict[str, list[Occurrence]] = defaultdict(list)
    details: dict[str, tuple[str, str, str, str]] = {}

    def add_entries(
        *,
        entries: Iterable[_MappingEntry],
        module: _ModuleInfo,
        scope_name: str,
        contract: str | None,
        record_type: str,
        prefix: tuple[str, ...] = (),
    ) -> None:
        entry_list = tuple(entries)
        for entry in entry_list:
            if entry.key is None:
                unpacked = _mapping_entries(entry.value, module)
                if unpacked is not None:
                    add_entries(
                        entries=unpacked,
                        module=module,
                        scope_name=scope_name,
                        contract=contract,
                        record_type=record_type,
                        prefix=prefix,
                    )
                continue
            path = (*prefix, entry.key)
            nested = _mapping_entries(entry.value, module)
            nested_record_type = record_type
            if nested is not None:
                nested_record_type = _entry_value(nested, {"record_type"}, module) or record_type
                add_entries(
                    entries=nested,
                    module=module,
                    scope_name=scope_name,
                    contract=contract,
                    record_type=nested_record_type,
                    prefix=path,
                )
            nested_key = ".".join(path)
            if contract is not None:
                discriminator = not prefix and entry.key in {"schema", "schema_id", "schema_version"}
                carrier_type = "*" if discriminator else record_type
                symbol = f"manifest:{contract}[{carrier_type}].{nested_key}"
                surface = "manifest_key"
            else:
                owner = module.unit.module if scope_name == "<module>" else f"{module.unit.module}.{scope_name}"
                symbol = f"mapping:{owner}.{nested_key}"
                surface = "mapping_key"
            if not is_candidate_name(entry.key) and symbol not in declared_locators:
                continue
            occurrence = Occurrence(module.unit.relative_path, entry.line, surface)
            occurrences[symbol].append(occurrence)
            details[symbol] = (entry.key, surface, symbol.rsplit(".", maxsplit=1)[0], nested_key)

    for module in modules:
        parameter_bindings = _literal_parameter_bindings(module)
        for scope_name, statements, _scope_node in _direct_scopes(module.tree):
            scope_constants = {**module.constants, **parameter_bindings.get(scope_name, {})}
            scope_module = _ModuleInfo(module.unit, module.tree, module.imports, scope_constants)
            for builder in _mapping_builders(scope_module, scope_name, statements, rules):
                if not builder.surface or not builder.entries:
                    continue
                contract = builder.forced_contract or _manifest_contract(builder.entries, scope_module)
                record_type = _entry_value(builder.entries, {"record_type"}, scope_module) or "*"
                add_entries(
                    entries=builder.entries,
                    module=scope_module,
                    scope_name=scope_name,
                    contract=contract,
                    record_type=record_type,
                )

    return tuple(
        Candidate(
            symbol=symbol,
            wire_name=details[symbol][0],
            surface=details[symbol][1],
            occurrences=tuple(sorted(set(items))),
            owner=details[symbol][2],
            field_name=details[symbol][3],
        )
        for symbol, items in sorted(occurrences.items())
    )


def _discover_from_units(
    units: Iterable[_SourceUnit],
    manifest_rules: tuple[RegistryManifest, ...] = (),
    declared_locators: frozenset[str] = frozenset(),
) -> _Discovery:
    modules = _resolve_project_constants(_parse_modules(units))
    classes = _collect_classes(modules)
    _resolve_class_kinds(classes)
    modules_by_name = {module.unit.module: module for module in modules}
    raw_fields: list[_RawField] = []
    shapes: list[_ModelShape] = []

    for item in sorted(classes.values(), key=lambda value: value.symbol):
        module = modules_by_name[item.unit.module]
        fields = _class_fields(item, module)
        if item.kind is None:
            continue
        artifact_refs = tuple(
            sorted(
                model_field.name
                for model_field in fields
                if "ArtifactRef" in model_field.annotation
                or model_field.name.endswith(("_artifact_ref", "_artifact_reference"))
            )
        )
        shapes.append(
            _ModelShape(
                owner=item.symbol,
                fields=fields,
                artifact_ref_fields=artifact_refs,
                occurrence=Occurrence(item.unit.relative_path, item.node.lineno, item.kind),
            )
        )
        raw_fields.extend(fields)

    for module in modules:
        functional_fields = _functional_typed_dict_fields(module)
        by_owner: dict[str, list[_RawField]] = defaultdict(list)
        for model_field in functional_fields:
            by_owner[model_field.owner].append(model_field)
            raw_fields.append(model_field)
        for owner, typed_fields in sorted(by_owner.items()):
            shapes.append(
                _ModelShape(
                    owner=owner,
                    fields=tuple(typed_fields),
                    artifact_ref_fields=tuple(
                        sorted(
                            model_field.name for model_field in typed_fields if "ArtifactRef" in model_field.annotation
                        )
                    ),
                    occurrence=typed_fields[0].occurrence,
                )
            )

    candidates_by_symbol: dict[str, list[_RawField]] = defaultdict(list)
    shape_by_owner = {shape.owner: shape for shape in shapes}
    for model_field in raw_fields:
        symbol = f"{model_field.owner}.{model_field.name}"
        if (
            is_candidate_name(model_field.name)
            or is_candidate_name(model_field.wire_name)
            or symbol in declared_locators
        ):
            candidates_by_symbol[symbol].append(model_field)

    model_candidates: list[Candidate] = []
    for symbol, matching_fields in sorted(candidates_by_symbol.items()):
        selected = matching_fields[0]
        shape = shape_by_owner[selected.owner]
        model_candidates.append(
            Candidate(
                symbol=symbol,
                wire_name=selected.wire_name,
                surface=selected.surface,
                occurrences=tuple(sorted({item.occurrence for item in matching_fields})),
                owner=selected.owner,
                field_name=selected.name,
                annotation=selected.annotation,
                inherited=selected.inherited,
                sibling_fields=tuple(sorted(field.name for field in shape.fields)),
                artifact_ref_fields=shape.artifact_ref_fields,
            )
        )

    combined: dict[str, Candidate] = {candidate.symbol: candidate for candidate in model_candidates}
    for candidate in _manifest_candidates(modules, manifest_rules, declared_locators):
        previous = combined.get(candidate.symbol)
        if previous is None:
            combined[candidate.symbol] = candidate
        else:
            combined[candidate.symbol] = Candidate(
                **{
                    **previous.__dict__,
                    "occurrences": tuple(sorted(set(previous.occurrences + candidate.occurrences))),
                }
            )
    return _Discovery(
        candidates=tuple(combined[symbol] for symbol in sorted(combined)),
        model_shapes=tuple(sorted(shapes, key=lambda item: item.owner)),
        boundary_violations=_actor_request_fingerprint_violations(modules),
    )


def discover_candidates(repository_root: Path) -> tuple[Candidate, ...]:
    """Discover provenance-shaped fields by parsing maintained Python source only."""
    root = Path(repository_root).resolve()
    rules: tuple[RegistryManifest, ...] = ()
    declared_locators: frozenset[str] = frozenset()
    registry_path = root / "provenance-registry.toml"
    if registry_path.is_file():
        registry = load_registry(registry_path)
        rules = registry.manifests
        declared_locators = frozenset(registry.by_locator)
    return _discover_from_units(_source_units(root), rules, declared_locators).candidates


def _require_table_list(value: object, label: str) -> list[dict[str, object]]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ProvenanceInputError(f"{label} must be an array of TOML tables")
    return value


def _require_nonempty_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProvenanceInputError(f"{label} must be a non-empty string")
    return value


def load_registry(path: Path) -> Registry:
    """Load and strictly validate the provenance registry."""
    registry_path = Path(path)
    try:
        with registry_path.open("rb") as stream:
            raw = tomllib.load(stream)
    except FileNotFoundError as error:
        raise ProvenanceInputError(f"Provenance registry does not exist: {registry_path}") from error
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ProvenanceInputError(f"Cannot load provenance registry {registry_path}: {error}") from error

    unknown_top_level = sorted(set(raw) - {"schema_version", "manifest", "legacy_relocation", "field"})
    if unknown_top_level:
        raise ProvenanceInputError(f"Provenance registry has unknown top-level keys: {', '.join(unknown_top_level)}")
    if raw.get("schema_version") != REGISTRY_SCHEMA:
        raise ProvenanceInputError(f"Provenance registry schema_version must be {REGISTRY_SCHEMA}")

    manifests: list[RegistryManifest] = []
    manifest_identities: set[tuple[str, str]] = set()
    for index, item in enumerate(_require_table_list(raw.get("manifest"), "manifest"), start=1):
        unknown = sorted(set(item) - _MANIFEST_KEYS)
        if unknown:
            raise ProvenanceInputError(f"manifest #{index} has unknown keys: {', '.join(unknown)}")
        missing = sorted(_MANIFEST_KEYS - set(item))
        if missing:
            raise ProvenanceInputError(f"manifest #{index} is missing keys: {', '.join(missing)}")
        contract = _require_nonempty_string(item["contract"], f"manifest #{index}.contract")
        sink = _require_nonempty_string(item["sink"], f"manifest #{index}.sink")
        identity = (contract, sink)
        if identity in manifest_identities:
            raise ProvenanceInputError(f"Duplicate manifest declaration: {contract} at {sink}")
        manifest_identities.add(identity)
        manifests.append(RegistryManifest(contract=contract, sink=sink))

    legacy_relocations: list[RegistryLegacyRelocation] = []
    previous_relocation: tuple[str, str] | None = None
    for index, item in enumerate(
        _require_table_list(raw.get("legacy_relocation"), "legacy_relocation"),
        start=1,
    ):
        unknown = sorted(set(item) - _LEGACY_RELOCATION_KEYS)
        if unknown:
            raise ProvenanceInputError(f"legacy_relocation #{index} has unknown keys: {', '.join(unknown)}")
        missing = sorted(_LEGACY_RELOCATION_KEYS - set(item))
        if missing:
            raise ProvenanceInputError(f"legacy_relocation #{index} is missing keys: {', '.join(missing)}")
        from_prefix = _require_nonempty_string(item["from_prefix"], f"legacy_relocation #{index}.from_prefix")
        to_prefix = _require_nonempty_string(item["to_prefix"], f"legacy_relocation #{index}.to_prefix")
        if not from_prefix.endswith(".") or not to_prefix.endswith("."):
            raise ProvenanceInputError("legacy relocation prefixes must end with a dot")
        if from_prefix == to_prefix:
            raise ProvenanceInputError("legacy relocation prefixes must differ")
        identity = (to_prefix, from_prefix)
        if previous_relocation is not None and identity <= previous_relocation:
            raise ProvenanceInputError("legacy relocation entries must be sorted and unique by to_prefix")
        if any(
            to_prefix.startswith(existing.to_prefix) or existing.to_prefix.startswith(to_prefix)
            for existing in legacy_relocations
        ):
            raise ProvenanceInputError("legacy relocation destination prefixes must not overlap")
        previous_relocation = identity
        legacy_relocations.append(RegistryLegacyRelocation(from_prefix=from_prefix, to_prefix=to_prefix))

    fields: list[RegistryField] = []
    all_locators: dict[str, str] = {}
    previous_symbol: str | None = None
    for index, item in enumerate(_require_table_list(raw.get("field"), "field"), start=1):
        unknown = sorted(set(item) - _ALL_FIELD_KEYS)
        if unknown:
            raise ProvenanceInputError(f"field #{index} has unknown keys: {', '.join(unknown)}")
        if "symbol" not in item:
            raise ProvenanceInputError(f"field #{index} is missing key: symbol")
        symbol = _require_nonempty_string(item["symbol"], f"field #{index}.symbol")
        if previous_symbol is not None and symbol <= previous_symbol:
            relation = "duplicate" if symbol == previous_symbol else "not sorted"
            raise ProvenanceInputError(f"Registry field symbols are {relation}: {symbol}")
        previous_symbol = symbol

        missing_common = sorted(_COMMON_REQUIRED_KEYS - set(item))
        if missing_common:
            raise ProvenanceInputError(f"Registry field {symbol} is missing keys: {', '.join(missing_common)}")
        category = _require_nonempty_string(item["category"], f"{symbol}.category")
        if category not in _CATEGORY_NAMES:
            raise ProvenanceInputError(f"Registry field {symbol} has unknown category: {category}")
        missing_category = sorted(_CATEGORY_KEYS[category] - set(item))
        if missing_category:
            raise ProvenanceInputError(
                f"Registry field {symbol} is missing {category} keys: {', '.join(missing_category)}"
            )

        status = _require_nonempty_string(item["status"], f"{symbol}.status")
        if status not in _FIELD_STATUSES:
            allowed = ", ".join(sorted(_FIELD_STATUSES))
            raise ProvenanceInputError(f"Registry field {symbol}.status must be one of: {allowed}")
        if status == "temporary_exception":
            missing_exception = sorted(_EXCEPTION_REQUIRED_KEYS - set(item))
            if missing_exception:
                raise ProvenanceInputError(
                    f"Registry field {symbol} is missing temporary-exception keys: {', '.join(missing_exception)}"
                )
            if not set(item) & _EXCEPTION_TARGET_KEYS:
                alternatives = " or ".join(sorted(_EXCEPTION_TARGET_KEYS))
                raise ProvenanceInputError(
                    f"Registry field {symbol} must define {alternatives} for a temporary exception"
                )
        elif set(item) & _EXCEPTION_KEYS:
            extras = ", ".join(sorted(set(item) & _EXCEPTION_KEYS))
            raise ProvenanceInputError(
                f"Registry field {symbol} uses temporary-exception metadata without "
                f"status=temporary_exception: {extras}"
            )

        for key in sorted(_COMMON_REQUIRED_KEYS | _CATEGORY_KEYS[category] | (set(item) & _EXCEPTION_KEYS)):
            value = item[key]
            if key in {"authoritative", "fail_closed"}:
                if not isinstance(value, bool):
                    raise ProvenanceInputError(f"Registry field {symbol}.{key} must be a Boolean")
            elif key == "evidence_levels":
                if (
                    not isinstance(value, list)
                    or not value
                    or any(not isinstance(level, str) or not level.strip() for level in value)
                ):
                    raise ProvenanceInputError(
                        f"Registry field {symbol}.evidence_levels must be a non-empty array of strings"
                    )
                if value != sorted(set(value)):
                    raise ProvenanceInputError(f"Registry field {symbol}.evidence_levels must be sorted and unique")
            else:
                _require_nonempty_string(value, f"{symbol}.{key}")
        if category == "compatibility" and item["compatibility_kind"] not in _COMPATIBILITY_KINDS:
            allowed = ", ".join(sorted(_COMPATIBILITY_KINDS))
            raise ProvenanceInputError(f"Registry field {symbol}.compatibility_kind must be one of: {allowed}")
        field_name = symbol.rsplit(".", maxsplit=1)[-1]
        if (_is_version_field_name(field_name) or _is_version_field_name(str(item["wire_name"]))) and category not in {
            "compatibility",
            "qualification_attestation",
        }:
            raise ProvenanceInputError(
                f"Registry field {symbol} uses a version-shaped field or wire name but category is {category}; "
                "use compatibility with an allowed compatibility_kind, or qualification_attestation"
            )
        if (
            category in {"artifact_integrity", "semantic_commitment"}
            and status == "current"
            and not item["fail_closed"]
        ):
            raise ProvenanceInputError(
                f"Registry field {symbol}.fail_closed must be true unless status=temporary_exception"
            )

        raw_aliases = item.get("aliases", [])
        if not isinstance(raw_aliases, list) or any(
            not isinstance(alias, str) or not alias.strip() for alias in raw_aliases
        ):
            raise ProvenanceInputError(f"Registry field {symbol}.aliases must be an array of non-empty strings")
        aliases = tuple(raw_aliases)
        if list(aliases) != sorted(set(aliases)):
            raise ProvenanceInputError(f"Registry field {symbol}.aliases must be sorted and unique")
        if symbol in aliases:
            raise ProvenanceInputError(f"Registry field {symbol} repeats its symbol as an alias")
        version_aliases = tuple(alias for alias in aliases if _is_version_field_name(alias.rsplit(".", 1)[-1]))
        if version_aliases and category not in {"compatibility", "qualification_attestation"}:
            raise ProvenanceInputError(
                f"Registry field {symbol} has version-shaped alias {version_aliases[0]} but category is {category}; "
                "use compatibility with an allowed compatibility_kind, or qualification_attestation"
            )
        for locator in (symbol, *aliases):
            if previous := all_locators.get(locator):
                raise ProvenanceInputError(f"Registry locator {locator} is declared by both {previous} and {symbol}")
            all_locators[locator] = symbol

        metadata = {key: value for key, value in item.items() if key not in {"symbol", "aliases"}}
        fields.append(RegistryField(symbol=symbol, aliases=aliases, metadata=metadata))
    return Registry(
        tuple(sorted(manifests, key=lambda item: (item.contract, item.sink))),
        tuple(legacy_relocations),
        tuple(fields),
    )


def _baseline_from_mapping(raw: object, label: str) -> Baseline:
    if not isinstance(raw, dict):
        raise ProvenanceInputError(f"{label} must be a JSON object")
    unknown = sorted(set(raw) - {"schema_version", "source_revision", "symbols"})
    if unknown:
        raise ProvenanceInputError(f"{label} has unknown keys: {', '.join(unknown)}")
    missing = sorted({"schema_version", "source_revision", "symbols"} - set(raw))
    if missing:
        raise ProvenanceInputError(f"{label} is missing keys: {', '.join(missing)}")
    if raw["schema_version"] != BASELINE_SCHEMA:
        raise ProvenanceInputError(f"{label} schema_version must be {BASELINE_SCHEMA}")
    source_ref = _require_nonempty_string(raw["source_revision"], f"{label}.source_revision")
    symbols = raw["symbols"]
    if not isinstance(symbols, list) or any(not isinstance(symbol, str) or not symbol for symbol in symbols):
        raise ProvenanceInputError(f"{label}.symbols must be an array of non-empty strings")
    if symbols != sorted(set(symbols)):
        raise ProvenanceInputError(f"{label}.symbols must be sorted and unique")
    return Baseline(source_ref=source_ref, symbols=tuple(symbols))


def load_baseline(path: Path) -> Baseline:
    """Load and strictly validate the migration baseline."""
    baseline_path = Path(path)
    try:
        raw = json.loads(baseline_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ProvenanceInputError(f"Provenance baseline does not exist: {baseline_path}") from error
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ProvenanceInputError(f"Cannot load provenance baseline {baseline_path}: {error}") from error
    return _baseline_from_mapping(raw, f"Provenance baseline {baseline_path}")


def _candidate_occurrences(candidates: Mapping[str, Candidate], symbols: Iterable[str]) -> tuple[Occurrence, ...]:
    return tuple(
        sorted(
            {
                occurrence
                for symbol in symbols
                for occurrence in candidates.get(symbol, Candidate("", "", "", (), "", "")).occurrences
            }
        )
    )


def _temporary_exception(candidate: Candidate, registry_by_locator: Mapping[str, RegistryField]) -> bool:
    item = registry_by_locator.get(candidate.symbol)
    return item is not None and item.is_exception


def _digest_stem(name: str) -> str | None:
    normalized = "_".join(_split_words(name))
    for suffix in ("_sha256", "_checksum", "_digest", "_hash", "_sha"):
        if normalized.endswith(suffix):
            return normalized.removesuffix(suffix).removesuffix("_content")
    return None


def _reference_stem(name: str) -> str:
    normalized = "_".join(_split_words(name))
    for suffix in ("_artifact_reference", "_artifact_ref", "_reference", "_ref"):
        normalized = normalized.removesuffix(suffix)
    return normalized


def _semantic_violations(
    discovery: _Discovery,
    registry: Registry,
    legacy_symbols: set[str],
) -> tuple[Violation, ...]:
    violations: list[Violation] = list(discovery.boundary_violations)
    candidates = {candidate.symbol: candidate for candidate in discovery.candidates}
    registry_by_locator = registry.by_locator

    for candidate in discovery.candidates:
        if candidate.symbol in legacy_symbols or _temporary_exception(candidate, registry_by_locator):
            continue
        item = registry_by_locator.get(candidate.symbol)
        if candidate.inherited and item is None:
            violations.append(
                Violation(
                    code="PROV010",
                    message=f"{candidate.symbol} inherits a new ambient content address.",
                    remediation=(
                        "Remove legacy content-addressing inheritance, or add a reviewed registry entry that names "
                        "the exact payload, authority, consumer, and mismatch behavior."
                    ),
                    symbols=(candidate.symbol,),
                    occurrences=candidate.occurrences,
                )
            )
        if candidate.field_name in {"content_hash", "content_sha", "content_sha256"} and not candidate.inherited:
            category = item.category if item is not None else None
            owner_name = candidate.owner.rsplit(".", maxsplit=1)[-1]
            if category != "artifact_integrity" and owner_name not in _CONTENT_ADDRESSED_BASE_NAMES:
                violations.append(
                    Violation(
                        code="PROV006",
                        message=f"{candidate.symbol} is a generic content digest without a named semantic boundary.",
                        remediation=(
                            "Remove the ambient digest, or rename and register the exact artifact or semantic "
                            "commitment with its canonical payload."
                        ),
                        symbols=(candidate.symbol,),
                        occurrences=candidate.occurrences,
                    )
                )

        digest_stem = _digest_stem(candidate.field_name)
        if digest_stem is not None and candidate.artifact_ref_fields:
            matching_refs = tuple(
                name
                for name in candidate.artifact_ref_fields
                if _reference_stem(name) in {digest_stem, "artifact"} or digest_stem == "artifact"
            )
            if matching_refs:
                violations.append(
                    Violation(
                        code="PROV006",
                        message=(
                            f"{candidate.symbol} duplicates the bytes already identified by ArtifactRef field "
                            f"{matching_refs[0]}."
                        ),
                        remediation=(
                            "Keep the ArtifactRef as the one artifact-integrity authority. Remove the adjacent "
                            "raw digest, or document a temporary claim-binding exception in the registry."
                        ),
                        symbols=(candidate.symbol,),
                        occurrences=candidate.occurrences,
                    )
                )

        owner_words = set(_split_words(candidate.owner.rsplit(".", maxsplit=1)[-1]))
        if candidate.field_name in {"generated_at", "generation_timestamp"} and owner_words & {
            "catalogue",
            "definition",
        }:
            violations.append(
                Violation(
                    code="PROV007",
                    message=f"{candidate.symbol} makes deterministic definition content depend on generation time.",
                    remediation=(
                        "Remove the generation time from the catalogue or deterministic definition. Record a real "
                        "domain event in a separate evidence envelope when one exists."
                    ),
                    symbols=(candidate.symbol,),
                    occurrences=candidate.occurrences,
                )
            )

        if (
            item is not None
            and item.category == "operational_commitment"
            and candidate.field_name == "request_fingerprint"
        ):
            scope = str(item.metadata.get("identity_scope", "")).lower()
            canonicalization = str(item.metadata.get("canonicalization", "")).lower()
            combined = f"{scope} {canonicalization}"
            has_exclusion = any(word in combined for word in ("exclude", "without", "not_identity", "non_identity"))
            has_correlation_boundary = "correlation" in combined or "provider_request" in combined
            if not (has_exclusion and has_correlation_boundary):
                violations.append(
                    Violation(
                        code="PROV011",
                        message=f"{candidate.symbol} does not document excluded provider/correlation identity fields.",
                        remediation=(
                            "Update identity_scope or canonicalization to state that provider request IDs, "
                            "transport data, and correlation data are excluded from logical actor-request identity."
                        ),
                        symbols=(candidate.symbol,),
                        occurrences=candidate.occurrences,
                    )
                )

    candidates_by_owner: dict[str, dict[str, Candidate]] = defaultdict(dict)
    for candidate in discovery.candidates:
        candidates_by_owner[candidate.owner][candidate.field_name] = candidate
    for owner, owner_candidates in sorted(candidates_by_owner.items()):
        revision = next(
            (
                candidate
                for name, candidate in owner_candidates.items()
                if name in {"source_revision", "git_revision", "git_commit", "source_commit"}
            ),
            None,
        )
        tree_digest = next(
            (
                candidate
                for name, candidate in owner_candidates.items()
                if "source_tree" in name and _hash_shaped_name(name)
            ),
            None,
        )
        if revision is not None and tree_digest is not None:
            symbols = tuple(sorted((revision.symbol, tree_digest.symbol)))
            if set(symbols).issubset(legacy_symbols) or any(
                _temporary_exception(candidate, registry_by_locator) for candidate in (revision, tree_digest)
            ):
                continue
            violations.append(
                Violation(
                    code="PROV006",
                    message=f"{owner} stores both a source revision and a source-tree digest for one Git boundary.",
                    remediation=(
                        "Use the clean Git revision as the source identity. Keep a source-tree digest only when "
                        "dirty or non-Git bytes are a separately named authority."
                    ),
                    symbols=symbols,
                    occurrences=_candidate_occurrences(candidates, symbols),
                )
            )

    owners_by_name: dict[str, list[str]] = defaultdict(list)
    for shape in discovery.model_shapes:
        owners_by_name[shape.owner.rsplit(".", maxsplit=1)[-1]].append(shape.owner)
    repeated_child_pairs: set[tuple[str, str]] = set()
    for parent_shape in discovery.model_shapes:
        parent_candidates = candidates_by_owner.get(parent_shape.owner, {})
        for relation_field in parent_shape.fields:
            referenced_names = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", relation_field.annotation))
            for child_name in sorted(referenced_names):
                possible_owners = owners_by_name.get(child_name, [])
                if len(possible_owners) != 1:
                    continue
                child_owner = possible_owners[0]
                if child_owner == parent_shape.owner:
                    continue
                child_candidates = candidates_by_owner.get(child_owner, {})
                for field_name in sorted(set(parent_candidates) & set(child_candidates)):
                    if not _hash_shaped_name(field_name):
                        continue
                    parent_candidate = parent_candidates[field_name]
                    child_candidate = child_candidates[field_name]
                    if parent_candidate.inherited or child_candidate.inherited:
                        continue
                    first_symbol, second_symbol = sorted((parent_candidate.symbol, child_candidate.symbol))
                    symbols = (first_symbol, second_symbol)
                    if symbols in repeated_child_pairs:
                        continue
                    repeated_child_pairs.add(symbols)
                    if (
                        set(symbols).issubset(legacy_symbols)
                        or _temporary_exception(parent_candidate, registry_by_locator)
                        or _temporary_exception(child_candidate, registry_by_locator)
                    ):
                        continue
                    violations.append(
                        Violation(
                            code="PROV006",
                            message=(
                                f"{parent_candidate.symbol} repeats a digest already carried by embedded model "
                                f"{child_owner}."
                            ),
                            remediation=(
                                "Keep the digest on the authority-owned parent or child boundary, not both. "
                                "Use a documented temporary exception only for deliberate claim binding."
                            ),
                            symbols=symbols,
                            occurrences=_candidate_occurrences(candidates, symbols),
                        )
                    )

    for shape in discovery.model_shapes:
        class_name = shape.owner.rsplit(".", maxsplit=1)[-1]
        words = set(_split_words(class_name))
        fields = {model_field.name: model_field for model_field in shape.fields}
        actor_identity = "actor" in words and "request" in words and "identity" in words
        profile_identity = "identity" in words and "profile" in words and bool(words & {"task", "world"})
        if actor_identity:
            suspicious = sorted(
                name
                for name in fields
                if name in {"provider_request_id", "provider_correlation_id"}
                or ("provider" in _split_words(name) and "request" in _split_words(name))
            )
            for name in suspicious:
                model_field = fields[name]
                symbol = f"{shape.owner}.{name}"
                violations.append(
                    Violation(
                        code="PROV008",
                        message=f"{symbol} puts provider correlation into logical actor-request identity.",
                        remediation=(
                            "Remove provider and correlation identifiers from ActorRequestIdentity. Keep them in the "
                            "invocation evidence envelope."
                        ),
                        symbols=(symbol,),
                        occurrences=(model_field.occurrence,),
                    )
                )
        if profile_identity:
            suspicious = sorted(
                name for name in fields if set(_split_words(name)) & {"correlation", "provider", "route", "transport"}
            )
            for name in suspicious:
                model_field = fields[name]
                symbol = f"{shape.owner}.{name}"
                violations.append(
                    Violation(
                        code="PROV009",
                        message=f"{symbol} puts provider or transport metadata into task/world profile identity.",
                        remediation=(
                            "Remove provider, route, transport, and correlation fields from logical task/world profile "
                            "identity. Put runtime attestations in provider evidence."
                        ),
                        symbols=(symbol,),
                        occurrences=(model_field.occurrence,),
                    )
                )
    return tuple(sorted(violations, key=lambda item: (item.code, item.symbols, item.message)))


def _git(repository_root: Path, arguments: Sequence[str], *, text: bool = True) -> subprocess.CompletedProcess[Any]:
    try:
        return subprocess.run(
            ["git", *arguments],
            cwd=repository_root,
            check=False,
            capture_output=True,
            text=text,
        )
    except OSError as error:
        raise ProvenanceInputError(f"Cannot run Git: {error}") from error


def _resolve_git_revision(repository_root: Path, revision: str) -> str:
    result = _git(repository_root, ["rev-parse", "--verify", f"{revision}^{{commit}}"])
    if result.returncode != 0:
        diagnostic = (result.stderr or result.stdout).strip()
        raise ProvenanceInputError(f"Cannot resolve base revision {revision}: {diagnostic}")
    if not isinstance(result.stdout, str):
        raise ProvenanceInputError(f"Git returned non-text output while resolving {revision}")
    return result.stdout.strip()


def _repository_relative(path: Path, repository_root: Path, label: str) -> str:
    try:
        return path.resolve().relative_to(repository_root.resolve()).as_posix()
    except ValueError as error:
        raise ProvenanceInputError(f"{label} must be inside the repository for base-revision checks: {path}") from error


def _baseline_at_revision(repository_root: Path, revision: str, relative_path: str) -> Baseline | None:
    result = _git(repository_root, ["show", f"{revision}:{relative_path}"])
    if result.returncode != 0:
        exists = _git(repository_root, ["cat-file", "-e", f"{revision}:{relative_path}"])
        if exists.returncode != 0:
            return None
        diagnostic = (result.stderr or result.stdout).strip()
        raise ProvenanceInputError(f"Cannot read {relative_path} at {revision}: {diagnostic}")
    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ProvenanceInputError(f"Baseline at {revision}:{relative_path} is not valid JSON: {error}") from error
    return _baseline_from_mapping(raw, f"Baseline at {revision}:{relative_path}")


def _source_units_at_revision(repository_root: Path, revision: str) -> tuple[_SourceUnit, ...]:
    roots_result = _git(
        repository_root,
        ["ls-tree", "-d", "--name-only", revision, "--", "src/aec_bench", "scripts"],
    )
    if roots_result.returncode != 0:
        diagnostic = (roots_result.stderr or roots_result.stdout).strip()
        raise ProvenanceInputError(f"Cannot list maintained source at {revision}: {diagnostic}")
    roots = tuple(line for line in roots_result.stdout.splitlines() if line)
    if not roots:
        raise ProvenanceInputError(f"No maintained Python source roots were found at {revision}")
    result = _git(
        repository_root,
        ["archive", "--format=tar", revision, "--", *roots],
        text=False,
    )
    if result.returncode != 0:
        diagnostic = result.stderr.decode("utf-8", errors="replace").strip()
        raise ProvenanceInputError(f"Cannot read maintained source at {revision}: {diagnostic}")
    units: list[_SourceUnit] = []
    try:
        with tarfile.open(fileobj=io.BytesIO(result.stdout), mode="r:") as archive:
            for member in sorted(archive.getmembers(), key=lambda item: item.name):
                path = Path(member.name)
                if (
                    not member.isfile()
                    or member.name == _SELF_PATH
                    or path.suffix != ".py"
                    or set(path.parts) & _IGNORED_PATH_PARTS
                ):
                    continue
                if not (path.parts[:2] == ("src", "aec_bench") or (path.parts and path.parts[0] == "scripts")):
                    continue
                extracted = archive.extractfile(member)
                if extracted is None:
                    continue
                try:
                    text = extracted.read().decode("utf-8")
                except UnicodeDecodeError as error:
                    raise ProvenanceInputError(f"Cannot decode {member.name} at {revision}: {error}") from error
                units.append(_SourceUnit(member.name, _module_name(member.name), text))
    except tarfile.TarError as error:
        raise ProvenanceInputError(f"Cannot parse source archive at {revision}: {error}") from error
    if not units:
        raise ProvenanceInputError(f"No maintained Python source was found at {revision}")
    return tuple(units)


def _registered_candidate_symbols(candidates: Iterable[Candidate], registry: Registry) -> set[str]:
    locators = registry.by_locator
    return {candidate.symbol for candidate in candidates if candidate.symbol in locators}


def _normalized_surface(surface: str) -> str:
    normalized = "_".join(_split_words(surface))
    if normalized in {
        "model_field",
        "pydantic",
        "pydantic_computed_field",
        "pydantic_inherited",
        "pydantic_model",
    }:
        return "pydantic_model"
    if normalized in {"manifest", "manifest_key"}:
        return "manifest"
    if normalized in {"mapping", "mapping_key"}:
        return "mapping"
    return normalized


def _registry_drift_violations(
    candidates: Mapping[str, Candidate],
    registry: Registry,
) -> tuple[Violation, ...]:
    violations: list[Violation] = []
    registry_by_locator = registry.by_locator
    for carrier_symbol, candidate in sorted(candidates.items()):
        item = registry_by_locator.get(carrier_symbol)
        if item is None:
            continue
        mismatches: list[str] = []
        if carrier_symbol == item.symbol:
            registered_wire_name = str(item.metadata["wire_name"])
            registered_surface = str(item.metadata["surface"])
            if registered_wire_name != candidate.wire_name:
                mismatches.append(
                    f"wire_name is {registered_wire_name!r}, but source serializes {candidate.wire_name!r}"
                )
            if _normalized_surface(registered_surface) != _normalized_surface(candidate.surface):
                mismatches.append(f"surface is {registered_surface!r}, but source surface is {candidate.surface!r}")
        else:
            alias_wire_name = carrier_symbol.rsplit(".", maxsplit=1)[-1]
            if alias_wire_name != candidate.wire_name:
                mismatches.append(
                    f"alias locator wire_name is {alias_wire_name!r}, but source serializes {candidate.wire_name!r}"
                )
        if not mismatches:
            continue
        remediation = (
            "Update the registry wire_name and surface to match the source contract, or restore the reviewed source "
            "serialization alias and boundary type."
            if carrier_symbol == item.symbol
            else (
                "Update the exact registry alias locator to match the carrier wire name, or restore the reviewed "
                "source serialization alias."
            )
        )
        violations.append(
            Violation(
                code="PROV012",
                message=(
                    f"Registry metadata drift for carrier {carrier_symbol} registered as {item.symbol}: "
                    f"{'; '.join(mismatches)}."
                ),
                remediation=remediation,
                symbols=(carrier_symbol,),
                occurrences=candidate.occurrences,
            )
        )
    return tuple(violations)


def _base_violations(
    *,
    repository_root: Path,
    registry: Registry,
    baseline: Baseline,
    baseline_path: Path,
    base_revision: str,
    current_candidates: Mapping[str, Candidate],
) -> tuple[Violation, ...]:
    resolved_base = _resolve_git_revision(repository_root, base_revision)
    relative_baseline = _repository_relative(baseline_path, repository_root, "Baseline")
    base_baseline = _baseline_at_revision(repository_root, resolved_base, relative_baseline)
    violations: list[Violation] = []
    if base_baseline is not None:
        for symbol in sorted(set(baseline.symbols) - set(base_baseline.symbols)):
            candidate = current_candidates.get(symbol)
            violations.append(
                Violation(
                    code="PROV002",
                    message=f"The legacy baseline grew after {resolved_base}: {symbol}.",
                    remediation=(
                        "Remove the symbol from provenance-baseline.json and add a complete provenance-registry.toml "
                        "entry, or remove the field."
                    ),
                    symbols=(symbol,),
                    occurrences=candidate.occurrences if candidate is not None else (),
                )
            )
        return tuple(violations)

    if baseline.source_ref != resolved_base:
        violations.append(
            Violation(
                code="PROV002",
                message=(
                    "The base revision has no provenance baseline, and current source_revision does not equal the base "
                    f"commit: {baseline.source_ref} != {resolved_base}."
                ),
                remediation=(
                    "Recreate the initial baseline from the exact pull-request base revision. Do not add current "
                    "fields to that baseline."
                ),
            )
        )
        return tuple(violations)

    base_discovery = _discover_from_units(
        _source_units_at_revision(repository_root, resolved_base),
        registry.manifests,
        frozenset(registry.by_locator),
    )
    expected = {
        candidate.symbol for candidate in base_discovery.candidates if candidate.symbol not in registry.by_locator
    }
    actual = set(baseline.symbols)
    for symbol in sorted(expected ^ actual):
        relation = "missing from" if symbol in expected else "not present in the base scan but included in"
        violations.append(
            Violation(
                code="PROV002",
                message=f"{symbol} is {relation} the initial legacy baseline.",
                remediation=(
                    "Regenerate the initial baseline from the exact base source scan. Then register every field added "
                    "after that revision."
                ),
                symbols=(symbol,),
            )
        )
    return tuple(violations)


def _group_findings(findings: Iterable[Finding]) -> dict[str, dict[str, tuple[str, ...]]]:
    grouped: dict[str, dict[str, list[str]]] = {
        "authority": defaultdict(list),
        "authoritative": defaultdict(list),
        "category": defaultdict(list),
        "current_vs_legacy": defaultdict(list),
        "deterministic_definition_risk": defaultdict(list),
        "domain_owner": defaultdict(list),
        "duplicated": defaultdict(list),
        "public_surface_exposure": defaultdict(list),
    }
    for finding in findings:
        metadata = finding.metadata
        symbol = finding.candidate.symbol
        grouped["category"][str(metadata.get("category", "unclassified"))].append(symbol)
        grouped["authority"][str(metadata.get("authority", "unclassified"))].append(symbol)
        grouped["domain_owner"][str(metadata.get("domain_owner", "unclassified"))].append(symbol)
        authoritative = metadata.get("authoritative")
        authority_group = (
            "authoritative" if authoritative is True else "informational" if authoritative is False else "unclassified"
        )
        grouped["authoritative"][authority_group].append(symbol)
        grouped["current_vs_legacy"][finding.state].append(symbol)
        duplication = str(metadata.get("duplication", "unclassified"))
        duplication_group = "unique" if duplication in {"none", "unique", "false"} else duplication
        grouped["duplicated"][duplication_group].append(symbol)
        owner_words = set(_split_words(finding.candidate.owner))
        risk = (
            "risk"
            if finding.candidate.field_name in {"generated_at", "generation_timestamp"}
            and owner_words & {"catalogue", "definition"}
            else "none"
        )
        grouped["deterministic_definition_risk"][risk].append(symbol)
        exposure = str(metadata.get("exposure", "unclassified"))
        public_group = "public" if exposure in {"public", "published", "wire", "web"} else exposure
        grouped["public_surface_exposure"][public_group].append(symbol)
    return {
        group: {name: tuple(sorted(symbols)) for name, symbols in sorted(values.items())}
        for group, values in sorted(grouped.items())
    }


def _deduplicate_violations(violations: Iterable[Violation]) -> tuple[Violation, ...]:
    result: dict[tuple[str, tuple[str, ...], str], Violation] = {}
    for violation in violations:
        result[(violation.code, violation.symbols, violation.message)] = violation
    return tuple(sorted(result.values(), key=lambda item: (item.code, item.symbols, item.message)))


def _relocated_legacy_symbols(
    discovered_symbols: Iterable[str],
    baseline_symbols: set[str],
    registry: Registry,
) -> dict[str, str]:
    """Map current moved symbols to their exact pre-move baseline symbols."""

    relocated: dict[str, str] = {}
    for symbol in discovered_symbols:
        for move in registry.legacy_relocations:
            if not symbol.startswith(move.to_prefix):
                continue
            previous = move.from_prefix + symbol.removeprefix(move.to_prefix)
            if previous in baseline_symbols:
                relocated[symbol] = previous
            break
    return relocated


def build_audit(
    repository_root: Path,
    registry_path: Path,
    baseline_path: Path,
    base_revision: str | None = None,
) -> dict[str, object]:
    """Build a deterministic audit dictionary for tests, CI, and report renderers."""
    root = Path(repository_root).resolve()
    registry = load_registry(Path(registry_path))
    baseline = load_baseline(Path(baseline_path))
    discovery = _discover_from_units(
        _source_units(root),
        registry.manifests,
        frozenset(registry.by_locator),
    )
    candidates = {candidate.symbol: candidate for candidate in discovery.candidates}
    discovered_symbols = set(candidates)
    baseline_symbols = set(baseline.symbols)
    registry_by_locator = registry.by_locator
    registered_discovered = _registered_candidate_symbols(discovery.candidates, registry)
    relocated_legacy = _relocated_legacy_symbols(discovered_symbols, baseline_symbols, registry)
    effective_legacy_symbols = baseline_symbols | set(relocated_legacy)

    findings: list[Finding] = []
    for candidate in discovery.candidates:
        registry_item = registry_by_locator.get(candidate.symbol)
        if registry_item is not None:
            state = "current"
            registry_symbol = registry_item.symbol
            metadata = registry_item.metadata
        elif candidate.symbol in effective_legacy_symbols:
            state = "legacy"
            registry_symbol = None
            metadata = {}
        else:
            state = "unregistered"
            registry_symbol = None
            metadata = {}
        findings.append(Finding(candidate, state, registry_symbol, metadata))

    violations: list[Violation] = []
    for symbol in sorted(discovered_symbols - registered_discovered - effective_legacy_symbols):
        candidate = candidates[symbol]
        violations.append(
            Violation(
                code="PROV001",
                message=f"New provenance-shaped field is not registered: {symbol}.",
                remediation=(
                    "Remove the field, or add a complete sorted [[field]] entry to provenance-registry.toml. "
                    "Do not add the field to provenance-baseline.json."
                ),
                symbols=(symbol,),
                occurrences=candidate.occurrences,
            )
        )
    represented_baseline_symbols = discovered_symbols | set(relocated_legacy.values())
    for symbol in sorted(baseline_symbols - represented_baseline_symbols):
        violations.append(
            Violation(
                code="PROV003",
                message=f"Legacy baseline entry is stale: {symbol}.",
                remediation=(
                    "Run scripts/check_provenance_fields.py --update-baseline to remove stale entries. "
                    "Baseline updates must never add symbols."
                ),
                symbols=(symbol,),
            )
        )
    for item in registry.fields:
        if not discovered_symbols & {item.symbol, *item.aliases}:
            violations.append(
                Violation(
                    code="PROV004",
                    message=f"Registry entry does not match a discovered field or exact alias: {item.symbol}.",
                    remediation=(
                        "Remove the orphaned registry entry, or update its symbol and exact aliases to match the "
                        "current field definition."
                    ),
                    symbols=(item.symbol,),
                )
            )
    for symbol in sorted(baseline_symbols & registered_discovered):
        candidate = candidates[symbol]
        violations.append(
            Violation(
                code="PROV005",
                message=f"Field is both registered and in the legacy baseline: {symbol}.",
                remediation="Remove the registered field from provenance-baseline.json.",
                symbols=(symbol,),
                occurrences=candidate.occurrences,
            )
        )

    violations.extend(_registry_drift_violations(candidates, registry))
    violations.extend(_semantic_violations(discovery, registry, effective_legacy_symbols))
    resolved_base: str | None = None
    if base_revision is not None:
        resolved_base = _resolve_git_revision(root, base_revision)
        violations.extend(
            _base_violations(
                repository_root=root,
                registry=registry,
                baseline=baseline,
                baseline_path=Path(baseline_path),
                base_revision=resolved_base,
                current_candidates=candidates,
            )
        )

    ordered_findings = tuple(sorted(findings, key=lambda item: item.candidate.symbol))
    report = AuditReport(
        findings=ordered_findings,
        violations=_deduplicate_violations(violations),
        groups=_group_findings(ordered_findings),
        baseline_count=len(baseline.symbols),
        registered_count=len(registry.fields),
        base_ref=resolved_base,
    ).as_dict()
    summary = report["summary"]
    assert isinstance(summary, dict)
    report_violations = report["violations"]
    assert isinstance(report_violations, list)
    summary.update(
        {
            "candidate_count": len(ordered_findings),
            "legacy_count": sum(finding.state == "legacy" for finding in ordered_findings),
            "registered_count": sum(finding.state == "current" for finding in ordered_findings),
            "unregistered_count": sum(finding.state == "unregistered" for finding in ordered_findings),
            "violation_count": len(report_violations),
        }
    )
    return report


def render_text(report: Mapping[str, object]) -> str:
    """Render every deterministic audit finding and violation as plain text."""
    summary = report.get("summary", {})
    if not isinstance(summary, Mapping):
        raise ProvenanceInputError("Audit report summary is malformed")
    lines = [
        "AEC-Bench provenance field audit",
        (
            f"Result: {'PASS' if summary.get('passed') else 'FAIL'}; "
            f"candidates={summary.get('candidate_count', summary.get('discovered', 0))}; "
            f"registered={summary.get('registered_count', 0)}; legacy={summary.get('legacy_count', 0)}; "
            f"violations={summary.get('violation_count', summary.get('violations', 0))}"
        ),
        "",
        "Findings:",
    ]
    findings = report.get("findings", [])
    if not isinstance(findings, list):
        raise ProvenanceInputError("Audit report findings are malformed")
    for finding in findings:
        if not isinstance(finding, Mapping):
            raise ProvenanceInputError("Audit report finding is malformed")
        symbol = finding.get("symbol")
        state = finding.get("state")
        surface = finding.get("surface")
        wire_name = finding.get("wire_name")
        lines.append(f"- {symbol} [{state}; {surface}; wire={wire_name}]")
        occurrences = finding.get("occurrences", [])
        if isinstance(occurrences, list):
            for occurrence in occurrences:
                if isinstance(occurrence, Mapping):
                    lines.append(
                        f"  occurrence: {occurrence.get('path')}:{occurrence.get('line')} ({occurrence.get('kind')})"
                    )

    lines.extend(("", "Groups:"))
    groups = report.get("groups", {})
    if not isinstance(groups, Mapping):
        raise ProvenanceInputError("Audit report groups are malformed")
    for group_name, values in sorted(groups.items()):
        if not isinstance(values, Mapping):
            continue
        lines.append(f"- {group_name}:")
        for value_name, symbols in sorted(values.items()):
            if isinstance(symbols, list):
                lines.append(f"  {value_name}: {', '.join(str(symbol) for symbol in symbols)}")

    lines.extend(("", "Violations:"))
    violations = report.get("violations", [])
    if not isinstance(violations, list):
        raise ProvenanceInputError("Audit report violations are malformed")
    if not violations:
        lines.append("- none")
    for violation in violations:
        if not isinstance(violation, Mapping):
            raise ProvenanceInputError("Audit report violation is malformed")
        symbols = violation.get("symbols", [])
        symbol_text = ", ".join(str(symbol) for symbol in symbols) if isinstance(symbols, list) else ""
        lines.append(f"- {violation.get('code')}: {violation.get('message')} [{symbol_text}]")
        occurrences = violation.get("occurrences", [])
        if isinstance(occurrences, list):
            for occurrence in occurrences:
                if isinstance(occurrence, Mapping):
                    lines.append(f"  at {occurrence.get('path')}:{occurrence.get('line')}")
        lines.append(f"  remediation: {violation.get('remediation')}")
    return "\n".join(lines) + "\n"


def _head_revision(repository_root: Path) -> str:
    result = _git(repository_root, ["rev-parse", "--verify", "HEAD^{commit}"])
    if result.returncode != 0:
        diagnostic = (result.stderr or result.stdout).strip()
        raise ProvenanceInputError(f"Cannot resolve HEAD for baseline creation: {diagnostic}")
    if not isinstance(result.stdout, str):
        raise ProvenanceInputError("Git returned non-text output while resolving HEAD")
    return result.stdout.strip()


def _write_baseline(path: Path, baseline: Baseline) -> None:
    payload = {
        "schema_version": BASELINE_SCHEMA,
        "source_revision": baseline.source_ref,
        "symbols": list(baseline.symbols),
    }
    try:
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as error:
        raise ProvenanceInputError(f"Cannot write provenance baseline {path}: {error}") from error


def update_baseline(repository_root: Path, registry_path: Path, baseline_path: Path) -> tuple[str, ...]:
    """Create an initial baseline, or remove stale entries without permitting growth."""
    root = Path(repository_root).resolve()
    registry = load_registry(Path(registry_path))
    discovery = _discover_from_units(
        _source_units(root),
        registry.manifests,
        frozenset(registry.by_locator),
    )
    unregistered = {
        candidate.symbol for candidate in discovery.candidates if candidate.symbol not in registry.by_locator
    }
    path = Path(baseline_path)
    if not path.exists():
        desired = tuple(sorted(unregistered))
        _write_baseline(path, Baseline(source_ref=_head_revision(root), symbols=desired))
        return desired

    current = load_baseline(path)
    current_symbols = set(current.symbols)
    relocated = _relocated_legacy_symbols(unregistered, current_symbols, registry)
    additions = sorted(unregistered - set(relocated) - current_symbols)
    if additions:
        raise ProvenanceBaselineGrowthError(
            "Deletion-only baseline update rejected new symbols: "
            + ", ".join(additions)
            + ". Register or remove them instead."
        )
    represented = unregistered | set(relocated.values())
    retained = tuple(symbol for symbol in current.symbols if symbol in represented)
    _write_baseline(path, Baseline(source_ref=current.source_ref, symbols=retained))
    return retained


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repository-root",
        "--repo-root",
        dest="repository_root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root. Defaults to the parent of scripts/.",
    )
    parser.add_argument("--registry", type=Path, help="Registry path. Relative paths resolve from the repository root.")
    parser.add_argument("--baseline", type=Path, help="Baseline path. Relative paths resolve from the repository root.")
    parser.add_argument("--base-revision", help="Pull-request base commit or ref for no-growth enforcement.")
    parser.add_argument(
        "--update-baseline", action="store_true", help="Create the missing baseline or remove stale entries."
    )
    parser.add_argument("--check", action="store_true", help="Return exit status 1 when policy violations exist.")
    parser.add_argument("--format", choices=("json", "text"), default="text", help="Report output format.")
    return parser


def _resolved_option_path(path: Path | None, repository_root: Path, default_name: str) -> Path:
    selected = path or Path(default_name)
    return selected if selected.is_absolute() else repository_root / selected


def main(argv: Sequence[str] | None = None) -> int:
    """Run the provenance audit and return a process-compatible status code."""
    arguments = _parser().parse_args(argv)
    repository_root = arguments.repository_root.resolve()
    registry_path = _resolved_option_path(arguments.registry, repository_root, "provenance-registry.toml")
    baseline_path = _resolved_option_path(arguments.baseline, repository_root, "provenance-baseline.json")
    try:
        if arguments.update_baseline:
            update_baseline(repository_root, registry_path, baseline_path)
        report = build_audit(
            repository_root,
            registry_path,
            baseline_path,
            base_revision=arguments.base_revision,
        )
    except ProvenanceBaselineGrowthError as error:
        print(f"provenance baseline update rejected: {error}", file=sys.stderr)
        return 1
    except ProvenanceInputError as error:
        print(f"provenance audit input error: {error}", file=sys.stderr)
        return 2

    if arguments.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_text(report), end="")
    violations = report.get("violations", [])
    return 1 if (arguments.check or arguments.base_revision) and violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
