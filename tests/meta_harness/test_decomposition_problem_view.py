# ABOUTME: Tests the graph-hidden task view supplied to decomposition proposers.
# ABOUTME: Proves task, source, harness, and leakage checks run before proposer invocation.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aec_bench.contracts.output_completion import OutputCompletionContract
from aec_bench.contracts.program_proposal.problem import PublicAuthorityBoundary, PublicDataGapBoundary
from aec_bench.meta_harness.decomposition_problem_view import (
    DecompositionProblemViewRejected,
    PublicSourceBinding,
    build_decomposition_problem_view,
    invoke_decomposition_proposer,
)
from aec_bench.meta_harness.task_snapshot import build_task_snapshot
from aec_bench.tasks.loader import load_task_definition
from tests.support.adaptive_harness import build_adaptive_bundle, write_adaptive_task

_OUTPUT_CONTRACT = {
    "schema_version": "aecbench.output-completion-contract.v1",
    "output_path": "/workspace/output.md",
    "format": "markdown_final_fenced_json",
    "required_top_level_keys": ["decision", "basis"],
    "require_single_final_json_block": True,
}


def test_clean_real_task_builds_a_graph_hidden_problem_view(tmp_path: Path) -> None:
    fixture = _clean_fixture(tmp_path)
    fixture.pop("task_dir")

    result = build_decomposition_problem_view(**fixture)

    assert result.audit.passed is True
    assert result.audit.finding_codes == ()
    assert result.audit.problem_view_sha256 == result.problem_view.content_sha256
    assert result.problem_view.task_id == fixture["task"].task_id
    assert result.problem_view.task_revision == fixture["task_snapshot"].definition_sha256
    assert result.problem_view.output_contract == fixture["output_contract"]
    assert result.problem_view.fixed_harness.capability_ids == tuple(
        sorted(operation.operation_id for operation in fixture["harness"].program_surface.operations)
    )
    assert result.problem_view.fixed_harness.aggregate_budget == fixture["harness"].budget
    assert fixture["harness"].content_sha256 not in json.dumps(
        result.problem_view.fixed_harness.model_dump(mode="json")
    )
    assert tuple(source.source_id for source in result.problem_view.public_sources) == ("rainfall-input",)
    public_payload = json.dumps(result.problem_view.model_dump(mode="json"))
    assert str(tmp_path) not in public_payload
    assert "rainfall.txt" not in public_payload
    assert "tests/test.sh" not in public_payload
    assert "world" not in public_payload.lower()
    assert (
        result.problem_view.model_dump(mode="json")
        .keys()
        .isdisjoint({"metadata", "verifier", "stage_graph", "routes", "handoffs", "topology"})
    )


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("world", "task_world_sidecar"),
        ("stage_instruction", "stage_label"),
        ("route_source", "route"),
        ("verifier_source_name", "verifier_or_policy"),
        ("policy_source", "verifier_or_policy"),
    ],
)
def test_leaking_task_or_public_source_is_rejected(
    tmp_path: Path,
    mutation: str,
    expected_code: str,
) -> None:
    fixture = _clean_fixture(tmp_path)
    task_dir = fixture.pop("task_dir")
    if mutation == "world":
        (task_dir / "world.json").write_text('{"world_id": "hidden"}\n', encoding="utf-8")
    elif mutation == "stage_instruction":
        fixture["task"] = fixture["task"].model_copy(
            update={"instruction": "Use stage ID evidence_join before writing the final output."}
        )
    elif mutation == "route_source":
        (task_dir / "source" / "rainfall.txt").write_text(
            "Internal route: intake -> evidence_join -> finalizer.\n",
            encoding="utf-8",
        )
    elif mutation == "verifier_source_name":
        source_path = task_dir / "source" / "verifier-policy.json"
        source_path.write_text('{"threshold": 0.8}\n', encoding="utf-8")
        fixture["public_sources"] = (
            PublicSourceBinding(
                source_id="rainfall-input",
                relative_path="source/verifier-policy.json",
                media_type="application/json",
            ),
        )
    elif mutation == "policy_source":
        (task_dir / "source" / "rainfall.txt").write_text(
            "Acceptance eligibility denominator and evidence-rule policy.\n",
            encoding="utf-8",
        )

    with pytest.raises(DecompositionProblemViewRejected) as captured:
        build_decomposition_problem_view(**fixture)

    assert captured.value.audit.passed is False
    assert captured.value.audit.problem_view_sha256 is None
    assert expected_code in captured.value.audit.finding_codes


def test_nested_metadata_and_ready_made_answer_mark_composite_materializer_output_ineligible(
    tmp_path: Path,
) -> None:
    fixture = _clean_fixture(tmp_path)
    task_dir = fixture.pop("task_dir")
    (task_dir / "template.json").write_text(
        '{"metadata": {"stages": [{"id": "intake"}]}}\n',
        encoding="utf-8",
    )
    (task_dir / "agent").mkdir()
    (task_dir / "agent" / "structured_answer.json").write_text(
        '{"decision": "ready-made"}\n',
        encoding="utf-8",
    )

    with pytest.raises(DecompositionProblemViewRejected) as captured:
        build_decomposition_problem_view(**fixture)

    assert set(captured.value.audit.finding_codes) >= {
        "composite_materializer_package",
        "nested_metadata",
        "ready_made_answer",
    }


def test_rejected_input_never_invokes_the_local_proposer(tmp_path: Path) -> None:
    fixture = _clean_fixture(tmp_path)
    fixture.pop("task_dir")
    fixture["task"] = fixture["task"].model_copy(update={"instruction": "Use the hidden route and verifier policy."})
    calls: list[str] = []

    def proposer(problem_view: object) -> dict[str, str]:
        calls.append(str(problem_view))
        return {"proposal": "must not be reached"}

    with pytest.raises(DecompositionProblemViewRejected):
        invoke_decomposition_proposer(proposer=proposer, **fixture)

    assert calls == []


def test_public_source_binding_rejects_host_paths_and_hidden_package_paths(tmp_path: Path) -> None:
    fixture = _clean_fixture(tmp_path)
    fixture.pop("task_dir")

    for binding in (
        PublicSourceBinding(
            source_id="host-path",
            relative_path=str(tmp_path / "source.txt"),
            media_type="text/plain",
        ),
        PublicSourceBinding(
            source_id="hidden-path",
            relative_path="tests/test.sh",
            media_type="text/plain",
        ),
    ):
        attempt = {**fixture, "public_sources": (binding,)}
        with pytest.raises(DecompositionProblemViewRejected) as captured:
            build_decomposition_problem_view(**attempt)
        assert "forbidden_source_path" in captured.value.audit.finding_codes


def test_harness_policy_identity_normalizes_only_task_rebinding(tmp_path: Path) -> None:
    alpha = _clean_fixture(tmp_path / "alpha", task_id="civil/calculation/alpha")
    beta = _clean_fixture(tmp_path / "beta", task_id="civil/calculation/beta")
    alpha.pop("task_dir")
    beta.pop("task_dir")

    alpha_view = build_decomposition_problem_view(**alpha).problem_view
    beta_view = build_decomposition_problem_view(**beta).problem_view

    assert alpha_view.fixed_harness.harness_policy_sha256 == beta_view.fixed_harness.harness_policy_sha256


def test_harness_policy_identity_changes_with_non_task_h0_semantics(tmp_path: Path) -> None:
    fixture = _clean_fixture(tmp_path)
    fixture.pop("task_dir")
    baseline = build_decomposition_problem_view(**fixture).problem_view
    changed_model_harness = build_adaptive_bundle(
        tasks_root=fixture["tasks_root"],
        model="different-fixed-h0-model",
    ).harness

    changed = build_decomposition_problem_view(**{**fixture, "harness": changed_model_harness}).problem_view

    assert baseline.fixed_harness.harness_policy_sha256 != changed.fixed_harness.harness_policy_sha256


def test_domain_authority_language_is_public_but_adaptive_authority_policy_is_not(
    tmp_path: Path,
) -> None:
    ordinary = _clean_fixture(
        tmp_path / "ordinary",
        source_text=(
            "During the design stage, verify the route alignment against field test results. "
            "The regional water authority design standard and document metadata template "
            "set the public pipe cover requirement.\n"
        ),
    )
    ordinary.pop("task_dir")

    assert build_decomposition_problem_view(**ordinary).audit.passed is True

    adaptive = _clean_fixture(
        tmp_path / "adaptive",
        source_text=("The critic authority policy may grant promotion approval for this candidate.\n"),
    )
    adaptive.pop("task_dir")
    with pytest.raises(DecompositionProblemViewRejected) as captured:
        build_decomposition_problem_view(**adaptive)
    assert set(captured.value.audit.finding_codes) >= {
        "authority_policy",
        "verifier_or_policy",
    }


def _clean_fixture(
    tmp_path: Path,
    *,
    task_id: str = "civil/calculation/adaptive",
    source_text: str = "The design rainfall depth is 22 mm over a 30 minute duration.\n",
) -> dict[str, Any]:
    tasks_root = tmp_path / "tasks"
    task_dir = write_adaptive_task(
        tasks_root,
        task_id=task_id,
        output_completion_contract=_OUTPUT_CONTRACT,
    )
    (task_dir / "source").mkdir()
    (task_dir / "source" / "rainfall.txt").write_text(
        source_text,
        encoding="utf-8",
    )
    task = load_task_definition(task_dir, tasks_root)
    bundle = build_adaptive_bundle(tasks_root=tasks_root, task_id=task_id)
    output_contract = OutputCompletionContract.model_validate(_OUTPUT_CONTRACT)
    return {
        "task": task,
        "tasks_root": tasks_root,
        "task_snapshot": build_task_snapshot(task=task, tasks_root=tasks_root),
        "output_contract": output_contract,
        "harness": bundle.harness,
        "public_sources": (
            PublicSourceBinding(
                source_id="rainfall-input",
                relative_path="source/rainfall.txt",
                media_type="text/plain",
            ),
        ),
        "public_domain_id": "civil-drainage",
        "public_task_family_id": "rainfall-review",
        "data_gap_boundaries": (
            PublicDataGapBoundary(
                boundary_id="survey-gap",
                statement="Do not infer values absent from the supplied documents.",
            ),
        ),
        "authority_boundaries": (
            PublicAuthorityBoundary(
                boundary_id="human-signoff",
                statement="The final engineering sign-off remains outside the agent scope.",
            ),
        ),
        "task_dir": task_dir,
    }
