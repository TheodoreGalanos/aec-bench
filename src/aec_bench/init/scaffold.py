# ABOUTME: Scaffold logic for aec-bench project directory creation and config writing.
# ABOUTME: Pure functions that create directories, write config files, and copy bundled skills.

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

# The packaged skill names that ship with aec-bench.
_PACKAGED_SKILLS: tuple[str, ...] = (
    "add-task",
    "configure-experiment",
    "create-dataset",
    "create-template",
    "domain-check",
    "hardening-pass",
)

_PACKAGED_AGENTS: tuple[str, ...] = (
    "tool_loop_anthropic.py",
    "tool_loop_azure_openai.py",
    "pydantic_ai_agent.py",
    "script_anthropic.py",
    "script_azure_openai.py",
)

_SCAFFOLD_DIRS: tuple[str, ...] = (
    "tasks",
    "seeds",
    "artefacts/ledger",
)

_PROJECT_CONFIG_TEMPLATE = """\
[project]
name = "{project_name}"

[paths]
tasks = "tasks"
seeds = "seeds"
ledger = "artefacts/ledger"
feedback = "artefacts/feedback"
jobs = "jobs"
templates = "templates"

[compute]
backend = "modal"
"""

_SUITE_TOML_CONTENT = """\
# Suite configuration — defines which templates to generate instances from.
# Run with: aec-bench generate dataset --config suite.toml
#
# Each [[dataset]] entry specifies a template, instance count, and optional
# filters. Templates are listed with: aec-bench generate list-templates

# --- Ground engineering ---
[[dataset]]
template = "terzaghi-bearing-capacity"
count = 5

# [[dataset]]
# template = "infinite-slope"
# count = 3
# difficulty = "easy,medium"    # Comma-separated difficulty filter

# --- Electrical ---
# [[dataset]]
# template = "voltage-drop"
# count = 5

# [[dataset]]
# template = "cable-sizing"
# count = 10

# --- Civil ---
# [[dataset]]
# template = "rational-method"
# count = 5

# --- Generation settings ---
[settings]
seed = 42
output = "tasks"
# tool_mode = "with-tool"     # Override: "with-tool", "no-tool", or "both"
"""

_GITIGNORE_CONTENT = """\
# aec-bench artefacts
artefacts/
jobs/
tasks/generated/

# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.venv/

# Environment
.env
.env.*

# Tool caches
.ruff_cache/
.pytest_cache/
.mypy_cache/
"""


@dataclass(frozen=True)
class ScaffoldResult:
    """Result of a scaffold operation."""

    created: bool
    project_root: Path
    messages: tuple[str, ...]


def create_scaffold(target: Path) -> ScaffoldResult:
    """Create the standard project directory structure under *target*.

    Directories that already exist are silently skipped.
    """
    messages: list[str] = []
    for rel in _SCAFFOLD_DIRS:
        dir_path = target / rel
        if dir_path.is_dir():
            messages.append(f"Skipped existing directory: {rel}")
        else:
            dir_path.mkdir(parents=True, exist_ok=True)
            messages.append(f"Created directory: {rel}")

    return ScaffoldResult(
        created=True,
        project_root=target,
        messages=tuple(messages),
    )


def write_project_config(target: Path, project_name: str, *, force: bool = False) -> None:
    """Write ``aec-bench.toml`` into *target*.

    If the file already exists and *force* is False, the write is skipped.
    """
    config_path = target / "aec-bench.toml"
    if config_path.exists() and not force:
        return
    config_path.write_text(
        _PROJECT_CONFIG_TEMPLATE.format(project_name=project_name),
        encoding="utf-8",
    )


def write_suite_toml(target: Path, *, force: bool = False) -> None:
    """Write ``suite.toml`` with example template configuration.

    If the file already exists and *force* is False, the write is skipped.
    """
    suite_path = target / "suite.toml"
    if suite_path.exists() and not force:
        return
    suite_path.write_text(_SUITE_TOML_CONTENT, encoding="utf-8")


def write_gitignore(target: Path, *, force: bool = False) -> None:
    """Write ``.gitignore`` with sensible defaults for aec-bench projects.

    If the file already exists and *force* is False, the write is skipped.
    """
    gitignore_path = target / ".gitignore"
    if gitignore_path.exists() and not force:
        return
    gitignore_path.write_text(_GITIGNORE_CONTENT, encoding="utf-8")


def _locate_bundled_source(package_name: str, fallback_dir: str) -> Path | None:
    """Locate a directory of bundled data files.

    Tries importlib.resources first (for installed packages), then falls back
    to a repo-local directory (for development).
    """
    try:
        from importlib.resources import as_file, files

        pkg = files(package_name)
        with as_file(pkg) as src:
            if src.is_dir():
                return Path(src)
    except (ImportError, ModuleNotFoundError, TypeError):
        pass

    repo_fallback = Path(__file__).resolve().parents[3] / fallback_dir
    if repo_fallback.is_dir():
        return repo_fallback

    return None


def copy_skills(target: Path) -> None:
    """Copy packaged skills into ``<target>/.claude/skills/``.

    Only the four packaged skill directories are written. User-added skill
    directories are left untouched.
    """
    source = _locate_bundled_source("aec_bench.init.skill_data", ".claude/skills")
    if source is None:
        return

    dest_root = target / ".claude" / "skills"
    dest_root.mkdir(parents=True, exist_ok=True)

    for skill_name in _PACKAGED_SKILLS:
        src_dir = source / skill_name
        if not src_dir.is_dir():
            continue
        dest_dir = dest_root / skill_name
        shutil.copytree(src_dir, dest_dir, dirs_exist_ok=True)


def copy_agents(target: Path) -> None:
    """Copy packaged default agents into ``<target>/agents/``.

    Only the packaged agent files are written. User-added agents are
    left untouched.
    """
    source = _locate_bundled_source("aec_bench.init.agent_data", "agents")
    if source is None:
        return

    dest_dir = target / "agents"
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Write __init__.py if not present
    init_path = dest_dir / "__init__.py"
    if not init_path.exists():
        init_path.write_text(
            "# ABOUTME: Default Harbor-native agents for aec-bench benchmark execution.\n"
            "# ABOUTME: Each agent subclasses Harbor's BaseAgent and composes library utilities.\n",
            encoding="utf-8",
        )

    for agent_file in _PACKAGED_AGENTS:
        src_file = source / agent_file
        if not src_file.is_file():
            continue
        dest_file = dest_dir / agent_file
        shutil.copy2(src_file, dest_file)
