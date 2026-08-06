# ABOUTME: Guards the root public-repo surface against stale local scaffolding.
# ABOUTME: Keeps README examples aligned with the live CLI and package boundaries.

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from aec_bench.init.scaffold import _PACKAGED_SKILLS

SKILL_ROOT = Path("src/aec_bench/init/skill_data")


def test_root_publishes_portable_agent_guidance_without_local_scaffolding() -> None:
    prohibited_root_files = {
        "CLAUDE.md",
        "CONTEXT.md",
        "package.json",
        "package-lock.json",
    }

    assert all(not Path(path).exists() for path in prohibited_root_files)
    assert Path("AGENTS.md").is_file()
    assert Path("src/aec_bench/web/frontend/package.json").is_file()


def test_readme_uses_current_public_commands() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "terzaghi-bearing-capacity" in readme
    assert "terzaghi-bearing --" not in readme
    assert "default_compute_backend" not in readme
    assert "research/" not in readme
    assert "aec-bench meta-harness recipe" in readme
    assert "/meta-harness" in readme
    assert "aec-bench --json evaluate -e experiment-001" in readme
    assert "evaluate -e experiment-001 -o json" not in readme


def test_readme_lists_every_packaged_skill() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert all(f"/{skill_name}`" in readme or f"/{skill_name} " in readme for skill_name in _PACKAGED_SKILLS)


def test_configure_experiment_skill_lists_every_harbor_backend() -> None:
    configure_root = SKILL_ROOT / "configure-experiment"
    run_command = Path("src/aec_bench/cli/commands/run.py").read_text(encoding="utf-8")
    help_match = re.search(r'help="Harbor execution backend: (?P<backends>[^."]+)\.', run_command)
    assert help_match is not None
    backends = {value.strip() for value in help_match.group("backends").split(",")}
    guidance = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (configure_root / "SKILL.md", configure_root / "references" / "manifest-schema.md")
    )

    assert all(f"`{backend}`" in guidance for backend in backends)


def test_research_tree_is_local_only() -> None:
    ignore_rules = {
        line.strip()
        for line in Path(".gitignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    tracked_research = subprocess.run(
        ["git", "ls-files", "research"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "/research/" in ignore_rules
    assert not any(rule.startswith("!") and "research/" in rule for rule in ignore_rules)
    assert tracked_research.stdout == ""
