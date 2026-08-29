# ABOUTME: Tests provenance authority handoff at the lifecycle-study retention boundary.
# ABOUTME: Proves live retention preserves recorder capture and recovery uses preregistered identity.

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

import aec_bench.experimentation.lifecycle_studies.retention as retention_runtime
import aec_bench.lifecycles.catalogue as lifecycle_catalogue
from aec_bench.experimentation.lifecycle_studies.ablation import build_lifecycle_ablation_plan
from aec_bench.ledger.writer import run_manifest_path
from aec_bench.lifecycles.compiled import load_compiled_lifecycle
from aec_bench.lifecycles.finalization import finalize_lifecycle_trial
from aec_bench.lifecycles.invocation import LifecycleInvocationPlanExpectation
from tests.support.lifecycle_studies import (
    TEMPLATE_ID,
    recorded_lifecycle_ablation_trial,
    rewrite_canonical_lifecycle_invocation,
)


def test_schema_two_recovery_uses_preregistered_provenance_expectation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, trial, package, run_dir = recorded_lifecycle_ablation_trial(tmp_path)
    plan = build_lifecycle_ablation_plan(manifest)
    authorities: list[LifecycleInvocationPlanExpectation] = []
    core_finalize = finalize_lifecycle_trial

    def capture_authority(**kwargs: Any) -> Any:
        authority = kwargs["source"].recording["finalization_authority"]
        assert isinstance(authority, LifecycleInvocationPlanExpectation)
        authorities.append(authority)
        return core_finalize(**kwargs)

    monkeypatch.setattr(retention_runtime, "finalize_lifecycle_trial", capture_authority)

    retention_runtime.recover_lifecycle_ablation_record(
        manifest=manifest,
        trial=trial,
        package_dir=package,
        run_dir=run_dir,
    )

    assert len(authorities) == 2
    for authority in authorities:
        assert authority.repository.commit == plan.code_provenance.repository_commit
        assert authority.repository.source_inventory_sha256 == plan.code_provenance.source_inventory_sha256
        assert authority.runtime.model_dump(mode="json") == trial.runtime_provenance.model_dump(mode="json")
        assert authority.verifier.registered.qualified_name == plan.code_provenance.verifier_qualified_name
        assert authority.verifier.registered.source_sha256 == plan.code_provenance.verifier_source_sha256
        assert authority.verifier.entrypoint.qualified_name == plan.code_provenance.verifier_entrypoint_qualified_name
        assert authority.verifier.entrypoint.source_sha256 == plan.code_provenance.verifier_entrypoint_source_sha256


def test_schema_two_recovery_rejects_self_consistent_lifecycle_identity_outside_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, trial, package, run_dir = recorded_lifecycle_ablation_trial(tmp_path)
    record_path = retention_runtime.recover_lifecycle_ablation_record(
        manifest=manifest,
        trial=trial,
        package_dir=package,
        run_dir=run_dir,
    )
    record_path.unlink()
    run_manifest_path(
        ledger_root=Path(manifest.ledger_root),
        experiment_id=manifest.experiment_id,
        run_id=trial.trial_id,
    ).unlink()
    snapshot = Path(manifest.ledger_root) / manifest.experiment_id / "_artifacts" / trial.trial_id
    _rewrite_snapshot_as_alternative_compiled_lifecycle(snapshot, monkeypatch)

    with pytest.raises(ValueError, match="planned lifecycle identity"):
        retention_runtime.recover_lifecycle_ablation_record(
            manifest=manifest,
            trial=trial,
            package_dir=package,
            run_dir=run_dir,
        )

    assert not record_path.exists()


def _rewrite_snapshot_as_alternative_compiled_lifecycle(
    snapshot: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    alternative_template_id = "forged-drainage-model-evidence-lifecycle-review"
    alternative_lifecycle_id = "forged-drainage-model-review"
    definition = lifecycle_catalogue._DEFINITIONS[TEMPLATE_ID]
    alternative_metadata = definition.metadata.model_copy(update={"template_id": alternative_template_id})
    alternative_lifecycle = definition.lifecycle.model_copy(update={"lifecycle_id": alternative_lifecycle_id})
    monkeypatch.setitem(
        lifecycle_catalogue._DEFINITIONS,
        alternative_template_id,
        replace(
            definition,
            metadata=alternative_metadata,
            lifecycle=alternative_lifecycle,
        ),
    )
    lifecycle_catalogue.lifecycle_executable_artifact_sha256.cache_clear()

    package = snapshot / "package"
    template_path = package / "template.json"
    template = _read_json(template_path)
    template["template_id"] = alternative_template_id
    _write_json(template_path, template)
    lifecycle_path = package / "lifecycle.json"
    lifecycle = _read_json(lifecycle_path)
    lifecycle["lifecycle_id"] = alternative_lifecycle_id
    _write_json(lifecycle_path, lifecycle)
    compiled = load_compiled_lifecycle(package).envelope

    run = snapshot / "run"
    state_path = run / "state.json"
    state = _read_json(state_path)
    state.update(
        {
            "lifecycle_id": compiled.lifecycle_id,
            "lifecycle_spec_sha256": compiled.lifecycle_spec_sha256,
            "package_sha256": compiled.package_sha256,
        }
    )
    request_hashes: dict[str, str] = {}
    for request_path in sorted(run.glob("episodes/*/*/episode_request.json")):
        request = _read_json(request_path)
        request["episode_id"] = f"{compiled.lifecycle_id}.{request['attempt_id']}"
        request["lifecycle_id"] = compiled.lifecycle_id
        request["lifecycle_spec_sha256"] = compiled.lifecycle_spec_sha256
        request["package_sha256"] = compiled.package_sha256
        _write_json(request_path, request)
        request_hashes[str(request["attempt_id"])] = _sha256(request_path)
        for result_path in (request_path.with_name("episode_result.json"), request_path.parent.parent / "result.json"):
            result = _read_json(result_path)
            result["episode_id"] = str(request["episode_id"])
            _write_json(result_path, result)
    for checkpoint in state["checkpoint_runs"]:
        for attempt in checkpoint["attempts"]:
            attempt["episode_request_sha256"] = request_hashes[str(attempt["attempt_id"])]
    _write_json(state_path, state)

    ledger_path = run / "lifecycle_ledger.jsonl"
    ledger = _read_jsonl(ledger_path)
    for entry in ledger:
        entry["entry_id"] = str(entry["entry_id"]).replace(
            f"{definition.lifecycle.lifecycle_id}:",
            f"{compiled.lifecycle_id}:",
            1,
        )
        entry["process_id"] = compiled.lifecycle_id
        summary = entry.get("summary")
        if isinstance(summary, dict) and summary.get("attempt_id") in request_hashes:
            summary["episode_request_sha256"] = request_hashes[str(summary["attempt_id"])]
    _write_jsonl(ledger_path, ledger)

    invocation_path = next((run / "experiments").glob("*/experiment-manifest.json"))
    verification_paths = (run / "verification.json", invocation_path.with_name("verification.json"))
    for verification_path in verification_paths:
        verification = _read_json(verification_path)
        verification.update(
            {
                "lifecycle_id": compiled.lifecycle_id,
                "template_id": compiled.template_id,
            }
        )
        _write_json(verification_path, verification)

    invocation = _read_json(invocation_path)
    invocation["lifecycle"].update(
        {
            "lifecycle_id": compiled.lifecycle_id,
            "spec_sha256": compiled.lifecycle_spec_sha256,
            "package_sha256": compiled.package_sha256,
            "package_files": {
                path.relative_to(package).as_posix(): _sha256(path)
                for path in sorted(package.rglob("*"))
                if path.is_file()
            },
        }
    )
    invocation["trial"]["compiled"] = compiled.model_dump(mode="json")
    invocation["outputs"]["artifacts"] = {
        relative: _sha256(run / relative) for relative in invocation["outputs"]["artifacts"]
    }
    invocation["outputs"]["verification.json"] = invocation["outputs"]["artifacts"]["verification.json"]
    invocation["outputs"]["metrics.json"] = invocation["outputs"]["artifacts"]["metrics.json"]
    rewrite_canonical_lifecycle_invocation(run, invocation)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _write_jsonl(path: Path, payloads: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(payload, sort_keys=True) + "\n" for payload in payloads), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
