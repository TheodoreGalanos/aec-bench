# ABOUTME: Tests for shared contract validation helpers in the aec-bench contracts package.
# ABOUTME: These tests define the expected behavior for string and path validation primitives.

import pytest
from hypothesis import given
from hypothesis import strategies as st

from aec_bench.contracts.validators import ensure_non_empty_string, ensure_relative_path


def test_ensure_non_empty_string_accepts_normal_text() -> None:
    assert ensure_non_empty_string("electrical") == "electrical"


def test_ensure_non_empty_string_rejects_blank_text() -> None:
    with pytest.raises(ValueError):
        ensure_non_empty_string("   ")


def test_ensure_non_empty_string_rejects_empty_string() -> None:
    with pytest.raises(ValueError):
        ensure_non_empty_string("")


def test_ensure_non_empty_string_rejects_tabs_and_newlines() -> None:
    with pytest.raises(ValueError):
        ensure_non_empty_string("\t\n")


def test_ensure_relative_path_accepts_relative_path() -> None:
    assert ensure_relative_path("environment/Dockerfile") == "environment/Dockerfile"


def test_ensure_relative_path_rejects_absolute_path() -> None:
    with pytest.raises(ValueError):
        ensure_relative_path("/workspace/output.jsonl")


def test_ensure_relative_path_rejects_blank_string() -> None:
    with pytest.raises(ValueError):
        ensure_relative_path("  ")


@given(st.text(min_size=1).filter(lambda s: s.strip()))
def test_non_empty_string_roundtrips_any_non_blank_text(text: str) -> None:
    assert ensure_non_empty_string(text) == text


@given(st.text().filter(lambda s: not s.strip()))
def test_non_empty_string_rejects_all_blank_text(text: str) -> None:
    with pytest.raises(ValueError):
        ensure_non_empty_string(text)


@given(
    st.text(
        alphabet=st.characters(blacklist_characters="/"),
        min_size=1,
    ).filter(lambda s: s.strip())
)
def test_relative_path_accepts_any_non_absolute_non_blank_path(path: str) -> None:
    assert ensure_relative_path(path) == path
