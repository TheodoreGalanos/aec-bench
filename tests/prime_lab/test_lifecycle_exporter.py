# ABOUTME: Tests local-only Prime exports for persistent whole-lifecycle interactions.
# ABOUTME: Proves public package identity, state isolation, tool progression, and task-owned reward.

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any, cast

import pytest
from typer.testing import CliRunner

from aec_bench.cli.main import app
from aec_bench.meta_harness.evidence_lifecycle import prepare_evidence_checkpoint
from aec_bench.prime_lab.lifecycle_environment import load_local_lifecycle_environment
from aec_bench.prime_lab.lifecycle_exporter import (
    PrimeLifecycleExportConfig,
    export_prime_lifecycle_environment,
)
from aec_bench.task_world_templates.catalogue import get_template
from aec_bench.task_world_templates.materializer import materialize_template_lifecycle

TEMPLATE_ID = "drainage-model-evidence-lifecycle-review"
INTERACTION_TEMPLATE_ID = "hydraulic-interaction-lifecycle-review"
PUBLIC_VARIANTS = (
    "staged_full_correction",
    "semantic_no_op_release",
)
RUNTIME_PROBE = Path(__file__).with_name("lifecycle_runtime_probe.py")
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

runner = CliRunner()


def test_lifecycle_export_references_registered_public_packages_without_copying(tmp_path: Path) -> None:
    packages = tuple(_materialize(tmp_path / "packages" / variant_id, variant_id) for variant_id in PUBLIC_VARIANTS)

    result = export_prime_lifecycle_environment(
        PrimeLifecycleExportConfig(
            name="ssc03-local-lifecycle",
            package_dirs=packages,
            output_dir=tmp_path / "environments",
            max_turns=60,
        )
    )

    manifest = _read_json(result.manifest_path)
    records = manifest["packages"]
    assert result.lifecycle_count == 2
    assert manifest["local_only"] is True
    assert manifest["execution_mode"] == "persistent_context"
    assert manifest["memory_visibility_policy"] == "persistent_context"
    assert manifest["reward_owner"] == "task_lifecycle_verifier"
    assert [record["variant_id"] for record in records] == sorted(PUBLIC_VARIANTS)
    assert [record["package_dir"] for record in records] == [str(path.resolve()) for path in sorted(packages)]
    assert all(record["visibility"] == "public" for record in records)
    assert all(len(record["lifecycle_spec_sha256"]) == 64 for record in records)
    assert all(len(record["package_sha256"]) == 64 for record in records)
    assert not (result.package_dir / result.environment_id / "packages").exists()
    assert not any(path.name == "aec_bench" for path in result.package_dir.rglob("aec_bench"))
    generated_init = (result.package_dir / result.environment_id / "__init__.py").read_text(encoding="utf-8")
    assert generated_init.startswith(
        "# ABOUTME: Exposes the generated local lifecycle environment loader.\n"
        "# ABOUTME: Keeps package import behavior limited to the Verifiers load contract.\n"
    )

    pyproject = tomllib.loads((result.package_dir / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = cast(list[str], pyproject["project"]["dependencies"])
    assert "verifiers>=0.1.14,<0.2" in dependencies
    assert "aec-bench[prime]" in dependencies
    source = pyproject["tool"]["uv"]["sources"]["aec-bench"]
    assert source == {"path": str(Path(manifest["source"]["root"])), "editable": True}
    readme = (result.package_dir / "README.md").read_text(encoding="utf-8")
    assert readme.startswith(f"# {result.environment_id}\n")
    assert "local-only" in readme.lower()
    assert "prime env push" not in readme
    assert "prime train" not in readme
    assert "vf-eval" not in readme
    assert "uv sync --python 3.13 --project /absolute/path/to/generated-package" in readme
    assert "/absolute/path/to/generated-package/.venv/bin/python \\\n  -c" in readme


def test_lifecycle_export_is_deterministic_and_preserves_existing_output_on_rejection(tmp_path: Path) -> None:
    package = _materialize(tmp_path / "package", PUBLIC_VARIANTS[0])
    config = PrimeLifecycleExportConfig(
        name="ssc03-deterministic",
        package_dirs=(package,),
        output_dir=tmp_path / "environments",
    )
    first = export_prime_lifecycle_environment(config)
    first_hash = _tree_hash(first.package_dir)

    second = export_prime_lifecycle_environment(config)
    assert _tree_hash(second.package_dir) == first_hash

    invalid = tmp_path / "unregistered"
    _copy_tree(package, invalid)
    template = _read_json(invalid / "template.json")
    template["template_id"] = "unregistered-lifecycle-template"
    _write_json(invalid / "template.json", template)

    with pytest.raises(ValueError, match="registered public lifecycle variant"):
        export_prime_lifecycle_environment(
            PrimeLifecycleExportConfig(
                name="ssc03-deterministic",
                package_dirs=(invalid,),
                output_dir=tmp_path / "environments",
            )
        )

    assert _tree_hash(first.package_dir) == first_hash


def test_lifecycle_export_rejects_empty_duplicate_and_unregistered_packages(tmp_path: Path) -> None:
    package = _materialize(tmp_path / "package", PUBLIC_VARIANTS[0])

    with pytest.raises(ValueError, match="at least one lifecycle package"):
        export_prime_lifecycle_environment(
            PrimeLifecycleExportConfig(name="empty", package_dirs=(), output_dir=tmp_path / "empty")
        )
    with pytest.raises(ValueError, match="duplicate lifecycle package"):
        export_prime_lifecycle_environment(
            PrimeLifecycleExportConfig(
                name="duplicate",
                package_dirs=(package, package),
                output_dir=tmp_path / "duplicate",
            )
        )
    with pytest.raises(ValueError, match="valid PEP 440"):
        export_prime_lifecycle_environment(
            PrimeLifecycleExportConfig(
                name="invalid-version",
                version="not a version",
                package_dirs=(package,),
                output_dir=tmp_path / "invalid-version",
            )
        )
    with pytest.raises(ValueError, match="Python keyword"):
        export_prime_lifecycle_environment(
            PrimeLifecycleExportConfig(
                name="class",
                package_dirs=(package,),
                output_dir=tmp_path / "keyword",
            )
        )
    invalid_source = tmp_path / "invalid-source"
    (invalid_source / "src" / "aec_bench").mkdir(parents=True)
    (invalid_source / "src" / "aec_bench" / "__init__.py").write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="installable aec-bench checkout"):
        export_prime_lifecycle_environment(
            PrimeLifecycleExportConfig(
                name="invalid-source",
                package_dirs=(package,),
                output_dir=tmp_path / "invalid-source-output",
                aec_bench_root=invalid_source,
            )
        )

    unregistered = tmp_path / "unregistered"
    _copy_tree(package, unregistered)
    (unregistered / "template.json").unlink()
    with pytest.raises(ValueError, match="registered public lifecycle variant"):
        export_prime_lifecycle_environment(
            PrimeLifecycleExportConfig(
                name="unregistered",
                package_dirs=(unregistered,),
                output_dir=tmp_path / "unregistered-output",
            )
        )


def test_local_lifecycle_environment_rejects_mixed_request_capabilities(tmp_path: Path) -> None:
    legacy = _materialize(tmp_path / "legacy", PUBLIC_VARIANTS[0])
    conditional = _materialize(tmp_path / "conditional", PUBLIC_VARIANTS[1])
    _add_conditional_evidence(conditional)
    result = export_prime_lifecycle_environment(
        PrimeLifecycleExportConfig(
            name="mixed-capabilities",
            package_dirs=(legacy, conditional),
            output_dir=tmp_path / "environments",
        )
    )

    with pytest.raises(ValueError, match="share one conditional evidence capability"):
        load_local_lifecycle_environment(manifest_path=result.manifest_path)


def test_local_lifecycle_environment_rejects_mixed_operation_capabilities(tmp_path: Path) -> None:
    legacy = _materialize(tmp_path / "legacy", PUBLIC_VARIANTS[0])
    interaction = materialize_template_lifecycle(
        get_template(INTERACTION_TEMPLATE_ID),
        tmp_path / "interaction",
        variant_id="tailwater_revision",
    )
    result = export_prime_lifecycle_environment(
        PrimeLifecycleExportConfig(
            name="mixed-operation-capabilities",
            package_dirs=(legacy, interaction),
            output_dir=tmp_path / "environments",
        )
    )

    with pytest.raises(ValueError, match="share one lifecycle operation capability"):
        load_local_lifecycle_environment(manifest_path=result.manifest_path)


def test_lifecycle_export_rejects_destination_overlap_without_mutating_packages(tmp_path: Path) -> None:
    package = _materialize(tmp_path / "victim" / "package", PUBLIC_VARIANTS[0])
    original_hash = _tree_hash(package)

    for name, output_dir in (
        ("package", tmp_path / "victim"),
        ("nested", package / "generated"),
        ("victim", tmp_path),
    ):
        with pytest.raises(ValueError, match="overlaps lifecycle package"):
            export_prime_lifecycle_environment(
                PrimeLifecycleExportConfig(
                    name=name,
                    package_dirs=(package,),
                    output_dir=output_dir,
                )
            )
        assert _tree_hash(package) == original_hash

    occupied = tmp_path / "occupied" / "local_environment"
    occupied.mkdir(parents=True)
    sentinel = occupied / "keep.txt"
    sentinel.write_text("keep\n", encoding="utf-8")
    with pytest.raises(ValueError, match="existing non-export directory"):
        export_prime_lifecycle_environment(
            PrimeLifecycleExportConfig(
                name="local-environment",
                package_dirs=(package,),
                output_dir=tmp_path / "occupied",
            )
        )
    assert sentinel.read_text(encoding="utf-8") == "keep\n"


def test_generated_lifecycle_environment_loads_outside_repo_root(tmp_path: Path) -> None:
    package = _materialize(tmp_path / "package", PUBLIC_VARIANTS[0])
    result = export_prime_lifecycle_environment(
        PrimeLifecycleExportConfig(
            name="ssc03-outside-import",
            package_dirs=(package,),
            output_dir=tmp_path / "environments",
            max_turns=17,
        )
    )
    outside = tmp_path / "outside"
    outside.mkdir()
    uv = shutil.which("uv")
    assert uv is not None
    sync = subprocess.run(
        [
            uv,
            "sync",
            "--quiet",
            "--python",
            sys.executable,
            "--project",
            str(result.package_dir),
        ],
        cwd=outside,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    assert sync.returncode == 0, sync.stderr

    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    process = subprocess.run(
        [
            str(result.package_dir / ".venv" / "bin" / "python"),
            "-c",
            (
                "from ssc03_outside_import import load_environment; "
                "env = load_environment(); "
                "print(type(env).__name__, len(env.dataset), env.max_turns, "
                "env.execution_mode, env.memory_visibility_policy)"
            ),
        ],
        cwd=outside,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert process.returncode == 0, process.stderr
    assert process.stdout.strip() == ("AecBenchLifecycleEnv 1 17 persistent_context persistent_context")


def test_generated_lifecycle_rollout_advances_all_checkpoints_in_one_persistent_session(tmp_path: Path) -> None:
    package = _materialize(tmp_path / "package", PUBLIC_VARIANTS[0])
    result = export_prime_lifecycle_environment(
        PrimeLifecycleExportConfig(
            name="ssc03-gold-lifecycle",
            package_dirs=(package,),
            output_dir=tmp_path / "environments",
        )
    )
    gold = _read_json(package / "hidden" / "gold-submissions.json")
    checkpoint_ids = [item["checkpoint_id"] for item in _read_json(package / "lifecycle.json")["checkpoints"]]
    actions = [
        {"name": "list_workspace", "arguments": {"path": "."}},
        {"name": "read_workspace_file", "arguments": {"path": "instruction.md"}},
    ]
    for checkpoint_id in checkpoint_ids:
        actions.extend(
            [
                {
                    "name": "write_checkpoint_submission",
                    "arguments": {
                        "checkpoint_id": checkpoint_id,
                        "content": json.dumps(gold[checkpoint_id]),
                    },
                },
                {"name": "submit_checkpoint", "arguments": {"checkpoint_id": checkpoint_id}},
            ]
        )
    probe = _run_generated_probe(
        result.package_dir,
        result.environment_id,
        tmp_path / "outside-gold",
        {"trajectory_id": "gold-rollout", "actions": actions},
    )

    responses = cast(list[dict[str, Any]], probe["responses"])
    assert probe["state_type"] == "State"
    assert probe["tool_names"] == [
        "list_workspace",
        "read_workspace_file",
        "write_checkpoint_submission",
        "submit_checkpoint",
        "revisit_checkpoint",
    ]
    assert all("state" not in parameters["properties"] for parameters in probe["tool_parameters"])
    assert "shell" not in json.dumps(probe["tool_names"])
    assert responses[0]["payload"]["status"] == "ok"
    assert "hidden" not in json.dumps(responses[0]["payload"])
    assert responses[1]["payload"]["status"] == "ok"
    transitions = [response for response in responses if response["name"] == "submit_checkpoint"]
    for index, transition in enumerate(transitions):
        expected_status = "complete" if index == len(checkpoint_ids) - 1 else "awaiting_checkpoint_submission"
        assert transition["payload"]["status"] == expected_status
        assert transition["has_final_env_response"] is (expected_status == "complete")
    assert all(
        response["payload"]["status"] == "written"
        for response in responses
        if response["name"] == "write_checkpoint_submission"
    )

    lifecycle = cast(dict[str, Any], probe["lifecycle"])
    attempts = [attempt for checkpoint in lifecycle["checkpoint_runs"] for attempt in checkpoint["attempts"]]
    assert lifecycle["status"] == "complete"
    assert [attempt["status"] for attempt in attempts] == ["submitted", "submitted", "submitted"]
    assert {attempt["session_id"] for attempt in attempts} == {"gold-rollout"}


def test_generated_lifecycle_rollout_exposes_conditional_evidence_only_for_capable_package(
    tmp_path: Path,
) -> None:
    package = _materialize(tmp_path / "package", PUBLIC_VARIANTS[0])
    _add_conditional_evidence(package)
    result = export_prime_lifecycle_environment(
        PrimeLifecycleExportConfig(
            name="ssc03-conditional-lifecycle",
            package_dirs=(package,),
            output_dir=tmp_path / "environments",
        )
    )
    gold = _read_json(package / "hidden" / "gold-submissions.json")
    checkpoint_ids = [item["checkpoint_id"] for item in _read_json(package / "lifecycle.json")["checkpoints"]]
    actions: list[dict[str, Any]] = [
        {
            "name": "request_evidence",
            "arguments": {
                "checkpoint_id": checkpoint_ids[0],
                "request_id": "survey_revision",
                "reason": "Resolve the source revision discrepancy.",
            },
        }
    ]
    for checkpoint_id in checkpoint_ids:
        actions.extend(
            [
                {
                    "name": "write_checkpoint_submission",
                    "arguments": {
                        "checkpoint_id": checkpoint_id,
                        "content": json.dumps(gold[checkpoint_id]),
                    },
                },
                {"name": "submit_checkpoint", "arguments": {"checkpoint_id": checkpoint_id}},
            ]
        )

    probe = _run_generated_probe(
        result.package_dir,
        result.environment_id,
        tmp_path / "outside-conditional",
        {"trajectory_id": "conditional-rollout", "actions": actions},
    )

    assert probe["tool_names"] == [
        "list_workspace",
        "read_workspace_file",
        "write_checkpoint_submission",
        "request_evidence",
        "submit_checkpoint",
        "revisit_checkpoint",
    ]
    request_response = next(
        response
        for response in cast(list[dict[str, Any]], probe["responses"])
        if response["name"] == "request_evidence"
    )
    assert request_response["payload"] == {
        "status": "released",
        "checkpoint_id": checkpoint_ids[0],
        "request_id": "survey_revision",
        "remaining_budget": 0,
        "released_files": [f"inbox/{checkpoint_ids[0]}/requests/survey_revision/survey-rev-b.txt"],
    }
    action = cast(dict[str, Any], probe["lifecycle"])["checkpoint_runs"][0]["evidence_request_actions"][0]
    assert action["session_id"] == "conditional-rollout"
    request_parameters = probe["tool_parameters"][probe["tool_names"].index("request_evidence")]
    assert set(request_parameters["properties"]) == {"checkpoint_id", "request_id", "reason"}


def test_generated_lifecycle_rollout_executes_hydraulic_operation_with_public_schema(
    tmp_path: Path,
) -> None:
    package = materialize_template_lifecycle(
        get_template(INTERACTION_TEMPLATE_ID),
        tmp_path / "package",
        variant_id="tailwater_revision",
    )
    identity_run = tmp_path / "identity-run"
    prepare_evidence_checkpoint(package, identity_run)
    current_source = _read_json(identity_run / "workspace" / "hydraulics" / "current-source.json")
    result = export_prime_lifecycle_environment(
        PrimeLifecycleExportConfig(
            name="ssc03-hydraulic-operation-lifecycle",
            package_dirs=(package,),
            output_dir=tmp_path / "environments",
        )
    )
    actions = [
        {"name": "list_workspace", "arguments": {"path": "hydraulics"}},
        {
            "name": "read_workspace_file",
            "arguments": {"path": "hydraulics/current-source.json"},
        },
        {
            "name": "execute_operation",
            "arguments": {
                "checkpoint_id": "baseline_analysis",
                "operation_id": "hydrology.design-10yr",
                "visible_source_state_sha256": current_source["visible_source_state_sha256"],
                "reason": "Calculate the declared baseline design hydrology.",
            },
        },
    ]

    probe = _run_generated_probe(
        result.package_dir,
        result.environment_id,
        tmp_path / "outside-hydraulic-operation",
        {"trajectory_id": "hydraulic-operation-rollout", "actions": actions},
    )

    assert probe["tool_names"] == [
        "list_workspace",
        "read_workspace_file",
        "write_checkpoint_submission",
        "execute_operation",
        "submit_checkpoint",
        "revisit_checkpoint",
    ]
    responses = cast(list[dict[str, Any]], probe["responses"])
    assert responses[0]["payload"] == {
        "status": "ok",
        "path": "hydraulics",
        "entries": ["current-source.json"],
    }
    operation = responses[2]["payload"]
    assert operation["status"] == "completed"
    assert operation["action_id"] == "operation-000001"
    assert operation["operation_id"] == "hydrology.design-10yr"
    assert operation["remaining_budget"] == 5
    assert "session_id" not in json.dumps(operation)
    assert "attempt_id" not in json.dumps(operation)
    parameters = probe["tool_parameters"][probe["tool_names"].index("execute_operation")]
    assert set(parameters["properties"]) == {
        "checkpoint_id",
        "operation_id",
        "visible_source_state_sha256",
        "reason",
    }
    assert "workspace/hydraulics/current-source.json" in probe["run_files"]
    assert "workspace/inbox/baseline_analysis/operations/operation-000001/hydrology.json" in probe["run_files"]


def test_lifecycle_reward_is_task_owned_and_only_runs_at_terminal_state(tmp_path: Path) -> None:
    package = _materialize(tmp_path / "package", PUBLIC_VARIANTS[0])
    result = export_prime_lifecycle_environment(
        PrimeLifecycleExportConfig(
            name="ssc03-task-owned-reward",
            package_dirs=(package,),
            output_dir=tmp_path / "environments",
        )
    )
    incomplete = _run_generated_probe(
        result.package_dir,
        result.environment_id,
        tmp_path / "outside-incomplete",
        {"trajectory_id": "incomplete-rollout", "score": True},
    )
    assert incomplete["reward"] == 0.0
    assert incomplete["reward_status"] == "incomplete"
    assert incomplete["metrics"]["aec_bench_lifecycle_reward"] == 0.0
    incomplete_lifecycle = cast(dict[str, Any], incomplete["lifecycle"])
    assert incomplete_lifecycle["checkpoint_runs"][0]["attempts"][0]["status"] == "failed"
    assert incomplete["verification"] is None
    assert incomplete["cleanup"] == {
        "state_keys_removed": True,
        "temporary_directory_exists": False,
    }

    gold = _read_json(package / "hidden" / "gold-submissions.json")
    checkpoint_ids = [item["checkpoint_id"] for item in _read_json(package / "lifecycle.json")["checkpoints"]]
    actions = []
    for checkpoint_id in checkpoint_ids:
        actions.extend(
            [
                {
                    "name": "write_checkpoint_submission",
                    "arguments": {
                        "checkpoint_id": checkpoint_id,
                        "content": json.dumps(gold[checkpoint_id]),
                    },
                },
                {"name": "submit_checkpoint", "arguments": {"checkpoint_id": checkpoint_id}},
            ]
        )
    complete = _run_generated_probe(
        result.package_dir,
        result.environment_id,
        tmp_path / "outside-complete",
        {"trajectory_id": "complete-rollout", "actions": actions, "score": True},
    )

    assert complete["reward"] == 1.0
    assert complete["reward_status"] == "verified"
    assert complete["metrics"]["aec_bench_lifecycle_reward"] == 1.0
    verification = cast(dict[str, Any], complete["verification"])
    assert verification["passed"] is True
    assert verification["reward"] == 1.0
    assert not [path for path in complete["run_files"] if "checkpoint_reward" in path]
    assert complete["cleanup"] == {
        "state_keys_removed": True,
        "temporary_directory_exists": False,
    }


def test_generated_lifecycle_environment_rejects_path_escape_and_package_hash_drift(tmp_path: Path) -> None:
    package = _materialize(tmp_path / "package", PUBLIC_VARIANTS[0])
    result = export_prime_lifecycle_environment(
        PrimeLifecycleExportConfig(
            name="ssc03-hash-drift",
            package_dirs=(package,),
            output_dir=tmp_path / "environments",
        )
    )
    confined = _run_generated_probe(
        result.package_dir,
        result.environment_id,
        tmp_path / "outside-confined",
        {
            "trajectory_id": "confined-rollout",
            "actions": [
                {
                    "name": "read_workspace_file",
                    "arguments": {"path": "../hidden/gold-submissions.json"},
                },
                {
                    "name": "write_checkpoint_submission",
                    "arguments": {"checkpoint_id": "initial_review", "content": "[]"},
                },
            ],
        },
    )
    responses = cast(list[dict[str, Any]], confined["responses"])
    assert responses[0]["payload"]["status"] == "rejected"
    assert responses[1]["payload"]["status"] == "rejected"

    release = next((package / "releases").rglob("*.md"))
    drift = _run_generated_probe(
        result.package_dir,
        result.environment_id,
        tmp_path / "outside-drift",
        {
            "trajectory_id": "drifted-rollout",
            "mutate_after_load": str(release),
            "capture_setup_error": True,
        },
    )
    assert drift["setup_error"] == "ValueError"
    assert "package identity" in drift["message"]


def test_generated_lifecycle_environment_rechecks_source_provenance_at_setup(tmp_path: Path) -> None:
    source_root = tmp_path / "bound-source"
    source_package = source_root / "src" / "aec_bench"
    shutil.copytree(
        REPOSITORY_ROOT / "src" / "aec_bench",
        source_package,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    shutil.copy2(REPOSITORY_ROOT / "pyproject.toml", source_root / "pyproject.toml")
    shutil.copy2(REPOSITORY_ROOT / "uv.lock", source_root / "uv.lock")
    marker = source_package / "prime_lab" / "source_drift_marker.py"
    marker.write_text("VALUE = 1\n", encoding="utf-8")
    package = _materialize(tmp_path / "package", PUBLIC_VARIANTS[0])
    result = export_prime_lifecycle_environment(
        PrimeLifecycleExportConfig(
            name="ssc03-source-drift",
            package_dirs=(package,),
            output_dir=tmp_path / "environments",
            aec_bench_root=source_root,
        )
    )

    drift = _run_generated_probe(
        result.package_dir,
        result.environment_id,
        tmp_path / "outside-source-drift",
        {
            "trajectory_id": "source-drifted-rollout",
            "mutate_after_load": str(marker),
            "capture_setup_error": True,
        },
        extra_python_path=source_root / "src",
    )
    assert drift["setup_error"] == "ValueError"
    assert "source provenance" in drift["message"]


def test_prime_export_lifecycle_cli_writes_local_only_manifest(tmp_path: Path) -> None:
    packages = tuple(_materialize(tmp_path / "packages" / variant_id, variant_id) for variant_id in PUBLIC_VARIANTS)
    command = [
        "--json",
        "prime",
        "export-lifecycle",
        "--name",
        "ssc03-cli-lifecycle",
        "--output-dir",
        str(tmp_path / "environments"),
        "--max-turns",
        "23",
    ]
    for package in packages:
        command.extend(["--package", str(package)])

    result = runner.invoke(app, command)

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "prime export-lifecycle"
    assert payload["data"]["local_only"] is True
    assert payload["data"]["lifecycle_count"] == 2
    manifest = _read_json(Path(payload["data"]["manifest_path"]))
    assert manifest["max_turns"] == 23
    help_result = runner.invoke(app, ["prime", "export-lifecycle", "--help"])
    assert help_result.exit_code == 0
    assert "hosted" not in help_result.output.lower()
    assert "train" not in help_result.output.lower()


def _materialize(path: Path, variant_id: str) -> Path:
    return materialize_template_lifecycle(get_template(TEMPLATE_ID), path, variant_id=variant_id)


def _add_conditional_evidence(package: Path) -> None:
    lifecycle_path = package / "lifecycle.json"
    template_path = package / "template.json"
    lifecycle = _read_json(lifecycle_path)
    template = _read_json(template_path)
    checkpoint_id = lifecycle["checkpoints"][0]["checkpoint_id"]
    conditional = {
        "request_budget": 1,
        "requests": [
            {
                "request_id": "survey_revision",
                "title": "Revised survey",
                "description": "Obtain the revised survey source.",
                "prerequisite_request_ids": [],
            }
        ],
    }
    lifecycle["checkpoints"][0]["conditional_evidence"] = conditional
    template["evidence_lifecycle"]["checkpoints"][0]["conditional_evidence"] = conditional
    _write_json(lifecycle_path, lifecycle)
    _write_json(template_path, template)
    _write_json(
        package / "hidden" / "evidence-request-resolutions.json",
        {
            "schema_version": "1",
            "lifecycle_id": lifecycle["lifecycle_id"],
            "resolutions": [
                {
                    "checkpoint_id": checkpoint_id,
                    "request_id": "survey_revision",
                    "source_path": f"hidden/evidence_requests/{checkpoint_id}/survey_revision",
                }
            ],
        },
    )
    evidence = package / "hidden" / "evidence_requests" / checkpoint_id / "survey_revision"
    evidence.mkdir(parents=True)
    (evidence / "survey-rev-b.txt").write_text("revision B\n", encoding="utf-8")


def _run_generated_probe(
    package_dir: Path,
    environment_id: str,
    outside: Path,
    request: dict[str, Any],
    *,
    extra_python_path: Path | None = None,
) -> dict[str, Any]:
    outside.mkdir()
    environment = os.environ.copy()
    python_paths = [str(package_dir)]
    if extra_python_path is not None:
        python_paths.append(str(extra_python_path))
    environment["PYTHONPATH"] = os.pathsep.join(python_paths)
    process = subprocess.run(
        [sys.executable, str(RUNTIME_PROBE), environment_id],
        cwd=outside,
        env=environment,
        input=json.dumps(request),
        capture_output=True,
        text=True,
        check=False,
        timeout=90,
    )
    assert process.returncode == 0, process.stderr
    assert not process.stderr.strip(), process.stderr
    return cast(dict[str, Any], json.loads(process.stdout))


def _read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _copy_tree(source: Path, destination: Path) -> None:
    shutil.copytree(source, destination)


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(path.read_bytes())
    return digest.hexdigest()
