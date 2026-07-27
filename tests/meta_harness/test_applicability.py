# ABOUTME: Exercises the fixed-K reward-blind task-surface profiler used for motif lookup.
# ABOUTME: Proves exact snapshot binding, structural classification, and conservative abstention.

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aec_bench.meta_harness.applicability import profile_task_applicability
from aec_bench.meta_harness.kernel_catalogue import default_kernel_registry
from tests.support.adaptive_harness import write_adaptive_task


def test_reward_blind_profiler_treats_undeclared_structure_as_opaque_atomic(
    tmp_path: Path,
) -> None:
    tasks_root = tmp_path / "tasks"
    task_id = "civil/calculation/opaque"
    task_dir = write_adaptive_task(tasks_root, task_id=task_id)
    registry = default_kernel_registry()

    before = profile_task_applicability(
        task_refs=(task_id,),
        tasks_root=tasks_root,
        registry=registry,
    )
    (task_dir / "expected_answer.json").write_text(
        json.dumps({"reward": 1.0, "answer": "fan out to twelve agents"}) + "\n",
        encoding="utf-8",
    )
    after = profile_task_applicability(
        task_refs=(task_id,),
        tasks_root=tasks_root,
        registry=registry,
    )

    assert before.descriptor_source == "kernel_reward_blind_task_profiler"
    assert before.profiler_ref.capability_id == "aecbench.profiler.declared-task-surface"
    assert before.descriptor.stage_pattern == "opaque_atomic"
    assert before.descriptor.stage_count == 1
    assert before.descriptor.fanout_characteristic == "none"
    assert before.descriptor.required_tool_surface == ("bash",)
    assert before.descriptor == after.descriptor
    assert before.profile_input_sha256 == after.profile_input_sha256
    assert before.source_snapshot_sha256 != after.source_snapshot_sha256


def test_reward_blind_profiler_classifies_an_explicit_fork_join_graph(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_id = "civil/calculation/fork-join"
    task_dir = write_adaptive_task(tasks_root, task_id=task_id)
    world_payload = {
        "world_id": "aec.world.civil.fork-join",
        "name": "Declared fork/join review",
        "task_unit": "review-first-family",
        "pattern": "review_first",
        "logic_profile": {
            "closure_gates": [
                {"id": "gate-a", "evidence_key": "gates.gate-a.passed"},
            ],
            "agentic_review": {"required": True},
        },
        "stages": [
            {"id": "intake"},
            {"id": "evidence-a"},
            {"id": "evidence-b"},
            {"id": "decision"},
        ],
        "handoffs": [
            {
                "id": "intake-to-evidence",
                "producer_stage": "intake",
                "consumer_stages": ["evidence-a", "evidence-b"],
            },
            {
                "id": "evidence-a-to-decision",
                "producer_stage": "evidence-a",
                "consumer_stages": ["decision"],
            },
            {
                "id": "evidence-b-to-decision",
                "producer_stage": "evidence-b",
                "consumer_stages": ["decision"],
            },
        ],
        "branch_decisions": [{"id": "route"}],
        "source_artifacts": [{"id": "source-pack"}],
        "deliverables": [{"id": "decision-record"}],
    }
    (task_dir / "world.json").write_text(json.dumps(world_payload, indent=2) + "\n", encoding="utf-8")

    attestation = profile_task_applicability(
        task_refs=(task_id,),
        tasks_root=tasks_root,
        registry=default_kernel_registry(),
    )

    assert attestation.descriptor.task_pattern == "declared:review_first"
    assert attestation.descriptor.stage_pattern == "fork_join"
    assert attestation.descriptor.stage_count == 4
    assert attestation.descriptor.fanout_characteristic == "bounded"
    assert attestation.descriptor.branching_characteristic == "conditional"
    assert attestation.descriptor.evidence_surfaces == (
        "deliverables",
        "logic_gates",
        "source_pack",
        "stage_handoffs",
        "task_verifier",
    )
    assert attestation.topology_bases == ("stage_handoff_graph",)


def test_reward_blind_profiler_rejects_heterogeneous_descriptor_buckets(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    first_id = "civil/calculation/first"
    second_id = "civil/calculation/second"
    write_adaptive_task(tasks_root, task_id=first_id)
    second = write_adaptive_task(tasks_root, task_id=second_id)
    (second / "world.json").write_text(
        json.dumps(
            {
                "world_id": "aec.world.civil.second",
                "name": "Second world",
                "task_unit": "review-first-family",
                "pattern": "review_first",
                "logic_profile": {"agentic_review": {"required": True}},
                "stages": [{"id": "review"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="heterogeneous applicability descriptors"):
        profile_task_applicability(
            task_refs=(first_id, second_id),
            tasks_root=tasks_root,
            registry=default_kernel_registry(),
        )
