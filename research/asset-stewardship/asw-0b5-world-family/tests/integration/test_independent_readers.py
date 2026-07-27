# ABOUTME: Integrates the independent generator and certifier readers over identical declaration bytes.
# ABOUTME: Audits source separation, dependency identities, and distinct rejection ownership.

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from certifier import boundary as certifier
from generator import boundary as generator
from support import canonical_bytes, generation_declaration

B5_ROOT = Path(__file__).parents[2]
SOURCE_ROOT = B5_ROOT
W1_DECLARATION = B5_ROOT / "declarations" / "w1-member-authority.json"


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_independent_readers_agree_on_valid_w1_and_generation_bytes() -> None:
    w1_raw = W1_DECLARATION.read_bytes()
    generation_raw = canonical_bytes(generation_declaration())

    assert generator.read_w1_declaration(w1_raw) == certifier.read_w1_declaration(w1_raw)
    assert generator.canonical_json_bytes(generator.read_w1_declaration(w1_raw)) == certifier.canonical_json_bytes(
        certifier.read_w1_declaration(w1_raw)
    )
    assert generator.world_generation_id(generation_raw) == certifier.world_generation_id(generation_raw)


def test_reader_source_graphs_do_not_import_each_other_or_lineage() -> None:
    generator_path = SOURCE_ROOT / "generator" / "boundary.py"
    certifier_path = SOURCE_ROOT / "certifier" / "boundary.py"

    generator_imports = imported_modules(generator_path)
    certifier_imports = imported_modules(certifier_path)

    assert not {
        "certifier",
        "lineage",
    }.intersection(generator_imports)
    assert not {
        "generator",
        "lineage",
    }.intersection(certifier_imports)
    assert generator_path.read_bytes() != certifier_path.read_bytes()


def test_readers_reject_same_bad_bytes_through_distinct_error_types() -> None:
    bad = W1_DECLARATION.read_bytes().replace(b":", b": ", 1)

    with pytest.raises(generator.GeneratorBoundaryError) as generator_failure:
        generator.read_w1_declaration(bad)
    with pytest.raises(certifier.CertifierBoundaryError) as certifier_failure:
        certifier.read_w1_declaration(bad)

    assert "generator:" in str(generator_failure.value)
    assert "certifier:" in str(certifier_failure.value)
    assert type(generator_failure.value) is not type(certifier_failure.value)


def test_source_and_dependency_capture_are_content_addressed_and_separate() -> None:
    generator_root = SOURCE_ROOT / "generator"
    certifier_root = SOURCE_ROOT / "certifier"
    source_files = ("boundary.py", "cli.py")
    dependencies = (("python-standard-library", "3.13"),)

    generator_source = generator.capture_source_identity(
        generator_root,
        source_files,
    )
    certifier_source = certifier.capture_source_identity(
        certifier_root,
        source_files,
    )
    generator_dependencies = generator.capture_dependency_identity(dependencies)
    certifier_dependencies = certifier.capture_dependency_identity(dependencies)

    assert generator_source != certifier_source
    assert generator_dependencies != certifier_dependencies
    assert len(generator_source) == len(certifier_source) == 64
    assert len(generator_dependencies) == len(certifier_dependencies) == 64
