#!/usr/bin/env python3
# ABOUTME: Builds deterministic import-graph evidence for the AEC-Bench source package.
# ABOUTME: Fails when owner cycles, optional-runtime leaks, or composition back-imports appear.

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import subprocess
import sys
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from re import fullmatch

OPTIONAL_RUNTIME_ROOTS = {
    "acp",
    "anthropic",
    "boto3",
    "botocore",
    "harbor",
    "modal",
    "morphcloud",
    "openai",
    "pydantic_ai",
    "verifiers",
}
NEUTRAL_OWNERS = {"contracts", "lifecycles", "worlds"}
COMPOSITION_ROOTS = {
    "aec_bench.lifecycles.catalogue": (
        "aec_bench.lifecycles.runtime",
        "aec_bench.lifecycles.stormwater_design",
        "aec_bench.lifecycles.structural_review",
    ),
    "aec_bench.worlds.catalogue": (
        "aec_bench.worlds.runtime",
        "aec_bench.worlds.monitoring",
        "aec_bench.worlds.stewardship",
    ),
}
GENERIC_RUNTIME_ROOTS = {
    "aec_bench.lifecycles.runtime": (
        "aec_bench.lifecycles.catalogue",
        "aec_bench.lifecycles.stormwater_design",
        "aec_bench.lifecycles.structural_review",
    ),
    "aec_bench.worlds.runtime": (
        "aec_bench.worlds.catalogue",
        "aec_bench.worlds.monitoring",
        "aec_bench.worlds.stewardship",
    ),
}
IGNORED_SOURCE_PARTS = {"__pycache__", "node_modules"}
DEFAULT_OWNER_POLICY_PATH = Path(__file__).with_name("owner_dependencies.toml")


@dataclass(frozen=True)
class OwnerDependencyException:
    """One narrow, owner-approved exception to the declared dependency matrix."""

    source_owner: str
    target_owner: str
    import_prefix: str
    reason: str
    expiry: date | None
    review_condition: str | None
    owner_approval: str


def _load_owner_policy_document(path: Path) -> dict[str, object]:
    try:
        with path.open("rb") as policy_file:
            document = tomllib.load(policy_file)
    except FileNotFoundError as error:
        raise ValueError(f"owner dependency policy file is missing: {path}") from error
    if not isinstance(document, dict):
        raise ValueError("owner dependency policy must be a TOML table")
    return document


def load_owner_dependency_policy(path: Path = DEFAULT_OWNER_POLICY_PATH) -> dict[str, set[str]]:
    """Load the complete owner dependency policy without importing source modules."""
    document = _load_owner_policy_document(path)
    raw_owners = document.get("owners")
    if not isinstance(raw_owners, dict):
        raise ValueError("owner dependency policy must contain an owners table")
    policy: dict[str, set[str]] = {}
    for owner, raw_policy in sorted(raw_owners.items()):
        if not isinstance(owner, str) or not owner:
            raise ValueError("owner dependency policy owner names must be non-empty strings")
        if not isinstance(raw_policy, dict) or set(raw_policy) != {"may_depend_on"}:
            raise ValueError(f"owner dependency policy entry is invalid: {owner}")
        targets = raw_policy["may_depend_on"]
        if not isinstance(targets, list) or any(not isinstance(target, str) or not target for target in targets):
            raise ValueError(f"owner dependency policy targets are invalid: {owner}")
        if len(targets) != len(set(targets)):
            raise ValueError(f"owner dependency policy targets must be unique: {owner}")
        policy[owner] = set(targets)
    return policy


def load_owner_dependency_exceptions(path: Path = DEFAULT_OWNER_POLICY_PATH) -> tuple[OwnerDependencyException, ...]:
    """Load narrow exceptions from the same maintained owner policy."""
    document = _load_owner_policy_document(path)
    raw_exceptions = document.get("exceptions", {})
    if not isinstance(raw_exceptions, dict):
        raise ValueError("owner dependency exceptions must be a TOML table")
    exceptions: list[OwnerDependencyException] = []
    required = {"source_owner", "target_owner", "import_prefix", "reason", "owner_approval"}
    for name, raw_exception in sorted(raw_exceptions.items()):
        if not isinstance(name, str) or not name:
            raise ValueError("owner dependency exception names must be non-empty strings")
        if not isinstance(raw_exception, dict):
            raise ValueError(f"owner dependency exception is invalid: {name}")
        fields = set(raw_exception)
        if not required.issubset(fields) or fields - required - {"expiry", "review_condition"}:
            raise ValueError(f"owner dependency exception fields are invalid: {name}")
        if "expiry" not in fields and "review_condition" not in fields:
            raise ValueError(f"owner dependency exception requires expiry or review_condition: {name}")
        values = {field: raw_exception[field] for field in required}
        if any(not isinstance(value, str) or not value.strip() for value in values.values()):
            raise ValueError(f"owner dependency exception values are invalid: {name}")
        import_prefix = values["import_prefix"].strip()
        if not import_prefix.startswith("aec_bench.") or "*" in import_prefix or len(import_prefix.split(".")) < 3:
            raise ValueError(f"owner dependency exception import prefix is too broad: {name}")
        expiry_value = raw_exception.get("expiry")
        if expiry_value is not None and not isinstance(expiry_value, date | str):
            raise ValueError(f"owner dependency exception expiry is invalid: {name}")
        try:
            expiry = date.fromisoformat(expiry_value) if isinstance(expiry_value, str) else expiry_value
        except ValueError as error:
            raise ValueError(f"owner dependency exception expiry is invalid: {name}") from error
        review_condition = raw_exception.get("review_condition")
        if review_condition is not None and (
            not isinstance(review_condition, str)
            or fullmatch(r"review-by:\d{4}-\d{2}-\d{2}", review_condition.strip()) is None
        ):
            raise ValueError(f"owner dependency exception review condition is invalid: {name}")
        if review_condition is not None:
            try:
                date.fromisoformat(review_condition.strip().removeprefix("review-by:"))
            except ValueError as error:
                raise ValueError(f"owner dependency exception review condition is invalid: {name}") from error
        exceptions.append(
            OwnerDependencyException(
                source_owner=values["source_owner"].strip(),
                target_owner=values["target_owner"].strip(),
                import_prefix=import_prefix,
                reason=values["reason"].strip(),
                expiry=expiry,
                review_condition=review_condition.strip() if review_condition is not None else None,
                owner_approval=values["owner_approval"].strip(),
            )
        )
    return tuple(exceptions)


def validate_owner_dependency_exceptions(
    owner_graph: dict[str, set[str]],
    owner_imports: dict[tuple[str, str], set[str]],
    exceptions: Iterable[OwnerDependencyException],
) -> tuple[tuple[str, ...], dict[tuple[str, str], set[str]]]:
    """Validate exceptions and return their narrow import prefixes by owner edge."""
    owners = set(owner_graph)
    violations: list[str] = []
    allowed_prefixes: dict[tuple[str, str], set[str]] = {}
    today = date.today()
    for exception in exceptions:
        label = f"{exception.source_owner} -> {exception.target_owner} ({exception.import_prefix})"
        if exception.source_owner not in owners:
            violations.append(f"exception declares unknown source owner: {label}")
            continue
        if exception.target_owner not in owners:
            violations.append(f"exception declares unknown target owner: {label}")
            continue
        edge = (exception.source_owner, exception.target_owner)
        if exception.target_owner not in owner_graph[exception.source_owner]:
            violations.append(f"exception does not match an observed owner dependency: {label}")
            continue
        if exception.expiry is not None and exception.expiry < today:
            violations.append(f"exception is expired: {label}")
            continue
        if exception.review_condition is not None:
            review_date = date.fromisoformat(exception.review_condition.removeprefix("review-by:"))
            if review_date < today:
                violations.append(f"exception review is overdue: {label}")
                continue
        imports = owner_imports.get(edge, set())
        if not any(
            imported == exception.import_prefix or imported.startswith(f"{exception.import_prefix}.")
            for imported in imports
        ):
            violations.append(f"exception import prefix does not match an observed import: {label}")
            continue
        allowed_prefixes.setdefault(edge, set()).add(exception.import_prefix)
    return tuple(sorted(violations)), allowed_prefixes


def validate_owner_dependency_policy(
    owner_graph: dict[str, set[str]],
    policy: dict[str, set[str]],
    *,
    owner_imports: dict[tuple[str, str], set[str]] | None = None,
    exception_prefixes: dict[tuple[str, str], set[str]] | None = None,
) -> tuple[str, ...]:
    """Return deterministic violations between the declared and observed owner graph."""
    owner_imports = owner_imports or {}
    exception_prefixes = exception_prefixes or {}
    actual_owners = set(owner_graph)
    policy_owners = set(policy)
    violations = [f"missing policy for owner: {owner}" for owner in sorted(actual_owners - policy_owners)]
    violations.extend(f"policy declares unknown owner: {owner}" for owner in sorted(policy_owners - actual_owners))
    for source in sorted(policy_owners):
        for target in sorted(policy[source] - actual_owners):
            violations.append(f"policy declares unknown dependency: {source} -> {target}")
    for source in sorted(actual_owners):
        for target in sorted(owner_graph[source] - policy.get(source, set())):
            edge = (source, target)
            imports = owner_imports.get(edge)
            prefixes = exception_prefixes.get(edge, set())
            if imports is None:
                violations.append(f"undeclared owner dependency: {source} -> {target}")
            else:
                violations.extend(
                    f"undeclared owner import: {source} -> {imported}"
                    for imported in sorted(imports)
                    if not any(imported == prefix or imported.startswith(f"{prefix}.") for prefix in prefixes)
                )
    return tuple(violations)


def _module_name(path: Path, package_root: Path) -> str:
    relative = path.relative_to(package_root).with_suffix("")
    parts = relative.parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(("aec_bench", *parts))


def _parsed_imports(path: Path, module_name: str) -> tuple[set[str], set[str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    internal: set[str] = set()
    external_roots: set[str] = set()
    package_name = module_name if path.name == "__init__.py" else module_name.rpartition(".")[0]

    for node in ast.walk(tree):
        names: Iterable[str]
        if isinstance(node, ast.Import):
            names = (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                relative_name = "." * node.level + (node.module or "")
                try:
                    imported_module = importlib.util.resolve_name(relative_name, package_name)
                except (ImportError, ValueError):
                    continue
            elif node.module:
                imported_module = node.module
            else:
                continue
            names = (
                imported_module,
                *(f"{imported_module}.{alias.name}" for alias in node.names if alias.name != "*"),
            )
        else:
            continue

        for name in names:
            if name == "aec_bench" or name.startswith("aec_bench."):
                internal.add(name)
            else:
                external_roots.add(name.split(".", maxsplit=1)[0])
    return internal, external_roots


def _known_target(imported: str, known_modules: set[str]) -> str | None:
    candidate = imported
    while candidate.startswith("aec_bench"):
        if candidate in known_modules:
            return candidate
        if "." not in candidate:
            break
        candidate = candidate.rpartition(".")[0]
    return None


def _owner(module_name: str) -> str | None:
    parts = module_name.split(".")
    return parts[1] if len(parts) > 1 else None


def _strongly_connected_components(graph: dict[str, set[str]]) -> list[list[str]]:
    index = 0
    indexes: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[list[str]] = []

    def visit(node: str) -> None:
        nonlocal index
        indexes[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)

        for target in sorted(graph.get(node, set())):
            if target not in indexes:
                visit(target)
                lowlinks[node] = min(lowlinks[node], lowlinks[target])
            elif target in on_stack:
                lowlinks[node] = min(lowlinks[node], indexes[target])

        if lowlinks[node] != indexes[node]:
            return
        component: list[str] = []
        while True:
            selected = stack.pop()
            on_stack.remove(selected)
            component.append(selected)
            if selected == node:
                break
        if len(component) > 1:
            components.append(sorted(component))

    for node in sorted(graph):
        if node not in indexes:
            visit(node)
    return sorted(components)


def _source_tree_sha256(paths: Iterable[Path], repository_root: Path) -> str:
    manifest = {
        path.relative_to(repository_root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(paths)
    }
    payload = json.dumps(manifest, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_audit(
    *,
    repository_root: Path,
    commit: str,
    minimal_import_smoke: str,
    minimal_import_command: str,
) -> dict[str, object]:
    package_root = repository_root / "src" / "aec_bench"
    source_paths = tuple(
        sorted(
            path
            for path in package_root.rglob("*.py")
            if not set(path.relative_to(package_root).parts) & IGNORED_SOURCE_PARTS
        )
    )
    if not package_root.is_dir() or not source_paths:
        raise ValueError(f"AEC-Bench source package is missing or empty: {package_root}")

    path_by_module = {_module_name(path, package_root): path for path in source_paths}
    known_modules = set(path_by_module)
    raw_internal: dict[str, set[str]] = {}
    external_roots: dict[str, set[str]] = {}
    graph: dict[str, set[str]] = {module: set() for module in known_modules}
    for module, path in path_by_module.items():
        internal, external = _parsed_imports(path, module)
        raw_internal[module] = internal
        external_roots[module] = external
        graph[module].update(
            target
            for imported in internal
            if (target := _known_target(imported, known_modules)) is not None and target != module
        )

    owners = sorted({owner for module in known_modules if (owner := _owner(module)) is not None})
    owner_graph: dict[str, set[str]] = {owner: set() for owner in owners}
    owner_imports: dict[tuple[str, str], set[str]] = {}
    for source, targets in graph.items():
        source_owner = _owner(source)
        if source_owner is None:
            continue
        for target in targets:
            target_owner = _owner(target)
            if target_owner is None or target_owner == source_owner:
                continue
            owner_graph[source_owner].add(target_owner)
            edge = (source_owner, target_owner)
            owner_imports.setdefault(edge, set()).update(
                imported_target
                for imported in raw_internal[source]
                if (imported_target := _known_target(imported, known_modules)) is not None
                and _owner(imported_target) == target_owner
            )

    owner_sccs = _strongly_connected_components(owner_graph)
    module_sccs = _strongly_connected_components(graph)
    module_sccs_by_owner_cycle = {
        ",".join(component): [
            module_component
            for module_component in module_sccs
            if {_owner(module) for module in module_component}.issubset(set(component))
        ]
        for component in owner_sccs
    }

    composition_back_imports = sorted(
        {
            f"{module} -> {root}"
            for root, forbidden_importers in COMPOSITION_ROOTS.items()
            for module, imports in raw_internal.items()
            if module.startswith(forbidden_importers)
            and any(name == root or name.startswith(f"{root}.") for name in imports)
        }
    )
    generic_runtime_back_imports = sorted(
        {
            f"{module} -> {target}"
            for runtime_root, concrete_prefixes in GENERIC_RUNTIME_ROOTS.items()
            for module, imports in raw_internal.items()
            if module == runtime_root or module.startswith(f"{runtime_root}.")
            for imported in imports
            if (target := _known_target(imported, known_modules)) is not None
            and any(target == prefix or target.startswith(f"{prefix}.") for prefix in concrete_prefixes)
        }
    )
    optional_leakage = sorted(
        f"{module}: {', '.join(sorted(external_roots[module] & OPTIONAL_RUNTIME_ROOTS))}"
        for module in known_modules
        if _owner(module) in NEUTRAL_OWNERS and external_roots[module] & OPTIONAL_RUNTIME_ROOTS
    )
    policy_path = repository_root / "scripts" / DEFAULT_OWNER_POLICY_PATH.name
    try:
        owner_policy = load_owner_dependency_policy(policy_path)
        exceptions = load_owner_dependency_exceptions(policy_path)
        exception_violations, exception_prefixes = validate_owner_dependency_exceptions(
            owner_graph, owner_imports, exceptions
        )
        owner_policy_violations = list(exception_violations)
        owner_policy_violations.extend(
            validate_owner_dependency_policy(
                owner_graph,
                owner_policy,
                owner_imports=owner_imports,
                exception_prefixes=exception_prefixes,
            )
        )
    except ValueError as error:
        owner_policy = {}
        owner_policy_violations = [str(error)]

    return {
        "schema_version": "1",
        "git_commit": commit,
        "source_tree_sha256": _source_tree_sha256(source_paths, repository_root),
        "module_count": len(known_modules),
        "top_level_package_graph": {owner: sorted(owner_graph[owner]) for owner in owners},
        "owner_dependency_policy": {owner: sorted(owner_policy[owner]) for owner in sorted(owner_policy)},
        "owner_dependency_policy_violations": list(owner_policy_violations),
        "top_level_strongly_connected_components": owner_sccs,
        "module_cycles_within_top_level_components": module_sccs_by_owner_cycle,
        "composition_root_back_imports": composition_back_imports,
        "generic_runtime_back_imports": generic_runtime_back_imports,
        "optional_dependency_leakage": optional_leakage,
        "minimal_install_import_smoke": {
            "status": minimal_import_smoke,
            "command": minimal_import_command,
        },
    }


def _current_commit(repository_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def render_audit_report(audit: dict[str, object]) -> str:
    """Render the owner graph and violations for a contributor-facing report."""
    graph = audit.get("top_level_package_graph", {})
    lines = ["Owner dependency graph:"]
    if isinstance(graph, dict):
        for owner, targets in sorted(graph.items()):
            rendered_targets = ", ".join(str(target) for target in targets) if targets else "(none)"
            lines.append(f"  {owner} -> {rendered_targets}")
    failures = {
        "owner dependency policy": audit.get("owner_dependency_policy_violations", []),
        "top-level owner cycles": audit.get("top_level_strongly_connected_components", []),
        "composition back-imports": audit.get("composition_root_back_imports", []),
        "generic runtime back-imports": audit.get("generic_runtime_back_imports", []),
        "optional dependency leakage": audit.get("optional_dependency_leakage", []),
    }
    active = {name: value for name, value in failures.items() if value}
    if not active:
        lines.append("Violations: none")
        return "\n".join(lines)
    lines.append("Violations:")
    for name, values in active.items():
        lines.append(f"  {name}:")
        if isinstance(values, list | tuple):
            lines.extend(f"    - {value}" for value in values)
        else:
            lines.append(f"    - {values}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--commit")
    parser.add_argument("--minimal-import-smoke", choices=("passed", "failed", "not-run"), default="not-run")
    parser.add_argument("--minimal-import-command", default="")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    repository_root = args.repository_root.resolve()
    commit = args.commit or _current_commit(repository_root)
    audit = build_audit(
        repository_root=repository_root,
        commit=commit,
        minimal_import_smoke=args.minimal_import_smoke,
        minimal_import_command=args.minimal_import_command,
    )
    output = json.dumps(audit, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(output, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")

    failures = {
        "owner dependency policy": audit["owner_dependency_policy_violations"],
        "top-level owner cycles": audit["top_level_strongly_connected_components"],
        "composition back-imports": audit["composition_root_back_imports"],
        "generic runtime back-imports": audit["generic_runtime_back_imports"],
        "optional dependency leakage": audit["optional_dependency_leakage"],
    }
    active_failures = {name: value for name, value in failures.items() if value}
    if args.check:
        print(render_audit_report(audit), file=sys.stderr)
        if active_failures:
            print(json.dumps(active_failures, indent=2, sort_keys=True), file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
