# ABOUTME: Defines the exact pinned SWMM build plan and fresh-workspace boundary for B5 generation.
# ABOUTME: Permits only the accepted source, patch, Release build, upstream tests, and one-thread compilation.

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

from generator import boundary
from repairs import solver_convergence

SWMM_REPOSITORY = "https://github.com/USEPA/Stormwater-Management-Model.git"
SWMM_VERSION = "5.2.4"
SWMM_COMMIT = "7952ca837988b1c32f791812eccc9fd64547e093"
SWMM_PATCH_SHA256 = "522fa1f285b27bfdd614eae79a841e5b9a7892573521d032f78fdbd281dba894"


class EngineBoundaryError(RuntimeError):
    """Raised when the pinned engine or its workspace boundary differs."""


def require_absent(path: Path) -> None:
    """Require a path that neither exists nor resolves as a symlink."""
    if path.exists() or path.is_symlink():
        raise EngineBoundaryError(f"workspace path must be absent: {path}")


def build_commands(*, workspace: Path, patch_path: Path) -> tuple[tuple[str, ...], ...]:
    """Return the only accepted pinned-source build command sequence."""
    source = workspace / "source"
    build = workspace / "build"
    install = workspace / "install"
    return (
        ("git", "clone", SWMM_REPOSITORY, str(source)),
        ("git", "checkout", SWMM_COMMIT),
        ("git", "apply", str(patch_path)),
        (
            "cmake",
            "-S",
            str(source),
            "-B",
            str(build),
            "-DCMAKE_BUILD_TYPE=Release",
            "-DBUILD_TESTS=ON",
            f"-DCMAKE_INSTALL_PREFIX={install}",
        ),
        ("cmake", "--build", str(build), "--parallel", "1"),
        ("ctest", "--test-dir", str(build), "--output-on-failure"),
        ("cmake", "--install", str(build)),
    )


def sha256_file(path: Path) -> str:
    """Return a file identity without loading the complete artifact into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(
    command: tuple[str, ...],
    *,
    cwd: Path | None = None,
    environment: dict[str, str] | None = None,
    timeout_seconds: int = 900,
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise EngineBoundaryError(f"command could not complete: {command!r}: {error}") from error
    if completed.returncode != 0:
        output = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
        raise EngineBoundaryError(f"command failed ({completed.returncode}): {command!r}\n{output}")
    return completed


def _library_environment(directory: Path) -> dict[str, str]:
    environment = dict(os.environ)
    variable = "DYLD_LIBRARY_PATH" if sys.platform == "darwin" else "LD_LIBRARY_PATH"
    existing = environment.get(variable)
    environment[variable] = str(directory) if not existing else f"{directory}{os.pathsep}{existing}"
    return environment


def _single_artifact(root: Path, names: tuple[str, ...]) -> Path:
    matches = [candidate for name in names for candidate in root.rglob(name) if candidate.is_file()]
    if len(matches) != 1:
        raise EngineBoundaryError(f"expected exactly one installed artifact from {names!r}; found {matches!r}")
    return matches[0]


def _relative_artifact(workspace: Path, path: Path) -> dict[str, str]:
    relative = path.relative_to(workspace).as_posix()
    boundary.validate_safe_relative_path(relative)
    return {"relative_path": relative, "sha256": sha256_file(path)}


def _tool_version(command: tuple[str, ...]) -> str:
    return _run(command, timeout_seconds=30).stdout.strip()


def build_engine(workspace: Path, patch_path: Path) -> Path:
    """Build and test the exact pinned SWMM source in one new B5 workspace."""
    workspace = workspace.resolve()
    patch_path = patch_path.resolve()
    require_absent(workspace)
    if not patch_path.is_file() or patch_path.is_symlink():
        raise EngineBoundaryError(f"portability patch must be one regular file: {patch_path}")
    if sha256_file(patch_path) != SWMM_PATCH_SHA256:
        raise EngineBoundaryError("portability patch SHA-256 differs from the accepted patch")
    workspace.mkdir(parents=True)
    source = workspace / "source"
    install = workspace / "install"
    commands = build_commands(workspace=workspace, patch_path=patch_path)

    _run(commands[0])
    _run(commands[1], cwd=source)
    commit = _run(("git", "rev-parse", "HEAD"), cwd=source, timeout_seconds=30).stdout.strip()
    if commit != SWMM_COMMIT:
        raise EngineBoundaryError(f"checkout resolved to {commit!r}, not the exact pin")
    if _run(("git", "status", "--short"), cwd=source, timeout_seconds=30).stdout:
        raise EngineBoundaryError("pinned checkout is not clean before the accepted patch")
    _run(commands[2], cwd=source)
    expected_patch_paths = (
        "extern/boost.cmake",
        "src/solver/CMakeLists.txt",
        "tests/CMakeLists.txt",
    )
    status = _run(("git", "status", "--short"), cwd=source, timeout_seconds=30).stdout.splitlines()
    changed_paths = tuple(sorted(line[3:] for line in status))
    if changed_paths != expected_patch_paths or any(not line.startswith(" M ") for line in status):
        raise EngineBoundaryError(f"accepted patch changed an unexpected source inventory: {status!r}")

    _run(commands[3])
    _run(commands[4])
    upstream_tests = _run(commands[5])
    _run(commands[6])
    status_after_build = _run(("git", "status", "--short"), cwd=source, timeout_seconds=30).stdout.splitlines()
    if tuple(sorted(line[3:] for line in status_after_build)) != expected_patch_paths:
        raise EngineBoundaryError("build changed the pinned source inventory")

    executable = _single_artifact(install, ("runswmm", "runswmm.exe"))
    solver_library = _single_artifact(install, ("libswmm5.dylib", "libswmm5.so", "swmm5.dll"))
    output_library = _single_artifact(
        install,
        ("libswmm-output.dylib", "libswmm-output.so", "swmm-output.dll"),
    )
    version = _run(
        (str(executable), "--version"),
        environment=_library_environment(executable.parent),
        timeout_seconds=30,
    ).stdout.strip()
    if version != SWMM_VERSION:
        raise EngineBoundaryError(f"runswmm version is {version!r}, expected {SWMM_VERSION!r}")

    readme = source / "README.md"
    if not readme.is_file() or "released in the Public Domain" not in readme.read_text(encoding="utf-8"):
        raise EngineBoundaryError("pinned README lacks the expected public-domain source notice")
    generated_header = source / "src" / "outfile" / "include" / "swmm_output_export.h"
    if not generated_header.is_file():
        raise EngineBoundaryError("output-library export header was not generated")
    if (
        _run(
            ("git", "check-ignore", "src/outfile/include/swmm_output_export.h"),
            cwd=source,
            timeout_seconds=30,
        ).stdout.strip()
        != "src/outfile/include/swmm_output_export.h"
    ):
        raise EngineBoundaryError("generated output-library header is not ignored upstream")

    receipt: dict[str, Any] = {
        "artifacts": {
            "engine_executable": _relative_artifact(workspace, executable),
            "output_library": _relative_artifact(workspace, output_library),
            "solver_library": _relative_artifact(workspace, solver_library),
        },
        "build": {
            "build_type": "Release",
            "cmake": _tool_version(("cmake", "--version")),
            "compiler": _tool_version(("cc", "--version")),
            "git": _tool_version(("git", "--version")),
            "machine": platform.machine(),
            "parallelism": 1,
            "platform": platform.system().lower(),
            "python": platform.python_version(),
        },
        "patch": {
            "changes_solver_or_output_calculations": False,
            "sha256": SWMM_PATCH_SHA256,
            "source_paths": list(expected_patch_paths),
        },
        "promotable": False,
        "rights": {
            "notice": "Official pinned README states that the C source is released in the Public Domain.",
            "readme_sha256": sha256_file(readme),
        },
        "schema_id": "asw-0b5.engine-build-receipt.v1",
        "source": {
            "commit": commit,
            "repository": SWMM_REPOSITORY,
            "version": SWMM_VERSION,
        },
        "upstream_tests": {
            "output_sha256": hashlib.sha256(
                (upstream_tests.stdout + upstream_tests.stderr).encode("utf-8")
            ).hexdigest(),
            "status": "pass",
        },
        "version_output": version,
    }
    receipt_path = workspace / "engine-build-receipt.json"
    receipt_path.write_bytes(boundary.canonical_json_bytes(receipt))
    return receipt_path


def _read_receipt(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        parsed = json.loads(raw)
    except (OSError, json.JSONDecodeError) as error:
        raise EngineBoundaryError(f"cannot read engine build receipt: {error}") from error
    if not isinstance(parsed, dict) or boundary.canonical_json_bytes(parsed) != raw:
        raise EngineBoundaryError("engine build receipt is not canonical JSON")
    return cast(dict[str, Any], parsed)


def verify_build_receipt(path: Path) -> dict[str, Any]:
    """Recheck a B5 build receipt and every actual artifact before generation."""
    path = path.resolve()
    receipt = _read_receipt(path)
    if set(receipt) != {
        "artifacts",
        "build",
        "patch",
        "promotable",
        "rights",
        "schema_id",
        "source",
        "upstream_tests",
        "version_output",
    }:
        raise EngineBoundaryError("engine build receipt has unexpected top-level keys")
    if receipt["schema_id"] != "asw-0b5.engine-build-receipt.v1" or receipt["promotable"] is not False:
        raise EngineBoundaryError("engine build receipt authority differs")
    if receipt["source"] != {
        "commit": SWMM_COMMIT,
        "repository": SWMM_REPOSITORY,
        "version": SWMM_VERSION,
    }:
        raise EngineBoundaryError("engine source identity differs")
    patch = receipt["patch"]
    if patch != {
        "changes_solver_or_output_calculations": False,
        "sha256": SWMM_PATCH_SHA256,
        "source_paths": [
            "extern/boost.cmake",
            "src/solver/CMakeLists.txt",
            "tests/CMakeLists.txt",
        ],
    }:
        raise EngineBoundaryError("engine patch identity or scope differs")
    build = receipt["build"]
    if not isinstance(build, dict) or build.get("build_type") != "Release" or build.get("parallelism") != 1:
        raise EngineBoundaryError("engine build settings differ")
    tests = receipt["upstream_tests"]
    if (
        not isinstance(tests, dict)
        or tests.get("status") != "pass"
        or not isinstance(tests.get("output_sha256"), str)
        or boundary.HASH_PATTERN.fullmatch(tests["output_sha256"]) is None
    ):
        raise EngineBoundaryError("upstream test evidence is absent")
    artifacts = receipt["artifacts"]
    if not isinstance(artifacts, dict) or set(artifacts) != {
        "engine_executable",
        "output_library",
        "solver_library",
    }:
        raise EngineBoundaryError("engine artifact inventory differs")
    resolved: dict[str, Path] = {}
    for role, item in artifacts.items():
        if not isinstance(item, dict) or set(item) != {"relative_path", "sha256"}:
            raise EngineBoundaryError(f"artifact record differs for {role}")
        relative = item["relative_path"]
        if not isinstance(relative, str):
            raise EngineBoundaryError(f"artifact relative path is invalid for {role}")
        boundary.validate_safe_relative_path(relative)
        artifact = path.parent / relative
        if (
            not artifact.is_file()
            or artifact.is_symlink()
            or not isinstance(item["sha256"], str)
            or sha256_file(artifact) != item["sha256"]
        ):
            raise EngineBoundaryError(f"engine artifact identity differs for {role}")
        resolved[role] = artifact
    version = _run(
        (str(resolved["engine_executable"]), "--version"),
        environment=_library_environment(resolved["engine_executable"].parent),
        timeout_seconds=30,
    ).stdout.strip()
    if version != SWMM_VERSION or receipt["version_output"] != SWMM_VERSION:
        raise EngineBoundaryError("engine version response differs")
    return receipt


def artifact_path(receipt_path: Path, role: str) -> Path:
    """Resolve one verified artifact role beneath its immutable build root."""
    receipt = verify_build_receipt(receipt_path)
    artifacts = cast(dict[str, dict[str, str]], receipt["artifacts"])
    if role not in artifacts:
        raise EngineBoundaryError(f"unknown engine artifact role {role!r}")
    return receipt_path.resolve().parent / artifacts[role]["relative_path"]


def request_engine_identity(receipt_path: Path) -> dict[str, str]:
    """Project verified build evidence into the exact path-free W2 request object."""
    receipt_path = receipt_path.resolve()
    receipt = verify_build_receipt(receipt_path)
    artifacts = cast(dict[str, dict[str, str]], receipt["artifacts"])
    return {
        "build_receipt_sha256": sha256_file(receipt_path),
        "commit": SWMM_COMMIT,
        "executable_sha256": artifacts["engine_executable"]["sha256"],
        "output_library_sha256": artifacts["output_library"]["sha256"],
        "patch_sha256": SWMM_PATCH_SHA256,
        "repository": SWMM_REPOSITORY,
        "settings_id": solver_convergence.ENGINE_SETTINGS_ID,
        "solver_library_sha256": artifacts["solver_library"]["sha256"],
        "version": SWMM_VERSION,
    }
