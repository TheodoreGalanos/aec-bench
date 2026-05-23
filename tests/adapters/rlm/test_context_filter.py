# ABOUTME: Tests for the RLM context filter and progress log formatting.
# ABOUTME: Validates threshold-based filtering, grep detection, error passthrough, and code preview.

from aec_bench.adapters.rlm.adapter import _format_code_preview
from aec_bench.adapters.rlm.context_filter import (
    ContextFilter,
    build_context_message,
    format_var_diff,
)
from aec_bench.contracts.constitution import InformationMinimalityParams


class TestBuildContextMessage:
    """Tests for build_context_message() — the core context gatekeeper."""

    def test_short_output_passes_through(self) -> None:
        result = build_context_message(
            stdout="hello world",
            error=None,
            code="print('hello world')",
        )
        assert result == "hello world"

    def test_empty_output_returns_no_output(self) -> None:
        result = build_context_message(
            stdout="",
            error=None,
            code="x = 1",
        )
        assert result == "(no output)"

    def test_error_always_passes_through_verbatim(self) -> None:
        long_error = "Traceback (most recent call last):\n" + "x" * 5000
        result = build_context_message(
            stdout="",
            error=long_error,
            code="bad_code()",
        )
        assert result == long_error

    def test_grep_output_under_10k_passes_through(self) -> None:
        grep_output = "3 match(es) for /voltage/:\n" + "x" * 8000
        result = build_context_message(
            stdout=grep_output,
            error=None,
            code="grep(doc, 'voltage')",
        )
        assert result == grep_output

    def test_grep_output_over_10k_gets_truncated(self) -> None:
        lines = "3 match(es) for /voltage/:\n" + "x" * 12000
        result = build_context_message(
            stdout=lines,
            error=None,
            code="grep(doc, 'voltage')",
        )
        assert len(result) < len(lines)
        assert "match(es) for /voltage/" in result
        assert "truncated" in result.lower()

    def test_large_output_gets_metadata_treatment(self) -> None:
        big_text = "Public Works Project PW1001\n" + "x" * 5000
        result = build_context_message(
            stdout=big_text,
            error=None,
            code="print(design_report)",
        )
        assert len(result) < len(big_text)
        assert "Public Works Project PW1001" in result
        # Should mention the size
        assert "5,031" in result or "chars" in result.lower()

    def test_output_exactly_at_threshold_passes_through(self) -> None:
        text = "x" * 2000
        result = build_context_message(
            stdout=text,
            error=None,
            code="print(x)",
        )
        assert result == text

    def test_output_one_over_threshold_gets_metadata(self) -> None:
        text = "x" * 2001
        result = build_context_message(
            stdout=text,
            error=None,
            code="print(x)",
        )
        assert len(result) < len(text)

    def test_metadata_includes_preview(self) -> None:
        text = "The quick brown fox " * 200  # ~4000 chars
        result = build_context_message(
            stdout=text,
            error=None,
            code="print(doc)",
        )
        # Should contain a preview of the content
        assert "The quick brown fox" in result

    def test_variable_assignment_gets_metadata(self) -> None:
        """When code assigns to a variable, the metadata should reference it."""
        big_text = "document content here\n" + "y" * 3000
        result = build_context_message(
            stdout=big_text,
            error=None,
            code="doc = READ('design_report')",
            new_vars=["doc"],
        )
        assert "doc" in result

    def test_none_stdout_with_no_error_returns_no_output(self) -> None:
        result = build_context_message(
            stdout=None,
            error=None,
            code="x = 1",
        )
        assert result == "(no output)"


class TestFormatVarDiff:
    """Tests for format_var_diff() — variable diff formatting."""

    def test_no_changes(self) -> None:
        result = format_var_diff(new=[], removed=[], repl_vars={})
        assert result == ""

    def test_new_string_variable(self) -> None:
        result = format_var_diff(
            new=["doc"],
            removed=[],
            repl_vars={"doc": "A long document..." + "x" * 5000},
        )
        assert "doc" in result
        assert "str" in result
        assert "5,017" in result or "chars" in result.lower()

    def test_new_dict_variable(self) -> None:
        result = format_var_diff(
            new=["results"],
            removed=[],
            repl_vars={"results": {"a": 1, "b": 2, "c": 3}},
        )
        assert "results" in result
        assert "dict" in result
        assert "3" in result

    def test_new_list_variable(self) -> None:
        result = format_var_diff(
            new=["items"],
            removed=[],
            repl_vars={"items": [1, 2, 3, 4, 5]},
        )
        assert "items" in result
        assert "list" in result
        assert "5" in result

    def test_removed_variable(self) -> None:
        result = format_var_diff(
            new=[],
            removed=["old_var"],
            repl_vars={},
        )
        assert "old_var" in result
        assert "removed" in result.lower()

    def test_multiple_new_variables(self) -> None:
        result = format_var_diff(
            new=["alpha", "beta"],
            removed=[],
            repl_vars={"alpha": 42, "beta": "hello"},
        )
        assert "alpha" in result
        assert "beta" in result


class TestFormatCodePreview:
    """Tests for _format_code_preview() — progress log formatting."""

    def test_simple_code_truncated_to_80(self) -> None:
        result = _format_code_preview("print('hello world')")
        assert result == "print('hello world')"

    def test_long_code_truncated(self) -> None:
        code = "x = " + "a" * 200
        result = _format_code_preview(code)
        assert len(result) == 80

    def test_extract_shows_fields(self) -> None:
        code = 'result = extract(spec_summaries, fields=["voltage", "cable_size", "protection"])'
        result = _format_code_preview(code)
        assert "voltage" in result
        assert "cable_size" in result
        assert "protection" in result
        assert "extract(spec_summaries" in result

    def test_extract_multiline_fields(self) -> None:
        code = 'info = extract(design_report, fields=[\n    "project_id",\n    "location",\n    "objectives",\n])'
        result = _format_code_preview(code)
        assert "project_id" in result
        assert "location" in result
        assert "objectives" in result
        assert "extract(design_report" in result

    def test_extract_no_fields_falls_back(self) -> None:
        code = "result = extract(doc, fields=some_var)"
        result = _format_code_preview(code)
        # No bracket-delimited fields, should fall back to first line
        assert "extract" in result

    def test_non_extract_first_line(self) -> None:
        code = "for d in drawings:\n    print(d)"
        result = _format_code_preview(code)
        assert result == "for d in drawings:"

    def test_grep_not_affected(self) -> None:
        code = "print(grep(doc, 'voltage'))"
        result = _format_code_preview(code)
        assert result == "print(grep(doc, 'voltage'))"


class TestContextFilterWithParams:
    def test_uses_default_params(self) -> None:
        cf = ContextFilter(InformationMinimalityParams())
        # Exactly at threshold (2000) — included verbatim
        out = cf.build_context_message(
            stdout="x" * 2000,
            error=None,
            code="print('x'*2000)",
        )
        assert out == "x" * 2000
        # One char over threshold — becomes metadata
        out2 = cf.build_context_message(
            stdout="x" * 2001,
            error=None,
            code="print('x'*2001)",
        )
        assert "Output: 2,001 chars" in out2

    def test_custom_default_threshold(self) -> None:
        cf = ContextFilter(InformationMinimalityParams(default_threshold=500))
        out = cf.build_context_message(
            stdout="x" * 600,
            error=None,
            code="foo",
        )
        assert "Output: 600 chars" in out

    def test_custom_search_threshold(self) -> None:
        cf = ContextFilter(InformationMinimalityParams(search_threshold=50))
        grep_output = "10 match(es) for /pattern/ in var:\n" + ("line\n" * 200)
        out = cf.build_context_message(
            stdout=grep_output,
            error=None,
            code="grep(var, 'pattern')",
        )
        # Grep output over the 50-char threshold should be truncated
        assert "truncated" in out

    def test_error_always_verbatim(self) -> None:
        cf = ContextFilter(InformationMinimalityParams(default_threshold=10))
        out = cf.build_context_message(
            stdout=None,
            error="Traceback (most recent call last):\n" + ("line\n" * 100),
            code="broken()",
        )
        assert "Traceback" in out
        assert "line\n" * 100 in out
