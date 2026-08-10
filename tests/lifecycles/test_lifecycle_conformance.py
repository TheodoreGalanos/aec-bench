# ABOUTME: Proves every registered lifecycle uses the shared finite progression path.
# ABOUTME: Checks terminal completion and repeatable verification from accepted evidence.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from aec_bench.lifecycles.catalogue import (
    lifecycle_operation_resolver,
    lifecycle_smoke_environment,
    lifecycle_template_ids,
    materialize_lifecycle,
    verify_lifecycle,
)
from aec_bench.lifecycles.runtime.episode import LifecycleEpisodeEnvironment
from aec_bench.lifecycles.runtime.lifecycle import read_evidence_lifecycle_state, run_evidence_lifecycle
from tests.support.lifecycle_episode import deterministic_episode_environment


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def _gold_submission_environment(package_dir: Path) -> LifecycleEpisodeEnvironment:
    submissions = _read_json(package_dir / "hidden" / "gold-submissions.json")

    def execute(context: dict[str, Any]) -> dict[str, str]:
        checkpoint_id = str(context["checkpoint_id"])
        submission_path = Path(str(context["submission_path"]))
        submission_path.parent.mkdir(parents=True, exist_ok=True)
        submission_path.write_text(
            json.dumps(submissions[checkpoint_id], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return {"status": "completed"}

    return deterministic_episode_environment(execute)


def _conformance_environment(template_id: str, package_dir: Path) -> LifecycleEpisodeEnvironment:
    environment = lifecycle_smoke_environment(template_id, package_dir)
    if environment is not None:
        return environment
    return _gold_submission_environment(package_dir)


@pytest.mark.parametrize("template_id", sorted(lifecycle_template_ids()))
def test_registered_lifecycle_completes_and_verifies_through_shared_progression(
    tmp_path: Path,
    template_id: str,
) -> None:
    package_dir = materialize_lifecycle(template_id, tmp_path / "package")
    run_dir = tmp_path / "run"
    operation_resolver = lifecycle_operation_resolver(package_dir, run_dir)

    result = run_evidence_lifecycle(
        package_dir,
        run_dir,
        episode_environment=_conformance_environment(template_id, package_dir),
        operation_resolver=operation_resolver,
    )
    state = read_evidence_lifecycle_state(
        package_dir,
        run_dir,
        operation_resolver=operation_resolver,
    )
    first_verification = verify_lifecycle(package_dir, run_dir)
    repeated_verification = verify_lifecycle(package_dir, run_dir)

    assert result["status"] == "complete"
    assert state["status"] == "complete"
    assert state["active_checkpoint_id"] is None
    assert all(checkpoint["status"] == "submitted" for checkpoint in state["checkpoint_runs"])
    assert all(len(checkpoint["attempts"]) == 1 for checkpoint in state["checkpoint_runs"])
    assert first_verification == repeated_verification
