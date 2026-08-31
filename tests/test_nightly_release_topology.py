# ABOUTME: Verifies nightly sharding and release workflow coverage against the maintained test tree.
# ABOUTME: Prevents CI topology changes from silently omitting test files or release boundary checks.

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts.run_test_shard import SHARD_COUNT, discover_test_files, select_test_shard

ROOT = Path(__file__).resolve().parents[1]
NIGHTLY = ROOT / ".github/workflows/nightly.yml"
RELEASE = ROOT / ".github/workflows/release.yml"


def _load_workflow(path: Path) -> dict[Any, Any]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def _trigger(document: dict[Any, Any]) -> Any:
    # YAML 1.1 parsers may load the GitHub Actions ``on`` key as True.
    return document.get("on", document.get(True))


def test_nightly_shards_cover_every_pytest_file_once() -> None:
    files = discover_test_files(ROOT)
    shards = [select_test_shard(files, shard_index=index, shard_count=SHARD_COUNT) for index in range(SHARD_COUNT)]

    assert files
    assert all(shard for shard in shards)
    assert set().union(*map(set, shards)) == set(files)
    assert sum(map(len, shards)) == len(files)


def test_nightly_workflow_runs_all_extras_and_has_a_stable_gate() -> None:
    document = _load_workflow(NIGHTLY)
    trigger = _trigger(document)
    jobs = document["jobs"]
    assert isinstance(jobs, dict)
    assert isinstance(trigger, dict)
    assert "schedule" in trigger
    assert "workflow_dispatch" in trigger

    complete = jobs["complete-python-suite"]
    assert isinstance(complete, dict)
    assert complete["strategy"]["matrix"]["shard_index"] == list(range(SHARD_COUNT))
    command = " ".join(step.get("run", "") for step in complete["steps"] if isinstance(step, dict))
    assert "uv sync --frozen --all-extras" in command
    assert "scripts/run_test_shard.py" in command
    assert "--shard-count 8" in command

    scale_command = " ".join(
        step.get("run", "") for step in jobs["conformance-recovery-scale-query"]["steps"] if isinstance(step, dict)
    )
    assert "tests/execution/test_fault_injection_scale.py" in scale_command
    assert "tests/ledger/test_evidence_index_scale.py" in scale_command

    platform_command = " ".join(
        step.get("run", "") for step in jobs["platform-paths"]["steps"] if isinstance(step, dict)
    )
    assert "uv sync --frozen" in platform_command
    assert "--all-extras" not in platform_command

    gate = jobs["nightly-gate"]
    assert isinstance(gate, dict)
    assert gate["name"] == "Nightly qualification gate"
    assert gate["if"] == "always()"
    assert set(gate["needs"]) == {
        "complete-python-suite",
        "conformance-recovery-scale-query",
        "frontend-and-plugin",
        "platform-paths",
        "prime-qualification",
        "deepseek-qualification",
    }


def test_release_workflow_is_tag_or_manual_only_and_checks_both_archives() -> None:
    document = _load_workflow(RELEASE)
    trigger = _trigger(document)
    jobs = document["jobs"]
    assert isinstance(trigger, dict)
    assert trigger["push"]["tags"] == ["v*"]
    assert "pull_request" not in trigger
    assert "workflow_dispatch" in trigger

    release = jobs["release-artifacts"]
    assert isinstance(release, dict)
    commands = " ".join(step.get("run", "") for step in release["steps"] if isinstance(step, dict))
    assert "uv build" in commands
    assert "scripts/verify_release_artifacts.py" in commands
    assert "--profile combined" in commands
    assert "find dist" in commands

    platform = jobs["release-platform"]
    platform_command = " ".join(step.get("run", "") for step in platform["steps"] if isinstance(step, dict))
    assert "uv sync --frozen" in platform_command
    assert "--all-extras" not in platform_command
    assert "tests/test_release_manifest.py" in commands

    gate = jobs["release-gate"]
    assert isinstance(gate, dict)
    assert gate["if"] == "always()"
    assert set(gate["needs"]) == {"release-artifacts", "release-platform"}


@pytest.mark.parametrize("path", (NIGHTLY, RELEASE))
def test_ci_workflows_are_tracked_sources(path: Path) -> None:
    assert path.is_file()
