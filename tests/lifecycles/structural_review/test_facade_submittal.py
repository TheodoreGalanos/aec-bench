# ABOUTME: Tests the structural facade submittal lifecycle as a second engineering-domain consumer.
# ABOUTME: Proves staged disclosure, template calculation reuse, honest closeout, and task-owned verification.

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from aec_bench.lifecycles.catalogue import (
    lifecycle_operation_resolver,
    materialize_lifecycle,
    verify_lifecycle,
)
from aec_bench.lifecycles.compiled import compile_lifecycle
from aec_bench.lifecycles.runtime.episode import LifecycleEpisodeEnvironment
from aec_bench.lifecycles.runtime.lifecycle import (
    load_validated_lifecycle_submissions,
    read_evidence_lifecycle_state,
    run_evidence_lifecycle,
)
from aec_bench.lifecycles.structural_review.facade_submittal import (
    LIFECYCLE,
    TEMPLATE_ID,
    validated_facade_submittal_package,
)
from aec_bench.templates.builtin.structural.facade_submittal_source_policy_package.engine import compute
from tests.support.lifecycle_episode import deterministic_episode_environment


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def _gold_environment(
    package_dir: Path,
    *,
    mutate: Callable[[str, dict[str, Any]], None] | None = None,
) -> LifecycleEpisodeEnvironment:
    submissions = _read_json(package_dir / "hidden" / "gold-submissions.json")

    def execute(context: dict[str, Any]) -> dict[str, str]:
        checkpoint_id = str(context["checkpoint_id"])
        submission = copy.deepcopy(submissions[checkpoint_id])
        if mutate is not None:
            mutate(checkpoint_id, submission)
        path = Path(str(context["submission_path"]))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(submission, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return {"source": "facade_submittal_test"}

    return deterministic_episode_environment(execute)


def test_facade_submittal_package_reuses_the_existing_template_calculation(tmp_path: Path) -> None:
    package = materialize_lifecycle(TEMPLATE_ID, tmp_path / "package")

    source = _read_json(package / "hidden" / "source-template.json")
    gold = _read_json(package / "hidden" / "gold-submissions.json")
    expected_metrics = compute(**source["source_values"])

    assert validated_facade_submittal_package(package) == {
        "source_template_id": "facade-submittal-source-policy-package",
        "checkpoint_ids": ["source_review", "comment_review", "response_review"],
    }
    assert lifecycle_operation_resolver(package, tmp_path / "run") is None
    assert gold["response_review"]["metrics"] == expected_metrics
    assert sorted(path.name for path in (package / "releases" / "source_review").iterdir()) == [
        "calculation-report.json",
        "facade-elevation.json",
        "material-schedule.json",
        "source-index.json",
    ]
    assert sorted(path.name for path in (package / "releases" / "comment_review").iterdir()) == [
        "boundary-exception-register.json",
        "comment-register.json",
    ]
    assert sorted(path.name for path in (package / "releases" / "response_review").iterdir()) == [
        "submittal-response.json"
    ]


def test_facade_submittal_compiles_without_operation_or_variant_identity(tmp_path: Path) -> None:
    compiled = compile_lifecycle(TEMPLATE_ID, tmp_path / "compiled")

    assert compiled.envelope.template_id == TEMPLATE_ID
    assert compiled.envelope.lifecycle_id == "facade-submittal-review"
    assert compiled.envelope.variant_id is None
    assert compiled.envelope.operation_protocol_sha256 is None
    assert len(compiled.envelope.package_sha256) == 64
    assert len(compiled.envelope.executable_artifact_sha256) == 64


def test_facade_submittal_lifecycle_completes_while_reporting_open_gaps(tmp_path: Path) -> None:
    package = materialize_lifecycle(TEMPLATE_ID, tmp_path / "package")
    run = tmp_path / "run"

    result = run_evidence_lifecycle(
        package,
        run,
        episode_environment=_gold_environment(package),
    )
    state = read_evidence_lifecycle_state(package, run)
    submissions = load_validated_lifecycle_submissions(package, run)
    verification = verify_lifecycle(package, run)

    assert result["status"] == "complete"
    assert state["status"] == "complete"
    assert submissions["response_review"]["review_decision"] == "technical_acceptance_with_open_gaps"
    assert submissions["response_review"]["readiness"] == "not_ready_to_close"
    assert len(submissions["response_review"]["findings"]) == 4
    assert verification["passed"] is True
    assert verification["reward"] == 1.0


def test_facade_submittal_verifier_rejects_a_false_closeout_claim(tmp_path: Path) -> None:
    package = materialize_lifecycle(TEMPLATE_ID, tmp_path / "package")
    run = tmp_path / "run"

    def change_closeout(checkpoint_id: str, submission: dict[str, Any]) -> None:
        if checkpoint_id == "response_review":
            submission["readiness"] = "review_in_progress"

    result = run_evidence_lifecycle(
        package,
        run,
        episode_environment=_gold_environment(package, mutate=change_closeout),
    )
    verification = verify_lifecycle(package, run)

    assert result["status"] == "complete"
    assert verification["passed"] is False
    assert verification["overall"] == "fail"
    assert verification["gates"]["checkpoint_contract"]["passed"] is True
    assert verification["gates"]["review_decision"] == {
        "passed": False,
        "score": 0.0,
        "failures": ["response_review.readiness"],
    }


def test_facade_submittal_declares_a_simple_finite_chain() -> None:
    assert [checkpoint.checkpoint_id for checkpoint in LIFECYCLE.checkpoints] == [
        "source_review",
        "comment_review",
        "response_review",
    ]
    assert [checkpoint.depends_on for checkpoint in LIFECYCLE.checkpoints] == [
        [],
        ["source_review"],
        ["comment_review"],
    ]
    assert all(checkpoint.conditional_evidence is None for checkpoint in LIFECYCLE.checkpoints)
    assert all(checkpoint.conditional_operations is None for checkpoint in LIFECYCLE.checkpoints)
