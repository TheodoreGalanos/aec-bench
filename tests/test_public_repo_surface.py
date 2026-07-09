# ABOUTME: Guards the root public-repo surface against stale local scaffolding.
# ABOUTME: Keeps README examples aligned with the live CLI and package boundaries.

from __future__ import annotations

from pathlib import Path


def test_root_does_not_publish_local_agent_or_node_scaffolding() -> None:
    root_only_files = {
        "AGENTS.md",
        "CLAUDE.md",
        "CONTEXT.md",
        "package.json",
        "package-lock.json",
    }

    assert all(not Path(path).exists() for path in root_only_files)
    assert Path("src/aec_bench/web/frontend/package.json").is_file()


def test_readme_uses_current_public_commands() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "terzaghi-bearing-capacity" in readme
    assert "terzaghi-bearing --" not in readme
    assert "default_compute_backend" not in readme
    assert "research/" not in readme
    assert "aec-bench meta-harness recipe" in readme
    assert "/meta-harness" in readme
