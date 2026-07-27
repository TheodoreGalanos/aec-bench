# ABOUTME: Specifies the certifier-side B5-W0 canonical declaration, identity, unit, and path boundary.
# ABOUTME: Proves this reader fails independently without importing generator or SWMM implementation.

from __future__ import annotations

import json
from pathlib import Path

import pytest
from asw_b5_certifier_boundary import boundary
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
    ("raw_factory", "failure_code"),
    [
        (lambda raw: b"\xef\xbb\xbf" + raw, "input-bom"),
        (lambda raw: raw.removesuffix(b"\n"), "input-final-newline"),
        (lambda raw: raw.replace(b",", b", ", 1), "input-not-canonical"),
        (
            lambda raw: raw.replace(
                b'{"authority":',
                b'{"authority":{},"authority":',
                1,
            ),
            "input-duplicate-name",
        ),
        (
            lambda raw: canonical_bytes({**json.loads(raw), "unexpected": "forbidden"}),
            "declaration-top-level",
        ),
        (
            lambda raw: raw.replace(
                b'"0.00000003333333333"',
                b'"3.333333333e-8"',
                1,
            ),
            "declaration-decimal",
        ),
        (
            lambda raw: raw.replace(
                b'"identity":"pump.H_0","lower":"17.0","unit":"m"',
                '"identity":"pump.H_0","lower":"17.0","unit":"m³/s"'.encode(),
                1,
            ),
            "declaration-unit",
        ),
    ],
)
def test_rejects_malformed_w1_bytes_with_certifier_owned_failures(
    raw_factory: object,
    failure_code: str,
) -> None:
    raw = W1_DECLARATION.read_bytes()
    mutate = raw_factory
    assert callable(mutate)

    with pytest.raises(boundary.CertifierBoundaryError, match=failure_code):
        boundary.read_w1_declaration(mutate(raw))


@pytest.mark.parametrize(
    "candidate",
    [
        ".",
        "../escape",
        "nested/./file",
        "nested//file",
        "nested\\file",
        "nested:file",
        "%2E%2E/file",
        "résumé.json",
        "nested/\x1ffile",
    ],
)
def test_rejects_unsafe_relative_paths(candidate: str) -> None:
    with pytest.raises(boundary.CertifierBoundaryError, match="unsafe-path"):
        boundary.validate_safe_relative_path(candidate)


def test_reads_and_hashes_generation_declaration_independently() -> None:
    declaration = generation_declaration()
    raw = canonical_bytes(declaration)

    parsed = boundary.read_generation_declaration(raw)

    assert parsed == declaration
    assert boundary.world_generation_id(raw).islower()
    assert len(boundary.world_generation_id(raw)) == 64


def test_rejects_bad_generation_hash_and_path_fields() -> None:
    declaration = generation_declaration()
    declaration["member_content_id"] = "A" * 64

    with pytest.raises(
        boundary.CertifierBoundaryError,
        match="generation-content-id",
    ):
        boundary.read_generation_declaration(canonical_bytes(declaration))

    declaration = generation_declaration()
    declaration["generator"]["source_path"] = "/tmp/source"
    with pytest.raises(
        boundary.CertifierBoundaryError,
        match="generation-generator-shape",
    ):
        boundary.read_generation_declaration(canonical_bytes(declaration))
