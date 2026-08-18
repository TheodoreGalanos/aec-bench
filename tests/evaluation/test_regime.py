# ABOUTME: Tests publication, verified loading, and semantic diff of evaluation regimes.
# ABOUTME: Proves diagnostic metadata stays outside canonical regime identity.

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aec_bench.cli.main import app
from aec_bench.contracts.evaluation_plane import AcceptancePolicy, RepositoryCriticSource
from aec_bench.contracts.evaluation_refs import CriticRole
from aec_bench.evaluation.regime import (
    diff_evaluation_regimes,
    load_evaluation_regime,
    publish_evaluation_regime,
)
from aec_bench.ledger.artifact_repository import ArtifactRepository
from tests.support.evaluation_regimes import make_regime

runner = CliRunner()


def test_semantic_regime_publication_is_deterministic(tmp_path: Path) -> None:
    repository = ArtifactRepository(tmp_path)
    regime = make_regime()

    first = publish_evaluation_regime(repository, regime)
    second = publish_evaluation_regime(repository, make_regime())

    assert first == second
    assert load_evaluation_regime(repository, first) == regime
    assert first.artifact.sha256 not in regime.model_dump_json()


def test_outcome_affecting_change_creates_new_regime_identity(tmp_path: Path) -> None:
    repository = ArtifactRepository(tmp_path)
    original = make_regime()
    changed = original.model_copy(
        update={
            "acceptance_policy": AcceptancePolicy(
                policy_id="acceptance.standard",
                configuration={"threshold": 0.9},
            )
        }
    )

    original_ref = publish_evaluation_regime(repository, original)
    changed_ref = publish_evaluation_regime(repository, changed)
    diff = diff_evaluation_regimes(
        left_ref=original_ref,
        left=original,
        right_ref=changed_ref,
        right=changed,
    )

    assert original_ref.artifact.sha256 != changed_ref.artifact.sha256
    assert [(change.path, change.before, change.after) for change in diff.changes] == [
        ("regime.acceptance_policy.configuration.threshold", 0.8, 0.9)
    ]


def test_repository_critic_revision_changes_regime_identity(tmp_path: Path) -> None:
    repository = ArtifactRepository(tmp_path)
    original = make_regime()
    development = original.critic(CriticRole.DEVELOPMENT)
    changed_development = development.model_copy(
        update={
            "source": RepositoryCriticSource(
                source_revision="2" * 40,
                entrypoint="aec_bench.evaluation.rubric_scorer",
            )
        }
    )
    changed = original.model_copy(
        update={
            "critics": tuple(
                changed_development if critic.role is CriticRole.DEVELOPMENT else critic for critic in original.critics
            )
        }
    )

    original_ref = publish_evaluation_regime(repository, original)
    changed_ref = publish_evaluation_regime(repository, changed)

    assert original_ref.artifact.sha256 != changed_ref.artifact.sha256


def test_diagnostic_metadata_cannot_enter_canonical_regime() -> None:
    payload = make_regime().model_dump(mode="json")

    for field in ("comment", "local_path", "publication_label", "published_at"):
        changed = dict(payload)
        changed[field] = "diagnostic"
        with pytest.raises(ValueError):
            type(make_regime()).model_validate(changed)


def test_regime_show_and_diff_cli_report_semantic_content(tmp_path: Path) -> None:
    repository = ArtifactRepository(tmp_path)
    original = make_regime()
    changed = original.model_copy(
        update={
            "acceptance_policy": AcceptancePolicy(
                policy_id="acceptance.standard",
                configuration={"threshold": 0.9},
            )
        }
    )
    original_ref = publish_evaluation_regime(repository, original)
    changed_ref = publish_evaluation_regime(repository, changed)

    show = runner.invoke(
        app,
        [
            "--json",
            "evaluation",
            "regime",
            "show",
            original_ref.artifact.artifact_id,
            "--artifact-root",
            str(tmp_path),
        ],
    )
    assert show.exit_code == 0, show.output
    show_payload = json.loads(show.output)
    assert show_payload["data"]["regime"]["regime_id"] == original.regime_id

    result = runner.invoke(
        app,
        [
            "--json",
            "evaluation",
            "regime",
            "diff",
            original_ref.artifact.artifact_id,
            changed_ref.artifact.artifact_id,
            "--artifact-root",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["data"]["changes"][0]["path"] == "regime.acceptance_policy.configuration.threshold"
