# ABOUTME: Installs explicit Prime skills into one isolated actor workspace.
# ABOUTME: Keeps generic Prime skill packaging separate from task-specific harness composition.

from __future__ import annotations

import shutil
from pathlib import Path

WORLD_ACTOR_SOCKET_ENV = "AEC_BENCH_WORLD_ACTOR_SOCKET"
WORLD_ACTOR_CAPABILITY_ENV = "AEC_BENCH_WORLD_ACTOR_CAPABILITY_TOKEN"


class PrimeSkillInstallError(RuntimeError):
    """Raised when an explicit Prime skill cannot be installed safely."""


def install_aec_world_skill(actor_workspace: Path) -> Path:
    """Install the generic actor skill and importable client in one workspace."""
    actor_workspace = actor_workspace.resolve()
    source = Path(__file__).with_name("skills") / "aec-world"
    package_source = source / "src" / "aec_world"
    package_directory = actor_workspace / "aec_world"
    if package_directory.exists():
        if not _installed_tree_matches(package_source, package_directory):
            raise PrimeSkillInstallError("aec-world package destination already exists with different content")
        return install_prime_skill(actor_workspace, source)
    skill_directory = install_prime_skill(actor_workspace, source)
    shutil.copytree(package_source, package_directory)
    return skill_directory


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


def _installed_tree_matches(source: Path, destination: Path) -> bool:
    if not destination.is_dir() or destination.is_symlink():
        return False
    if any(path.is_symlink() for path in destination.rglob("*")):
        return False
    expected = {
        path.relative_to(source): path.read_bytes()
        for path in source.rglob("*")
        if path.is_file() and not path.is_symlink()
    }
    installed = {path.relative_to(destination): path for path in destination.rglob("*") if path.is_file()}
    if any(relative not in expected and "__pycache__" not in relative.parts for relative in installed):
        return False
    return all(
        relative in installed and installed[relative].read_bytes() == content for relative, content in expected.items()
    )
