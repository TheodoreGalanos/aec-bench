# ABOUTME: Tests the optional generated-task replay sidecar and exact regeneration path.
# ABOUTME: Proves external source retention, runtime separation, and overwrite safety.

from __future__ import annotations

import io
import json
import shutil
import tarfile
import tomllib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aec_bench.cli.main import app
from aec_bench.generation import replay as replay_module
from aec_bench.generation.replay import (
    ArtifactTemplateSource,
    GenerationManifest,
    GitTemplateSource,
    load_generation_manifest,
    replay_generation,
)
from aec_bench.tasks.loader import load_task_definition

runner = CliRunner()
BUILTIN_TEMPLATE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "aec_bench"
    / "templates"
    / "builtin"
    / "ground"
    / "terzaghi_bearing_capacity"
)
CUSTOM_VERIFIER_TEMPLATE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "aec_bench"
    / "templates"
    / "builtin"
    / "civil"
    / "coastal_flood_equipment_elevation_issue_review_package"
)


def _generate_external_task(tmp_path: Path, source_template: Path = BUILTIN_TEMPLATE) -> Path:
    template = tmp_path / "external-template"
    shutil.copytree(source_template, template)
    output = tmp_path / "generated"
    result = runner.invoke(
        app,
        [
            "generate",
            "task",
            "--template",
            str(template),
            "--instances",
            "1",
            "--seed",
            "71",
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    return output


def test_standalone_generation_keeps_replay_data_out_of_task_runtime(tmp_path: Path) -> None:
    output = _generate_external_task(tmp_path)
    manifest = load_generation_manifest(output / "generation-manifest.json")
    task_dir = output / manifest.instances[0].task_id
    task_config = tomllib.loads((task_dir / "task.toml").read_text(encoding="utf-8"))

    assert "version" not in task_config
    assert "generation" not in task_config
    assert isinstance(manifest.source, ArtifactTemplateSource)
    assert manifest.config_ref == "generation-config.json"
    serialized_manifest = json.dumps(manifest.model_dump(mode="json")).lower()
    assert all(term not in serialized_manifest for term in ("provider", "actor", "transport", "harbor"))


def test_external_template_source_is_one_verified_artifact(tmp_path: Path) -> None:
    output = _generate_external_task(tmp_path)
    manifest = load_generation_manifest(output / "generation-manifest.json")

    assert isinstance(manifest.source, ArtifactTemplateSource)
    retained_files = [path for path in (output / ".generation-artifacts").rglob("*") if path.is_file()]
    assert len(retained_files) == 1
    assert retained_files[0].stat().st_size == manifest.source.artifact.size_bytes


def test_clean_builtin_template_uses_one_git_revision(tmp_path: Path) -> None:
    output = tmp_path / "generated"
    result = runner.invoke(
        app,
        [
            "generate",
            "task",
            "terzaghi-bearing-capacity",
            "--instances",
            "1",
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output

    manifest = load_generation_manifest(output / "generation-manifest.json")
    assert isinstance(manifest.source, GitTemplateSource)
    assert len(manifest.source.revision) == 40
    assert not (output / ".generation-artifacts").exists()
    assert "sha256" not in json.dumps(manifest.model_dump(mode="json"))

    replay = replay_generation(output / "generation-manifest.json", tmp_path / "replayed")
    assert replay.runtime_matches
    assert replay.replay_metadata_differences == ()


def test_replay_reproduces_all_runtime_task_files(tmp_path: Path) -> None:
    output = _generate_external_task(tmp_path)
    replay_output = tmp_path / "replayed"

    result = replay_generation(output / "generation-manifest.json", replay_output)

    assert result.runtime_matches
    assert result.runtime_differences == ()
    assert result.replay_metadata_differences == ()


def test_replay_cli_reports_an_exact_runtime_match(tmp_path: Path) -> None:
    output = _generate_external_task(tmp_path)
    replay_output = tmp_path / "cli-replayed"

    result = runner.invoke(
        app,
        [
            "generate",
            "replay",
            str(output / "generation-manifest.json"),
            "--output",
            str(replay_output),
        ],
    )

    assert result.exit_code == 0, result.output
    response = json.loads(result.output)
    assert response["data"]["runtime_matches"] is True
    assert response["data"]["runtime_differences"] == []
    assert response["data"]["replay_metadata_differences"] == []


def test_replay_cli_separates_runtime_differences_and_honours_overwrite(tmp_path: Path) -> None:
    output = _generate_external_task(tmp_path)
    manifest = load_generation_manifest(output / "generation-manifest.json")
    instruction = output / manifest.instances[0].task_id / "instruction.md"
    instruction.write_text(instruction.read_text(encoding="utf-8") + "\nChanged after generation.\n", encoding="utf-8")
    replay_output = tmp_path / "cli-replayed"
    replay_output.mkdir()
    (replay_output / "stale.txt").write_text("stale", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "generate",
            "replay",
            str(output / "generation-manifest.json"),
            "--output",
            str(replay_output),
            "--overwrite",
        ],
    )

    assert result.exit_code == 2, result.output
    response = json.loads(result.output)
    assert response["status"] == "partial"
    expected_difference = f"{manifest.instances[0].task_id}/instruction.md: content differs"
    assert response["data"]["runtime_differences"] == [expected_difference]
    assert response["data"]["replay_metadata_differences"] == []
    assert not (replay_output / "stale.txt").exists()


def test_replay_preserves_a_relative_non_json_generation_config(tmp_path: Path) -> None:
    output = _generate_external_task(tmp_path)
    manifest_path = output / "generation-manifest.json"
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    (output / "generation-config.json").unlink()
    (output / "suite.toml").write_text('name = "external-suite"\n', encoding="utf-8")
    manifest_payload["config_ref"] = "suite.toml"
    manifest_path.write_text(json.dumps(manifest_payload), encoding="utf-8")

    replay_output = tmp_path / "toml-replayed"
    result = replay_generation(manifest_path, replay_output)

    assert result.runtime_matches
    assert result.replay_metadata_differences == ()
    assert (replay_output / "suite.toml").read_text(encoding="utf-8") == 'name = "external-suite"\n'


def test_manifest_rejects_a_config_reference_inside_a_runtime_task(tmp_path: Path) -> None:
    output = _generate_external_task(tmp_path)
    manifest_path = output / "generation-manifest.json"
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_payload["config_ref"] = f"{manifest_payload['instances'][0]['task_id']}/instruction.md"

    with pytest.raises(ValueError, match="cannot overlap a runtime task"):
        GenerationManifest.model_validate(manifest_payload)


@pytest.mark.parametrize("config_ref", ["../suite.toml", "nested\\suite.toml", "/suite.toml"])
def test_manifest_rejects_nonportable_config_references(tmp_path: Path, config_ref: str) -> None:
    output = _generate_external_task(tmp_path)
    manifest_payload = json.loads((output / "generation-manifest.json").read_text(encoding="utf-8"))
    manifest_payload["config_ref"] = config_ref

    with pytest.raises(ValueError, match="portable relative path"):
        GenerationManifest.model_validate(manifest_payload)


def test_template_source_extraction_rejects_path_traversal(tmp_path: Path) -> None:
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w") as archive:
        content = b"unsafe"
        member = tarfile.TarInfo("../escaped.txt")
        member.size = len(content)
        archive.addfile(member, io.BytesIO(content))

    with pytest.raises(ValueError, match="unsafe template source archive member"):
        replay_module._extract_template_archive(payload.getvalue(), tmp_path / "extract")

    assert not (tmp_path / "escaped.txt").exists()


def test_replay_refuses_to_overwrite_without_the_flag(tmp_path: Path) -> None:
    output = _generate_external_task(tmp_path)
    replay_output = tmp_path / "replayed"
    replay_output.mkdir()

    with pytest.raises(FileExistsError, match="use --overwrite"):
        replay_generation(output / "generation-manifest.json", replay_output)


def test_replay_never_replaces_a_git_repository_root(tmp_path: Path) -> None:
    output = _generate_external_task(tmp_path)
    replay_output = tmp_path / "repository"
    (replay_output / ".git").mkdir(parents=True)

    with pytest.raises(ValueError, match="Git repository root"):
        replay_generation(output / "generation-manifest.json", replay_output, overwrite=True)

    assert (replay_output / ".git").is_dir()


def test_removing_replay_sidecars_does_not_change_task_loading(tmp_path: Path) -> None:
    output = _generate_external_task(tmp_path)
    manifest_path = output / "generation-manifest.json"
    manifest = load_generation_manifest(manifest_path)
    task_dir = output / manifest.instances[0].task_id
    before = load_task_definition(task_dir, output)

    manifest_path.unlink()
    (output / "generation-config.json").unlink()
    after = load_task_definition(task_dir, output)

    assert before == after


def test_custom_verifier_instance_file_contains_only_consumed_values(tmp_path: Path) -> None:
    output = _generate_external_task(tmp_path, CUSTOM_VERIFIER_TEMPLATE)
    instance_path = next(output.rglob("tests/instance.json"))
    payload = json.loads(instance_path.read_text(encoding="utf-8"))

    assert set(payload) == {"parameters", "ground_truth"}
    assert "packet_variant" in payload["parameters"]
