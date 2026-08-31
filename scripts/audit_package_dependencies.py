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
from pathlib import Path

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
IGNORED_SOURCE_PARTS = {"__pycache__", "node_modules"}
DEFAULT_OWNER_POLICY_PATH = Path(__file__).with_name("owner_dependencies.toml")


def load_owner_dependency_policy(path: Path = DEFAULT_OWNER_POLICY_PATH) -> dict[str, set[str]]:
    """Load the complete owner dependency policy without importing source modules."""
    with path.open("rb") as policy_file:
        document = tomllib.load(policy_file)
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


def validate_owner_dependency_policy(owner_graph: dict[str, set[str]], policy: dict[str, set[str]]) -> tuple[str, ...]:
    """Return deterministic violations between the declared and observed owner graph."""
    actual_owners = set(owner_graph)
    policy_owners = set(policy)
    violations = [f"missing policy for owner: {owner}" for owner in sorted(actual_owners - policy_owners)]
    violations.extend(f"policy declares unknown owner: {owner}" for owner in sorted(policy_owners - actual_owners))
    for source in sorted(policy_owners):
        for target in sorted(policy[source] - actual_owners):
            violations.append(f"policy declares unknown dependency: {source} -> {target}")
    for source in sorted(actual_owners):
        for target in sorted(owner_graph[source] - policy.get(source, set())):
            violations.append(f"undeclared owner dependency: {source} -> {target}")
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
    for source, targets in graph.items():
        source_owner = _owner(source)
        if source_owner is None:
            continue
        owner_graph[source_owner].update(
            target_owner
            for target in targets
            if (target_owner := _owner(target)) is not None and target_owner != source_owner
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
    optional_leakage = sorted(
        f"{module}: {', '.join(sorted(external_roots[module] & OPTIONAL_RUNTIME_ROOTS))}"
        for module in known_modules
        if _owner(module) in NEUTRAL_OWNERS and external_roots[module] & OPTIONAL_RUNTIME_ROOTS
    )
    owner_policy = load_owner_dependency_policy(repository_root / "scripts" / DEFAULT_OWNER_POLICY_PATH.name)
    owner_policy_violations = validate_owner_dependency_policy(owner_graph, owner_policy)

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
        "optional dependency leakage": audit["optional_dependency_leakage"],
    }
    active_failures = {name: value for name, value in failures.items() if value}
    if args.check and active_failures:
        print(json.dumps(active_failures, indent=2, sort_keys=True), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
