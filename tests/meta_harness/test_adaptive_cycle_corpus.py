# ABOUTME: Tests immutable discovery, calibration, and holdout corpus preparation.
# ABOUTME: Proves split visibility, lineage independence, topology identity, and generation provenance.

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aec_bench.contracts.task_definition import Visibility
from aec_bench.meta_harness.adaptive_cycle_corpus import prepare_adaptive_cycle_corpus
from aec_bench.meta_harness.kernel_catalogue import default_kernel_registry
from tests.support.adaptive_harness import write_adaptive_task


def test_prepare_adaptive_cycle_corpus_freezes_a_strict_2_2_2_manifest(
    tmp_path: Path,
) -> None:
    """The first production corpus has independent two-world evidence in every campaign split."""
    tasks_root, discovery, calibration, holdout = _write_corpus(tmp_path)

    manifest = prepare_adaptive_cycle_corpus(
        corpus_id="drainage.phase5b.v1",
        discovery_task_refs=discovery,
        repair_task_refs=discovery,
        calibration_task_refs=calibration,
        holdout_task_refs=holdout,
        tasks_root=tasks_root,
        registry=default_kernel_registry(),
    )

    assert manifest.discovery.task_refs == discovery
    assert manifest.repair_task_refs == discovery
    assert manifest.calibration.task_refs == calibration
    assert manifest.holdout.task_refs == holdout
    assert manifest.discovery.visibility is Visibility.PUBLIC
    assert manifest.calibration.visibility is Visibility.PUBLIC
    assert manifest.holdout.visibility is Visibility.HOLDOUT
    assert manifest.discovery.applicability.descriptor == manifest.calibration.applicability.descriptor
    assert manifest.discovery.applicability.descriptor == manifest.holdout.applicability.descriptor
    assert len(manifest.topology_signature_sha256) == 64
    assert len(manifest.content_sha256) == 64
    identities = (
        *manifest.discovery.generation_identities,
        *manifest.calibration.generation_identities,
        *manifest.holdout.generation_identities,
    )
    assert len({(item.template, item.seed, item.instance_index) for item in identities}) == 6


def test_prepare_adaptive_cycle_corpus_requires_explicit_holdout_visibility(
    tmp_path: Path,
) -> None:
    """A public task cannot become holdout merely because a manifest labels it that way."""
    tasks_root, discovery, calibration, holdout = _write_corpus(tmp_path)
    task_toml = tasks_root / holdout[0] / "task.toml"
    task_toml.write_text(
        task_toml.read_text(encoding="utf-8").replace(
            'visibility = "holdout"',
            'visibility = "public"',
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must explicitly declare visibility holdout"):
        prepare_adaptive_cycle_corpus(
            corpus_id="drainage.phase5b.v1",
            discovery_task_refs=discovery,
            repair_task_refs=discovery,
            calibration_task_refs=calibration,
            holdout_task_refs=holdout,
            tasks_root=tasks_root,
            registry=default_kernel_registry(),
        )


def test_prepare_adaptive_cycle_corpus_requires_two_tasks_per_evidence_split(
    tmp_path: Path,
) -> None:
    """A one-world result cannot support discovery, calibration, or holdout evidence."""
    tasks_root, discovery, calibration, holdout = _write_corpus(tmp_path)

    with pytest.raises(ValueError, match="calibration corpus requires at least 2 task refs"):
        prepare_adaptive_cycle_corpus(
            corpus_id="drainage.phase5b.v1",
            discovery_task_refs=discovery,
            repair_task_refs=discovery,
            calibration_task_refs=(calibration[0],),
            holdout_task_refs=holdout,
            tasks_root=tasks_root,
            registry=default_kernel_registry(),
        )


def test_prepare_adaptive_cycle_corpus_limits_repair_to_discovery_tasks(
    tmp_path: Path,
) -> None:
    """Repair may learn from discovery evidence, but never from calibration or holdout."""
    tasks_root, discovery, calibration, holdout = _write_corpus(tmp_path)

    with pytest.raises(ValueError, match="repair tasks must be a subset of discovery tasks"):
        prepare_adaptive_cycle_corpus(
            corpus_id="drainage.phase5b.v1",
            discovery_task_refs=discovery,
            repair_task_refs=(calibration[0],),
            calibration_task_refs=calibration,
            holdout_task_refs=holdout,
            tasks_root=tasks_root,
            registry=default_kernel_registry(),
        )


def test_prepare_adaptive_cycle_corpus_rejects_selection_split_overlap(
    tmp_path: Path,
) -> None:
    """Calibration worlds must not repeat discovery or repair task identities."""
    tasks_root, discovery, calibration, holdout = _write_corpus(tmp_path)

    with pytest.raises(ValueError, match="corpus task refs must be disjoint across evidence splits"):
        prepare_adaptive_cycle_corpus(
            corpus_id="drainage.phase5b.v1",
            discovery_task_refs=discovery,
            repair_task_refs=discovery,
            calibration_task_refs=(calibration[1], discovery[0]),
            holdout_task_refs=holdout,
            tasks_root=tasks_root,
            registry=default_kernel_registry(),
        )


def test_prepare_adaptive_cycle_corpus_rejects_same_bucket_topology_drift(
    tmp_path: Path,
) -> None:
    """A coarse fork/join descriptor cannot hide a different declared handoff graph."""
    tasks_root, discovery, calibration, holdout = _write_corpus(tmp_path)
    world_path = tasks_root / holdout[0] / "world.json"
    world = json.loads(world_path.read_text(encoding="utf-8"))
    world["handoffs"][1]["consumer_stages"] = ["review_b"]
    world_path.write_text(json.dumps(world, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="exactly one declared topology signature"):
        prepare_adaptive_cycle_corpus(
            corpus_id="drainage.phase5b.v1",
            discovery_task_refs=discovery,
            repair_task_refs=discovery,
            calibration_task_refs=calibration,
            holdout_task_refs=holdout,
            tasks_root=tasks_root,
            registry=default_kernel_registry(),
        )


def test_prepare_adaptive_cycle_corpus_requires_stable_generated_provenance(
    tmp_path: Path,
) -> None:
    """Every selected task needs the seed and stable index used to generate it."""
    tasks_root, discovery, calibration, holdout = _write_corpus(tmp_path)
    task_toml = tasks_root / discovery[0] / "task.toml"
    task_toml.write_text(
        task_toml.read_text(encoding="utf-8").replace("instance_index = 0\n", ""),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid generated-instance provenance"):
        prepare_adaptive_cycle_corpus(
            corpus_id="drainage.phase5b.v1",
            discovery_task_refs=discovery,
            repair_task_refs=discovery,
            calibration_task_refs=calibration,
            holdout_task_refs=holdout,
            tasks_root=tasks_root,
            registry=default_kernel_registry(),
        )


def test_prepare_adaptive_cycle_corpus_rejects_duplicate_generation_identity(
    tmp_path: Path,
) -> None:
    """Renaming a generated directory does not create an independent research instance."""
    tasks_root, discovery, calibration, holdout = _write_corpus(tmp_path)
    second = tasks_root / holdout[1] / "task.toml"
    second_payload = second.read_text(encoding="utf-8")
    second_payload = second_payload.replace("seed = 501", "seed = 500")
    second_payload = second_payload.replace("instance_index = 21", "instance_index = 20")
    second.write_text(second_payload, encoding="utf-8")

    with pytest.raises(ValueError, match="generation identities must be unique"):
        prepare_adaptive_cycle_corpus(
            corpus_id="drainage.phase5b.v1",
            discovery_task_refs=discovery,
            repair_task_refs=discovery,
            calibration_task_refs=calibration,
            holdout_task_refs=holdout,
            tasks_root=tasks_root,
            registry=default_kernel_registry(),
        )


def _write_corpus(
    tmp_path: Path,
) -> tuple[Path, tuple[str, str], tuple[str, str], tuple[str, str]]:
    tasks_root = tmp_path / "tasks"
    discovery = ("civil/review/discovery-a", "civil/review/discovery-b")
    calibration = ("civil/review/calibration-a", "civil/review/calibration-b")
    holdout = ("civil/review/holdout-a", "civil/review/holdout-b")
    specifications = (
        (discovery[0], Visibility.PUBLIC, 300, 0),
        (discovery[1], Visibility.PUBLIC, 301, 1),
        (calibration[0], Visibility.PUBLIC, 400, 10),
        (calibration[1], Visibility.PUBLIC, 401, 11),
        (holdout[0], Visibility.HOLDOUT, 500, 20),
        (holdout[1], Visibility.HOLDOUT, 501, 21),
    )
    for task_id, visibility, seed, instance_index in specifications:
        _write_corpus_task(
            tasks_root,
            task_id=task_id,
            visibility=visibility,
            seed=seed,
            instance_index=instance_index,
        )
    return tasks_root, discovery, calibration, holdout


def _write_corpus_task(
    tasks_root: Path,
    *,
    task_id: str,
    visibility: Visibility,
    seed: int,
    instance_index: int,
) -> None:
    task_dir = write_adaptive_task(tasks_root, task_id=task_id)
    task_toml = task_dir / "task.toml"
    task_toml.write_text(
        task_toml.read_text(encoding="utf-8").replace(
            'visibility = "public"',
            f'visibility = "{visibility.value}"',
        )
        + (
            "\n[generation]\n"
            'origin = "generated"\n'
            'template = "drainage-review"\n'
            f'template_source_sha256 = "{"0" * 64}"\n'
            f"seed = {seed}\n"
            f"instance_index = {instance_index}\n"
            'difficulty = "medium"\n'
            'archetype = "review-first"\n'
        ),
        encoding="utf-8",
    )
    world = {
        "world_id": f"aec.world.{task_id.replace('/', '.')}",
        "name": task_id,
        "task_unit": "generated-task-instance",
        "pattern": "source review -> parallel evidence -> closure",
        "logic_profile": {
            "closure_gates": [{"id": "complete", "evidence_key": "review.complete"}],
            "agentic_review": {"required": True},
        },
        "stages": [
            {"id": "intake"},
            {"id": "review_a"},
            {"id": "review_b"},
            {"id": "decision"},
        ],
        "handoffs": [
            {
                "id": "intake-review",
                "producer_stage": "intake",
                "consumer_stages": ["review_a", "review_b"],
            },
            {
                "id": "review-a-decision",
                "producer_stage": "review_a",
                "consumer_stages": ["decision"],
            },
            {
                "id": "review-b-decision",
                "producer_stage": "review_b",
                "consumer_stages": ["decision"],
            },
        ],
        "branch_decisions": [{"id": "route", "evidence_key": "review.route"}],
    }
    (task_dir / "world.json").write_text(json.dumps(world, indent=2) + "\n", encoding="utf-8")
