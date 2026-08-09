# ABOUTME: Tests least-privilege Harbor export of content-pinned lifecycle worlds.
# ABOUTME: Proves stormwater integration staging, provenance, verifier isolation, and fail-closed semantics.

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import pytest
from harbor.models.task.task import Task as HarborTask  # type: ignore[import-untyped]

from aec_bench.contracts.evidence_lifecycle import ConditionalEvidenceSpec, EvidenceRequestSpec
from aec_bench.harness.harbor_task_export import (
    HARBOR_LIFECYCLE_BRIDGE_MODE,
    ExportedHarborTask,
    export_compiled_lifecycle_harbor_task,
    load_harbor_lifecycle_bridge,
    validate_harbor_lifecycle_semantics,
    verify_exported_lifecycle_run,
    write_harbor_lifecycle_attestation,
)
from aec_bench.harness.harbor_task_exporting import bridge as harbor_bridge_module
from aec_bench.harness.harbor_task_exporting import runtime_wheel, stable_io
from aec_bench.harness.harbor_task_exporting.stable_io import RegularFileSnapshot
from aec_bench.lifecycles.catalogue import lifecycle_definition, lifecycle_smoke_environment
from aec_bench.lifecycles.compiled import (
    CompiledLifecycle,
    CompiledLifecycleEnvelope,
    compile_lifecycle,
)
from aec_bench.lifecycles.runtime.lifecycle import run_evidence_lifecycle
from aec_bench.tasks.registry import TaskRegistry
from aec_bench.tasks.validator import validate_task

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_ID = "hydraulic-interaction-lifecycle-review"


def _directory_sha256(path: Path) -> str:
    manifest = {
        candidate.relative_to(path).as_posix(): hashlib.sha256(candidate.read_bytes()).hexdigest()
        for candidate in sorted(path.rglob("*"))
        if candidate.is_file()
    }
    return hashlib.sha256(
        json.dumps(
            manifest,
            allow_nan=False,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _export_stormwater(tmp_path: Path) -> tuple[CompiledLifecycle, ExportedHarborTask, Path]:
    compiled = compile_lifecycle(
        TEMPLATE_ID,
        tmp_path / "compiled",
        variant_id="administrative_no_op",
    )
    tasks_root = tmp_path / "tasks"
    task_dir = tasks_root / "civil" / "stormwater-hydraulic-interaction"
    exported = export_compiled_lifecycle_harbor_task(
        compiled,
        task_dir,
        project_root=REPO_ROOT,
    )
    return compiled, exported, tasks_root


def test_verifier_runtime_source_ignores_local_frontend_dependencies(tmp_path: Path) -> None:
    package_root = tmp_path / "aec_bench"
    source = package_root / "runtime.py"
    source.parent.mkdir(parents=True)
    source.write_text("VALUE = 1\n", encoding="utf-8")
    frontend_dependency = package_root / "web" / "frontend" / "node_modules" / ".bin" / "tool"
    frontend_dependency.parent.mkdir(parents=True)
    frontend_dependency.symlink_to(source)

    payloads = runtime_wheel._canonical_source_payloads(package_root)

    assert payloads == [("aec_bench/runtime.py", b"VALUE = 1\n")]


def test_stormwater_export_is_loadable_staged_and_verifier_isolated(tmp_path: Path) -> None:
    compiled, exported, tasks_root = _export_stormwater(tmp_path)
    task_dir = exported.task_dir

    registry = TaskRegistry(tasks_root)
    registry.reload()
    assert registry.load_errors == []
    task = registry.get("civil/stormwater-hydraulic-interaction")
    assert task is not None
    assert task.environment.dockerfile == "environment/Dockerfile"
    assert task.verifier.script == "tests/test.sh"
    assert task.verifier.expected_output_path == "/workspace/lifecycle-run"
    assert HarborTask(task_dir).paths.is_valid()
    validation = validate_task(task_dir, tasks_root=tasks_root)
    assert validation.passed
    assert validation.findings == []

    manifest = json.loads(exported.manifest_path.read_text(encoding="utf-8"))
    assert manifest["source"]["envelope"] == compiled.envelope.model_dump(mode="json")
    assert manifest["source"]["package_sha256"] == compiled.envelope.package_sha256
    assert manifest["bridge"] == {
        "allowed_tools": [
            "execute_operation",
            "list_workspace",
            "read_workspace_file",
            "revisit_checkpoint",
            "submit_checkpoint",
            "write_checkpoint_submission",
        ],
        "mode": HARBOR_LIFECYCLE_BRIDGE_MODE,
        "output_path": "/workspace/lifecycle-run",
        "reward_owner": "harbor_verifier",
        "visibility_policy": "persistent_context",
    }
    task_toml = task_dir / "task.toml"
    test_script = task_dir / "tests" / "test.sh"
    assert manifest["harbor"] == {
        "output_path": "/workspace/lifecycle-run",
        "reward_owner": "harbor_verifier",
        "security": {
            "agent_timeout_sec": 3600.0,
            "allow_internet": False,
            "build_timeout_sec": 1800.0,
            "cpus": 2,
            "memory_mb": 4096,
            "storage_mb": 10240,
            "verifier_timeout_sec": 600.0,
        },
        "task_toml": "task.toml",
        "task_toml_sha256": hashlib.sha256(task_toml.read_bytes()).hexdigest(),
        "test_script": "tests/test.sh",
        "test_script_sha256": hashlib.sha256(test_script.read_bytes()).hexdigest(),
    }

    initial = task_dir / "environment" / "context" / "initial"
    assert (initial / "instruction.md").is_file()
    assert (initial / "inbox" / "baseline_analysis" / "notice.md").is_file()
    assert (initial / "checkpoints" / "baseline_analysis" / "operations.json").is_file()
    assert (initial / "hydraulics" / "current-source.json").is_file()
    assert not (initial / "inbox" / "revision_analysis").exists()
    assert not (task_dir / "environment" / "runtime").exists()
    assert (task_dir / "tests" / "compiled-world" / "hidden").is_dir()
    assert exported.verifier_runtime_wheel_path.is_relative_to(task_dir / "tests")

    agent_surface = b"\n".join(
        path.read_bytes() for path in sorted((task_dir / "environment").rglob("*")) if path.is_file()
    )
    assert b"build_hydraulic_review_smoke_environment" not in agent_surface
    assert b"verify_hydraulic_review_lifecycle" not in agent_surface
    assert b"administrative_no_op" not in agent_surface
    with ZipFile(exported.verifier_runtime_wheel_path) as verifier_runtime:
        assert "aec_bench/harness/harbor_task_export.py" in verifier_runtime.namelist()

    bridge = load_harbor_lifecycle_bridge(task_dir / "environment")
    assert bridge.task_root == task_dir.resolve()
    assert bridge.package_dir == (task_dir / "tests" / "compiled-world").resolve()
    assert bridge.envelope == compiled.envelope
    assert bridge.allowed_tools == tuple(manifest["bridge"]["allowed_tools"])


def test_bridge_validation_fails_closed_before_execution_on_provenance_drift(tmp_path: Path) -> None:
    _, exported, _ = _export_stormwater(tmp_path)
    initial_instruction = exported.task_dir / "environment" / "context" / "initial" / "instruction.md"
    initial_instruction.write_text("tampered\n", encoding="utf-8")

    with pytest.raises(ValueError, match="initial context does not match"):
        load_harbor_lifecycle_bridge(exported.task_dir / "environment")


def test_bridge_rejects_coordinated_agent_surface_and_manifest_replacement(tmp_path: Path) -> None:
    _, exported, _ = _export_stormwater(tmp_path)
    initial_context = exported.task_dir / "environment" / "context" / "initial"
    (initial_context / "future-release.json").write_text('{"future": true}\n', encoding="utf-8")
    instruction = exported.task_dir / "instruction.md"
    instruction.write_text(instruction.read_text(encoding="utf-8") + "Future hint.\n", encoding="utf-8")
    dockerfile = exported.task_dir / "environment" / "Dockerfile"
    dockerfile.write_text(dockerfile.read_text(encoding="utf-8") + "ENV BYPASS=1\n", encoding="utf-8")

    manifest = json.loads(exported.manifest_path.read_text(encoding="utf-8"))
    manifest["agent_surface"]["initial_context_sha256"] = _directory_sha256(initial_context)
    manifest["agent_surface"]["task_instruction_sha256"] = hashlib.sha256(instruction.read_bytes()).hexdigest()
    manifest["agent_surface"]["dockerfile_sha256"] = hashlib.sha256(dockerfile.read_bytes()).hexdigest()
    payload = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    exported.manifest_path.write_text(payload, encoding="utf-8")
    (exported.task_dir / "tests" / "compiled-world-export.json").write_text(payload, encoding="utf-8")

    with pytest.raises(ValueError, match="canonical agent surface"):
        load_harbor_lifecycle_bridge(exported.task_dir / "environment")


def test_bridge_validation_binds_hidden_manifest_and_harbor_security_contract(tmp_path: Path) -> None:
    _, exported, _ = _export_stormwater(tmp_path)
    hidden_manifest = exported.task_dir / "tests" / "compiled-world-export.json"
    hidden_manifest.write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="hidden export manifest does not match"):
        load_harbor_lifecycle_bridge(exported.task_dir / "environment")

    _, second, _ = _export_stormwater(tmp_path / "security")
    task_toml = second.task_dir / "task.toml"
    task_toml.write_text(
        task_toml.read_text(encoding="utf-8").replace("allow_internet = false", "allow_internet = true"),
        encoding="utf-8",
    )
    manifest = json.loads(second.manifest_path.read_text(encoding="utf-8"))
    manifest["harbor"]["task_toml_sha256"] = hashlib.sha256(task_toml.read_bytes()).hexdigest()
    payload = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    second.manifest_path.write_text(payload, encoding="utf-8")
    (second.task_dir / "tests" / "compiled-world-export.json").write_text(payload, encoding="utf-8")

    with pytest.raises(ValueError, match="security contract"):
        load_harbor_lifecycle_bridge(second.task_dir / "environment")

    _, third, _ = _export_stormwater(tmp_path / "verifier-script")
    test_script = third.task_dir / "tests" / "test.sh"
    test_script.write_text(test_script.read_text(encoding="utf-8") + "echo bypass\n", encoding="utf-8")
    manifest = json.loads(third.manifest_path.read_text(encoding="utf-8"))
    manifest["harbor"]["test_script_sha256"] = hashlib.sha256(test_script.read_bytes()).hexdigest()
    payload = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    third.manifest_path.write_text(payload, encoding="utf-8")
    (third.task_dir / "tests" / "compiled-world-export.json").write_text(payload, encoding="utf-8")

    with pytest.raises(ValueError, match="canonical lifecycle export"):
        load_harbor_lifecycle_bridge(third.task_dir / "environment")


def test_bridge_rejects_coordinated_verifier_runtime_and_manifest_replacement(tmp_path: Path) -> None:
    _, exported, _ = _export_stormwater(tmp_path)
    synthetic_path = "aec_bench/harness/harbor_task_export.py"
    synthetic_source = b"def synthetic_reward_bypass(): return 1.0\n"
    with ZipFile(exported.verifier_runtime_wheel_path, "w") as wheel:
        wheel.writestr(synthetic_path, synthetic_source)
    synthetic_tree = {
        synthetic_path: hashlib.sha256(synthetic_source).hexdigest(),
    }
    synthetic_tree_sha256 = hashlib.sha256(
        json.dumps(
            synthetic_tree,
            allow_nan=False,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    manifest = json.loads(exported.manifest_path.read_text(encoding="utf-8"))
    manifest["verifier"]["runtime_wheel_sha256"] = hashlib.sha256(
        exported.verifier_runtime_wheel_path.read_bytes()
    ).hexdigest()
    manifest["verifier"]["source_tree_sha256"] = synthetic_tree_sha256
    payload = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    exported.manifest_path.write_text(payload, encoding="utf-8")
    (exported.task_dir / "tests" / "compiled-world-export.json").write_text(payload, encoding="utf-8")

    with pytest.raises(ValueError, match="canonical verifier source"):
        load_harbor_lifecycle_bridge(exported.task_dir / "environment")


@pytest.mark.parametrize(
    ("manifest_relative_path", "expected_label"),
    (
        ("compiled-world-export.json", "task-owned bridge manifest"),
        ("tests/compiled-world-export.json", "hidden export manifest"),
    ),
)
def test_bridge_rejects_manifest_replacement_after_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    manifest_relative_path: str,
    expected_label: str,
) -> None:
    _, exported, _ = _export_stormwater(tmp_path)
    manifest_path = exported.task_dir / manifest_relative_path
    validate_source_identity = harbor_bridge_module.validate_source_identity

    def replace_manifest_after_source_validation(
        *,
        source: dict[str, Any],
        envelope: CompiledLifecycleEnvelope,
    ) -> None:
        validate_source_identity(source=source, envelope=envelope)
        manifest_path.write_text("{}\n", encoding="utf-8")

    monkeypatch.setattr(
        harbor_bridge_module,
        "validate_source_identity",
        replace_manifest_after_source_validation,
    )

    with pytest.raises(ValueError, match=rf"{expected_label} changed after it was read"):
        load_harbor_lifecycle_bridge(exported.task_dir / "environment")


def test_bridge_rejects_runtime_wheel_replacement_after_canonical_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, exported, _ = _export_stormwater(tmp_path)
    validate_runtime_wheel = harbor_bridge_module.validate_verifier_runtime_wheel

    def replace_runtime_after_validation(
        runtime_wheel: RegularFileSnapshot,
        verifier: dict[str, Any],
    ) -> None:
        validate_runtime_wheel(runtime_wheel, verifier)
        exported.verifier_runtime_wheel_path.write_bytes(b"replaced after validation")

    monkeypatch.setattr(
        harbor_bridge_module,
        "validate_verifier_runtime_wheel",
        replace_runtime_after_validation,
    )

    with pytest.raises(ValueError, match="verifier runtime changed after it was read"):
        load_harbor_lifecycle_bridge(exported.task_dir / "environment")


def test_descriptor_bound_reader_rejects_symlinked_files(tmp_path: Path) -> None:
    target = tmp_path / "target.bin"
    target.write_bytes(b"trusted")
    link = tmp_path / "link.bin"
    link.symlink_to(target)
    read_snapshot = stable_io.read_stable_regular_file

    with pytest.raises(ValueError, match="must not be a symbolic link"):
        read_snapshot(link, label="test file", max_bytes=1024)


def test_descriptor_bound_reader_rejects_replacement_during_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"a" * (1024 * 1024 + 1))
    replacement = tmp_path / "replacement.bin"
    replacement.write_bytes(b"replacement")
    read_snapshot = stable_io.read_stable_regular_file
    original_read = os.read
    replaced = False

    def replace_after_first_chunk(descriptor: int, count: int) -> bytes:
        nonlocal replaced
        chunk = original_read(descriptor, count)
        if not replaced:
            replacement.replace(source)
            replaced = True
        return chunk

    monkeypatch.setattr(os, "read", replace_after_first_chunk)

    with pytest.raises(ValueError, match="changed while it was read"):
        read_snapshot(source, label="test file", max_bytes=2 * 1024 * 1024)


def test_descriptor_bound_reader_rejects_in_place_mutation_before_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"trusted")
    original_open = os.open
    mutated = False

    def mutate_before_open(path: os.PathLike[str] | str, flags: int) -> int:
        nonlocal mutated
        if not mutated:
            source.write_bytes(b"mutated")
            mutated = True
        return original_open(path, flags)

    monkeypatch.setattr(os, "open", mutate_before_open)

    with pytest.raises(ValueError, match="changed before it was read"):
        stable_io.read_stable_regular_file(source, label="test file", max_bytes=1024)


def test_repeated_export_is_content_deterministic(tmp_path: Path) -> None:
    compiled = compile_lifecycle(
        TEMPLATE_ID,
        tmp_path / "compiled",
        variant_id="administrative_no_op",
    )
    project_snapshot = tmp_path / "canonical-project-snapshot"
    (project_snapshot / "src").mkdir(parents=True)
    shutil.copy2(REPO_ROOT / "pyproject.toml", project_snapshot / "pyproject.toml")
    shutil.copytree(
        REPO_ROOT / "src" / "aec_bench",
        project_snapshot / "src" / "aec_bench",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )
    first_from_snapshot = export_compiled_lifecycle_harbor_task(
        compiled,
        tmp_path / "snapshot-tasks" / "civil" / "stormwater-hydraulic-interaction",
        project_root=project_snapshot,
    )
    second = export_compiled_lifecycle_harbor_task(
        compiled,
        tmp_path / "second-tasks" / "civil" / "stormwater-hydraulic-interaction",
        project_root=project_snapshot,
    )

    assert first_from_snapshot.manifest_path.read_bytes() == second.manifest_path.read_bytes()
    assert (
        first_from_snapshot.verifier_runtime_wheel_path.read_bytes() == second.verifier_runtime_wheel_path.read_bytes()
    )
    assert (
        first_from_snapshot.task_dir / "environment" / "context" / "initial" / "hydraulics" / "current-source.json"
    ).read_bytes() == (
        second.task_dir / "environment" / "context" / "initial" / "hydraulics" / "current-source.json"
    ).read_bytes()


def test_independent_verifier_uses_hidden_package_only_after_agent_phase(tmp_path: Path) -> None:
    compiled, exported, _ = _export_stormwater(tmp_path)
    verifier_package = exported.task_dir / "tests" / "compiled-world"
    run_dir = tmp_path / "reference-run"
    environment = lifecycle_smoke_environment(TEMPLATE_ID, verifier_package)
    assert environment is not None
    run_evidence_lifecycle(verifier_package, run_dir, episode_environment=environment)
    write_harbor_lifecycle_attestation(
        run_dir,
        load_harbor_lifecycle_bridge(exported.task_dir / "environment"),
    )

    reward_path = tmp_path / "verifier" / "reward.json"
    details_path = tmp_path / "verifier" / "details.json"
    details = verify_exported_lifecycle_run(
        package_dir=verifier_package,
        run_dir=run_dir,
        envelope_path=exported.task_dir / "tests" / "compiled-world-envelope.json",
        export_manifest_path=exported.task_dir / "tests" / "compiled-world-export.json",
        verifier_runtime_wheel_path=exported.verifier_runtime_wheel_path,
        reward_path=reward_path,
        details_path=details_path,
    )

    assert json.loads(reward_path.read_text(encoding="utf-8")) == {"reward": 1.0}
    assert details["passed"] is True
    assert details["reward_owner"] == "harbor_verifier"
    assert details["source_package_sha256"] == compiled.envelope.package_sha256
    assert details["bridge_manifest_sha256"] == hashlib.sha256(exported.manifest_path.read_bytes()).hexdigest()
    assert details["verification"]["reward"] == 1.0


def test_independent_verifier_rejects_missing_or_drifted_bridge_attestation(tmp_path: Path) -> None:
    _, exported, _ = _export_stormwater(tmp_path)
    verifier_package = exported.task_dir / "tests" / "compiled-world"
    run_dir = tmp_path / "reference-run"
    environment = lifecycle_smoke_environment(TEMPLATE_ID, verifier_package)
    assert environment is not None
    run_evidence_lifecycle(verifier_package, run_dir, episode_environment=environment)

    verifier_arguments = {
        "package_dir": verifier_package,
        "run_dir": run_dir,
        "envelope_path": exported.task_dir / "tests" / "compiled-world-envelope.json",
        "export_manifest_path": exported.task_dir / "tests" / "compiled-world-export.json",
        "verifier_runtime_wheel_path": exported.verifier_runtime_wheel_path,
        "reward_path": tmp_path / "verifier" / "reward.json",
        "details_path": tmp_path / "verifier" / "details.json",
    }
    with pytest.raises(ValueError, match="bridge attestation"):
        verify_exported_lifecycle_run(**verifier_arguments)

    attestation_path = write_harbor_lifecycle_attestation(
        run_dir,
        load_harbor_lifecycle_bridge(exported.task_dir / "environment"),
    )
    attestation = json.loads(attestation_path.read_text(encoding="utf-8"))
    attestation["manifest_sha256"] = "0" * 64
    attestation_path.write_text(json.dumps(attestation, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="bridge attestation does not match"):
        verify_exported_lifecycle_run(**verifier_arguments)


def test_verifier_rejects_hidden_package_or_runtime_drift(tmp_path: Path) -> None:
    _, exported, _ = _export_stormwater(tmp_path)
    package = exported.task_dir / "tests" / "compiled-world"
    (package / "README.md").write_text("tampered\n", encoding="utf-8")

    with pytest.raises(ValueError, match="compiled world envelope does not match"):
        verify_exported_lifecycle_run(
            package_dir=package,
            run_dir=tmp_path / "not-reached",
            envelope_path=exported.task_dir / "tests" / "compiled-world-envelope.json",
            export_manifest_path=exported.task_dir / "tests" / "compiled-world-export.json",
            verifier_runtime_wheel_path=exported.verifier_runtime_wheel_path,
            reward_path=tmp_path / "reward.json",
            details_path=tmp_path / "details.json",
        )


def test_harbor_semantics_reject_unsupported_lifecycle_and_output_contracts() -> None:
    lifecycle = lifecycle_definition(TEMPLATE_ID).lifecycle
    first = lifecycle.checkpoints[0]

    with pytest.raises(ValueError, match="exact JSON submission fields"):
        validate_harbor_lifecycle_semantics(
            lifecycle.model_copy(
                update={
                    "checkpoints": [
                        first.model_copy(update={"allow_additional_submission_fields": True}),
                        *lifecycle.checkpoints[1:],
                    ]
                }
            )
        )

    evidence_request_lifecycle = lifecycle_definition("drainage-model-evidence-lifecycle-review").lifecycle
    evidence_checkpoint = evidence_request_lifecycle.checkpoints[0].model_copy(
        update={
            "conditional_evidence": ConditionalEvidenceSpec(
                request_budget=1,
                requests=(
                    EvidenceRequestSpec(
                        request_id="bounded-request",
                        title="Bounded request",
                        description="Release one declared packet.",
                    ),
                ),
            )
        }
    )
    with pytest.raises(ValueError, match="conditional evidence requests"):
        validate_harbor_lifecycle_semantics(
            evidence_request_lifecycle.model_copy(
                update={"checkpoints": [evidence_checkpoint, *evidence_request_lifecycle.checkpoints[1:]]}
            )
        )

    second = lifecycle.checkpoints[1]
    with pytest.raises(ValueError, match="linear checkpoint graph"):
        validate_harbor_lifecycle_semantics(
            lifecycle.model_copy(
                update={
                    "checkpoints": [
                        first,
                        second.model_copy(update={"depends_on": []}),
                        *lifecycle.checkpoints[2:],
                    ]
                }
            )
        )
