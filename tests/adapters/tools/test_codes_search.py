# ABOUTME: Tests for the codes_search tool executor in aec-bench Python.
# ABOUTME: Covers CLI argument translation and subprocess output capture.

from pathlib import Path

from aec_bench.adapters.tools.codes_search import CodesSearchToolExecutor


def test_codes_search_executor_invokes_cli_with_expected_flags(tmp_path: Path) -> None:
    script_path = tmp_path / "codes_search.py"
    script_path.write_text(
        "import json, sys\nprint(json.dumps(sys.argv[1:]))\n",
        encoding="utf-8",
    )
    executor = CodesSearchToolExecutor(workspace_dir=tmp_path, script_path=script_path)

    result = executor.execute(
        {
            "query": "egress width",
            "jurisdiction": "new_york_city",
            "code_type": "Building Code",
            "limit": 2,
        }
    )

    assert result.error_message is None
    assert "--query" in result.output_text
    assert "egress width" in result.output_text
    assert "--code-type" in result.output_text


def test_codes_search_executor_reports_script_failure(tmp_path: Path) -> None:
    script_path = tmp_path / "codes_search.py"
    script_path.write_text(
        "import sys\nprint('boom', file=sys.stderr)\nsys.exit(2)\n",
        encoding="utf-8",
    )
    executor = CodesSearchToolExecutor(workspace_dir=tmp_path, script_path=script_path)

    result = executor.execute(
        {
            "query": "egress width",
            "jurisdiction": "new_york_city",
            "code_type": "Building Code",
        }
    )

    assert result.error_message == "codes_search failed with exit code 2"
    assert "boom" in result.output_text
