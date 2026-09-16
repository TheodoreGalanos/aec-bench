# ABOUTME: Verifies the documented AEC-Bench import and command surfaces.
# ABOUTME: Prevents package facades and CLI registrations from growing without review.

from __future__ import annotations

import ast
import importlib
import re
from importlib.util import find_spec
from pathlib import Path
from types import ModuleType

import pytest

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
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "_EXPORTS":
            assert node.value is not None
            exports = ast.literal_eval(node.value)
            if object_name in exports:
                target_module, target_name = exports[object_name]
                return _source_declares(target_module, target_name)
    return (
        any(
            isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) and node.name == object_name
            for node in tree.body
        )
        or any(
            isinstance(node, ast.Import | ast.ImportFrom)
            and any((alias.asname or alias.name.rsplit(".", 1)[-1]) == object_name for alias in node.names)
            for node in tree.body
        )
        or any(
            isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == object_name for target in node.targets)
            for node in tree.body
        )
    )


def _missing_optional_dependency(module_name: str, error: ModuleNotFoundError) -> bool:
    if module_name in {"aec_bench.harness.harbor_workflow", "aec_bench.harness.harbor_runtime"}:
        return error.name == "harbor" and find_spec("harbor") is None
    return (
        module_name == "aec_bench.evolution"
        and error.name is not None
        and error.name in {"numpy", "ribs"}
        and find_spec(error.name) is None
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
                assert hasattr(module, object_name), f"{module_name}.{object_name} is missing"
            except ModuleNotFoundError as error:
                if not _missing_optional_dependency(module_name, error):
                    raise
                # Resolve the declared target even when its optional dependency is absent.
                assert _source_declares(module_name, object_name), f"{module_name}.{object_name} is missing"

    package_facades = [module_name for module_name in entries if _source_path(module_name).name == "__init__.py"]
    for module_name in package_facades:
        _, expected = entries[module_name]
        try:
            module = _module(module_name)
        except ModuleNotFoundError as error:
            if not _missing_optional_dependency(module_name, error):
                raise
            assert _source_all(module_name) == expected
        else:
            assert tuple(module.__all__) == expected


def test_experimental_surfaces_are_importable_without_becoming_root_exports() -> None:
    entries = _python_inventory()
    root = _module("aec_bench")
    for module_name, (classification, objects) in entries.items():
        if classification != "Experimental":
            continue
        try:
            module = _module(module_name)
        except ModuleNotFoundError as error:
            if not _missing_optional_dependency(module_name, error):
                raise
            for object_name in objects:
                assert _source_declares(module_name, object_name), f"{module_name}.{object_name} is missing"
            continue
        declared = getattr(module, "__all__", ())
        for object_name in objects:
            if declared:
                assert object_name in declared, f"{module_name}.{object_name} is not declared"
            else:
                assert hasattr(module, object_name), f"{module_name}.{object_name} is missing"
        assert module_name.rsplit(".", 1)[0] not in root.__all__


def test_registered_cli_commands_match_the_inventory() -> None:
    assert _registered_cli_commands() == _supported_cli_commands()


def test_inventory_handles_a_lazy_export_with_an_absent_evolution_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    import tests.test_public_api_inventory as inventory

    module = ModuleType("aec_bench.evolution")
    monkeypatch.setattr(module, "__all__", ("ReportWriter",), raising=False)

    def missing_dependency(name: str) -> object:
        raise ModuleNotFoundError("No module named 'numpy'", name="numpy")

    monkeypatch.setattr(module, "__getattr__", missing_dependency, raising=False)
    monkeypatch.setattr(inventory, "_module", lambda name: module)
    monkeypatch.setattr(inventory, "find_spec", lambda name: None)
    monkeypatch.setattr(
        inventory,
        "_python_inventory",
        lambda: {
            "aec_bench.evolution": ("Supported", ("ReportWriter",)),
        },
    )
    inventory.test_supported_facade_exports_match_the_inventory()


def test_inventory_does_not_hide_missing_repository_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    import tests.test_public_api_inventory as inventory

    def broken_import(name: str) -> ModuleType:
        raise ModuleNotFoundError("broken repository import", name="aec_bench.evolution.missing")

    monkeypatch.setattr(inventory, "_module", broken_import)
    monkeypatch.setattr(
        inventory,
        "_python_inventory",
        lambda: {
            "aec_bench.evolution": ("Supported", ("CandidateProposal",)),
        },
    )
    with pytest.raises(ModuleNotFoundError, match="broken repository import"):
        inventory.test_supported_facade_exports_match_the_inventory()


def test_lazy_source_check_requires_the_target_definition(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import tests.test_public_api_inventory as inventory

    facade = tmp_path / "facade.py"
    facade.write_text('_EXPORTS: dict = {"ReportWriter": ("aec_bench.evolution.application", "missing_symbol")}\n')
    source_path = inventory._source_path
    monkeypatch.setattr(
        inventory, "_source_path", lambda name: facade if name == "aec_bench.evolution" else source_path(name)
    )
    assert not inventory._source_declares("aec_bench.evolution", "ReportWriter")


def test_inventory_does_not_treat_a_broken_installed_dependency_as_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    import tests.test_public_api_inventory as inventory

    monkeypatch.setattr(inventory, "find_spec", lambda name: object())
    error = ModuleNotFoundError("broken installed dependency", name="numpy")
    assert not inventory._missing_optional_dependency("aec_bench.evolution", error)
