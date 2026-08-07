# ABOUTME: Enforces the small dependency boundaries that protect task and contract ownership.
# ABOUTME: Prevents provider SDKs and execution frameworks from leaking into neutral packages.

from __future__ import annotations

import ast
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
NEUTRAL_ROOTS = (
    REPOSITORY_ROOT / "src" / "aec_bench" / "contracts",
    REPOSITORY_ROOT / "src" / "aec_bench" / "task_world_templates",
)
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


def _top_level_imports(source_path: Path) -> set[str]:
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".", maxsplit=1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".", maxsplit=1)[0])
    return imported


def test_neutral_contracts_and_worlds_do_not_import_optional_runtimes() -> None:
    violations = {
        str(source_path.relative_to(REPOSITORY_ROOT)): sorted(imported)
        for neutral_root in NEUTRAL_ROOTS
        for source_path in neutral_root.rglob("*.py")
        if (imported := _top_level_imports(source_path) & OPTIONAL_RUNTIME_ROOTS)
    }

    assert violations == {}


def test_worlds_do_not_import_provider_adapters() -> None:
    world_root = REPOSITORY_ROOT / "src" / "aec_bench" / "task_world_templates"
    violations: list[str] = []
    for source_path in world_root.rglob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        for node in ast.walk(tree):
            module = node.module if isinstance(node, ast.ImportFrom) else None
            names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else []
            if (module and module.startswith("aec_bench.providers")) or any(
                name.startswith("aec_bench.providers") for name in names
            ):
                violations.append(str(source_path.relative_to(REPOSITORY_ROOT)))

    assert sorted(set(violations)) == []
