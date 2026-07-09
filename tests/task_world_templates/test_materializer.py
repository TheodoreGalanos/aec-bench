# ABOUTME: Tests materialisation and verification of composite task-world template examples.
# ABOUTME: Ensures packages preserve sources, hidden state, verifier output, and data gaps.

from __future__ import annotations

import json
from pathlib import Path

from aec_bench.task_world_templates.catalogue import get_template, list_templates
from aec_bench.task_world_templates.materializer import materialize_template_example, verify_template_example


def test_materialize_template_example_writes_runnable_task_world_package(tmp_path: Path) -> None:
    template = get_template("pump-station-duty-package")

    package = materialize_template_example(template, tmp_path)

    assert (package / "README.md").exists()
    assert (package / "template.json").exists()
    assert not (package / "product.json").exists()
    assert (package / "world.json").exists()
    assert (package / "source" / "task.md").exists()
    assert (package / "hidden" / "world_state.json").exists()
    assert (package / "hidden" / "verifier_config.json").exists()
    assert (package / "agent" / "structured_answer.json").exists()
    assert (package / "verifier" / "result.json").exists()

    result = json.loads((package / "verifier" / "result.json").read_text(encoding="utf-8"))
    assert result["overall"] == "pass"
    assert result["score"] == 1.0
    assert result["data_gaps"][0]["needed_to_run_in_reality"]


def test_all_builtin_templates_materialize_and_verify(tmp_path: Path) -> None:
    for template in list_templates():
        package = materialize_template_example(template, tmp_path / template.template_id)
        result = verify_template_example(package)

        assert result["overall"] == "pass", template.template_id
        assert result["score"] == 1.0
        assert result["template_id"] == template.template_id


def test_verify_template_example_flags_missing_handoff(tmp_path: Path) -> None:
    template = get_template("stormwater-drainage-package")
    package = materialize_template_example(template, tmp_path)
    answer_path = package / "agent" / "structured_answer.json"
    answer = json.loads(answer_path.read_text(encoding="utf-8"))
    answer["handoffs"].pop("peak_runoff_m3_s")
    answer_path.write_text(json.dumps(answer, indent=2), encoding="utf-8")

    result = verify_template_example(package)

    assert result["overall"] == "fail"
    assert result["gates"]["handoff_consistency"]["passed"] is False
    assert "peak_runoff_m3_s" in result["gates"]["handoff_consistency"]["missing"]
