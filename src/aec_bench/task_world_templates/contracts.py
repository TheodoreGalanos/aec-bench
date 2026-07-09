# ABOUTME: Contract models for composite task-world templates.
# ABOUTME: Compiles product-world definitions into existing task-world profile payloads.

from __future__ import annotations

from typing import Any

from pydantic import Field

from aec_bench.contracts.task_world import (
    AgenticReviewProfile,
    ClosureGate,
    ConstructionGate,
    LogicProfile,
    OperationProfile,
    TaskWorldProfile,
)
from aec_bench.contracts.validators import NonEmptyStr, StrictModel


class SourceArtifactSpec(StrictModel):
    id: NonEmptyStr
    artifact_type: NonEmptyStr
    description: NonEmptyStr
    carries: list[NonEmptyStr] = Field(default_factory=list)
    modality: NonEmptyStr = "text"


class CompositeTaskWorldStage(StrictModel):
    id: NonEmptyStr
    title: NonEmptyStr
    discipline: NonEmptyStr
    template_refs: list[NonEmptyStr] = Field(default_factory=list)
    consumes: list[NonEmptyStr] = Field(default_factory=list)
    produces: list[NonEmptyStr] = Field(default_factory=list)
    branch_decisions: list[NonEmptyStr] = Field(default_factory=list)
    verifier_gates: list[NonEmptyStr] = Field(default_factory=list)


class HandoffSpec(StrictModel):
    id: NonEmptyStr
    description: NonEmptyStr
    unit: NonEmptyStr
    producer_stage: NonEmptyStr
    consumer_stages: list[NonEmptyStr] = Field(default_factory=list)
    example_value: Any
    tolerance: float | None = None


class BranchDecisionSpec(StrictModel):
    id: NonEmptyStr
    description: NonEmptyStr
    allowed: list[NonEmptyStr]
    selected_example: NonEmptyStr
    evidence_key: NonEmptyStr


class VerifierGateSpec(StrictModel):
    id: NonEmptyStr
    category: NonEmptyStr
    proposition: NonEmptyStr
    required_evidence: list[NonEmptyStr] = Field(default_factory=list)
    authority: NonEmptyStr | None = None
    failure_effect: NonEmptyStr | None = None
    weight: float = 1.0


class DeliverableSpec(StrictModel):
    id: NonEmptyStr
    path: NonEmptyStr
    description: NonEmptyStr


class DataGapSpec(StrictModel):
    id: NonEmptyStr
    description: NonEmptyStr
    needed_to_run_in_reality: bool = True
    severity: NonEmptyStr = "medium"


class CompositeTaskWorldTemplate(StrictModel):
    template_id: NonEmptyStr
    name: NonEmptyStr
    summary: NonEmptyStr
    pattern: NonEmptyStr
    discipline_scope: list[NonEmptyStr]
    source_artifacts: list[SourceArtifactSpec]
    stages: list[CompositeTaskWorldStage]
    handoffs: list[HandoffSpec]
    branch_decisions: list[BranchDecisionSpec] = Field(default_factory=list)
    verifier_gates: list[VerifierGateSpec]
    deliverables: list[DeliverableSpec]
    data_gaps: list[DataGapSpec]
    subset_axes: list[NonEmptyStr] = Field(default_factory=lambda: ["discipline_scope", "data_gaps"])
    difference_axes: list[NonEmptyStr] = Field(default_factory=lambda: ["verifier_gates", "source_artifacts"])
    projection_axes: list[NonEmptyStr] = Field(default_factory=lambda: ["source_pack", "stage_graph", "verifier_gates"])
    product_axes: list[NonEmptyStr] = Field(default_factory=lambda: ["handoff_chain", "discipline_interface"])

    @property
    def world_id(self) -> str:
        return f"aec.task_world.composite.{self.template_id}"

    def compile_task_world_profile(self) -> TaskWorldProfile:
        closure_gates = [
            ClosureGate(
                id=gate.id,
                evidence_key=f"gates.{gate.id}.passed",
                proposition=gate.proposition,
                expected=True,
                authority=gate.authority,
                failure_effect=gate.failure_effect,
            )
            for gate in self.verifier_gates
        ]
        construction_gates = [
            ConstructionGate(
                id=f"deliverable_{deliverable.id}",
                proposition=f"Deliverable manifest includes {deliverable.path}.",
                construction_required=[deliverable.path],
                failure_effect="The composite task-world package is incomplete.",
            )
            for deliverable in self.deliverables
        ]
        logic_profile = LogicProfile(
            closure_gates=closure_gates,
            construction_gates=construction_gates,
            agentic_review=AgenticReviewProfile(
                required=True,
                guidance=(
                    "Review the staged handoff chain, source references, and verifier "
                    "records before accepting the compiled task-world deliverable."
                ),
            ),
        )
        operation_profile = OperationProfile(
            subset_axes=self.subset_axes,
            difference_axes=self.difference_axes,
            projection_axes=self.projection_axes,
            product_axes=self.product_axes,
            extension_policy="Preserve handoff IDs, source artifact IDs, and gate IDs across variants.",
        )
        return TaskWorldProfile(
            world_id=self.world_id,
            name=self.name,
            task_unit="composite-task-world-template",
            logic_profile=logic_profile,
            operation_profile=operation_profile,
        )

    def compile_task_world_payload(self) -> dict[str, Any]:
        payload = self.compile_task_world_profile().model_dump(mode="json", exclude_none=True)
        payload.update(
            {
                "template_id": self.template_id,
                "summary": self.summary,
                "pattern": self.pattern,
                "discipline_scope": self.discipline_scope,
                "source_artifacts": [artifact.model_dump(mode="json") for artifact in self.source_artifacts],
                "stages": [stage.model_dump(mode="json") for stage in self.stages],
                "handoffs": [handoff.model_dump(mode="json") for handoff in self.handoffs],
                "branch_decisions": [decision.model_dump(mode="json") for decision in self.branch_decisions],
                "deliverables": [deliverable.model_dump(mode="json") for deliverable in self.deliverables],
                "data_gaps": [gap.model_dump(mode="json") for gap in self.data_gaps],
                "operation_handles": self.operation_handles(),
            }
        )
        return payload

    def operation_handles(self) -> dict[str, dict[str, Any]]:
        return {
            "source_pack": {
                "paths": ["source_artifacts"],
                "operation": "projection",
                "description": "Project the task to only the source evidence pack.",
            },
            "stage_graph": {
                "paths": ["stages"],
                "operation": "projection",
                "description": "Project the task to staged template dependencies.",
            },
            "handoff_chain": {
                "paths": ["handoffs"],
                "operation": "product",
                "description": "Compose upstream outputs into downstream inputs.",
            },
            "discipline_interface": {
                "paths": ["discipline_scope", "stages"],
                "operation": "product",
                "description": "Compose discipline-specific stages into one product workflow.",
            },
            "verifier_gates": {
                "paths": ["verifier_gates"],
                "operation": "difference",
                "description": "Compare verifier gate coverage across composite task-world variants.",
            },
            "data_gaps": {
                "paths": ["data_gaps"],
                "operation": "subset",
                "description": "Subset to gaps that block real-world execution.",
            },
        }

    def example_handoffs(self) -> dict[str, Any]:
        return {handoff.id: handoff.example_value for handoff in self.handoffs}

    def example_branch_decisions(self) -> dict[str, str]:
        return {decision.id: decision.selected_example for decision in self.branch_decisions}

    def expected_answer(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "world_id": self.world_id,
            "handoffs": self.example_handoffs(),
            "branch_decisions": self.example_branch_decisions(),
            "deliverables": [deliverable.path for deliverable in self.deliverables],
            "source_refs": [artifact.id for artifact in self.source_artifacts],
            "notes": (
                "Runnable example answer for contract verification; real instances require the recorded data gaps."
            ),
        }
