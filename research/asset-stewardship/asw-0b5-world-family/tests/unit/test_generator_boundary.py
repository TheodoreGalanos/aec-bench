# ABOUTME: Specifies the generator-side B5-W0 canonical declaration, identity, unit, and path boundary.
# ABOUTME: Exercises fail-closed behavior before any hydraulic generator or SWMM execution exists.

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from asw_b5_generator_boundary import boundary
from support import canonical_bytes, generation_declaration

B5_ROOT = Path(__file__).parents[2]
W1_DECLARATION = B5_ROOT / "declarations" / "w1-member-authority.json"


def test_reads_exact_w1_declaration_and_reconstructs_its_bytes() -> None:
    raw = W1_DECLARATION.read_bytes()

    declaration = boundary.read_w1_declaration(raw)

    assert len(declaration["parameters"]) == 46
    assert len(declaration["composites"]) == 3
    assert boundary.canonical_json_bytes(declaration) == raw


@pytest.mark.parametrize(
    ("mutator", "failure_code"),
    [
        (lambda raw: b"\xef\xbb\xbf" + raw, "bytes.bom"),
        (lambda raw: raw.removesuffix(b"\n"), "bytes.terminal-lf"),
        (lambda raw: raw.replace(b":", b": ", 1), "bytes.noncanonical"),
        (
            lambda raw: raw.replace(
                b'{"authority":',
                b'{"authority":{},"authority":',
                1,
            ),
            "bytes.duplicate-key",
        ),
        (
            lambda raw: canonical_bytes({**json.loads(raw), "unexpected": "forbidden"}),
            "shape.top-level",
        ),
        (
            lambda raw: raw.replace(
                b'"0.00000006944444444"',
                b'"6.944444444e-8"',
                1,
            ),
            "scalar.decimal",
        ),
        (
            lambda raw: raw.replace(
                b'"identity":"well.D_w","lower":"2.80","unit":"m"',
                b'"identity":"well.D_w","lower":"2.80","unit":"s"',
                1,
            ),
            "unit.mismatch",
        ),
    ],
)
def test_rejects_malformed_w1_bytes_for_specific_reasons(
    mutator: object,
    failure_code: str,
) -> None:
    raw = W1_DECLARATION.read_bytes()
    mutate = mutator
    assert callable(mutate)

    with pytest.raises(boundary.GeneratorBoundaryError, match=failure_code):
        boundary.read_w1_declaration(mutate(raw))


@pytest.mark.parametrize(
    "candidate",
    [
        "",
        ".",
        "..",
        "/absolute.json",
        "nested//file.json",
        "nested/../file.json",
        r"nested\file.json",
        "C:drive.json",
        "nested/%2e%2e/file.json",
        "nested/ｆile.json",
        "nested/\x00file.json",
    ],
)
def test_rejects_unsafe_relative_paths(candidate: str) -> None:
    with pytest.raises(boundary.GeneratorBoundaryError, match="path.unsafe"):
        boundary.validate_safe_relative_path(candidate)


def test_accepts_only_exact_generation_declaration_shape() -> None:
    declaration = generation_declaration()
    raw = canonical_bytes(declaration)

    parsed = boundary.read_generation_declaration(raw)

    assert parsed == declaration
    assert boundary.world_generation_id(raw) == boundary.world_generation_id(boundary.canonical_json_bytes(parsed))


def test_rejects_noncanonical_or_unknown_generation_fields() -> None:
    declaration = generation_declaration()
    declaration["executed_at"] = "2026-07-27T00:00:00Z"

    with pytest.raises(
        boundary.GeneratorBoundaryError,
        match="generation.shape",
    ):
        boundary.read_generation_declaration(canonical_bytes(declaration))


def test_source_identity_rejects_symlinks_and_special_files(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.py"
    source.write_text(
        "# ABOUTME: Test source file for identity capture.\\n# ABOUTME: Contains no runtime behavior.\\n",
        encoding="utf-8",
    )
    symlink = tmp_path / "link.py"
    symlink.symlink_to(source)
    fifo = tmp_path / "source.fifo"
    os.mkfifo(fifo)

    with pytest.raises(boundary.GeneratorBoundaryError, match="source.file-type"):
        boundary.capture_source_identity(tmp_path, ("link.py",))
    with pytest.raises(boundary.GeneratorBoundaryError, match="source.file-type"):
        boundary.capture_source_identity(tmp_path, ("source.fifo",))
