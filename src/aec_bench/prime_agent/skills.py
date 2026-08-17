# ABOUTME: Installs explicit Prime skills into one isolated actor workspace.
# ABOUTME: Keeps generic Prime skill packaging separate from task-specific harness composition.

from __future__ import annotations

import json
import shutil
from pathlib import Path

from aec_bench.prime_agent.batch import resolve_prime_executable

ACTOR_LEDGER_PLAN_INSTRUCTION = (
    "Before your first world action, load and use the full `aec-actor-ledger` skill. "
    "Use its compact results and bounded search and window calls instead of printing full saved state. "
    "Before you delegate work, load and use the full `agent-message` and `agent-observe` skills. "
    "Use bounded child message previews and ask children to return compact findings. "
    "The root and all children are one actor principal. You still choose every action and argument from current "
    "actor-visible evidence."
)


class PrimeSkillInstallError(RuntimeError):
    """Raised when an explicit Prime skill cannot be installed safely."""


def install_aec_world_skill(actor_workspace: Path) -> Path:
    """Install Prime-specific instructions for the generic world actor client."""
    source = Path(__file__).with_name("skill_packages") / "aec-world"
    return install_prime_skill(actor_workspace, source)


def install_aec_actor_ledger_skill(actor_workspace: Path) -> Path:
    """Install the optional structured actor-ledger capability."""
    return _install_importable_skill(
        actor_workspace,
        skill_name="aec-actor-ledger",
        package_name="aec_actor_ledger",
    )


def install_prime_refine_skill(actor_workspace: Path) -> Path:
    """Install Prime's agent-callable refinement bridge for a discovery run."""
    source = Path(__file__).with_name("skill_packages") / "refine"
    return install_prime_skill(actor_workspace, source)


def install_prime_bundled_skill(actor_workspace: Path, *, executable: str, skill_name: str) -> Path:
    """Copy one skill from the selected upstream Prime installation into the actor workspace."""
    if skill_name not in {"agent-message", "agent-observe"}:
        raise ValueError(f"unsupported Prime bundled skill: {skill_name}")
    resolved_executable = resolve_prime_executable(executable)
    source = _find_prime_bundled_skill(resolved_executable, skill_name)
    return install_prime_skill(actor_workspace, source)


def install_actor_ledger_plan_skills(actor_workspace: Path, *, executable: str) -> tuple[Path, ...]:
    """Install the shared bounded-ledger and optional child-coordination capability."""
    return (
        install_aec_actor_ledger_skill(actor_workspace),
        *(
            install_prime_bundled_skill(actor_workspace, executable=executable, skill_name=skill_name)
            for skill_name in ("agent-message", "agent-observe")
        ),
    )


def install_prime_skill(actor_workspace: Path, source: Path) -> Path:
    """Install one explicit packaged skill without using ambient discovery."""
    actor_workspace = actor_workspace.resolve()
    source = source.resolve()
    if not source.is_dir():
        raise PrimeSkillInstallError(f"packaged Prime skill is missing: {source.name}")
    skill_directory = actor_workspace / ".prime-skills" / source.name
    if skill_directory.exists():
        if not _installed_tree_matches(source, skill_directory):
            raise PrimeSkillInstallError(
                f"Prime skill destination already exists with different content: {source.name}"
            )
        return skill_directory
    skill_directory.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, skill_directory)
    return skill_directory


def _install_importable_skill(actor_workspace: Path, *, skill_name: str, package_name: str) -> Path:
    actor_workspace = actor_workspace.resolve()
    source = Path(__file__).with_name("skill_packages") / skill_name
    package_source = source / "src" / package_name
    package_directory = actor_workspace / package_name
    if package_directory.exists():
        if not _installed_tree_matches(package_source, package_directory):
            raise PrimeSkillInstallError(f"{skill_name} package destination already exists with different content")
        return install_prime_skill(actor_workspace, source)
    skill_directory = install_prime_skill(actor_workspace, source)
    shutil.copytree(package_source, package_directory)
    return skill_directory


def _find_prime_bundled_skill(executable: Path, skill_name: str) -> Path:
    for directory in executable.parents:
        package_file = directory / "package.json"
        if not package_file.is_file():
            continue
        try:
            package = json.loads(package_file.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(package, dict) or package.get("name") != "prime-agent":
            continue
        for skills_directory in (directory / "dist" / "skills", directory / "skills"):
            source = skills_directory / skill_name
            if (source / "SKILL.md").is_file():
                return source
        break
    raise PrimeSkillInstallError(f"installed Prime Agent does not contain its {skill_name} skill")


def _installed_tree_matches(source: Path, destination: Path) -> bool:
    if not destination.is_dir() or destination.is_symlink():
        return False
    if any(path.is_symlink() for path in destination.rglob("*")):
        return False
    expected = {
        path.relative_to(source): path.read_bytes()
        for path in source.rglob("*")
        if path.is_file() and not path.is_symlink() and "__pycache__" not in path.relative_to(source).parts
    }
    installed = {path.relative_to(destination): path for path in destination.rglob("*") if path.is_file()}
    if any(relative not in expected and "__pycache__" not in relative.parts for relative in installed):
        return False
    return all(
        relative in installed and installed[relative].read_bytes() == content for relative, content in expected.items()
    )
