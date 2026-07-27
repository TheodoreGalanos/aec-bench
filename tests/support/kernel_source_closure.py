# ABOUTME: Computes the internal Python import closure for fixed-kernel source tests.
# ABOUTME: Resolves package initializers, relative imports, and literal dynamic imports without importing code.

from __future__ import annotations

import ast
from collections import deque
from pathlib import Path


def internal_source_closure(
    *,
    project_root: Path,
    seed_paths: tuple[str, ...],
    dynamic_paths: tuple[str, ...] = (),
) -> tuple[str, ...]:
    """Return every internal Python source reachable from the supplied owned paths."""
    source_root = project_root / "src"
    path_by_module, module_by_path, package_modules = _module_index(source_root)
    pending = deque((*seed_paths, *dynamic_paths))
    closure: set[str] = set()

    while pending:
        inventory_path = pending.popleft()
        if inventory_path in closure:
            continue
        closure.add(inventory_path)
        module_name = module_by_path.get(inventory_path)
        if module_name is None:
            continue
        source_path = source_root / inventory_path
        imported_modules = _internal_imports(
            source_path=source_path,
            module_name=module_name,
            is_package=module_name in package_modules,
        )
        for imported_module in imported_modules:
            for dependency_path in _import_source_paths(
                imported_module,
                path_by_module=path_by_module,
                package_modules=package_modules,
            ):
                if dependency_path not in closure:
                    pending.append(dependency_path)

    return tuple(sorted(closure))


def _module_index(
    source_root: Path,
) -> tuple[dict[str, str], dict[str, str], set[str]]:
    path_by_module: dict[str, str] = {}
    module_by_path: dict[str, str] = {}
    package_modules: set[str] = set()
    for source_path in sorted((source_root / "aec_bench").rglob("*.py")):
        relative_path = source_path.relative_to(source_root).as_posix()
        module_parts = list(source_path.relative_to(source_root).with_suffix("").parts)
        if module_parts[-1] == "__init__":
            module_parts.pop()
            package_modules.add(".".join(module_parts))
        module_name = ".".join(module_parts)
        path_by_module[module_name] = relative_path
        module_by_path[relative_path] = module_name
    return path_by_module, module_by_path, package_modules


def _internal_imports(
    *,
    source_path: Path,
    module_name: str,
    is_package: bool,
) -> set[str]:
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    collector = _ImportCollector(
        current_package=module_name if is_package else module_name.rpartition(".")[0],
    )
    collector.visit(tree)
    return collector.modules


def _import_source_paths(
    module_name: str,
    *,
    path_by_module: dict[str, str],
    package_modules: set[str],
) -> tuple[str, ...]:
    if not module_name.startswith("aec_bench"):
        return ()
    parts = module_name.split(".")
    source_paths: list[str] = []
    for end in range(1, len(parts) + 1):
        candidate = ".".join(parts[:end])
        source_path = path_by_module.get(candidate)
        if source_path is None:
            continue
        if end == len(parts) or candidate in package_modules:
            source_paths.append(source_path)
    return tuple(source_paths)


class _ImportCollector(ast.NodeVisitor):
    def __init__(self, *, current_package: str) -> None:
        self._current_package = current_package
        self.modules: set[str] = set()

    def visit_If(self, node: ast.If) -> None:
        if _is_type_checking_guard(node.test):
            for statement in node.orelse:
                self.visit(statement)
            return
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        self.modules.update(alias.name for alias in node.names if alias.name.startswith("aec_bench"))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        base_module = _resolve_import_from(
            current_package=self._current_package,
            module=node.module,
            level=node.level,
        )
        if not base_module.startswith("aec_bench"):
            return
        self.modules.add(base_module)
        self.modules.update(f"{base_module}.{alias.name}" for alias in node.names if alias.name != "*")

    def visit_Call(self, node: ast.Call) -> None:
        if _is_import_module_call(node.func) and node.args:
            module_arg = node.args[0]
            if isinstance(module_arg, ast.Constant) and isinstance(module_arg.value, str):
                if module_arg.value.startswith("aec_bench"):
                    self.modules.add(module_arg.value)
        self.generic_visit(node)


def _resolve_import_from(
    *,
    current_package: str,
    module: str | None,
    level: int,
) -> str:
    if level == 0:
        return module or ""
    package_parts = current_package.split(".") if current_package else []
    retained = len(package_parts) - (level - 1)
    if retained < 0:
        return ""
    resolved_parts = package_parts[:retained]
    if module:
        resolved_parts.extend(module.split("."))
    return ".".join(resolved_parts)


def _is_type_checking_guard(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Name)
        and node.id == "TYPE_CHECKING"
        or isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "typing"
        and node.attr == "TYPE_CHECKING"
    )


def _is_import_module_call(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Name)
        and node.id == "import_module"
        or isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "importlib"
        and node.attr == "import_module"
    )
