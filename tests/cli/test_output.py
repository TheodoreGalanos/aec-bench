# ABOUTME: Tests for the CLI output envelope infrastructure.
# ABOUTME: Validates CLIResult serialisation, emit() behaviour, and TTY detection.

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from click.exceptions import Exit as ClickExit

from aec_bench.cli.output import CLIResult, emit, is_tty


class TestCLIResult:
    def test_success_status(self) -> None:
        result = CLIResult.build(command="test", data={"key": "value"}, errors=[])
        assert result.status == "success"
        assert result.data == {"key": "value"}

    def test_partial_status(self) -> None:
        result = CLIResult.build(command="test", data={"key": "value"}, errors=["something failed"])
        assert result.status == "partial"

    def test_error_status(self) -> None:
        result = CLIResult.build(command="test", data=None, errors=["fatal error"])
        assert result.status == "error"

    def test_to_dict_has_all_fields(self) -> None:
        result = CLIResult.build(
            command="evaluate",
            data={"n": 1},
            errors=[],
            start_time=time.monotonic() - 1.5,
        )
        d = result.to_dict()
        assert set(d.keys()) == {
            "command",
            "status",
            "data",
            "errors",
            "version",
            "duration_seconds",
        }
        assert d["command"] == "evaluate"
        assert d["status"] == "success"
        assert d["duration_seconds"] >= 1.0

    def test_duration_zero_when_no_start_time(self) -> None:
        result = CLIResult.build(command="test", data={}, errors=[])
        assert result.duration_seconds == 0.0

    def test_exit_code_success(self) -> None:
        result = CLIResult.build(command="test", data={}, errors=[])
        assert result.exit_code == 0

    def test_exit_code_error(self) -> None:
        result = CLIResult.build(command="test", data=None, errors=["err"])
        assert result.exit_code == 1

    def test_exit_code_partial(self) -> None:
        result = CLIResult.build(command="test", data={"k": "v"}, errors=["warn"])
        assert result.exit_code == 2

    def test_serialises_path_and_datetime(self) -> None:
        from datetime import UTC, datetime

        result = CLIResult.build(
            command="test",
            data={
                "path": Path("/tmp/foo"),
                "ts": datetime(2026, 1, 1, tzinfo=UTC),
            },
            errors=[],
        )
        text = json.dumps(result.to_dict(), default=str)
        assert "/tmp/foo" in text
        assert "2026" in text


class TestEmit:
    def test_emit_json_mode_produces_envelope(
        self,
        capsys: pytest.CaptureFixture,
    ) -> None:
        with patch("aec_bench.cli.output._should_emit_json", return_value=True):
            emit("test-cmd", data={"key": "val"})
        captured = capsys.readouterr()
        envelope = json.loads(captured.out)
        assert envelope["command"] == "test-cmd"
        assert envelope["status"] == "success"
        assert envelope["data"] == {"key": "val"}

    def test_emit_human_mode_calls_renderer(self) -> None:
        rendered: list[Any] = []

        def renderer(data: Any) -> None:
            rendered.append(data)

        with patch("aec_bench.cli.output._should_emit_json", return_value=False):
            emit("test-cmd", data={"key": "val"}, human_renderer=renderer)
        assert rendered == [{"key": "val"}]

    def test_emit_error_raises_typer_exit(self) -> None:
        with patch("aec_bench.cli.output._should_emit_json", return_value=True):
            with pytest.raises(ClickExit) as exc_info:
                emit("test-cmd", data=None, errors=["fatal"])
            assert exc_info.value.exit_code == 1

    def test_emit_partial_raises_typer_exit(self) -> None:
        with patch("aec_bench.cli.output._should_emit_json", return_value=True):
            with pytest.raises(ClickExit) as exc_info:
                emit("test-cmd", data={"k": "v"}, errors=["warn"])
            assert exc_info.value.exit_code == 2

    def test_emit_data_none_produces_error_envelope(
        self,
        capsys: pytest.CaptureFixture,
    ) -> None:
        with (
            patch("aec_bench.cli.output._should_emit_json", return_value=True),
            pytest.raises(ClickExit),
        ):
            emit("test-cmd", data=None, errors=["not found"])
        captured = capsys.readouterr()
        envelope = json.loads(captured.out)
        assert envelope["status"] == "error"
        assert envelope["data"] is None


class TestGlobalFlags:
    def test_json_and_text_mutually_exclusive(self) -> None:
        from typer.testing import CliRunner

        from aec_bench.cli.main import app

        cli_runner = CliRunner()
        result = cli_runner.invoke(app, ["--json", "--text", "--version"])
        assert result.exit_code != 0
        assert "Cannot use --json and --text together" in result.output

    def test_json_flag_sets_force_json(self) -> None:
        from typer.testing import CliRunner

        from aec_bench.cli.main import app

        cli_runner = CliRunner()
        result = cli_runner.invoke(app, ["--json", "--version"])
        assert result.exit_code == 0

    def test_text_flag_sets_force_text(self) -> None:
        from typer.testing import CliRunner

        from aec_bench.cli.main import app

        cli_runner = CliRunner()
        result = cli_runner.invoke(app, ["--text", "--version"])
        assert result.exit_code == 0


class TestEmitIntegration:
    def test_version_field_matches_package(self) -> None:
        from aec_bench import __version__

        result = CLIResult.build(command="test", data={}, errors=[])
        assert result.version == __version__

    def test_envelope_has_all_required_fields(
        self,
        capsys: pytest.CaptureFixture,
    ) -> None:
        with patch("aec_bench.cli.output._should_emit_json", return_value=True):
            emit("test", data={"k": "v"})
        captured = capsys.readouterr()
        envelope = json.loads(captured.out)
        required_fields = {"command", "status", "data", "errors", "version", "duration_seconds"}
        assert set(envelope.keys()) == required_fields

    def test_list_data_preserved_in_envelope(
        self,
        capsys: pytest.CaptureFixture,
    ) -> None:
        with patch("aec_bench.cli.output._should_emit_json", return_value=True):
            emit("test", data=[{"name": "a"}, {"name": "b"}])
        captured = capsys.readouterr()
        envelope = json.loads(captured.out)
        assert isinstance(envelope["data"], list)
        assert len(envelope["data"]) == 2


class TestAutoDetection:
    def test_piped_output_is_json(self, capsys: pytest.CaptureFixture) -> None:
        with patch("aec_bench.cli.output._should_emit_json", return_value=True):
            emit("test", data={"k": "v"})
        captured = capsys.readouterr()
        envelope = json.loads(captured.out)
        assert envelope["command"] == "test"
        assert envelope["status"] == "success"

    def test_tty_output_is_human(self) -> None:
        rendered: list[Any] = []
        with patch("aec_bench.cli.output._should_emit_json", return_value=False):
            emit("test", data={"k": "v"}, human_renderer=lambda d: rendered.append(d))
        assert len(rendered) == 1
        assert rendered[0] == {"k": "v"}

    def test_tty_output_without_renderer_does_not_crash(
        self,
        capsys: pytest.CaptureFixture,
    ) -> None:
        with patch("aec_bench.cli.output._should_emit_json", return_value=False):
            emit("test", data={"k": "v"})
        # Falls back to Rich syntax-highlighted JSON; just verify no exception


class TestIsTTY:
    def test_is_tty_true_when_terminal(self) -> None:
        with patch("sys.stdout") as mock_stdout:
            mock_stdout.isatty.return_value = True
            assert is_tty() is True

    def test_is_tty_false_when_piped(self) -> None:
        with patch("sys.stdout") as mock_stdout:
            mock_stdout.isatty.return_value = False
            assert is_tty() is False
