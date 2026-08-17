# ABOUTME: Installs the standalone world-actor client into an isolated actor workspace.
# ABOUTME: Rejects symlink and content conflicts while returning stable installed-source identity.

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path


class WorldActorClientInstallError(RuntimeError):
    """Raised when the standalone actor client cannot be installed safely."""


@dataclass(frozen=True, slots=True)
class InstalledClient:
    """One installed standalone client and its stable source identity."""

    package_directory: Path
    content_sha256: str


def install_world_actor_client(actor_workspace: Path) -> InstalledClient:
    """Install the packaged ``aec_world`` source without installing AEC-Bench."""
    requested_workspace = Path(actor_workspace)
    if requested_workspace.is_symlink():
        raise WorldActorClientInstallError("actor workspace must not be a symbolic link")
    workspace = requested_workspace.resolve()
    if not workspace.is_dir():
        raise WorldActorClientInstallError("actor workspace must exist before client installation")

    source = Path(__file__).with_name("client_package") / "aec_world"
    _require_safe_tree(source, label="packaged world actor client")
    content_sha256 = _tree_sha256(source)
    destination = workspace / "aec_world"
    if destination.exists() or destination.is_symlink():
        _require_safe_tree(destination, label="installed world actor client")
        if not _trees_match(source, destination):
            raise WorldActorClientInstallError("world actor client destination has different content")
        return InstalledClient(package_directory=destination, content_sha256=content_sha256)

    shutil.copytree(source, destination)
    _require_safe_tree(destination, label="installed world actor client")
    if not _trees_match(source, destination):
        raise WorldActorClientInstallError("world actor client installation did not preserve source content")
    return InstalledClient(package_directory=destination, content_sha256=content_sha256)


def _require_safe_tree(root: Path, *, label: str) -> None:
    if not root.is_dir() or root.is_symlink():
        raise WorldActorClientInstallError(f"{label} is missing or unsafe")
    if any(path.is_symlink() for path in root.rglob("*")):
        raise WorldActorClientInstallError(f"{label} contains a symbolic link")


def _tree_files(root: Path) -> dict[Path, Path]:
    return {
        path.relative_to(root): path
        for path in root.rglob("*")
        if path.is_file() and "__pycache__" not in path.relative_to(root).parts
    }


def _tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for relative, path in sorted(_tree_files(root).items(), key=lambda item: item[0].as_posix()):
        encoded = relative.as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def _trees_match(source: Path, destination: Path) -> bool:
    expected = {relative: path.read_bytes() for relative, path in _tree_files(source).items()}
    actual = {relative: path.read_bytes() for relative, path in _tree_files(destination).items()}
    return actual == expected


__all__ = ["InstalledClient", "WorldActorClientInstallError", "install_world_actor_client"]
