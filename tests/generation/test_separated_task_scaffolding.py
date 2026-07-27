# ABOUTME: Tests generation of graph-hidden public tasks with external sealed authority material.
# ABOUTME: Proves the shared scaffolder preserves Harbor structure without co-locating truth.

from __future__ import annotations

from pathlib import Path

import pytest
from harbor.models.task.task import Task as HarborTask  # type: ignore[import-untyped]

from aec_bench.generation.sampler import sample_instance
from aec_bench.generation.scaffolder import scaffold_task_instance
from aec_bench.tasks.loader import load_task_definition
from aec_bench.templates.registry import load_engine_module, load_template

TEMPLATE_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "aec_bench"
    / "templates"
    / "builtin"
    / "civil"
    / "drainage_model_run_provenance_issue_review_package"
)
PUBLIC_INSTRUCTION = (
    "Review the supplied drainage evidence using only the public source documents.\n"
    "Write the required source-grounded artifact to /workspace/output.md.\n"
)


def test_shared_scaffolder_separates_public_and_sealed_task_material(
    tmp_path: Path,
) -> None:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    sampled = sample_instance(
        config,
        engine.compute,
        "medium",
        seed=0,
        instance_index=0,
    ).model_copy(update={"instance_name": "phase91a-calibration-test"})
    public_root = tmp_path / "tasks"
    sealed_root = tmp_path / "sealed-tasks"

    public_task = scaffold_task_instance(
        config,
        (template_dir / "engine.py").read_text(encoding="utf-8"),
        template_dir,
        sampled,
        public_root,
        sealed_output_dir=sealed_root,
        public_instruction=PUBLIC_INSTRUCTION,
    )
    sealed_task = sealed_root / public_task.relative_to(public_root)

    assert (public_task / "instruction.md").read_text(encoding="utf-8") == (PUBLIC_INSTRUCTION)
    assert not (public_task / "world.json").exists()
    assert not (public_task / "tests" / "instance.json").exists()
    assert not (public_task / "tests" / "fixtures").exists()
    assert (public_task / "tests" / "test.sh").is_file()
    assert (public_task / "tests" / "verify.py").is_file()
    assert (sealed_task / "world.json").is_file()
    assert (sealed_task / "tests" / "instance.json").is_file()
    assert (sealed_task / "tests" / "fixtures" / "golden_pass.md").is_file()
    assert (sealed_task / "tests" / "fixtures" / "golden_fail.md").is_file()

    task = load_task_definition(public_task, public_root)
    assert task.task_id == public_task.relative_to(public_root).as_posix()
    assert HarborTask(public_task).paths.is_valid()


@pytest.mark.parametrize(
    ("sealed_output_dir", "public_instruction"),
    ((None, PUBLIC_INSTRUCTION), ("sealed", None)),
)
def test_separated_scaffolding_requires_both_roots_and_public_instruction(
    tmp_path: Path,
    sealed_output_dir: str | None,
    public_instruction: str | None,
) -> None:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    sampled = sample_instance(
        config,
        engine.compute,
        "medium",
        seed=0,
        instance_index=0,
    )

    with pytest.raises(ValueError, match="sealed output and public instruction"):
        scaffold_task_instance(
            config,
            (template_dir / "engine.py").read_text(encoding="utf-8"),
            template_dir,
            sampled,
            tmp_path / "tasks",
            sealed_output_dir=(None if sealed_output_dir is None else tmp_path / sealed_output_dir),
            public_instruction=public_instruction,
        )
