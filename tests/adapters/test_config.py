# ABOUTME: Tests for adapter configuration helpers in aec-bench Python.
# ABOUTME: Covers explicit model alias resolution without hidden defaults.

from aec_bench.adapters.config import resolve_model_alias


def test_resolve_model_alias_uses_explicit_alias_map() -> None:
    resolved = resolve_model_alias(
        "sonnet",
        aliases={"sonnet": "claude-3-7-sonnet-20250219"},
    )

    assert resolved == "claude-3-7-sonnet-20250219"


def test_resolve_model_alias_returns_verbatim_model_when_no_alias_exists() -> None:
    resolved = resolve_model_alias("gpt-5.4", aliases={"sonnet": "claude-3-7-sonnet-20250219"})

    assert resolved == "gpt-5.4"
