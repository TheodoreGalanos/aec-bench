# ABOUTME: Tests for importing Harbor trial artifacts into Python TrialRecord contracts.
# ABOUTME: Covers a real successful Harbor trial and missing-result failure handling.

import asyncio
import hashlib
import json
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from aec_bench.contracts.agent_output import AgentOutputStatus
from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.contracts.output_completion import (
    OutputCommitAttestation,
    OutputCompletionContract,
    evaluate_output_completion,
)
from aec_bench.contracts.proposal_execution_types import ProposalSessionStatus
from aec_bench.contracts.task_definition import Visibility
from aec_bench.contracts.trial_record import Completeness
from aec_bench.harness.harbor_importing.contracts import HarborImportError
from aec_bench.harness.harbor_importing.core import (
    import_harbor_job,
    import_harbor_trial,
    iter_harbor_trial_dirs,
)
from aec_bench.harness.harbor_importing.proposal_evidence.api import (
    load_proposal_harbor_candidate_failure_evidence,
    load_proposal_harbor_import_evidence,
)
from aec_bench.harness.proposal_runtime_archive import build_proposal_runtime_archive
from aec_bench.harness.proposal_session_config import (
    ProposalSessionHostConfig,
    load_proposal_session_host_inputs,
)
from aec_bench.harness.proposal_session_runtime import (
    build_proposal_session_execution_ref,
    run_proposal_session,
)
from aec_bench.harness.proposal_task_package import (
    ProposalTaskPackageIdentity,
    build_proposal_task_package,
)
from aec_bench.meta_harness.program_proposal_compilation import (
    ProposalRunSessionBundle,
)
from tests.harness.test_proposal_session import (
    _compiled_rlm_commit_bundle,
    _evaluation_coordinate,
    _proposal_model,
    _RecordingProposalEnvironment,
    _sha,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
HARBOR_JOB_DIR = REPO_ROOT / "jobs" / "2026-03-04__17-57-43"
HARBOR_TRIAL_DIR = HARBOR_JOB_DIR / "brisbane-8rm__BHVuXg2"

_skip_no_job_data = pytest.mark.skipif(
    not HARBOR_JOB_DIR.exists(),
    reason="requires archived Harbor job data in jobs/",
)


@_skip_no_job_data
def test_import_harbor_trial_maps_real_successful_trial() -> None:
    record = import_harbor_trial(trial_dir=HARBOR_TRIAL_DIR, repo_root=REPO_ROOT)

    assert record.trial_id == "brisbane-8rm__BHVuXg2"
    assert record.experiment_id == "6834bc30-3801-4a45-a114-afb2d3764b7d"
    assert record.task.task_id == "mechanical/heat-load/audit-office-building/brisbane-8rm"
    assert record.task.task_revision == "b3b51915e026ccfe5393293338afb9360eefdd1d4d17c55760494334241403c5"
    assert record.task.visibility is Visibility.PUBLIC
    assert record.agent.adapter == "tool-loop-anthropic"
    assert record.agent.adapter_revision == "1.0.0"
    assert record.agent.model == "claude-sonnet-4-6"
    assert record.agent.configuration["max_turns"] == 20
    assert record.environment.compute_backend == "modal"
    assert record.environment.runtime_image.endswith(
        "tasks/mechanical/heat-load/audit-office-building/brisbane-8rm/environment/Dockerfile"
    )
    assert record.inputs.system_prompt is not None
    assert record.inputs.input_files is not None
    assert record.outputs.agent_output is not None
    assert record.outputs.agent_output.status is AgentOutputStatus.COMPLETED
    assert record.outputs.raw_output_path is not None
    assert record.outputs.conversation_path is not None
    assert record.outputs.agent_result is not None
    assert "usage_input_tokens" not in record.outputs.agent_result
    assert record.outputs.terminated is True
    assert record.evaluation.reward == pytest.approx(1.0)
    assert record.evaluation.validity.verifier_completed is True
    assert record.evaluation.breakdown is not None
    assert record.evaluation.breakdown["detected"] == 3
    assert record.timing.total_seconds > 0
    assert record.timing.agent_seconds is not None
    assert record.timing.setup_seconds is not None
    assert record.timing.verification_seconds is not None
    assert record.cost is not None
    assert record.cost.model_calls is not None
    assert record.cost.tokens_in == 131093
    assert record.cost.tokens_out == 9283
    assert record.cost.cache_read_tokens == 50835
    assert record.cost.cache_write_tokens == 14707
    assert record.cost.estimated_cost_usd == pytest.approx(0.25379475)
    assert record.completeness is Completeness.PARTIAL


def test_import_current_entrypoint_result_uses_nested_failed_status_despite_nonempty_output(
    tmp_path: Path,
) -> None:
    repo_root, trial_dir = _write_current_entrypoint_trial(tmp_path)

    record = import_harbor_trial(trial_dir=trial_dir, repo_root=repo_root)

    assert record.outputs.agent_output is not None
    assert record.outputs.agent_output.status is AgentOutputStatus.FAILED
    assert record.outputs.agent_output.error_message == "provider exploded after partial output"


def test_import_current_entrypoint_result_preserves_failure_evidence(tmp_path: Path) -> None:
    repo_root, trial_dir = _write_current_entrypoint_trial(tmp_path)

    record = import_harbor_trial(trial_dir=trial_dir, repo_root=repo_root)

    assert record.outputs.agent_result is not None
    assert record.outputs.agent_result["failure_kind"] == "provider_error"
    assert not record.outputs.terminated
    assert not record.outputs.truncated
    assert record.outputs.final_reason == "provider_error"


def test_import_current_entrypoint_result_preserves_typed_completion_reason(tmp_path: Path) -> None:
    repo_root, trial_dir = _write_current_entrypoint_trial(tmp_path)
    agent_result_path = trial_dir / "artifacts" / "agent" / "agent_result.json"
    agent_result = json.loads(agent_result_path.read_text(encoding="utf-8"))
    agent_result.update(
        {
            "completion_reason": "output_contract_satisfied",
            "completion_assistance": {
                "contract_satisfied": True,
                "reminder_sent": True,
                "reminder_turn": 6,
                "explicit_final_turn": 7,
            },
        }
    )
    agent_result_path.write_text(json.dumps(agent_result), encoding="utf-8")

    record = import_harbor_trial(trial_dir=trial_dir, repo_root=repo_root)

    assert record.outputs.agent_result is not None
    assert record.outputs.agent_result["completion_reason"] == "output_contract_satisfied"
    assert record.outputs.terminated
    assert not record.outputs.truncated
    assert record.outputs.final_reason == "output_contract_satisfied"
    assert record.outputs.agent_result["completion_assistance"] == {
        "contract_satisfied": True,
        "reminder_sent": True,
        "reminder_turn": 6,
        "explicit_final_turn": 7,
    }


def test_import_current_entrypoint_result_preserves_verified_output_commit(
    tmp_path: Path,
) -> None:
    repo_root, trial_dir, attestation = _write_current_entrypoint_output_commit_trial(tmp_path)

    record = import_harbor_trial(trial_dir=trial_dir, repo_root=repo_root)

    assert record.outputs.agent_result is not None
    assert record.outputs.agent_result["completion_reason"] == "output_contract_committed"
    assert record.outputs.agent_result["completion_commit"] == attestation.model_dump(mode="json")


def test_import_current_entrypoint_result_rejects_mutated_output_commit_artifact(
    tmp_path: Path,
) -> None:
    repo_root, trial_dir, _attestation = _write_current_entrypoint_output_commit_trial(tmp_path)
    (trial_dir / "artifacts" / "agent" / "output.md").write_text(
        "artifact mutated after the committed bytes were recorded\n",
        encoding="utf-8",
    )

    with pytest.raises(
        HarborImportError,
        match="output commit.*SHA-256.*artifact",
    ):
        import_harbor_trial(trial_dir=trial_dir, repo_root=repo_root)


def test_import_current_entrypoint_result_rejects_output_commit_size_mismatch(
    tmp_path: Path,
) -> None:
    repo_root, trial_dir, _attestation = _write_current_entrypoint_output_commit_trial(tmp_path)
    _rewrite_output_commit(
        trial_dir,
        lambda payload: payload.update({"output_size_bytes": int(payload["output_size_bytes"]) + 1}),
    )

    with pytest.raises(HarborImportError, match="output commit byte size"):
        import_harbor_trial(trial_dir=trial_dir, repo_root=repo_root)


def test_import_current_entrypoint_result_rejects_output_commit_contract_mismatch(
    tmp_path: Path,
) -> None:
    repo_root, trial_dir, _attestation = _write_current_entrypoint_output_commit_trial(tmp_path)
    _rewrite_output_commit(
        trial_dir,
        lambda payload: payload.update({"completion_contract_sha256": "c" * 64}),
    )

    with pytest.raises(HarborImportError, match="output commit contract SHA-256"):
        import_harbor_trial(trial_dir=trial_dir, repo_root=repo_root)


def test_import_current_entrypoint_result_rejects_output_commit_evaluation_mismatch(
    tmp_path: Path,
) -> None:
    repo_root, trial_dir, _attestation = _write_current_entrypoint_output_commit_trial(tmp_path)

    def _change_evaluation(payload: dict[str, object]) -> None:
        raw_evaluation = payload["completion_evaluation"]
        assert isinstance(raw_evaluation, dict)
        evaluation = dict(raw_evaluation)
        evaluation["present_top_level_keys"] = ["different"]
        payload["completion_evaluation"] = evaluation

    _rewrite_output_commit(trial_dir, _change_evaluation)

    with pytest.raises(HarborImportError, match="output commit structural evaluation"):
        import_harbor_trial(trial_dir=trial_dir, repo_root=repo_root)


def test_import_current_entrypoint_result_rejects_missing_output_commit_artifact(
    tmp_path: Path,
) -> None:
    repo_root, trial_dir, _attestation = _write_current_entrypoint_output_commit_trial(tmp_path)
    (trial_dir / "artifacts" / "agent" / "output.md").unlink()

    with pytest.raises(HarborImportError, match="output commit artifact is missing"):
        import_harbor_trial(trial_dir=trial_dir, repo_root=repo_root)


def test_import_current_entrypoint_result_rejects_symlinked_output_commit_artifact(
    tmp_path: Path,
) -> None:
    repo_root, trial_dir, _attestation = _write_current_entrypoint_output_commit_trial(tmp_path)
    output_path = trial_dir / "artifacts" / "agent" / "output.md"
    target_path = trial_dir / "artifacts" / "agent" / "output-target.md"
    target_path.write_bytes(output_path.read_bytes())
    output_path.unlink()
    output_path.symlink_to(target_path)

    with pytest.raises(HarborImportError, match="non-symlink regular file"):
        import_harbor_trial(trial_dir=trial_dir, repo_root=repo_root)


def test_import_current_entrypoint_result_rejects_metadata_only_output_commit_claim(
    tmp_path: Path,
) -> None:
    repo_root, trial_dir = _write_current_entrypoint_trial(tmp_path)
    attestation = _install_output_commit_contract(repo_root, trial_dir, commit_turn=7)
    harbor_result_path = trial_dir / "result.json"
    harbor_result = json.loads(harbor_result_path.read_text(encoding="utf-8"))
    harbor_result["agent_result"]["metadata"].update(
        {
            "completion_reason": "output_contract_committed",
            "completion_commit": attestation.model_dump(mode="json"),
        }
    )
    harbor_result_path.write_text(json.dumps(harbor_result), encoding="utf-8")

    with pytest.raises(HarborImportError, match="metadata-only output commit claim"):
        import_harbor_trial(trial_dir=trial_dir, repo_root=repo_root)


def test_import_includes_task_output_completion_contract_as_hashed_input(tmp_path: Path) -> None:
    repo_root, trial_dir = _write_current_entrypoint_trial(tmp_path)
    contract_path = (
        repo_root / "tasks" / "civil" / "calculation" / "entrypoint-import" / "environment" / "output_contract.json"
    )
    contract_path.parent.mkdir(parents=True)
    contract_bytes = b'{"schema_version":"aecbench.output-completion-contract.v1"}\n'
    contract_path.write_bytes(contract_bytes)

    record = import_harbor_trial(trial_dir=trial_dir, repo_root=repo_root)

    assert record.inputs.input_files is not None
    reference = next(
        item for item in record.inputs.input_files if item.path.endswith("environment/output_contract.json")
    )
    assert reference.source == "output_completion_contract"
    assert reference.hash == hashlib.sha256(contract_bytes).hexdigest()


def test_import_current_entrypoint_result_preserves_typed_stop_and_turn_evidence(tmp_path: Path) -> None:
    repo_root, trial_dir = _write_current_entrypoint_trial(tmp_path)
    agent_result_path = trial_dir / "artifacts" / "agent" / "agent_result.json"
    agent_result = json.loads(agent_result_path.read_text(encoding="utf-8"))
    agent_result.update(
        {
            "failure_kind": "turn_limit_reached",
            "stop_reason": "iteration_cap",
            "provider_error": "Iteration cap reached (7/7)",
        }
    )
    agent_result_path.write_text(json.dumps(agent_result), encoding="utf-8")
    harbor_result_path = trial_dir / "result.json"
    harbor_result = json.loads(harbor_result_path.read_text(encoding="utf-8"))
    harbor_result["agent_result"]["metadata"].update({"stop_reason": "token_budget", "turns_used": 3, "max_turns": 9})
    harbor_result_path.write_text(json.dumps(harbor_result), encoding="utf-8")

    record = import_harbor_trial(trial_dir=trial_dir, repo_root=repo_root)

    assert record.outputs.agent_result is not None
    assert record.outputs.agent_result["stop_reason"] == "iteration_cap"
    assert record.outputs.agent_result["turns_used"] == 7
    assert record.outputs.agent_result["max_turns"] == 7
    assert not record.outputs.terminated
    assert record.outputs.truncated
    assert record.outputs.final_reason == "iteration_cap"


def test_import_turn_limited_output_accepts_positive_verifier_attestation(tmp_path: Path) -> None:
    repo_root, trial_dir = _write_current_entrypoint_trial(tmp_path)
    agent_result_path = trial_dir / "artifacts" / "agent" / "agent_result.json"
    agent_result = json.loads(agent_result_path.read_text(encoding="utf-8"))
    agent_result.update(
        {
            "agent_output": {
                "status": "partial",
                "output_path": "/workspace/output.md",
                "output_format": "markdown",
                "error_message": "Iteration cap reached (32/32)",
            },
            "failure_kind": "turn_limit_reached",
            "stop_reason": "iteration_cap",
            "turns_used": 32,
            "max_turns": 32,
            "provider_error": "Iteration cap reached (32/32)",
        }
    )
    agent_result_path.write_text(json.dumps(agent_result), encoding="utf-8")
    (trial_dir / "verifier" / "reward.json").write_text('{"reward": 0.92}\n', encoding="utf-8")
    (trial_dir / "verifier" / "details.json").write_text(
        json.dumps({"gates": {"matrix": {"score": 0.25}}}),
        encoding="utf-8",
    )

    record = import_harbor_trial(trial_dir=trial_dir, repo_root=repo_root)

    assert record.outputs.agent_output is not None
    assert record.outputs.agent_output.status is AgentOutputStatus.PARTIAL
    assert record.evaluation.reward == pytest.approx(0.92)
    assert record.evaluation.validity.output_parseable is True
    assert record.evaluation.validity.schema_valid is True
    assert record.evaluation.validity.verifier_completed is True


def test_import_current_entrypoint_result_preserves_provider_error(tmp_path: Path) -> None:
    repo_root, trial_dir = _write_current_entrypoint_trial(tmp_path)

    record = import_harbor_trial(trial_dir=trial_dir, repo_root=repo_root)

    assert record.outputs.agent_result is not None
    assert record.outputs.agent_result["provider_error"] == "provider exploded after partial output"


def test_import_current_entrypoint_result_uses_executed_adapter_identity(
    tmp_path: Path,
) -> None:
    repo_root, trial_dir = _write_current_entrypoint_trial(tmp_path)

    record = import_harbor_trial(trial_dir=trial_dir, repo_root=repo_root)

    assert record.agent.adapter == "tool_loop"
    assert record.agent.model == "claude-sonnet-4-20250514"


def test_import_current_entrypoint_result_preserves_effective_configuration(
    tmp_path: Path,
) -> None:
    repo_root, trial_dir = _write_current_entrypoint_trial(tmp_path)

    record = import_harbor_trial(trial_dir=trial_dir, repo_root=repo_root)

    assert record.agent.configuration["max_turns"] == 7
    assert record.agent.configuration["max_tool_calls"] == 9
    assert record.agent.configuration["tool_policy"] == "allowlisted"


def test_import_current_entrypoint_result_normalizes_all_usage_into_cost(tmp_path: Path) -> None:
    repo_root, trial_dir = _write_current_entrypoint_trial(tmp_path)

    record = import_harbor_trial(trial_dir=trial_dir, repo_root=repo_root)

    assert record.outputs.agent_result is not None
    assert not any(key.startswith("usage_") for key in record.outputs.agent_result)
    assert record.cost is not None
    assert record.cost.tokens_in == 101
    assert record.cost.tokens_out == 202
    assert record.cost.cache_read_tokens == 33
    assert record.cost.cache_write_tokens == 44
    assert record.cost.advisor_calls == 2
    assert record.cost.advisor_input_tokens == 55
    assert record.cost.advisor_output_tokens == 66


def test_import_lifecycle_bridge_uses_runtime_lifecycle_status_without_flat_output(
    tmp_path: Path,
) -> None:
    repo_root, trial_dir = _write_lifecycle_bridge_trial(tmp_path)

    record = import_harbor_trial(trial_dir=trial_dir, repo_root=repo_root)

    assert record.outputs.agent_output is not None
    assert record.outputs.agent_output.status is AgentOutputStatus.COMPLETED
    assert record.outputs.agent_result is not None
    assert record.outputs.agent_result["lifecycle_status"] == "complete"
    assert record.outputs.agent_result["reward_owner"] == "harbor_verifier"
    assert record.outputs.agent_result["bridge_mode"] == "host_evidence_lifecycle.v1"


def test_import_harbor_trial_derives_morph_backend_from_import_path_environment(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    task_dir = repo_root / "tasks" / "mechanical" / "heat-load" / "alpha"
    trial_dir = repo_root / "jobs" / "job-001" / "trial-morph"
    (task_dir / "tests").mkdir(parents=True)
    (trial_dir / "artifacts" / "agent").mkdir(parents=True)
    (trial_dir / "verifier").mkdir(parents=True)
    (task_dir / "instruction.md").write_text(
        "Write your answer to /workspace/output.md.\n",
        encoding="utf-8",
    )
    (task_dir / "task.toml").write_text(
        '[metadata]\nvisibility = "public"\n\n[agent]\ntimeout_sec = 60\n',
        encoding="utf-8",
    )
    (task_dir / "tests" / "test.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (trial_dir / "artifacts" / "agent" / "output.md").write_text("answer\n", encoding="utf-8")
    (trial_dir / "verifier" / "reward.json").write_text('{"reward": 1.0}\n', encoding="utf-8")
    (trial_dir / "result.json").write_text(
        """
{
  "trial_name": "trial-morph",
  "task_checksum": "sha256-task",
  "config": {
    "task": {"path": "tasks/mechanical/heat-load/alpha"},
    "agent": {"name": "entrypoint", "model_name": "test-model", "kwargs": {"adapter": "tool_loop"}},
    "environment": {
      "type": null,
      "import_path": "aec_bench.providers.morph_harbor:MorphHarborEnvironment",
      "kwargs": {"compute_backend": "morph"}
    },
    "job_id": "experiment-001"
  },
  "agent_info": {"name": "entrypoint", "version": "1.0.0"},
  "agent_result": {},
  "started_at": "2026-06-05T00:00:00Z",
  "finished_at": "2026-06-05T00:00:01Z"
}
""".strip(),
        encoding="utf-8",
    )

    record = import_harbor_trial(trial_dir=trial_dir, repo_root=repo_root)

    assert record.environment.compute_backend == "morph"


def test_import_harbor_trial_includes_reviewer_summary_in_breakdown(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    task_dir = repo_root / "tasks" / "mechanical" / "heat-load" / "alpha"
    trial_dir = repo_root / "jobs" / "job-001" / "trial-reviewed"
    (task_dir / "tests").mkdir(parents=True)
    (trial_dir / "artifacts" / "agent").mkdir(parents=True)
    (trial_dir / "verifier").mkdir(parents=True)
    (trial_dir / "reviewer").mkdir(parents=True)
    (task_dir / "instruction.md").write_text(
        "Write your answer to /workspace/output.md.\n",
        encoding="utf-8",
    )
    (task_dir / "task.toml").write_text(
        '[metadata]\nvisibility = "public"\n\n[agent]\ntimeout_sec = 60\n',
        encoding="utf-8",
    )
    (task_dir / "tests" / "test.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (trial_dir / "artifacts" / "agent" / "output.md").write_text("answer\n", encoding="utf-8")
    (trial_dir / "verifier" / "reward.json").write_text('{"reward": 1.0}\n', encoding="utf-8")
    (trial_dir / "reviewer" / "summary.json").write_text(
        json.dumps({"status": "complete", "event_candidates": ["verifier_language_gap"]}),
        encoding="utf-8",
    )
    (trial_dir / "result.json").write_text(
        """
{
  "trial_name": "trial-reviewed",
  "task_checksum": "sha256-task",
  "config": {
    "task": {"path": "tasks/mechanical/heat-load/alpha"},
    "agent": {"name": "entrypoint", "model_name": "test-model", "kwargs": {"adapter": "tool_loop"}},
    "environment": {"type": "modal", "kwargs": {}},
    "job_id": "experiment-001"
  },
  "agent_info": {"name": "entrypoint", "version": "1.0.0"},
  "agent_result": {},
  "started_at": "2026-06-05T00:00:00Z",
  "finished_at": "2026-06-05T00:00:01Z"
}
""".strip(),
        encoding="utf-8",
    )

    record = import_harbor_trial(trial_dir=trial_dir, repo_root=repo_root)

    assert record.evaluation.breakdown is not None
    assert record.evaluation.breakdown["llm_reviewer"]["status"] == "complete"


def test_import_proposal_session_requires_complete_isolation_evidence(
    tmp_path: Path,
) -> None:
    repo_root, trial_dir, expected = _write_proposal_harbor_trial(tmp_path)

    record = import_harbor_trial(trial_dir=trial_dir, repo_root=repo_root)
    evidence = load_proposal_harbor_import_evidence(
        trial_dir=trial_dir,
        repo_root=repo_root,
    )

    assert evidence is not None
    assert evidence.session_id == expected["session_id"]
    assert evidence.candidate_id == expected["candidate_id"]
    assert evidence.candidate_artifact_sha256 == expected["candidate_artifact_sha256"]
    assert evidence.proposal_graph_sha256 == expected["proposal_graph_sha256"]
    assert evidence.compilation_sha256 == expected["compilation_sha256"]
    assert evidence.session_plan_sha256 == expected["session_plan_sha256"]
    assert record.agent.adapter == "proposal_session"
    assert record.outputs.agent_output is not None
    assert record.outputs.agent_output.status is AgentOutputStatus.COMPLETED
    assert record.outputs.artifacts is not None
    kinds = {artifact.kind for artifact in record.outputs.artifacts}
    assert {
        "proposal_session_receipt",
        "proposal_verifier_rotation_receipt",
        "proposal_artifact_seal_manifest",
        "proposal_cleanup_receipt",
        "proposal_task_package_manifest",
        "proposal_runtime_archive",
        "proposal_session_bundle",
    }.issubset(kinds)
    serialized_configuration = json.dumps(record.agent.configuration, sort_keys=True)
    assert "bundle_path" not in serialized_configuration
    assert "runtime_archive_path" not in serialized_configuration
    assert str(tmp_path) not in serialized_configuration


@pytest.mark.parametrize(
    ("relative_path", "error"),
    [
        (
            "agent/proposal-session/session-receipt.json",
            "proposal session receipt",
        ),
        (
            "proposal-morph-boundary/verifier-rotation.json",
            "verifier rotation",
        ),
        (
            "proposal-morph-boundary/seal-manifest.json",
            "artifact seal",
        ),
        (
            "proposal-morph-boundary/proposal-cleanup.json",
            "cleanup",
        ),
    ],
)
def test_import_proposal_session_rejects_missing_required_evidence(
    tmp_path: Path,
    relative_path: str,
    error: str,
) -> None:
    repo_root, trial_dir, _ = _write_proposal_harbor_trial(tmp_path)
    (trial_dir / relative_path).unlink()

    with pytest.raises(HarborImportError, match=error):
        import_harbor_trial(trial_dir=trial_dir, repo_root=repo_root)


@pytest.mark.parametrize(
    "tamper",
    ["collected_session", "sealed_artifact", "rotation_lineage", "metadata_lineage"],
)
def test_import_proposal_session_rejects_physical_or_causal_lineage_tamper(
    tmp_path: Path,
    tamper: str,
) -> None:
    repo_root, trial_dir, _ = _write_proposal_harbor_trial(tmp_path)
    if tamper == "collected_session":
        target = trial_dir / "agent" / "proposal-session" / "session-receipt.json"
        target.write_bytes(target.read_bytes() + b" ")
    elif tamper == "sealed_artifact":
        target = trial_dir / "proposal-morph-boundary" / "sealed-artifacts" / "workspace" / "output.md"
        target.write_bytes(target.read_bytes() + b"tamper")
    elif tamper == "rotation_lineage":
        target = trial_dir / "proposal-morph-boundary" / "verifier-rotation.json"
        payload = json.loads(target.read_text(encoding="utf-8"))
        payload["candidate_container_identity"] = "container.unrelated"
        payload.pop("content_sha256")
        _write_content_addressed_json(target, payload)
    else:
        target = trial_dir / "result.json"
        payload = json.loads(target.read_text(encoding="utf-8"))
        payload["agent_result"]["metadata"]["candidate_id"] = "candidate.unrelated"
        target.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(HarborImportError):
        import_harbor_trial(trial_dir=trial_dir, repo_root=repo_root)


def test_import_proposal_session_rejects_evidence_through_symlinked_parent(
    tmp_path: Path,
) -> None:
    repo_root, trial_dir, _ = _write_proposal_harbor_trial(tmp_path)
    outside_agent = tmp_path / "outside-agent"
    (trial_dir / "agent").rename(outside_agent)
    (trial_dir / "agent").symlink_to(outside_agent, target_is_directory=True)

    with pytest.raises(HarborImportError, match="escapes the Harbor trial boundary"):
        import_harbor_trial(trial_dir=trial_dir, repo_root=repo_root)


def test_import_candidate_failure_never_fabricates_trial_record(
    tmp_path: Path,
) -> None:
    repo_root, trial_dir, expected = _write_proposal_harbor_trial(
        tmp_path,
        candidate_failure=True,
    )

    assert expected["trial_record_permitted"] is False
    with pytest.raises(HarborImportError, match="does not permit TrialRecord"):
        import_harbor_trial(trial_dir=trial_dir, repo_root=repo_root)


def test_load_proposal_candidate_failure_evidence_reconciles_isolation_boundary(
    tmp_path: Path,
) -> None:
    repo_root, trial_dir, expected = _write_proposal_harbor_trial(
        tmp_path,
        candidate_failure=True,
    )

    evidence = load_proposal_harbor_candidate_failure_evidence(
        trial_dir=trial_dir,
        repo_root=repo_root,
    )

    assert evidence is not None
    assert evidence.session_receipt.status is ProposalSessionStatus.CANDIDATE_FAILURE
    assert evidence.session_receipt.trial_record_permitted is False
    assert evidence.session_id == expected["session_id"]
    assert evidence.candidate_id == expected["candidate_id"]
    assert {
        "proposal_session_receipt",
        "proposal_verifier_rotation_receipt",
        "proposal_artifact_seal_manifest",
        "proposal_cleanup_receipt",
    }.issubset({artifact.kind for artifact in evidence.artifacts})


def test_load_proposal_candidate_failure_evidence_rejects_sealed_tamper(
    tmp_path: Path,
) -> None:
    repo_root, trial_dir, _ = _write_proposal_harbor_trial(
        tmp_path,
        candidate_failure=True,
    )
    target = (
        trial_dir
        / "proposal-morph-boundary"
        / "sealed-artifacts"
        / "workspace"
        / "proposal-session"
        / "session-receipt.json"
    )
    target.write_bytes(target.read_bytes() + b"tamper")

    with pytest.raises(HarborImportError, match="changed after capture"):
        load_proposal_harbor_candidate_failure_evidence(
            trial_dir=trial_dir,
            repo_root=repo_root,
        )


@_skip_no_job_data
def test_import_harbor_trial_rejects_missing_result_json(tmp_path: Path) -> None:
    with pytest.raises(HarborImportError, match="missing Harbor result artifact"):
        import_harbor_trial(trial_dir=tmp_path, repo_root=REPO_ROOT)


@_skip_no_job_data
def test_iter_harbor_trial_dirs_finds_only_trial_directories() -> None:
    trial_dirs = iter_harbor_trial_dirs(job_dir=HARBOR_JOB_DIR)

    assert len(trial_dirs) == 60
    assert trial_dirs[0].name == "adelaide-15rm__EUcepGa"
    assert trial_dirs[-1].name == "townsville-8rm__WBreAVv"


@_skip_no_job_data
def test_import_harbor_job_maps_real_job_directory() -> None:
    records = import_harbor_job(job_dir=HARBOR_JOB_DIR, repo_root=REPO_ROOT)

    assert len(records) == 60
    assert records[0].experiment_id == "6834bc30-3801-4a45-a114-afb2d3764b7d"
    assert records[0].task.task_id == "mechanical/heat-load/audit-mixed-use/adelaide-15rm"
    assert records[-1].task.task_id == "mechanical/heat-load/audit-office-building/townsville-8rm"
    assert all(record.environment.compute_backend == "modal" for record in records)


def _write_current_entrypoint_trial(tmp_path: Path) -> tuple[Path, Path]:
    repo_root, task_dir, trial_dir = _write_task_and_trial_roots(tmp_path, trial_name="trial-entrypoint-current")
    (task_dir / "instruction.md").write_text(
        "Write your answer to /workspace/output.md.\n",
        encoding="utf-8",
    )
    (trial_dir / "artifacts" / "agent" / "output.md").write_text(
        "partial but nonempty answer\n",
        encoding="utf-8",
    )
    current_result = {
        "adapter_name": "tool_loop",
        "resolved_model": "claude-sonnet-4-20250514",
        "configuration_record": {
            "max_turns": 7,
            "max_tool_calls": 9,
            "tool_policy": "allowlisted",
        },
        "agent_output": {
            "status": "failed",
            "output_path": "/workspace/output.md",
            "output_format": "markdown",
            "error_message": "provider exploded after partial output",
        },
        "transcript": [],
        "failure_kind": "provider_error",
        "stop_reason": None,
        "turns_used": 7,
        "max_turns": 7,
        "raw_output_text": "partial but nonempty answer",
        "provider_error": "provider exploded after partial output",
        "usage_input_tokens": 101,
        "usage_output_tokens": 202,
        "usage_cache_read_tokens": 33,
        "usage_cache_write_tokens": 44,
        "usage_advisor_calls": 2,
        "usage_advisor_input_tokens": 55,
        "usage_advisor_output_tokens": 66,
        "runtime_execution_attestation": {"schema_version": "aecbench.runtime-execution-attestation.v1"},
    }
    (trial_dir / "artifacts" / "agent" / "agent_result.json").write_text(
        json.dumps(current_result),
        encoding="utf-8",
    )
    _write_harbor_result(
        trial_dir,
        trial_name="trial-entrypoint-current",
        metadata={
            "adapter_name": "tool_loop",
            "resolved_model": "claude-sonnet-4-20250514",
            "model": "claude-sonnet-4-20250514",
            "runtime_execution_attestation": current_result["runtime_execution_attestation"],
            "exec_return_code": 0,
        },
        input_tokens=101,
        output_tokens=202,
    )
    return repo_root, trial_dir


def _write_current_entrypoint_output_commit_trial(
    tmp_path: Path,
) -> tuple[Path, Path, OutputCommitAttestation]:
    repo_root, trial_dir = _write_current_entrypoint_trial(tmp_path)
    attestation = _install_output_commit_contract(repo_root, trial_dir, commit_turn=7)
    agent_result_path = trial_dir / "artifacts" / "agent" / "agent_result.json"
    agent_result = json.loads(agent_result_path.read_text(encoding="utf-8"))
    agent_result.update(
        {
            "agent_output": {
                "status": "completed",
                "output_path": "/workspace/output.md",
                "output_format": "markdown",
                "error_message": None,
            },
            "failure_kind": None,
            "stop_reason": None,
            "completion_reason": "output_contract_committed",
            "completion_assistance": None,
            "completion_commit": attestation.model_dump(mode="json"),
            "provider_error": None,
        }
    )
    agent_result_path.write_text(json.dumps(agent_result), encoding="utf-8")
    return repo_root, trial_dir, attestation


def _install_output_commit_contract(
    repo_root: Path,
    trial_dir: Path,
    *,
    commit_turn: int,
) -> OutputCommitAttestation:
    output_path = trial_dir / "artifacts" / "agent" / "output.md"
    output_path.write_text(
        '# Review\n\n```json\n{"summary": {"status": "complete"}}\n```\n',
        encoding="utf-8",
    )
    contract = OutputCompletionContract(
        schema_version="aecbench.output-completion-contract.v1",
        output_path="/workspace/output.md",
        format="markdown_final_fenced_json",
        required_top_level_keys=("summary",),
        require_single_final_json_block=True,
    )
    contract_path = (
        repo_root / "tasks" / "civil" / "calculation" / "entrypoint-import" / "environment" / "output_contract.json"
    )
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    contract_path.write_text(contract.model_dump_json(), encoding="utf-8")
    output_bytes = output_path.read_bytes()
    evaluation = evaluate_output_completion(contract, output_bytes.decode("utf-8"))
    return OutputCommitAttestation(
        schema_version="aecbench.output-commit-attestation.v1",
        mechanism="agent_explicit_output_commit",
        output_path="/workspace/output.md",
        output_sha256=hashlib.sha256(output_bytes).hexdigest(),
        output_size_bytes=len(output_bytes),
        completion_contract_sha256=canonical_content_sha256(contract.model_dump(mode="json")),
        completion_evaluation=evaluation,
        initial_output_sha256=None,
        commit_turn=commit_turn,
    )


def _rewrite_output_commit(
    trial_dir: Path,
    mutate: Callable[[dict[str, object]], None],
) -> None:
    agent_result_path = trial_dir / "artifacts" / "agent" / "agent_result.json"
    agent_result = json.loads(agent_result_path.read_text(encoding="utf-8"))
    completion_commit = dict(agent_result["completion_commit"])
    mutate(completion_commit)
    completion_commit.pop("content_sha256", None)
    agent_result["completion_commit"] = completion_commit
    agent_result_path.write_text(json.dumps(agent_result), encoding="utf-8")


def _write_lifecycle_bridge_trial(tmp_path: Path) -> tuple[Path, Path]:
    repo_root, task_dir, trial_dir = _write_task_and_trial_roots(tmp_path, trial_name="trial-lifecycle-bridge")
    (task_dir / "instruction.md").write_text(
        "Preserve the completed lifecycle run at /workspace/lifecycle-run.\n",
        encoding="utf-8",
    )
    lifecycle_run = trial_dir / "artifacts" / "agent" / "lifecycle-run"
    lifecycle_run.mkdir(parents=True)
    (lifecycle_run / "state.json").write_text(
        json.dumps({"status": "complete"}),
        encoding="utf-8",
    )
    (trial_dir / "verifier" / "reward.json").write_text('{"reward": 1.0}\n', encoding="utf-8")
    (trial_dir / "verifier" / "details.json").write_text(
        json.dumps(
            {
                "passed": True,
                "reward_owner": "harbor_verifier",
                "verification": {"passed": True, "reward": 1.0},
            }
        ),
        encoding="utf-8",
    )
    _write_harbor_result(
        trial_dir,
        trial_name="trial-lifecycle-bridge",
        metadata={
            "adapter_name": "tool_loop",
            "bridge_mode": "host_evidence_lifecycle.v1",
            "bridge_manifest_sha256": "a" * 64,
            "lifecycle_status": "complete",
            "model": "claude-sonnet-4-20250514",
            "reward_owner": "harbor_verifier",
        },
        input_tokens=303,
        output_tokens=404,
        agent_kwargs={
            "adapter": "tool_loop",
            "lifecycle_bridge": "host_evidence_lifecycle.v1",
            "max_turns": 60,
        },
    )
    return repo_root, trial_dir


def _write_task_and_trial_roots(
    tmp_path: Path,
    *,
    trial_name: str,
) -> tuple[Path, Path, Path]:
    repo_root = tmp_path / "repo"
    task_dir = repo_root / "tasks" / "civil" / "calculation" / "entrypoint-import"
    trial_dir = repo_root / "jobs" / "job-001" / trial_name
    (task_dir / "tests").mkdir(parents=True)
    (trial_dir / "artifacts" / "agent").mkdir(parents=True)
    (trial_dir / "verifier").mkdir(parents=True)
    (task_dir / "task.toml").write_text(
        '[metadata]\nvisibility = "public"\n\n[agent]\ntimeout_sec = 60\n',
        encoding="utf-8",
    )
    (task_dir / "tests" / "test.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    return repo_root, task_dir, trial_dir


def _write_harbor_result(
    trial_dir: Path,
    *,
    trial_name: str,
    metadata: dict[str, object],
    input_tokens: int,
    output_tokens: int,
    agent_kwargs: dict[str, object] | None = None,
) -> None:
    payload = {
        "trial_name": trial_name,
        "task_checksum": "sha256-task",
        "config": {
            "task": {"path": "tasks/civil/calculation/entrypoint-import"},
            "agent": {
                "name": "entrypoint",
                "model_name": "configured-model-alias",
                "kwargs": agent_kwargs or {"adapter": "tool_loop"},
            },
            "environment": {"type": "modal", "kwargs": {}},
            "job_id": "experiment-001",
        },
        "agent_info": {"name": "entrypoint", "version": "1.0.0"},
        "agent_result": {
            "n_input_tokens": input_tokens,
            "n_output_tokens": output_tokens,
            "metadata": metadata,
        },
        "started_at": "2026-07-22T00:00:00Z",
        "finished_at": "2026-07-22T00:00:01Z",
    }
    (trial_dir / "result.json").write_text(json.dumps(payload), encoding="utf-8")


def _write_proposal_harbor_trial(
    tmp_path: Path,
    *,
    candidate_failure: bool = False,
) -> tuple[Path, Path, dict[str, object]]:
    repo_root = tmp_path / "repo"
    bundle, source_task_root = _compiled_rlm_commit_bundle(tmp_path / "compiled")
    bundle_path = tmp_path / "proposal-session-bundle.json"
    bundle_path.write_text(bundle.model_dump_json(), encoding="utf-8")
    runtime = build_proposal_runtime_archive(
        package_root=REPO_ROOT / "src" / "aec_bench",
        archive_path=tmp_path / "proposal-runtime.tar.gz",
    )
    output_contract = OutputCompletionContract.model_validate(
        bundle.compilation.proposal_freeze.problem_view.output_contract,
    )
    derived_task = repo_root / "tasks" / bundle.task_snapshot.task_id
    derived = build_proposal_task_package(
        source_task_dir=source_task_root,
        destination_task_dir=derived_task,
        identity=ProposalTaskPackageIdentity(
            task_id=bundle.task_snapshot.task_id,
            task_revision=bundle.task_snapshot.definition_sha256,
            source_task_package_sha256=bundle.task_snapshot.package_sha256,
            problem_view_sha256=bundle.compilation.proposal_freeze.problem_view.content_sha256,
            output_contract_sha256=(bundle.compilation.proposal_graph.finalizer.output_completion_contract_sha256),
            visibility=Visibility.PUBLIC,
        ),
        output_contract=output_contract,
        verifier_asset_paths=("tests/test.sh",),
    )
    host_config = ProposalSessionHostConfig(
        bundle_path=str(bundle_path.resolve()),
        bundle_file_sha256=hashlib.sha256(bundle_path.read_bytes()).hexdigest(),
        bundle_content_sha256=bundle.content_sha256,
        source_task_dir=str(source_task_root.resolve()),
        source_task_package_sha256=bundle.task_snapshot.package_sha256,
        runtime_archive_path=str(runtime.path.resolve()),
        runtime_archive_sha256=runtime.archive_sha256,
        runtime_archive_content_sha256=runtime.content_sha256,
        evaluation_coordinate=_evaluation_coordinate(bundle),
        execution_schedule_sha256=_sha("execution-schedule"),
        execution_assignment_sha256=_sha("execution-assignment"),
    )
    trial_name = "trial-proposal"
    trial_dir = repo_root / "jobs" / "job-001" / trial_name
    expected = _write_proposal_harbor_trial_artifacts(
        repo_root=repo_root,
        trial_dir=trial_dir,
        bundle=bundle,
        source_task_root=source_task_root,
        derived_task_dir=derived.path,
        host_config=host_config,
        recording_root=tmp_path / "recording-environment",
        candidate_failure=candidate_failure,
    )
    return repo_root, trial_dir, expected


def _write_proposal_harbor_trial_artifacts(
    *,
    repo_root: Path,
    trial_dir: Path,
    bundle: ProposalRunSessionBundle,
    source_task_root: Path,
    derived_task_dir: Path,
    host_config: ProposalSessionHostConfig,
    recording_root: Path,
    candidate_failure: bool = False,
) -> dict[str, object]:
    loaded = load_proposal_session_host_inputs(
        host_config.model_dump(mode="json"),
        environment_dir=derived_task_dir / "environment",
    )
    session_id = f"proposal-session.{trial_dir.name}"
    execution = build_proposal_session_execution_ref(
        inputs=loaded,
        session_id=session_id,
        environment_session_id=f"harbor-environment.{trial_dir.name}",
        backend="morph",
    )
    environment = _RecordingProposalEnvironment(
        root=recording_root,
        bundle=bundle,
        runtime_archive_sha256=host_config.runtime_archive_sha256,
        failed_node_ids=(
            {
                (
                    bundle.compilation.proposal_graph.semantic_subtasks[0].node_id
                    if bundle.compilation.proposal_graph.semantic_subtasks
                    else bundle.compilation.proposal_graph.finalizer.node_id
                ),
            }
            if candidate_failure
            else None
        ),
    )
    session_root = recording_root / "proposal-session"
    receipt = asyncio.run(
        run_proposal_session(
            bundle=bundle,
            execution=execution,
            source_task_root=source_task_root,
            session_root=session_root,
            environment=environment,
        )
    )
    receipt_path = session_root / "session-receipt.json"
    receipt_path.write_text(
        json.dumps(receipt.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    collected_session = trial_dir / "agent" / "proposal-session"
    collected_session.parent.mkdir(parents=True)
    shutil.copytree(session_root, collected_session)
    (trial_dir / "verifier").mkdir()
    metadata = {
        "adapter_name": "proposal_session",
        "resolved_model": _proposal_model(bundle),
        "model": _proposal_model(bundle),
        "proposal_session_id": receipt.session_id,
        "proposal_session_receipt_sha256": receipt.content_sha256,
        "proposal_session_status": receipt.status.value,
        "trial_record_permitted": receipt.trial_record_permitted,
        "failure_code": None if receipt.failure_code is None else receipt.failure_code.value,
        "candidate_id": bundle.compilation.candidate_ref.candidate_id,
        "proposal_graph_sha256": bundle.compilation.proposal_graph.content_sha256,
        "compilation_sha256": bundle.compilation.content_sha256,
        "session_plan_sha256": bundle.session_plan.content_sha256,
        "reward_owner": "harbor_verifier",
    }
    attempted_resources = tuple(node.resources for node in receipt.node_receipts if node.resources is not None)
    _write_proposal_result(
        trial_dir=trial_dir,
        task_path=derived_task_dir.relative_to(repo_root).as_posix(),
        task_revision=bundle.task_snapshot.definition_sha256,
        model=_proposal_model(bundle),
        host_config=host_config,
        metadata=metadata,
        input_tokens=sum(resource.tokens_in or 0 for resource in attempted_resources),
        output_tokens=sum(resource.tokens_out or 0 for resource in attempted_resources),
        cost_usd=sum(resource.estimated_cost_usd or 0.0 for resource in attempted_resources),
    )
    expected: dict[str, object] = {
        "session_id": receipt.session_id,
        "candidate_id": bundle.compilation.candidate_ref.candidate_id,
        "candidate_artifact_sha256": (bundle.compilation.candidate_ref.candidate_artifact_sha256),
        "proposal_graph_sha256": bundle.compilation.proposal_graph.content_sha256,
        "compilation_sha256": bundle.compilation.content_sha256,
        "session_plan_sha256": bundle.session_plan.content_sha256,
        "trial_record_permitted": receipt.trial_record_permitted,
    }
    output: bytes | None = None
    output_path: Path | None = None
    if receipt.status is ProposalSessionStatus.COMPLETED:
        output = environment.output_by_node[bundle.compilation.proposal_graph.finalizer.node_id]
        output_path = trial_dir / "agent" / "output.md"
        output_path.write_bytes(output)
        (trial_dir / "verifier" / "reward.json").write_text(
            '{"reward": 1.0}\n',
            encoding="utf-8",
        )
        (trial_dir / "verifier" / "details.json").write_text(
            '{"passed": true}\n',
            encoding="utf-8",
        )
    final_transition = next(
        node.container_transition for node in reversed(receipt.node_receipts) if node.container_transition is not None
    )
    boundary = trial_dir / "proposal-morph-boundary"
    seal_dir = boundary / "sealed-artifacts"
    seal_entries: list[dict[str, object]] = []
    sealed_sources = {
        **({"/workspace/output.md": output_path} if output_path is not None else {}),
        **{
            f"/workspace/proposal-session/{path.relative_to(collected_session).as_posix()}": path
            for path in sorted(collected_session.rglob("*"))
            if path.is_file()
        },
    }
    for remote_path, source in sorted(sealed_sources.items()):
        target = seal_dir / remote_path.removeprefix("/")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        seal_entries.append(
            {
                "path": remote_path,
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "size_bytes": source.stat().st_size,
            }
        )
    seal_manifest = {
        "schema_version": "aecbench.proposal-artifact-seal.v1",
        "runtime_archive_sha256": host_config.runtime_archive_sha256,
        "runtime_archive_content_sha256": host_config.runtime_archive_content_sha256,
        "artifacts": seal_entries,
    }
    if receipt.status is ProposalSessionStatus.CANDIDATE_FAILURE:
        seal_manifest.update(
            {
                "handoff_variant": "candidate_failure",
                "candidate_failure_session_receipt_sha256": receipt.content_sha256,
            }
        )
    _write_content_addressed_json(boundary / "seal-manifest.json", seal_manifest)
    verifier_identity = "container.verifier"
    rotation = {
        "schema_version": "aecbench.proposal-verifier-rotation.v1",
        "status": "completed",
        "runtime_archive_sha256": host_config.runtime_archive_sha256,
        "runtime_archive_content_sha256": host_config.runtime_archive_content_sha256,
        "tests_content_sha256": hashlib.sha256(b"tests").hexdigest(),
        "candidate_container_identity": final_transition.current_container_identity,
        "verifier_container_identity": verifier_identity,
        "candidate_container_stopped": True,
        "artifacts_sealed": True,
        "mounts_wiped": True,
        "output_restored": output is not None,
        "tests_uploaded": True,
        "sealed_output_sha256": (None if output is None else hashlib.sha256(output).hexdigest()),
    }
    if receipt.status is ProposalSessionStatus.CANDIDATE_FAILURE:
        rotation.update(
            {
                "handoff_variant": "candidate_failure",
                "candidate_failure_session_receipt_sha256": receipt.content_sha256,
            }
        )
    rotation_path = boundary / "verifier-rotation.json"
    _write_content_addressed_json(rotation_path, rotation)
    stored_rotation = json.loads(rotation_path.read_text(encoding="utf-8"))
    cleanup = {
        "schema_version": "aecbench.proposal-morph-cleanup.v1",
        "status": "completed",
        "delete_requested": True,
        "boundary_phase_at_stop": "verifier",
        "runtime_archive_sha256": host_config.runtime_archive_sha256,
        "runtime_archive_content_sha256": host_config.runtime_archive_content_sha256,
        "runtime_snapshot_identity": "snapshot.1",
        "trial_instance_identity": "instance.1",
        "rotation_receipt_sha256": hashlib.sha256(rotation_path.read_bytes()).hexdigest(),
        "rotation_receipt_content_sha256": stored_rotation["content_sha256"],
        "rotation_receipt_verified": True,
        "expected_verifier_container_identity": verifier_identity,
        "observed_verifier_container_identity": verifier_identity,
        "verifier_container_identity_verified": True,
        "verifier_container_stopped": True,
        "verifier_container_scrubbed": True,
        "trial_instance_scrubbed": True,
        "trial_instance_stopped": True,
        "runtime_snapshot_deleted": True,
        "failure_steps": [],
    }
    if receipt.status is ProposalSessionStatus.CANDIDATE_FAILURE:
        cleanup.update(
            {
                "handoff_variant": "candidate_failure",
                "candidate_failure_session_receipt_sha256": receipt.content_sha256,
            }
        )
    _write_content_addressed_json(boundary / "proposal-cleanup.json", cleanup)
    return expected


def _write_proposal_result(
    *,
    trial_dir: Path,
    task_path: str,
    task_revision: str,
    model: str,
    host_config: ProposalSessionHostConfig,
    metadata: dict[str, object],
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
) -> None:
    payload = {
        "trial_name": trial_dir.name,
        "task_checksum": task_revision,
        "config": {
            "task": {"path": task_path},
            "agent": {
                "name": "proposal-agent",
                "model_name": model,
                "import_path": "agents.entrypoint_agent:EntrypointAgent",
                "kwargs": {
                    "adapter": "proposal_session",
                    "extra_env": {},
                    "proposal_session": host_config.model_dump(mode="json"),
                },
            },
            "environment": {
                "import_path": ("aec_bench.providers.proposal_morph.environment:ProposalMorphHarborEnvironment"),
                "kwargs": {
                    "compute_backend": "morph",
                    "runtime_archive_path": host_config.runtime_archive_path,
                    "runtime_archive_sha256": host_config.runtime_archive_sha256,
                    "runtime_archive_content_sha256": (host_config.runtime_archive_content_sha256),
                },
            },
            "job_id": "experiment-proposal",
        },
        "agent_info": {"name": "entrypoint", "version": "1.0.0"},
        "agent_result": {
            "n_input_tokens": input_tokens,
            "n_output_tokens": output_tokens,
            "cost_usd": cost_usd,
            "metadata": metadata,
        },
        "started_at": "2026-07-24T00:00:00Z",
        "finished_at": "2026-07-24T00:00:01Z",
        "verifier": {
            "started_at": "2026-07-24T00:00:00.900000Z",
            "finished_at": "2026-07-24T00:00:01Z",
        },
    }
    trial_dir.mkdir(parents=True, exist_ok=True)
    (trial_dir / "result.json").write_text(json.dumps(payload), encoding="utf-8")


def _write_content_addressed_json(
    path: Path,
    payload: dict[str, object],
) -> None:
    content = dict(payload)
    content["content_sha256"] = canonical_content_sha256(content)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(content, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
