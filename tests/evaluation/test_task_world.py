# ABOUTME: Tests task-world materialisation for reviewer-ready benchmark runs.
# ABOUTME: Covers explicit sidecars, default profiles, and preserved run evidence.

from __future__ import annotations

import json
from pathlib import Path

from aec_bench.evaluation.task_world import materialize_workspace_task_world_run


def test_materialize_workspace_run_uses_task_world_sidecar(tmp_path: Path) -> None:
    task_dir = tmp_path / "task"
    workspace = tmp_path / "workspace"
    verifier_dir = workspace / "logs" / "verifier"
    task_dir.mkdir()
    verifier_dir.mkdir(parents=True)
    (task_dir / "instruction.md").write_text("Prepare a submission compliance review.", encoding="utf-8")
    (task_dir / "world.yaml").write_text(
        """
world_id: private.winning_work.compliance_review
name: Submission compliance review world
task_unit: Review a proposal response against a client returnables matrix.
logic_profile:
  closure_gates:
    - id: verifier_reward_available
      proposition: Verifier reward JSON is present.
      evidence_key: verifier.reward
      expected: present
      authority: verifier_artifact
      failure_effect: review_blocked
  construction_gates:
    - id: compliance_claim_has_witness
      proposition: Compliance claims cite preserved reviewer evidence.
      construction_required:
        - agent.output_md
        - verifier.details
      failure_effect: claim_unproven
  containment_gates:
    - id: source_matrix_disagreement
      contradiction: Source documents and returnables matrix disagree.
      when:
        key: contradictions.source_matrix_disagreement
        exists: true
      record_key: contradictions.source_matrix_disagreement
      required_record:
        - sources
        - affected_claims
        - allowed_next_actions
      failure_effect: event_candidate
  event_triggers:
    - id: unmodeled_returnable_language
      classification: schema_gap
      repair_targets:
        - world_schema
  agentic_review:
    required: true
    review_modes:
      - verifier_result
      - output_artifacts
      - trace
      - source_authority
operation_profile:
  subset_axes:
    - returnables
  difference_axes:
    - source_pack_visibility
  projection_axes:
    - compliance_matrix
  product_axes:
    - work_package
  extension_policy: Promote uncaptured returnable classes into world-schema repair candidates.
""".strip(),
        encoding="utf-8",
    )
    (workspace / "output.md").write_text("Compliance review complete.", encoding="utf-8")
    (verifier_dir / "reward.json").write_text(json.dumps({"reward": 1.0}), encoding="utf-8")
    (verifier_dir / "details.json").write_text(json.dumps({"checks": []}), encoding="utf-8")

    materialized = materialize_workspace_task_world_run(task_dir=task_dir, workspace_dir=workspace)

    assert materialized.world_profile.world_id == "private.winning_work.compliance_review"
    assert materialized.world_profile.logic_profile.agentic_review.review_modes == [
        "verifier_result",
        "output_artifacts",
        "trace",
        "source_authority",
    ]
    assert materialized.evidence["verifier"]["reward"] == {"reward": 1.0}
    assert materialized.to_review_payload()["world"]["operation_profile"]["projection_axes"] == ["compliance_matrix"]


def test_materialize_workspace_run_derives_default_profile_when_no_sidecar(
    tmp_path: Path,
) -> None:
    task_dir = tmp_path / "tasks" / "electrical" / "voltage-drop"
    workspace = tmp_path / "workspace"
    verifier_dir = workspace / "logs" / "verifier"
    task_dir.mkdir(parents=True)
    verifier_dir.mkdir(parents=True)
    (task_dir / "instruction.md").write_text("Calculate voltage drop.", encoding="utf-8")
    (task_dir / "task.toml").write_text(
        """
version = "1.0"

[metadata]
difficulty = "easy"
category = "reasoning"
tags = ["electrical", "deterministic"]
""".strip(),
        encoding="utf-8",
    )
    (workspace / "output.md").write_text("Voltage drop is 3.2%.", encoding="utf-8")
    (verifier_dir / "reward.json").write_text(json.dumps({"reward": 1.0}), encoding="utf-8")
    (verifier_dir / "details.json").write_text(json.dumps({"tolerance": "met"}), encoding="utf-8")

    materialized = materialize_workspace_task_world_run(task_dir=task_dir, workspace_dir=workspace)

    assert materialized.world_profile.world_id == "aec_bench.electrical.voltage-drop"
    assert materialized.world_profile.logic_profile.agentic_review.required is True
    assert [gate.id for gate in materialized.world_profile.logic_profile.closure_gates] == [
        "verifier_reward_available",
        "verifier_details_available",
    ]
    assert "verifier_details" in materialized.world_profile.operation_profile.difference_axes
    assert materialized.to_review_payload()["logic_profile"]["agentic_review"]["required"] is True
