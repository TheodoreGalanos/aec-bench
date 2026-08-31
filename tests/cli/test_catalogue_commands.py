# ABOUTME: Tests the installed catalogue build, check, and semantic diff commands.
# ABOUTME: Protects deterministic generation, freshness failures, and identity-based differences.

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import aec_bench.catalogue as catalogue_module
from aec_bench.cli.main import app

runner = CliRunner()


def test_catalogue_build_and_check_generate_both_catalogues(tmp_path: Path) -> None:
    built = runner.invoke(app, ["--json", "catalogue", "build", "--root", str(tmp_path)])

    assert built.exit_code == 0, built.stdout
    payload = json.loads(built.stdout)
    assert payload["data"]["worlds"] == 2
    assert (tmp_path / "src/aec_bench/worlds/generated_catalogue.py").is_file()
    assert (tmp_path / "src/aec_bench/lifecycles/generated_catalogue.py").is_file()

    checked = runner.invoke(app, ["--json", "catalogue", "check", "--root", str(tmp_path)])

    assert checked.exit_code == 0, checked.stdout
    assert json.loads(checked.stdout)["data"]["status"] == "ok"


def test_catalogue_build_reads_the_explicit_owner_lists_before_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        catalogue_module,
        "WORLD_OWNER_IMPORTS",
        catalogue_module.WORLD_OWNER_IMPORTS[:1],
    )
    monkeypatch.setattr(
        catalogue_module,
        "LIFECYCLE_OWNER_IMPORTS",
        catalogue_module.LIFECYCLE_OWNER_IMPORTS[:1],
    )

    built = runner.invoke(app, ["--json", "catalogue", "build", "--root", str(tmp_path)])

    assert built.exit_code == 0, built.stdout
    payload = json.loads(built.stdout)["data"]
    assert payload["worlds"] == 1
    assert payload["lifecycles"] == 1
    world_source = (tmp_path / "src/aec_bench/worlds/generated_catalogue.py").read_text(encoding="utf-8")
    assert "DAM_SEEPAGE_DESCRIPTOR" in world_source
    assert "PUMP_STATION_DESCRIPTOR" not in world_source


def test_catalogue_check_reports_an_owner_module_that_cannot_be_imported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        catalogue_module,
        "WORLD_OWNER_IMPORTS",
        (("missing-world", "aec_bench.worlds.missing", "WORLD_DESCRIPTOR", "MISSING_DESCRIPTOR"),),
    )

    checked = runner.invoke(app, ["--json", "catalogue", "check", "--root", str(tmp_path)])

    assert checked.exit_code == 1
    assert "world owner missing-world cannot be imported" in checked.stderr


def test_catalogue_check_reports_stale_generated_output(tmp_path: Path) -> None:
    assert runner.invoke(app, ["--json", "catalogue", "build", "--root", str(tmp_path)]).exit_code == 0
    generated = tmp_path / "src/aec_bench/worlds/generated_catalogue.py"
    generated.write_text(generated.read_text(encoding="utf-8") + "\n# stale\n", encoding="utf-8")

    checked = runner.invoke(app, ["--json", "catalogue", "check", "--root", str(tmp_path)])

    assert checked.exit_code == 1
    assert "generated catalogue is stale" in checked.stderr


def test_catalogue_diff_reports_semantic_field_changes(tmp_path: Path) -> None:
    snapshot = tmp_path / "catalogue.json"
    built = runner.invoke(
        app,
        ["--json", "catalogue", "build", "--root", str(tmp_path), "--snapshot", str(snapshot)],
    )
    assert built.exit_code == 0, built.stdout
    document = json.loads(snapshot.read_text(encoding="utf-8"))
    document["worlds"][0]["title"] = "Changed title"
    snapshot.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    diff = runner.invoke(app, ["--json", "catalogue", "diff", "--against", str(snapshot)])

    assert diff.exit_code == 0, diff.stdout
    changes = json.loads(diff.stdout)["data"]["changed"]
    assert any(change["kind"] == "world" and "title" in change["fields"] for change in changes)

    text_diff = runner.invoke(app, ["--text", "catalogue", "diff", "--against", str(snapshot)])
    assert text_diff.exit_code == 0, text_diff.stdout
    assert "title: Changed title -> Dam seepage monitoring" in text_diff.stdout


def test_catalogue_diff_rejects_duplicate_snapshot_identity(tmp_path: Path) -> None:
    snapshot = tmp_path / "invalid.json"
    built = runner.invoke(
        app,
        ["--json", "catalogue", "build", "--root", str(tmp_path), "--snapshot", str(snapshot)],
    )
    assert built.exit_code == 0, built.stdout
    document = json.loads(snapshot.read_text(encoding="utf-8"))
    document["worlds"].append(document["worlds"][0])
    snapshot.write_text(json.dumps(document), encoding="utf-8")

    diff = runner.invoke(app, ["--json", "catalogue", "diff", "--against", str(snapshot)])

    assert diff.exit_code == 1
    assert "duplicate entity identity" in diff.stderr


def test_catalogue_diff_rejects_uuid_reuse_across_entity_kinds(tmp_path: Path) -> None:
    snapshot = tmp_path / "invalid.json"
    built = runner.invoke(
        app,
        ["--json", "catalogue", "build", "--root", str(tmp_path), "--snapshot", str(snapshot)],
    )
    assert built.exit_code == 0, built.stdout
    document = json.loads(snapshot.read_text(encoding="utf-8"))
    document["profiles"][0]["id"] = document["worlds"][0]["id"]
    snapshot.write_text(json.dumps(document), encoding="utf-8")

    diff = runner.invoke(app, ["--json", "catalogue", "diff", "--against", str(snapshot)])

    assert diff.exit_code == 1
    assert "duplicate entity identity" in diff.stderr


def test_catalogue_diff_rejects_invalid_entity_version(tmp_path: Path) -> None:
    snapshot = tmp_path / "invalid.json"
    built = runner.invoke(
        app,
        ["--json", "catalogue", "build", "--root", str(tmp_path), "--snapshot", str(snapshot)],
    )
    assert built.exit_code == 0, built.stdout
    document = json.loads(snapshot.read_text(encoding="utf-8"))
    document["worlds"][0]["version"] = 0
    snapshot.write_text(json.dumps(document), encoding="utf-8")

    diff = runner.invoke(app, ["--json", "catalogue", "diff", "--against", str(snapshot)])

    assert diff.exit_code == 1
    assert "invalid entry" in diff.stderr


def test_catalogue_diff_rejects_entity_version_regression(tmp_path: Path) -> None:
    snapshot = tmp_path / "future.json"
    built = runner.invoke(
        app,
        ["--json", "catalogue", "build", "--root", str(tmp_path), "--snapshot", str(snapshot)],
    )
    assert built.exit_code == 0, built.stdout
    document = json.loads(snapshot.read_text(encoding="utf-8"))
    document["worlds"][0]["version"] += 1
    snapshot.write_text(json.dumps(document), encoding="utf-8")

    diff = runner.invoke(app, ["--json", "catalogue", "diff", "--against", str(snapshot)])

    assert diff.exit_code == 1
    assert "version regressed" in diff.stderr
