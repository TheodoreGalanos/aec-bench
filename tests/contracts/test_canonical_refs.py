# ABOUTME: Tests CanonicalRef + CanonicalRefSet contracts for typo-fixer normalisation pass.
# ABOUTME: Each canonical ref carries a name and authoritative value used for near-match detection.

import dataclasses

import pytest

from aec_bench.contracts.canonical_refs import (
    CanonicalRef,
    CanonicalRefSet,
    parse_canonical_refs,
)


def test_canonical_ref_is_frozen():
    ref = CanonicalRef(name="project_id", value="EST11221")
    with pytest.raises(dataclasses.FrozenInstanceError):
        ref.value = "EST99999"  # type: ignore[misc]


def test_canonical_ref_set_iterates_in_declaration_order():
    refs = CanonicalRefSet(
        refs=(
            CanonicalRef(name="project_id", value="EST11221"),
            CanonicalRef(name="base_name", value="RAAF Base East Sale"),
        )
    )
    names = [r.name for r in refs.refs]
    assert names == ["project_id", "base_name"]


def test_parse_canonical_refs_from_toml_table():
    toml_dict = {
        "project_id": "EST11221",
        "base_name": "RAAF Base East Sale",
        "client": "Department of Works",
    }
    refs = parse_canonical_refs(toml_dict)
    assert len(refs.refs) == 3
    by_name = {r.name: r.value for r in refs.refs}
    assert by_name["project_id"] == "EST11221"
    assert by_name["base_name"] == "RAAF Base East Sale"


def test_parse_canonical_refs_empty_dict_returns_empty_set():
    refs = parse_canonical_refs({})
    assert refs.refs == ()


def test_canonical_ref_value_must_be_non_empty():
    with pytest.raises(ValueError):
        CanonicalRef(name="x", value="")
