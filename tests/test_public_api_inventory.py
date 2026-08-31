# ABOUTME: Verifies the documented AEC-Bench import and command surfaces.
# ABOUTME: Prevents package facades and CLI registrations from growing without review.

from __future__ import annotations

import ast
import importlib
import re
from pathlib import Path
from types import ModuleType

INVENTORY = Path("docs/API_INVENTORY.md")
MAIN_CLI = Path("src/aec_bench/cli/main.py")


def _python_inventory() -> dict[str, tuple[str, tuple[str, ...]]]:
    text = INVENTORY.read_text(encoding="utf-8")
    entries: dict[str, tuple[str, tuple[str, ...]]] = {}
    pattern = re.compile(r"^\| `([^`]+)` \| (Supported|Experimental|Legacy) \| (.*?) \|", re.MULTILINE)
    for module_name, classification, objects in pattern.findall(text):
        assert module_name not in entries, f"duplicate public API inventory entry: {module_name}"
        entries[module_name] = (classification, tuple(re.findall(r"`([^`]+)`", objects)))
    return entries


def _module(module_name: str) -> ModuleType:
    return importlib.import_module(module_name)


def _source_declares(module_name: str, object_name: str) -> bool:
    source = _source_path(module_name)
    tree = ast.parse(source.read_text(encoding="utf-8"))
    return any(
        isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) and node.name == object_name
        for node in tree.body
    ) or any(
        isinstance(node, ast.Import | ast.ImportFrom)
        and any((alias.asname or alias.name.rsplit(".", 1)[-1]) == object_name for alias in node.names)
        for node in tree.body
    )


def _source_all(module_name: str) -> tuple[str, ...]:
    source = _source_path(module_name)
    tree = ast.parse(source.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets
        ):
            value = ast.literal_eval(node.value)
            return tuple(value)
    return ()


def _source_path(module_name: str) -> Path:
    source = Path("src", *module_name.split(".")).with_suffix(".py")
    if source.is_file():
        return source
    return Path("src", *module_name.split("."), "__init__.py")


def _registered_cli_commands() -> set[str]:
    tree = ast.parse(MAIN_CLI.read_text(encoding="utf-8"))
    commands: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr == "command" and node.args and isinstance(node.args[0], ast.Constant):
            commands.add(str(node.args[0].value))
        if node.func.attr == "add_typer":
            for keyword in node.keywords:
                if keyword.arg == "name" and isinstance(keyword.value, ast.Constant):
                    commands.add(str(keyword.value.value))
    return commands


def _supported_cli_commands() -> set[str]:
    text = INVENTORY.read_text(encoding="utf-8")
    match = re.search(r"^\| Supported \| (.*?) \|$", text, re.MULTILINE)
    assert match is not None
    return set(re.findall(r"`([^`]+)`", match.group(1)))


def test_inventory_has_one_classification_for_each_documented_python_surface() -> None:
    entries = _python_inventory()
    assert entries
    assert all(classification in {"Supported", "Experimental", "Legacy"} for classification, _ in entries.values())
    assert "aec_bench" in entries
    assert "aec_bench.worlds" in entries


def test_supported_facade_exports_match_the_inventory() -> None:
    entries = _python_inventory()
    for module_name, (classification, objects) in entries.items():
        if classification != "Supported":
            continue
        for object_name in objects:
            try:
                module = _module(module_name)
            except ModuleNotFoundError:
                # Optional extras are not installed in the core test profile.
                assert _source_declares(module_name, object_name), f"{module_name}.{object_name} is missing"
            else:
                assert hasattr(module, object_name), f"{module_name}.{object_name} is missing"

    package_facades = [module_name for module_name in entries if _source_path(module_name).name == "__init__.py"]
    for module_name in package_facades:
        _, expected = entries[module_name]
        try:
            module = _module(module_name)
        except ModuleNotFoundError:
            assert _source_all(module_name) == expected
        else:
            assert tuple(module.__all__) == expected


def test_experimental_surfaces_are_importable_without_becoming_root_exports() -> None:
    entries = _python_inventory()
    root = _module("aec_bench")
    for module_name, (classification, objects) in entries.items():
        if classification != "Experimental":
            continue
        module = _module(module_name)
        declared = getattr(module, "__all__", ())
        for object_name in objects:
            if declared:
                assert object_name in declared, f"{module_name}.{object_name} is not declared"
            else:
                assert hasattr(module, object_name), f"{module_name}.{object_name} is missing"
        assert module_name.rsplit(".", 1)[0] not in root.__all__


def test_registered_cli_commands_match_the_inventory() -> None:
    assert _registered_cli_commands() == _supported_cli_commands()
