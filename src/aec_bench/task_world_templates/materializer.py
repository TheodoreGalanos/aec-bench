# ABOUTME: Materialises runnable examples from composite task-world templates.
# ABOUTME: Verifies source, handoff, branch, and deliverable evidence after compilation.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from aec_bench.task_world_templates.catalogue import get_template
from aec_bench.task_world_templates.contracts import CompositeTaskWorldTemplate
from aec_bench.task_world_templates.lifecycles import (
    materialize_lifecycle_template,
    verify_lifecycle_template,
)


def materialize_template_example(template: CompositeTaskWorldTemplate, output_dir: Path) -> Path:
    package_dir = Path(output_dir)
    for child in ["source", "hidden", "agent", "verifier", "deliverables"]:
        (package_dir / child).mkdir(parents=True, exist_ok=True)

    _write_json(package_dir / "template.json", template.model_dump(mode="json"))
    _write_json(package_dir / "world.json", template.compile_task_world_payload())
    (package_dir / "README.md").write_text(_readme(template), encoding="utf-8")
    (package_dir / "source" / "task.md").write_text(_task_text(template), encoding="utf-8")

    world_state = {
        "template_id": template.template_id,
        "world_id": template.world_id,
        "expected_answer": template.expected_answer(),
    }
    verifier_config = {
        "template_id": template.template_id,
        "verifier_gates": [gate.model_dump(mode="json") for gate in template.verifier_gates],
        "data_gaps": [gap.model_dump(mode="json") for gap in template.data_gaps],
    }
    _write_json(package_dir / "hidden" / "world_state.json", world_state)
    _write_json(package_dir / "hidden" / "verifier_config.json", verifier_config)
    _write_json(package_dir / "agent" / "structured_answer.json", template.expected_answer())

    for deliverable in template.deliverables:
        deliverable_path = package_dir / deliverable.path
        deliverable_path.parent.mkdir(parents=True, exist_ok=True)
        deliverable_path.write_text(
            (
                f"# {template.name}\n\n{deliverable.description}\n\n"
                "This example is closed by structured handoff evidence.\n"
            ),
            encoding="utf-8",
        )

    result = verify_template_example(package_dir)
    _write_json(package_dir / "verifier" / "result.json", result)
    return package_dir


def verify_template_example(package_dir: Path) -> dict[str, Any]:
    root = Path(package_dir)
    template_payload = _read_json(root / "template.json")
    template = CompositeTaskWorldTemplate.model_validate(template_payload)
    world_state = _read_json(root / "hidden" / "world_state.json")
    verifier_config = _read_json(root / "hidden" / "verifier_config.json")
    answer = _read_json(root / "agent" / "structured_answer.json")
    expected = world_state["expected_answer"]

    source_gate = _check_keys(
        expected=set(expected["source_refs"]),
        actual=set(answer.get("source_refs", [])),
    )
    handoff_gate = _check_mapping(expected["handoffs"], answer.get("handoffs", {}))
    branch_gate = _check_mapping(expected["branch_decisions"], answer.get("branch_decisions", {}))
    deliverable_gate = _check_keys(
        expected=set(expected["deliverables"]),
        actual=set(answer.get("deliverables", [])),
    )

    gates: dict[str, dict[str, Any]] = {
        "source_grounding": source_gate | {"category": "source_grounding"},
        "handoff_consistency": handoff_gate | {"category": "handoff_consistency"},
        "branch_consistency": branch_gate | {"category": "branch_consistency"},
        "deliverable_manifest": deliverable_gate | {"category": "deliverable"},
    }
    for gate in verifier_config["verifier_gates"]:
        base = _gate_from_required_evidence(gate, answer, gates)
        gates[gate["id"]] = base | {"category": gate["category"]}

    passed = sum(1 for gate in gates.values() if gate["passed"])
    score = round(passed / len(gates), 4) if gates else 0.0
    result = {
        "template_id": template.template_id,
        "world_id": template.world_id,
        "overall": "pass" if passed == len(gates) else "fail",
        "score": score,
        "gates": gates,
        "data_gaps": verifier_config["data_gaps"],
    }
    _write_json(root / "verifier" / "result.json", result)
    return result


def materialize_template_id_example(template_id: str, output_dir: Path) -> Path:
    return materialize_template_example(get_template(template_id), output_dir)


def materialize_template_lifecycle(template: CompositeTaskWorldTemplate, output_dir: Path) -> Path:
    """Materialize a registered evidence lifecycle for one composite template."""
    template = CompositeTaskWorldTemplate.model_validate(template.model_dump(mode="json"))
    if template.evidence_lifecycle is None:
        raise ValueError(f"template {template.template_id!r} does not define an evidence lifecycle")
    return materialize_lifecycle_template(template, output_dir)


def verify_template_lifecycle(package_dir: Path, run_dir: Path) -> dict[str, Any]:
    """Verify one completed lifecycle run through its registered task-specific verifier."""
    return verify_lifecycle_template(package_dir, run_dir)


def _gate_from_required_evidence(
    gate: dict[str, Any],
    answer: dict[str, Any],
    system_gates: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    missing: list[str] = []
    for evidence in gate.get("required_evidence", []):
        if evidence == "source_refs" and not system_gates["source_grounding"]["passed"]:
            missing.extend(system_gates["source_grounding"]["missing"])
        elif evidence == "deliverables" and not system_gates["deliverable_manifest"]["passed"]:
            missing.extend(system_gates["deliverable_manifest"]["missing"])
        elif evidence.startswith("handoffs."):
            key = evidence.removeprefix("handoffs.")
            if key not in answer.get("handoffs", {}):
                missing.append(key)
        elif evidence.startswith("branches."):
            key = evidence.removeprefix("branches.")
            if key not in answer.get("branch_decisions", {}):
                missing.append(key)
    return {"passed": not missing, "missing": sorted(set(missing)), "mismatched": []}


def _check_mapping(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    missing = [key for key in expected if key not in actual]
    mismatched = [key for key, value in expected.items() if key in actual and actual[key] != value]
    return {"passed": not missing and not mismatched, "missing": missing, "mismatched": mismatched}


def _check_keys(expected: set[str], actual: set[str]) -> dict[str, Any]:
    missing = sorted(expected - actual)
    return {"passed": not missing, "missing": missing, "mismatched": []}


def _task_text(template: CompositeTaskWorldTemplate) -> str:
    stage_lines = "\n".join(f"- {stage.id}: {stage.title}" for stage in template.stages)
    gap_lines = "\n".join(f"- {gap.id}: {gap.description}" for gap in template.data_gaps)
    return (
        f"# {template.name}\n\n"
        f"{template.summary}\n\n"
        "## Required Stages\n\n"
        f"{stage_lines}\n\n"
        "## Reality Data Gaps\n\n"
        f"{gap_lines}\n"
    )


def _readme(template: CompositeTaskWorldTemplate) -> str:
    return (
        f"# {template.name}\n\n"
        "This package is a runnable example compiled from a composite task-world template.\n\n"
        "- `template.json` records the declarative composite task-world template.\n"
        "- `world.json` records the existing task-world/meta-harness payload.\n"
        "- `source/task.md` is the agent-facing task brief.\n"
        "- `hidden/world_state.json` and `hidden/verifier_config.json` drive verification.\n"
        "- `agent/structured_answer.json` is the example answer under test.\n"
        "- `verifier/result.json` records deterministic verifier output.\n"
    )


def _read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
