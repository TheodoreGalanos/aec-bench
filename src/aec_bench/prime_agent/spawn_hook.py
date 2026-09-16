# ABOUTME: Installs AEC-Bench's explicit Prime and IPython hooks in one run workspace.
# ABOUTME: Keeps hook source separate from the upstream installation and ambient configuration.

from __future__ import annotations

import shutil
from pathlib import Path


def prime_spawn_extension(session_directory: Path) -> Path:
    return session_directory.parent / "spawn-hook" / "spawn.mjs"


def install_prime_spawn_hook(session_directory: Path, environment: dict[str, str]) -> None:
    """Copy packaged hooks and select their isolated IPython startup profile."""
    extension = prime_spawn_extension(session_directory)
    assets = Path(__file__).with_name("hook_assets")
    if extension.parent.is_symlink() or any(path.is_symlink() for path in extension.parent.rglob("*")):
        raise ValueError("Prime spawn hook directory must not contain symbolic links")
    extension.parent.mkdir(parents=True, exist_ok=True)
    for name in ("spawn.mjs", "spawn.py"):
        destination = extension.with_name(name)
        shutil.copyfile(assets / name, destination)
    profile = extension.parent / "ipython"
    startup = profile / "profile_default" / "startup"
    startup.mkdir(parents=True, exist_ok=True)
    (startup / "00-aec-spawn.py").write_text(
        f"__import__('runpy').run_path({str(extension.with_suffix('.py'))!r})"
        "['load_ipython_extension'](get_ipython())\n",
        encoding="utf-8",
    )
    environment["IPYTHONDIR"] = str(profile)
    environment["AEC_BENCH_PRIME_SESSION_ROOT"] = str(session_directory)
