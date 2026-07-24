# ABOUTME: Resolves the SSC-03 model-selected intervention against immutable source packages.
# ABOUTME: Reuses the shared hydraulic calculation graph after a selection-bound source transition.

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from aec_bench.meta_harness.evidence_lifecycle_state import (
    LifecycleOperationActionRecord,
    LifecycleOperationDisposition,
    LifecycleOperationOutcome,
)
from aec_bench.meta_harness.evidence_request_protocol import EvidenceLifecycleError
from aec_bench.meta_harness.lifecycle_operation_protocol import (
    LifecycleOperationPlan,
    LifecycleOperationSourceContext,
)
from aec_bench.task_world_templates.contracts import LifecycleOperationSpec
from aec_bench.task_world_templates.hydraulics.identity import canonical_json_sha256
from aec_bench.task_world_templates.hydraulics.operations import (
    Ssc03HydraulicOperationResolver,
    _read_json,
    _source_context,
    _source_identity_payload,
    _write_json,
)

_SELECTION_CHECKPOINT_ID = "intervention_selection"
_SOURCE_OPERATION_ID = "source-intervention.selected"


class Ssc03HydraulicInterventionResolver(Ssc03HydraulicOperationResolver):
    """Resolve one archived bounded selection into the active hydraulic source."""

    def _configure_source_packages(self) -> None:
        self._problem = self.package_dir / str(self._manifest["problem_package_path"])
        raw_paths = self._manifest["intervention_package_paths"]
        if not isinstance(raw_paths, dict) or not raw_paths:
            raise EvidenceLifecycleError("intervention package paths are absent from the resolver manifest")
        self._interventions = {
            str(intervention_id): self.package_dir / str(path) for intervention_id, path in raw_paths.items()
        }

    def _source_packages(self) -> tuple[Path, ...]:
        return (self._problem, *(self._interventions[key] for key in sorted(self._interventions)))

    def _source_transition_operation_ids(self) -> frozenset[str]:
        return frozenset({_SOURCE_OPERATION_ID})

    def _source_transition_kinds(self) -> frozenset[str]:
        return frozenset({"activate_source_intervention"})

    def current_source(
        self,
        actions: Sequence[LifecycleOperationActionRecord],
    ) -> LifecycleOperationSourceContext:
        activated = next(
            (
                action
                for action in reversed(actions)
                if action.operation_id == _SOURCE_OPERATION_ID
                and action.operation_kind == "activate_source_intervention"
                and action.outcome == LifecycleOperationOutcome.COMPLETED
            ),
            None,
        )
        if activated is None:
            return _source_context(self._problem, revision_id="problem")
        intervention_id, _selection_sha256 = self._validated_selection()
        return _source_context(self._interventions[intervention_id], revision_id=intervention_id)

    def _plan_source_transition(
        self,
        operation: LifecycleOperationSpec,
        resolution: dict[str, Any],
        actions: Sequence[LifecycleOperationActionRecord],
        *,
        source_before: LifecycleOperationSourceContext,
    ) -> LifecycleOperationPlan:
        del actions
        if resolution.get("selection_checkpoint_id") != _SELECTION_CHECKPOINT_ID:
            raise EvidenceLifecycleError("intervention operation does not bind the selection checkpoint")
        intervention_id, selection_sha256 = self._validated_selection()
        source_after = _source_context(self._interventions[intervention_id], revision_id=intervention_id)
        payload = {
            "schema_version": "1",
            "operation_id": operation.operation_id,
            "kind": operation.kind,
            "selected_intervention_id": intervention_id,
            "selection_checkpoint_id": _SELECTION_CHECKPOINT_ID,
            "selection_submission_sha256": selection_sha256,
            "source_after": source_after.visible_source_state_sha256,
            "physical_source_after": source_after.physical_source_state_sha256,
        }
        return LifecycleOperationPlan(
            operation_id=operation.operation_id,
            operation_kind=operation.kind,
            disposition=LifecycleOperationDisposition.ACTIVATED,
            source_before=source_before,
            source_after=source_after,
            input_projection_sha256=canonical_json_sha256(payload),
            prerequisite_action_ids=(),
            model_visible_artifact_paths=("source-identity.json", "source-state.json"),
            payload=payload,
        )

    def _write_source_transition_artifacts(self, plan: LifecycleOperationPlan, artifact_dir: Path) -> None:
        _write_json(artifact_dir / "source-state.json", plan.source_after.source_state)
        identity = _source_identity_payload(plan.source_after)
        identity.update(
            {
                "selected_intervention_id": plan.payload["selected_intervention_id"],
                "selection_checkpoint_id": plan.payload["selection_checkpoint_id"],
                "selection_submission_sha256": plan.payload["selection_submission_sha256"],
            }
        )
        _write_json(artifact_dir / "source-identity.json", identity)

    def _validated_selection(self) -> tuple[str, str]:
        selection_path = self.run_dir / "episodes" / _SELECTION_CHECKPOINT_ID / "submission.json"
        if not selection_path.is_file():
            raise EvidenceLifecycleError("archived intervention selection is unavailable")
        selection = _read_json(selection_path)
        intervention_id = selection.get("selected_intervention_id")
        if not isinstance(intervention_id, str) or intervention_id not in self._interventions:
            raise EvidenceLifecycleError("archived intervention selection is not declared")
        selection_basis = selection.get("selection_basis")
        if not isinstance(selection_basis, str) or not selection_basis.strip():
            raise EvidenceLifecycleError("archived intervention selection basis is blank")
        problem = _source_context(self._problem, revision_id="problem")
        if selection.get("visible_source_state_sha256") != problem.visible_source_state_sha256:
            raise EvidenceLifecycleError("archived intervention selection does not bind the problem source")
        return intervention_id, hashlib.sha256(selection_path.read_bytes()).hexdigest()
