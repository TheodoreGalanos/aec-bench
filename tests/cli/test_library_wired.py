# ABOUTME: Regression test ensuring `aec-bench library export` is registered on the root CLI.
# ABOUTME: Verifies the library subcommand group is wired into the main Typer app.

from typer.testing import CliRunner

from aec_bench.cli.main import app

runner = CliRunner()


def test_library_subcommand_is_registered() -> None:
    result = runner.invoke(app, ["library", "--help"])
    assert result.exit_code == 0
    assert "export" in result.output.lower()
