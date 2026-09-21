# ABOUTME: Resolves readable hydraulic evidence choices against host-owned operation records.
# ABOUTME: Keeps hashes, action IDs, run references, and repeated memo fields out of actor submissions.

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal

from aec_bench.contracts.validators import NonEmptyStr, StrictModel
from aec_bench.lifecycles.runtime.operation_protocol import LifecycleOperationResolver
from aec_bench.lifecycles.runtime.state import LifecycleOperationActionRecord, LifecycleOperationOutcome
from aec_bench.lifecycles.stormwater_design.hydraulic_evidence import (
    CLAIM_BOUNDARY,
    ClaimBoundary,
    ReadinessDecision,
    ScenarioEvidence,
    ScenarioId,
    load_scenario_evidence,
)


class ScenarioAssessment(StrictModel):
    scenario_id: ScenarioId
    evidence_checkpoint: NonEmptyStr
    screening_outcome: Literal["criteria_met", "criteria_not_met"]
    failed_criteria: tuple[NonEmptyStr, ...]


class HydraulicAssessment(StrictModel):
    checkpoint_id: NonEmptyStr
    source_revision: NonEmptyStr
    accepted_decisions: tuple[ScenarioAssessment, ...] = ()
    superseded_scenarios: tuple[ScenarioId, ...] = ()
    evidence_checkpoint: NonEmptyStr | None = None
    readiness_decision: ReadinessDecision | None = None
    claim_boundary: ClaimBoundary
    selected_intervention_id: NonEmptyStr | None = None
    selection_basis: NonEmptyStr | None = None


def bind_hydraulic_submissions(
    package: Path,
    run: Path,
    submissions: dict[str, Any],
    actions: Sequence[LifecycleOperationActionRecord],
    resolver: LifecycleOperationResolver,
) -> dict[str, dict[str, Any]]:
    """Resolve actor references without selecting evidence or changing engineering conclusions."""
    assessments = {key: HydraulicAssessment.model_validate(value) for key, value in submissions.items()}
    selected: dict[str, dict[str, LifecycleOperationActionRecord]] = {}
    initial_source = resolver.current_source([])
    source_hashes = {initial_source.revision_id: initial_source.visible_source_state_sha256}
    prefix: list[LifecycleOperationActionRecord] = []
    for action in sorted(actions, key=lambda item: item.sequence):
        prefix.append(action)
        source = resolver.current_source(prefix)
        source_hashes[source.revision_id] = source.visible_source_state_sha256
        if action.outcome in {LifecycleOperationOutcome.COMPLETED, LifecycleOperationOutcome.ALREADY_CURRENT}:
            selected.setdefault(action.checkpoint_id, {})[action.operation_id] = action

    evidence: dict[str, dict[str, ScenarioEvidence]] = {}
    for checkpoint_id, choices in selected.items():
        evidence[checkpoint_id], _failures = load_scenario_evidence(package, run, choices)

    bound: dict[str, dict[str, Any]] = {}
    initial = "problem_analysis" if "problem_analysis" in assessments else "baseline_analysis"
    revised = "intervention_analysis" if initial == "problem_analysis" else "revision_analysis"
    order = list(assessments)
    for checkpoint_id, assessment in assessments.items():
        if assessment.source_revision not in source_hashes:
            raise ValueError(f"unknown released source revision: {assessment.source_revision}")
        result: dict[str, Any] = {
            "checkpoint_id": checkpoint_id,
            "visible_source_state_sha256": source_hashes[assessment.source_revision],
            "claim_boundary": assessment.claim_boundary.model_dump(mode="json"),
        }
        if assessment.selected_intervention_id is not None:
            result["selected_intervention_id"] = assessment.selected_intervention_id
        if checkpoint_id == "intervention_selection":
            result["selection_basis"] = assessment.selection_basis
            bound[checkpoint_id] = result
            continue
        if checkpoint_id == "revision_analysis":
            result["revision_id"] = assessment.source_revision
        result["readiness_decision"] = assessment.readiness_decision
        evidence_checkpoint = assessment.evidence_checkpoint if checkpoint_id == "closeout_review" else checkpoint_id
        if evidence_checkpoint not in selected:
            raise ValueError(f"no calculation evidence for checkpoint: {evidence_checkpoint}")
        result["selected_operations"] = {key: action.action_id for key, action in selected[evidence_checkpoint].items()}
        decisions: list[dict[str, Any]] = []
        for decision in assessment.accepted_decisions:
            chosen = decision.evidence_checkpoint
            if chosen not in order or order.index(chosen) > order.index(checkpoint_id):
                raise ValueError(f"evidence checkpoint is not yet available: {chosen}")
            item = evidence.get(chosen, {}).get(decision.scenario_id)
            if item is None:
                raise ValueError(f"no scenario evidence for {chosen}: {decision.scenario_id}")
            decisions.append(
                {
                    "decision_id": f"decision.{decision.scenario_id}.{chosen.removesuffix('_analysis')}",
                    "scenario_id": decision.scenario_id,
                    "hydrology_action_id": item.hydrology_action_id,
                    "detention_action_id": item.detention_action_id,
                    "hgl_action_id": item.hgl_action_id,
                    "hydraulic_run_id": item.hydraulic_run_id,
                    "screening_outcome": decision.screening_outcome,
                    "failed_criteria": list(decision.failed_criteria),
                }
            )
        result["accepted_decisions"] = decisions
        if checkpoint_id in {revised, "closeout_review"}:
            result["supersession_lineage"] = [
                {
                    "scenario_id": scenario,
                    "superseded_decision_id": f"decision.{scenario}.{initial.removesuffix('_analysis')}",
                    "replacement_decision_id": f"decision.{scenario}.{revised.removesuffix('_analysis')}",
                }
                for scenario in assessment.superseded_scenarios
            ]
        if checkpoint_id == "closeout_review":
            references = evidence[evidence_checkpoint]
            result["run_reference"] = {
                key: item.run_reference.model_dump(mode="json") for key, item in references.items()
            }
            result["report_reference"] = {
                key: item.report_reference.model_dump(mode="json") for key, item in references.items()
            }
            result["memo"] = {
                key: result[key]
                for key in (
                    "run_reference",
                    "report_reference",
                    "supersession_lineage",
                    "readiness_decision",
                    "claim_boundary",
                )
            }
            result["memo"]["decision_ids"] = {item["scenario_id"]: item["decision_id"] for item in decisions}
            if assessment.selected_intervention_id is not None:
                result["memo"]["selected_intervention_id"] = assessment.selected_intervention_id
        bound[checkpoint_id] = result
    return bound


def hydraulic_submission_contract(fields: list[str]) -> str:
    """Describe the actor contract shared by both hydraulic lifecycles."""
    keys = "\n".join(f"- `{field}`" for field in fields if field != "checkpoint_id")
    return f"""## Structured submission contract

Supply these top-level keys. The host supplies `checkpoint_id`:

{keys}

`source_revision` is the readable `revision_id` in `operations/current-source.json`.
The host owns source hashes, action IDs, run identities,
artifact hashes, and the reference maps in the evidence record. Do not copy them into the submission.

Where required, `accepted_decisions` contains one record for `design-10yr` and one for `major-100yr`.
Each record has exactly `scenario_id`, `evidence_checkpoint`, `screening_outcome`, and `failed_criteria`.
Choose the analysis checkpoint whose evidence supports the decision. Retain the earlier checkpoint
for an unaffected decision; choose the revised analysis for a replacement. Use `criteria_met` or
`criteria_not_met` and a sorted list of failed criterion names. The host does not choose the evidence
checkpoint or correct these conclusions.

`superseded_scenarios` lists the scenarios whose earlier decisions you replace, in scenario order.
At closeout, `evidence_checkpoint` selects the analysis checkpoint for the final runs and reports.
Use `screening_ready` only when all current criteria pass; otherwise use `not_screening_ready`.
Keep the declared `claim_boundary`. Where required, `selected_intervention_id` names your chosen
intervention and `selection_basis` explains the engineering reason for that choice.

At every checkpoint, use this exact `claim_boundary` object:

```json
{json.dumps(CLAIM_BOUNDARY, indent=2)}
```
"""
