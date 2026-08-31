# ABOUTME: Verifies the required pull-request workflow and changed-owner test map.
# ABOUTME: Keeps the branch-protection target, owner coverage, and selected test paths explicit.

from __future__ import annotations

import json
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

from scripts.run_changed_owner_tests import OWNER_TESTS, _changed_source_paths, _owner_for_source, _test_paths

ROOT = Path(__file__).resolve().parents[1]
OWNER_POLICY = ROOT / "scripts/owner_dependencies.toml"
WORKFLOW = ROOT / ".github/workflows/required-pr.yml"


def test_owner_test_map_matches_policy_and_points_to_existing_paths() -> None:
    with OWNER_POLICY.open("rb") as policy_file:
        owners = set(tomllib.load(policy_file)["owners"])

    assert set(OWNER_TESTS) == owners
    assert all((ROOT / path).exists() for paths in OWNER_TESTS.values() for path in paths)


def test_changed_owner_selection_handles_known_unknown_and_non_source_paths() -> None:
    assert _owner_for_source("src/aec_bench/worlds/runtime.py") == "worlds"
    assert _owner_for_source("src/aec_bench/new_owner/module.py") == "*"
    assert _owner_for_source("docs/README.md") is None

    assert _test_paths(("docs/README.md",)) == ()
    assert _test_paths(("tests/contracts/test_identity.py",)) == ("tests/contracts/test_identity.py",)
    assert _test_paths(("src/aec_bench/worlds/runtime.py",)) == ("tests/worlds/test_catalogue.py",)
    assert _test_paths(("src/aec_bench/new_owner/module.py",)) == ("tests/",)


def test_changed_source_selection_is_exact_and_excludes_non_python_paths() -> None:
    changed = (
        "src/aec_bench/worlds/runtime.py",
        "src/aec_bench/worlds/data.toml",
        "tests/worlds/test_catalogue.py",
        "docs/README.md",
    )

    assert _changed_source_paths(changed) == ("src/aec_bench/worlds/runtime.py",)


@pytest.mark.skipif(shutil.which("ruby") is None, reason="Ruby is required to parse GitHub Actions YAML")
def test_required_workflow_has_one_stable_aggregate_gate() -> None:
    ruby = """
require "json"
require "yaml"
document = YAML.load_file(ARGV.fetch(0))
puts JSON.generate({"trigger" => document[true], "jobs" => document.fetch("jobs")})
"""
    parsed = subprocess.run(
        ["ruby", "-e", ruby, str(WORKFLOW)],
        check=True,
        capture_output=True,
        text=True,
    )
    document = json.loads(parsed.stdout)
    jobs = document["jobs"]
    mandatory = {"architecture-contracts", "core-behavior", "quality", "changed-owner-tests"}

    assert document["trigger"] == {"pull_request": None}
    assert mandatory <= set(jobs)
    assert jobs["required-pr-gate"]["name"] == "Required PR gate"
    assert jobs["required-pr-gate"]["if"] == "always()"
    assert set(jobs["required-pr-gate"]["needs"]) == mandatory
