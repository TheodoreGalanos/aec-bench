# ABOUTME: Tests for promotion-gate helpers in the aec-bench Python implementation.
# ABOUTME: Covers placeholder detection, output-contract checks, and required asset checks.

from pathlib import Path

from aec_bench.tasks.promotion import (
    PromotionCheckResult,
    PromotionReadinessReport,
    evaluate_promotion_readiness,
)
from tests.support.task_factories import make_task_definition


def test_promotion_readiness_accepts_resolved_instruction_and_assets(tmp_path: Path) -> None:
    task = make_task_definition(
        instruction="Review the documents and write findings to /workspace/output.jsonl.",
    )
    _create_required_task_assets(tmp_path)

    result = evaluate_promotion_readiness(task, tmp_path)

    assert isinstance(result, PromotionReadinessReport)
    assert result.ready is True
    assert result.issues == []


def test_promotion_readiness_rejects_placeholder_instruction() -> None:
    task = make_task_definition(instruction="Review the {jurisdiction} documents.")

    result = evaluate_promotion_readiness(task)

    assert result.ready is False
    assert PromotionCheckResult.UNRESOLVED_INSTRUCTION in result.issues


def test_promotion_readiness_rejects_output_path_mismatch() -> None:
    task = make_task_definition(
        instruction="Review the documents and write findings to /workspace/output.md.",
        verifier=make_task_definition().verifier.model_copy(update={"expected_output_path": "/workspace/output.jsonl"}),
    )

    result = evaluate_promotion_readiness(task)

    assert result.ready is False
    assert result.issues == [PromotionCheckResult.OUTPUT_PATH_MISMATCH]


def test_promotion_readiness_reports_missing_required_assets(tmp_path: Path) -> None:
    task = make_task_definition(
        instruction="Review the documents and write findings to /workspace/output.jsonl.",
    )

    result = evaluate_promotion_readiness(task, tmp_path)

    assert result.ready is False
    assert PromotionCheckResult.MISSING_DOCKERFILE in result.issues
    assert PromotionCheckResult.MISSING_COMPOSE_FILE in result.issues
    assert PromotionCheckResult.MISSING_MANIFEST in result.issues
    assert PromotionCheckResult.MISSING_TOOL_SOURCE in result.issues
    assert PromotionCheckResult.MISSING_VERIFIER_SCRIPT in result.issues


def _create_required_task_assets(task_dir: Path) -> None:
    (task_dir / "environment").mkdir(parents=True)
    (task_dir / "tests").mkdir(parents=True)
    (task_dir / "environment" / "Dockerfile").write_text("FROM ubuntu:24.04\n", encoding="utf-8")
    (task_dir / "environment" / "docker-compose.yaml").write_text(
        "services: {}\n",
        encoding="utf-8",
    )
    (task_dir / "environment" / "manifest.jsonl").write_text("", encoding="utf-8")
    (task_dir / "environment" / "codes_search.py").write_text("print('ok')\n", encoding="utf-8")
    (task_dir / "tests" / "test.sh").write_text("#!/bin/bash\n", encoding="utf-8")
