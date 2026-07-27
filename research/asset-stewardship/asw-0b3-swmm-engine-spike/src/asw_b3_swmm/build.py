# ABOUTME: Builds the exact pinned SWMM source in a fresh research workspace and records provenance.
# ABOUTME: Applies only the hashed CMake portability patch and never deletes or reuses build material.

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from asw_b3_swmm.constants import SWMM_COMMIT, SWMM_REPOSITORY, SWMM_VERSION


class BuildBoundaryError(RuntimeError):
    """Raised when the pinned build cannot be proven or crosses its safe workspace boundary."""


def sha256_file(path: Path) -> str:
    """Return the SHA-256 identity of one file."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assert_absent_workspace(path: Path) -> None:
    """Reject all existing workspace paths so no stale output can be reused."""
    if path.exists() or path.is_symlink():
        raise BuildBoundaryError(f"workspace already exists and will not be reused: {path}")


def validate_version_output(output: str) -> None:
    """Require the CLI version response to be exactly the selected candidate version."""
    if re.fullmatch(r"\s*5\.2\.4\s*", output) is None:
        raise BuildBoundaryError(f"engine version must be exactly {SWMM_VERSION!r}; got {output!r}")


def build_commands(patch_path: Path, workspace: Path) -> tuple[tuple[str, ...], ...]:
    """Describe the build commands in execution order for tests and provenance."""
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


def _run(
    command: tuple[str, ...],
    *,
    cwd: Path | None = None,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=900,
    )
    if completed.returncode != 0:
        output = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
        raise BuildBoundaryError(f"command failed ({completed.returncode}): {command!r}\n{output}")
    return completed


def _dynamic_library_environment(bin_directory: Path) -> dict[str, str]:
    environment = dict(os.environ)
    variable = "DYLD_LIBRARY_PATH" if sys.platform == "darwin" else "LD_LIBRARY_PATH"
    existing = environment.get(variable)
    environment[variable] = str(bin_directory) if not existing else f"{bin_directory}{os.pathsep}{existing}"
    return environment


def _find_one(directory: Path, names: tuple[str, ...]) -> Path:
    matches = [directory / name for name in names if (directory / name).is_file()]
    if len(matches) != 1:
        raise BuildBoundaryError(f"expected exactly one of {names!r} under {directory}; found {matches!r}")
    return matches[0]


def _tool_output(command: tuple[str, ...]) -> str:
    return _run(command).stdout.strip()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def build_engine(workspace: Path, patch_path: Path) -> Path:
    """Clone, patch, test, and install SWMM in a new workspace, returning its receipt."""
    workspace = workspace.resolve()
    patch_path = patch_path.resolve()
    assert_absent_workspace(workspace)
    if not patch_path.is_file():
        raise BuildBoundaryError(f"portability patch does not exist: {patch_path}")
    workspace.mkdir(parents=True)
    source = workspace / "source"
    install = workspace / "install"
    commands = build_commands(patch_path, workspace)

    clone = _run(commands[0])
    checkout = _run(commands[1], cwd=source)
    resolved_commit = _run(("git", "rev-parse", "HEAD"), cwd=source).stdout.strip()
    if resolved_commit != SWMM_COMMIT:
        raise BuildBoundaryError(f"checkout resolved to {resolved_commit}, not {SWMM_COMMIT}")
    if _run(("git", "diff"), cwd=source).stdout:
        raise BuildBoundaryError("fresh checkout unexpectedly contains tracked changes")

    patch = _run(commands[2], cwd=source)
    status_after_patch = _run(("git", "status", "--short"), cwd=source).stdout.splitlines()
    expected_patch_status = {
        " M extern/boost.cmake",
        " M src/solver/CMakeLists.txt",
        " M tests/CMakeLists.txt",
    }
    if set(status_after_patch) != expected_patch_status:
        raise BuildBoundaryError(f"patch changed unexpected source paths: {status_after_patch!r}")

    configure = _run(commands[3])
    compile_result = _run(commands[4])
    upstream_test = _run(commands[5])
    install_result = _run(commands[6])

    status_after_build = _run(("git", "status", "--short"), cwd=source).stdout.splitlines()
    expected_build_status = expected_patch_status
    if set(status_after_build) != expected_build_status:
        raise BuildBoundaryError(f"build changed unexpected source paths: {status_after_build!r}")
    generated_header = source / "src" / "outfile" / "include" / "swmm_output_export.h"
    if not generated_header.is_file():
        raise BuildBoundaryError("build did not create the expected output-API export header")
    ignored_header = _run(
        ("git", "check-ignore", "src/outfile/include/swmm_output_export.h"),
        cwd=source,
    ).stdout.strip()
    if ignored_header != "src/outfile/include/swmm_output_export.h":
        raise BuildBoundaryError("generated output-API header is not covered by the upstream ignore boundary")

    bin_directory = install / "bin"
    executable = _find_one(bin_directory, ("runswmm", "runswmm.exe"))
    output_library = _find_one(
        bin_directory,
        ("libswmm-output.dylib", "libswmm-output.so", "swmm-output.dll"),
    )
    solver_library = _find_one(bin_directory, ("libswmm5.dylib", "libswmm5.so", "swmm5.dll"))
    version = _run(
        (str(executable), "--version"),
        environment=_dynamic_library_environment(bin_directory),
    )
    validate_version_output(version.stdout)

    readme = source / "README.md"
    readme_text = readme.read_text(encoding="utf-8")
    if "released in the Public Domain" not in readme_text:
        raise BuildBoundaryError("pinned official README no longer contains the expected public-domain notice")

    artifacts = {
        "runswmm": {"path": str(executable), "sha256": sha256_file(executable)},
        "swmm_output_library": {
            "path": str(output_library),
            "sha256": sha256_file(output_library),
        },
        "swmm_solver_library": {
            "path": str(solver_library),
            "sha256": sha256_file(solver_library),
        },
    }
    receipt: dict[str, Any] = {
        "receipt_version": "asw-0b3.engine-build-receipt.v1",
        "authority": {
            "stage": "ASW-0B3",
            "scope": "research_only",
            "promotable": False,
            "path_is_contract": False,
        },
        "source": {
            "repository": SWMM_REPOSITORY,
            "version": SWMM_VERSION,
            "commit": resolved_commit,
            "readme_sha256": sha256_file(readme),
            "rights_notice": "Official pinned README states that the C source is released in the Public Domain.",
        },
        "patch": {
            "path": str(patch_path),
            "sha256": sha256_file(patch_path),
            "tracked_paths": sorted(expected_patch_status),
            "changes_solver_or_output_calculations": False,
        },
        "build": {
            "workspace": str(workspace),
            "commands": [list(command) for command in commands],
            "source_status_after_build": status_after_build,
            "ignored_generated_header_sha256": sha256_file(generated_header),
            "compiler": _tool_output(("cc", "--version")),
            "cmake": _tool_output(("cmake", "--version")),
            "git": _tool_output(("git", "--version")),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "upstream_test_output": upstream_test.stdout.strip(),
            "logs": {
                "clone": clone.stdout + clone.stderr,
                "checkout": checkout.stdout + checkout.stderr,
                "patch": patch.stdout + patch.stderr,
                "configure": configure.stdout + configure.stderr,
                "compile": compile_result.stdout + compile_result.stderr,
                "install": install_result.stdout + install_result.stderr,
            },
        },
        "artifacts": artifacts,
        "version_output": version.stdout.strip(),
    }
    receipt_path = workspace / "engine-build-receipt.json"
    _write_json(receipt_path, receipt)
    return receipt_path


def verify_build_receipt(path: Path) -> dict[str, Any]:
    """Reload a receipt and prove its pin and artifact hashes before execution."""
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BuildBoundaryError(f"cannot read build receipt: {exc}") from exc
    if receipt.get("receipt_version") != "asw-0b3.engine-build-receipt.v1":
        raise BuildBoundaryError("unsupported build receipt version")
    source = receipt.get("source", {})
    if (
        source.get("repository"),
        source.get("version"),
        source.get("commit"),
    ) != (SWMM_REPOSITORY, SWMM_VERSION, SWMM_COMMIT):
        raise BuildBoundaryError("build receipt does not identify the exact candidate")
    authority = receipt.get("authority", {})
    if (
        authority.get("stage") != "ASW-0B3"
        or authority.get("promotable") is not False
        or authority.get("scope") != "research_only"
        or authority.get("path_is_contract") is not False
    ):
        raise BuildBoundaryError("build receipt lacks the research-only authority boundary")
    if receipt.get("version_output") != SWMM_VERSION:
        raise BuildBoundaryError("build receipt lacks the exact version response")
    patch = receipt.get("patch", {})
    patch_path = Path(str(patch.get("path", "")))
    if (
        not patch_path.is_absolute()
        or not patch_path.is_file()
        or patch.get("changes_solver_or_output_calculations") is not False
        or sha256_file(patch_path) != patch.get("sha256")
    ):
        raise BuildBoundaryError("portability patch identity changed after build")
    artifacts = receipt.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != {
        "runswmm",
        "swmm_output_library",
        "swmm_solver_library",
    }:
        raise BuildBoundaryError("build receipt has an incomplete artifact inventory")
    for name, item in artifacts.items():
        if not isinstance(item, dict):
            raise BuildBoundaryError(f"invalid artifact receipt for {name}")
        artifact_path = Path(str(item.get("path", "")))
        expected_hash = item.get("sha256")
        if (
            not artifact_path.is_absolute()
            or not artifact_path.is_file()
            or sha256_file(artifact_path) != expected_hash
        ):
            raise BuildBoundaryError(f"artifact identity changed after build: {name}")
    return receipt
