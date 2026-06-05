# ABOUTME: Verifies package build rules keep release archives scoped to public assets.
# ABOUTME: Guards against local workspaces and private material leaking into distributions.

from __future__ import annotations

import tomllib
from pathlib import Path


def test_sdist_manifest_is_release_scoped() -> None:
    config = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    sdist = config["tool"]["hatch"]["build"]["targets"]["sdist"]

    assert set(sdist["include"]) == {
        "/.env.example",
        "/LICENSE",
        "/README.md",
        "/pyproject.toml",
        "/uv.lock",
        "/src",
        "/tasks",
        "/tests",
    }
    assert {
        "/packages",
        "/task_decompositions",
        "/task_genomes",
        "/tasks/generated",
        "/workspaces",
    }.issubset(set(sdist["exclude"]))


def test_wheel_build_targets_aec_bench_package() -> None:
    config = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    wheel = config["tool"]["hatch"]["build"]["targets"]["wheel"]

    assert wheel["packages"] == ["src/aec_bench"]


def test_tui_mascot_asset_is_available_for_package_builds() -> None:
    mascot = Path("src/aec_bench/tui/assets/mascot.jpg")

    assert mascot.is_file()
    assert mascot.stat().st_size > 0
