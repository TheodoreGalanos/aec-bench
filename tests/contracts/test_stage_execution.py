# ABOUTME: Tests directly referenced declared-stage graphs and stage execution evidence contracts.
# ABOUTME: Verifies dataflow routing, terminal outputs, and tamper-evident artifact lineage.

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.execution_program import ExecutionProgramRef
from aec_bench.contracts.harness_instance import ProgramOperationRef
from aec_bench.contracts.stage_execution import (
    DeclaredHandoff,
    DeclaredStage,
    DeclaredStageGraph,
    KernelInstructionOverride,
    StageContextManifest,
    StageContextRoute,
    StageExecutionReceipt,
    StageJobFileDigest,
    StageOutput,
    StageResourceEvidence,
    declared_stage_graph_from_payload,
)
from aec_bench.contracts.task_snapshot import ArtifactTaskSnapshotRef
from aec_bench.contracts.trial_record import ArtifactReference


def _artifact(path: Path, *, kind: str, digest: str) -> ArtifactReference:
    return ArtifactReference(
        kind=kind,
        path=str(path),
        sha256=digest,
        media_type="application/json",
    )


def _stage_graph() -> DeclaredStageGraph:
    return DeclaredStageGraph(
        task_id="civil/review/drainage",
        review_profile_id="review.civil.drainage",
        stages=(
            DeclaredStage(
                stage_id="inventory",
                title="Inventory sources",
                discipline="civil",
                consumes=("document_register",),
                produces=("source_inventory",),
            ),
            DeclaredStage(
                stage_id="authority",
                title="Resolve authority",
                discipline="drainage",
                consumes=("source_inventory", "criteria"),
                produces=("provenance_ledger",),
            ),
            DeclaredStage(
                stage_id="decision",
                title="Make decision",
                discipline="civil",
                consumes=("provenance_ledger",),
                produces=("readiness_decision",),
            ),
        ),
        handoffs=(
            DeclaredHandoff(
                handoff_id="packet_id",
                producer_stage_id="inventory",
                consumer_stage_ids=("decision",),
            ),
        ),
    )


def test_declared_stage_graph_derives_routes_and_required_outputs() -> None:
    graph = _stage_graph()

    assert graph.schema_version == "aecbench.declared-stage-graph.v3"
    assert graph.topological_order == ("inventory", "authority", "decision")
    assert graph.predecessor_stage_ids("authority") == ("inventory",)
    assert graph.predecessor_stage_ids("decision") == ("inventory", "authority")
    assert graph.routed_artifact_ids("inventory", "authority") == ("source_inventory",)
    assert graph.routed_artifact_ids("inventory", "decision") == ("packet_id",)
    assert graph.required_output_ids("inventory") == ("packet_id", "source_inventory")
    assert graph.required_output_ids("decision") == ("readiness_decision",)
    assert "content_sha256" not in graph.model_dump(mode="json")

    pre_cutover = graph.model_dump(mode="json")
    pre_cutover["world_package_sha256"] = "a" * 64
    with pytest.raises(ValidationError):
        DeclaredStageGraph.model_validate(pre_cutover)

    pre_cutover_version = graph.model_dump(mode="json")
    pre_cutover_version["schema_version"] = "aecbench.declared-stage-graph.v1"
    with pytest.raises(ValidationError):
        DeclaredStageGraph.model_validate(pre_cutover_version)


def test_declared_stage_graph_rejects_cycles_and_ambiguous_producers() -> None:
    with pytest.raises(ValidationError, match="declared stage graph must be acyclic"):
        DeclaredStageGraph(
            task_id="civil/review/cycle",
            review_profile_id="review.civil.cycle",
            stages=(
                DeclaredStage(stage_id="a", consumes=("from_b",), produces=("from_a",)),
                DeclaredStage(stage_id="b", consumes=("from_a",), produces=("from_b",)),
            ),
        )

    with pytest.raises(ValidationError, match="declared stage outputs must have one producer"):
        DeclaredStageGraph(
            task_id="civil/review/ambiguous",
            review_profile_id="review.civil.ambiguous",
            stages=(
                DeclaredStage(stage_id="a", produces=("shared",)),
                DeclaredStage(stage_id="b", produces=("shared",)),
            ),
        )


def test_declared_stage_graph_payload_decoder_preserves_declared_field_order() -> None:
    with pytest.raises(ValueError, match="declared stage text must be non-empty when supplied"):
        declared_stage_graph_from_payload(
            task_id="civil/review/drainage",
            review_profile_id="review.civil.drainage",
            payload={
                "stages": [
                    {
                        "id": "inventory",
                        "title": 42,
                        "consumes": "not-a-list",
                    }
                ],
                "handoffs": "not-a-list",
            },
        )

    with pytest.raises(ValueError, match="stage consumes must be a list"):
        declared_stage_graph_from_payload(
            task_id="civil/review/drainage",
            review_profile_id="review.civil.drainage",
            payload={
                "stages": [
                    {
                        "id": "inventory",
                        "consumes": "not-a-list",
                        "produces": "not-a-list",
                    }
                ]
            },
        )


def test_declared_stage_graph_payload_decoder_preserves_collection_order() -> None:
    with pytest.raises(ValueError, match="declared task-review stage must be a mapping"):
        declared_stage_graph_from_payload(
            task_id="civil/review/drainage",
            review_profile_id="review.civil.drainage",
            payload={"stages": [None], "handoffs": "not-a-list"},
        )

    with pytest.raises(ValueError, match="declared task-review handoff requires a non-empty id"):
        declared_stage_graph_from_payload(
            task_id="civil/review/drainage",
            review_profile_id="review.civil.drainage",
            payload={
                "stages": [{"id": "inventory"}],
                "handoffs": [{"id": "", "producer_stage": ""}],
            },
        )


def test_declared_stage_graph_payload_decoder_preserves_value() -> None:
    decoded = declared_stage_graph_from_payload(
        task_id="civil/review/drainage",
        review_profile_id="review.civil.drainage",
        payload={
            "stages": [
                {
                    "id": "inventory",
                    "title": "Inventory sources",
                    "discipline": "civil",
                    "consumes": ["document_register"],
                    "produces": ["source_inventory"],
                    "branch_decisions": ["inventory_complete"],
                    "verifier_gates": ["inventory_schema"],
                },
                {
                    "id": "authority",
                    "consumes": ["source_inventory"],
                    "produces": ["provenance_ledger"],
                },
            ],
            "handoffs": [
                {
                    "id": "packet_id",
                    "producer_stage": "inventory",
                    "consumer_stages": ["authority"],
                }
            ],
        },
    )
    expected = DeclaredStageGraph(
        task_id="civil/review/drainage",
        review_profile_id="review.civil.drainage",
        stages=(
            DeclaredStage(
                stage_id="inventory",
                title="Inventory sources",
                discipline="civil",
                consumes=("document_register",),
                produces=("source_inventory",),
                branch_decision_ids=("inventory_complete",),
                verifier_gate_ids=("inventory_schema",),
            ),
            DeclaredStage(
                stage_id="authority",
                consumes=("source_inventory",),
                produces=("provenance_ledger",),
            ),
        ),
        handoffs=(
            DeclaredHandoff(
                handoff_id="packet_id",
                producer_stage_id="inventory",
                consumer_stage_ids=("authority",),
            ),
        ),
    )

    assert decoded == expected
    assert decoded is not None


def test_declared_stage_graph_payload_decoder_ignores_handoffs_without_stages() -> None:
    assert (
        declared_stage_graph_from_payload(
            task_id="civil/review/drainage",
            review_profile_id="review.civil.drainage",
            payload={"handoffs": "not-a-list"},
        )
        is None
    )


def test_stage_output_and_receipt_bind_exact_context_and_physical_artifacts(tmp_path: Path) -> None:
    graph = _stage_graph()
    upstream = _artifact(tmp_path / "upstream.json", kind="stage-execution-receipt", digest="1" * 64)
    rendered_context = _artifact(tmp_path / "context.json", kind="stage-context", digest="2" * 64)
    context = StageContextManifest(
        task_id=graph.task_id,
        stage_graph_ref=graph.ref,
        consumer_stage_id="authority",
        base_context_sha256="3" * 64,
        routes=(
            StageContextRoute(
                input_id="source_inventory",
                producer_stage_id="inventory",
                producer_receipt=upstream,
            ),
        ),
        rendered_context=rendered_context,
    )
    parsed = StageOutput(
        task_id=graph.task_id,
        stage_id="authority",
        outputs={"provenance_ledger": {"status": "current"}},
    )
    receipt = StageExecutionReceipt(
        plan_run_id="plan-stage",
        run_id="run-stage",
        program_ref=ExecutionProgramRef(program_id="program-stage", version="1.0.0"),
        program_node_id="authority",
        operation_ref=ProgramOperationRef(operation_id="run-stage"),
        attempt=1,
        task_id=graph.task_id,
        task_snapshot=ArtifactTaskSnapshotRef(
            task_id=graph.task_id,
            artifact=ArtifactRef(
                artifact_id=f"artifacts/sha256/{'7' * 64}",
                sha256="7" * 64,
                size_bytes=1,
                media_type="application/vnd.aec-bench.task-snapshot+tar+zstd",
            ),
        ),
        stage_graph_ref=graph.ref,
        stage_id="authority",
        context_manifest=_artifact(
            tmp_path / "context-manifest.json",
            kind="stage-context-manifest",
            digest="8" * 64,
        ),
        upstream_receipts=(upstream,),
        raw_output=_artifact(tmp_path / "output.md", kind="stage-output-raw", digest="9" * 64),
        parsed_output=_artifact(tmp_path / "stage-output.json", kind="stage-output", digest="b" * 64),
        agent_result=_artifact(tmp_path / "agent-result.json", kind="stage-agent-result", digest="c" * 64),
        job_dir=str(tmp_path / "job"),
        job_files=(StageJobFileDigest(relative_path="trial/output.md", sha256="d" * 64, size_bytes=42),),
        resources=StageResourceEvidence(
            wall_seconds=12.5,
            tokens_in=1_200,
            tokens_out=300,
            cache_read_tokens=500,
            estimated_cost_usd=0.018,
            agent_turns=3,
            tool_calls=4,
        ),
    )

    assert "content_sha256" not in parsed.model_dump(mode="json")
    assert "content_sha256" not in context.model_dump(mode="json")
    assert receipt.schema_version == "aecbench.stage-execution-receipt.v3"
    assert "content_sha256" not in receipt.model_dump(mode="json")
    assert receipt.upstream_receipts == (upstream,)
    assert receipt.resources.tokens_in == 1_200

    pre_cutover = receipt.model_dump(mode="json")
    pre_cutover["world_package_sha256"] = "a" * 64
    with pytest.raises(ValidationError):
        StageExecutionReceipt.model_validate(pre_cutover)

    pre_cutover_version = receipt.model_dump(mode="json")
    pre_cutover_version["schema_version"] = "aecbench.stage-execution-receipt.v1"
    with pytest.raises(ValidationError):
        StageExecutionReceipt.model_validate(pre_cutover_version)


def test_stage_output_nested_containers_are_immutable() -> None:
    output = StageOutput(
        task_id="civil/review/drainage",
        stage_id="authority",
        outputs={
            "provenance_ledger": {
                "status": "current",
                "checks": ["source-present"],
            },
        },
    )
    original_dump = output.model_dump(mode="json")
    nested_output = cast(dict[str, Any], output.outputs["provenance_ledger"])
    nested_checks = cast(list[str], nested_output["checks"])

    with pytest.raises(TypeError):
        nested_output["status"] = "tampered"
    with pytest.raises(TypeError):
        nested_checks.append("forged-check")

    assert output.model_dump(mode="json") == original_dump
    assert output.model_copy(deep=True).model_dump(mode="json") == original_dump


def test_stage_contracts_reject_wrong_artifact_kinds_and_duplicate_routes(tmp_path: Path) -> None:
    wrong = _artifact(tmp_path / "wrong.json", kind="trial-record", digest="1" * 64)
    with pytest.raises(ValidationError, match="stage context routes require stage-execution receipts"):
        StageContextRoute(
            input_id="source_inventory",
            producer_stage_id="inventory",
            producer_receipt=wrong,
        )

    upstream = _artifact(tmp_path / "upstream.json", kind="stage-execution-receipt", digest="2" * 64)
    route = StageContextRoute(
        input_id="source_inventory",
        producer_stage_id="inventory",
        producer_receipt=upstream,
    )
    with pytest.raises(ValidationError, match="stage context routes must be unique"):
        StageContextManifest(
            task_id="civil/review/drainage",
            stage_graph_ref=_stage_graph().ref,
            consumer_stage_id="authority",
            base_context_sha256="4" * 64,
            routes=(route, route),
            rendered_context=_artifact(
                tmp_path / "context.json",
                kind="stage-context",
                digest="5" * 64,
            ),
        )


def test_kernel_instruction_override_binds_exact_stage_and_finalization_shapes() -> None:
    context_manifest = _artifact(Path("context-manifest.json"), kind="stage-context-manifest", digest="2" * 64)
    stage = KernelInstructionOverride(
        mode="declared_stage",
        task_id="civil/review/drainage",
        original_instruction_sha256="1" * 64,
        effective_instruction="Execute only the authority stage.",
        stage_id="authority",
        context_manifest=context_manifest,
    )
    finalization = KernelInstructionOverride(
        mode="task_finalization",
        task_id="civil/review/drainage",
        original_instruction_sha256="1" * 64,
        effective_instruction="Finalize the task from the complete receipt set.",
    )

    assert stage.context_manifest == context_manifest
    assert "content_sha256" not in finalization.model_dump(mode="json")
    with pytest.raises(ValidationError, match="declared-stage override requires"):
        KernelInstructionOverride(
            mode="declared_stage",
            task_id="civil/review/drainage",
            original_instruction_sha256="1" * 64,
            effective_instruction="Missing bound stage context.",
        )
    with pytest.raises(ValidationError, match="task-finalization override cannot carry"):
        KernelInstructionOverride(
            mode="task_finalization",
            task_id="civil/review/drainage",
            original_instruction_sha256="1" * 64,
            effective_instruction="Unexpected stage selection.",
            stage_id="authority",
        )
