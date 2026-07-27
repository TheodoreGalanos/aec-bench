# ABOUTME: Tests exact engine pins and fail-closed build-workspace rules for the B3 spike.
# ABOUTME: Guards against loose version checks, reused workspaces, and unrecorded portability changes.

from __future__ import annotations

import json
from pathlib import Path

import pytest
from asw_b3_swmm.build import (
    BuildBoundaryError,
    assert_absent_workspace,
    build_commands,
    sha256_file,
    validate_version_output,
    verify_build_receipt,
)
from asw_b3_swmm.constants import SWMM_COMMIT, SWMM_REPOSITORY, SWMM_VERSION


def test_candidate_identity_is_exact() -> None:
    assert SWMM_REPOSITORY == "https://github.com/USEPA/Stormwater-Management-Model.git"
    assert SWMM_VERSION == "5.2.4"
    assert SWMM_COMMIT == "7952ca837988b1c32f791812eccc9fd64547e093"


def test_version_output_requires_an_exact_full_match() -> None:
    validate_version_output("\n5.2.4\n")

    for invalid in ("5.2.40", "EPA SWMM 5.2.4", "5.2.4-dev", "5.2"):
        with pytest.raises(BuildBoundaryError, match="exactly"):
            validate_version_output(invalid)


def test_build_workspace_must_not_exist(tmp_path: Path) -> None:
    target = tmp_path / "build-root"
    assert_absent_workspace(target)
    target.mkdir()

    with pytest.raises(BuildBoundaryError, match="already exists"):
        assert_absent_workspace(target)


def test_build_commands_enable_the_single_relevant_upstream_test() -> None:
    commands = build_commands(Path("/research/patch.patch"), Path("/tmp/work"))

    assert commands[0] == ("git", "clone", SWMM_REPOSITORY, "/tmp/work/source")
    assert ("git", "checkout", SWMM_COMMIT) in commands
    assert ("git", "apply", "/research/patch.patch") in commands
    configure = next(command for command in commands if command[:2] == ("cmake", "-S"))
    assert "-DBUILD_TESTS=ON" in configure
    assert "-DCMAKE_BUILD_TYPE=Release" in configure
    assert ("ctest", "--test-dir", "/tmp/work/build", "--output-on-failure") in commands


def test_receipt_rechecks_the_portability_patch_before_execution(tmp_path: Path) -> None:
    patch = tmp_path / "portability.patch"
    patch.write_text("build wiring only\n", encoding="utf-8")
    artifacts: dict[str, dict[str, str]] = {}
    for name in ("runswmm", "swmm_output_library", "swmm_solver_library"):
        artifact = tmp_path / name
        artifact.write_bytes(name.encode("ascii"))
        artifacts[name] = {
            "path": str(artifact),
            "sha256": sha256_file(artifact),
        }
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(
        json.dumps(
            {
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
                    "commit": SWMM_COMMIT,
                },
                "patch": {
                    "path": str(patch),
                    "sha256": sha256_file(patch),
                    "changes_solver_or_output_calculations": False,
                },
                "artifacts": artifacts,
                "version_output": SWMM_VERSION,
            }
        ),
        encoding="utf-8",
    )
    verify_build_receipt(receipt_path)
    patch.write_text("changed after build\n", encoding="utf-8")

    with pytest.raises(BuildBoundaryError, match="portability patch identity changed"):
        verify_build_receipt(receipt_path)
