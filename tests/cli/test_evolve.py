# ABOUTME: Tests for the aec-bench evolve CLI subcommand group.
# ABOUTME: Covers init, run (with stub), and history commands.

from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

from aec_bench.cli.main import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# evolve init
# ---------------------------------------------------------------------------


class TestEvolveInit:
    """Validate workspace scaffolding via 'aec-bench evolve init'."""

    def test_scaffolds_workspace(self, tmp_path: Path) -> None:
        """Init should create manifest.yaml, prompts/system.md, and skills/ dir."""
        ws = tmp_path / "my-workspace"
        result = runner.invoke(app, ["evolve", "init", str(ws), "--name", "Test Agent"])

        assert result.exit_code == 0, result.output
        assert (ws / "manifest.yaml").exists()
        assert (ws / "prompts" / "system.md").exists()
        assert (ws / "skills").is_dir()

    def test_manifest_contents(self, tmp_path: Path) -> None:
        """Manifest should contain name, agent_adapter, and evolvable_layers."""
        ws = tmp_path / "ws"
        runner.invoke(app, ["evolve", "init", str(ws), "--name", "My Agent"])

        manifest = yaml.safe_load((ws / "manifest.yaml").read_text())
        assert manifest["name"] == "My Agent"
        assert manifest["agent_adapter"] == "rlm"
        assert "prompts" in manifest["evolvable_layers"]
        assert "skills" in manifest["evolvable_layers"]

    def test_rejects_existing_workspace(self, tmp_path: Path) -> None:
        """Init should exit with code 1 when manifest.yaml already exists."""
        ws = tmp_path / "ws"
        ws.mkdir(parents=True)
        (ws / "manifest.yaml").write_text("name: existing\n")

        result = runner.invoke(app, ["evolve", "init", str(ws), "--name", "New"])
        assert result.exit_code != 0

    def test_custom_adapter(self, tmp_path: Path) -> None:
        """Init with --adapter tool_loop should write that adapter to manifest."""
        ws = tmp_path / "ws"
        runner.invoke(
            app,
            [
                "evolve",
                "init",
                str(ws),
                "--name",
                "Tool Agent",
                "--adapter",
                "tool_loop",
            ],
        )

        manifest = yaml.safe_load((ws / "manifest.yaml").read_text())
        assert manifest["agent_adapter"] == "tool_loop"

    def test_system_md_has_placeholder(self, tmp_path: Path) -> None:
        """The default system.md should contain a non-empty placeholder prompt."""
        ws = tmp_path / "ws"
        runner.invoke(app, ["evolve", "init", str(ws), "--name", "Agent"])

        content = (ws / "prompts" / "system.md").read_text()
        assert len(content.strip()) > 0

    def test_output_contains_workspace_path(self, tmp_path: Path) -> None:
        """Human-readable output should mention the workspace path."""
        ws = tmp_path / "ws"
        result = runner.invoke(app, ["evolve", "init", str(ws), "--name", "Agent"])

        assert str(ws) in result.output


# ---------------------------------------------------------------------------
# evolve history
# ---------------------------------------------------------------------------


class TestEvolveHistory:
    """Validate evolution timeline display via 'aec-bench evolve history'."""

    def _init_workspace(self, path: Path, name: str = "Test") -> None:
        """Helper: scaffold a valid workspace at path."""
        runner.invoke(app, ["evolve", "init", str(path), "--name", name])

    def test_rejects_non_workspace_path(self, tmp_path: Path) -> None:
        """History should exit with code 1 for a path without manifest.yaml."""
        result = runner.invoke(app, ["evolve", "history", str(tmp_path)])
        assert result.exit_code != 0

    def test_shows_empty_history_message(self, tmp_path: Path) -> None:
        """History on a freshly-initialised workspace should report no versions."""
        ws = tmp_path / "ws"
        self._init_workspace(ws)

        result = runner.invoke(app, ["evolve", "history", str(ws)])
        assert result.exit_code == 0
        assert "No evolution history" in result.output

    def test_shows_run_header_after_versioning(self, tmp_path: Path) -> None:
        """History should show a run header when evolution run tags exist."""
        ws = tmp_path / "ws"
        self._init_workspace(ws)

        from aec_bench.evolution.workspace import Workspace

        workspace = Workspace(ws)
        workspace.init_versioning()
        # Create a legacy-style run tag so list_runs() returns a result
        workspace._git("tag", "-a", "evo-1", "-m", "cycle 1 score=0.750")

        result = runner.invoke(app, ["evolve", "history", str(ws)])
        assert result.exit_code == 0
        # New grouped format shows run count in header and cycle tags per run
        assert "run(s)" in result.output
        assert "evo-1" in result.output

    def test_history_shows_grouped_run_output(self, tmp_path: Path) -> None:
        """History should show workspace name, run count, and per-run cycle detail."""
        ws = tmp_path / "ws"
        self._init_workspace(ws)

        from aec_bench.evolution.workspace import Workspace

        workspace = Workspace(ws)
        workspace.init_versioning()
        workspace._git("tag", "-a", "evo-1", "-m", "cycle 1 score=0.750")

        result = runner.invoke(app, ["evolve", "history", str(ws)])
        assert result.exit_code == 0
        # Workspace name and run summary line should appear
        assert "Test" in result.output
        assert "cycle(s)" in result.output
