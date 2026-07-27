# ABOUTME: Specifies the pinned SWMM build identity and fresh-workspace boundary for the W2 generator.
# ABOUTME: Ensures engine setup cannot reuse stale files, drift from the pin, or change build parallelism.

from __future__ import annotations

from pathlib import Path

import pytest
from generator import engine


def test_build_plan_uses_exact_pin_patch_release_and_one_thread(tmp_path: Path) -> None:
    patch = tmp_path / "swmm.patch"
    workspace = tmp_path / "engine"

    commands = engine.build_commands(workspace=workspace, patch_path=patch)

    assert commands[0] == (
        "git",
        "clone",
        "https://github.com/USEPA/Stormwater-Management-Model.git",
        str(workspace / "source"),
    )
    assert commands[1] == ("git", "checkout", "7952ca837988b1c32f791812eccc9fd64547e093")
    assert commands[2] == ("git", "apply", str(patch))
    assert "-DCMAKE_BUILD_TYPE=Release" in commands[3]
    assert commands[4][-2:] == ("--parallel", "1")


def test_fresh_workspace_rejects_existing_directory_file_and_symlink(tmp_path: Path) -> None:
    directory = tmp_path / "directory"
    directory.mkdir()
    file_path = tmp_path / "file"
    file_path.write_text("occupied", encoding="utf-8")
    symlink = tmp_path / "link"
    symlink.symlink_to(file_path)

    for candidate in (directory, file_path, symlink):
        with pytest.raises(engine.EngineBoundaryError, match="workspace"):
            engine.require_absent(candidate)

