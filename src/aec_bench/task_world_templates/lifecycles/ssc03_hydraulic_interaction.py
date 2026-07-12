# ABOUTME: Materializes and validates the public SSC-03 hydraulic interaction lifecycle family.
# ABOUTME: Embeds immutable PR18 packages while keeping source resolvers and verifier answers host-owned.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aec_bench.task_world_templates.catalogue import get_template
from aec_bench.task_world_templates.contracts import CompositeTaskWorldTemplate, EvidenceCheckpointSpec
from aec_bench.task_world_templates.hydraulics import build_hydraulic_run_request, materialize_hydraulic_world
from aec_bench.task_world_templates.hydraulics.contracts import HydraulicSourceState
from aec_bench.task_world_templates.hydraulics.operations import Ssc03HydraulicOperationResolver
from aec_bench.task_world_templates.hydraulics.revisions import build_hydraulic_revision_source_state
from aec_bench.task_world_templates.hydraulics.worlds.ssc03_detention_network import build_source_state
from aec_bench.task_world_templates.lifecycles.ssc03_hydraulic_interaction_variants import (
    DEFAULT_VARIANT_ID,
    Ssc03HydraulicInteractionVariantSpec,
    get_ssc03_hydraulic_interaction_variant,
)

TEMPLATE_ID = "hydraulic-interaction-lifecycle-review"
LIFECYCLE_ID = "ssc03.hydraulic-interaction-lifecycle"


def build_ssc03_hydraulic_operation_resolver(
    package_dir: Path,
    run_dir: Path,
) -> Ssc03HydraulicOperationResolver:
    """Build the task-owned resolver for one validated interaction package."""
    validated_ssc03_hydraulic_interaction_variant(package_dir)
    return Ssc03HydraulicOperationResolver(package_dir, run_dir)


def materialize_ssc03_hydraulic_interaction_lifecycle(
    output_dir: Path,
    *,
    template: CompositeTaskWorldTemplate | None = None,
    variant_id: str | None = None,
) -> Path:
    """Materialize one deterministic three-checkpoint hydraulic interaction package."""
    output = Path(output_dir)
    template = template or get_template(TEMPLATE_ID)
    if template.template_id != TEMPLATE_ID or template.evidence_lifecycle is None:
        raise ValueError(f"unexpected hydraulic interaction template: {template.template_id}")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError(f"output directory must be empty: {output}")
    variant = get_ssc03_hydraulic_interaction_variant(variant_id or DEFAULT_VARIANT_ID)

    _write_json(output / "template.json", template.model_dump(mode="json"))
    _write_json(output / "world.json", template.compile_task_world_payload())
    _write_json(output / "lifecycle.json", template.evidence_lifecycle.model_dump(mode="json"))
    (output / "README.md").parent.mkdir(parents=True, exist_ok=True)
    (output / "README.md").write_text(_readme(), encoding="utf-8")
    for checkpoint_id, instruction in _instructions(template).items():
        path = output / "instructions" / f"{checkpoint_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(instruction, encoding="utf-8")
    for checkpoint_id, release in _releases(variant).items():
        path = output / "releases" / checkpoint_id / "notice.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(release, encoding="utf-8")

    baseline_source = build_source_state()
    revision_source = build_hydraulic_revision_source_state(variant.revision_id)
    materialize_hydraulic_world(
        baseline_source.world_id,
        output / "hidden" / "hydraulic" / "packages" / "baseline",
        source_state=baseline_source,
    )
    materialize_hydraulic_world(
        revision_source.world_id,
        output / "hidden" / "hydraulic" / "packages" / "revision",
        source_state=revision_source,
    )
    _write_json(output / "hidden" / "variant.json", variant.model_dump(mode="json"))
    _write_json(output / "hidden" / "lifecycle-operation-resolutions.json", _resolution_manifest(variant))
    return output


def validated_ssc03_hydraulic_interaction_variant(package_dir: Path) -> dict[str, Any]:
    """Validate variant identity and both embedded immutable PR18 source packages."""
    package = Path(package_dir)
    try:
        raw_variant = _read_json(package / "hidden" / "variant.json")
        variant = Ssc03HydraulicInteractionVariantSpec.model_validate(raw_variant)
        if variant != get_ssc03_hydraulic_interaction_variant(variant.variant_id):
            raise ValueError("registered variant mismatch")
        baseline_package = package / "hidden" / "hydraulic" / "packages" / "baseline"
        revision_package = package / "hidden" / "hydraulic" / "packages" / "revision"
        build_hydraulic_run_request(baseline_package, scenario_id="design-10yr")
        build_hydraulic_run_request(revision_package, scenario_id="design-10yr")
        baseline = HydraulicSourceState.model_validate(_read_json(baseline_package / "source" / "source-state.json"))
        revision = HydraulicSourceState.model_validate(_read_json(revision_package / "source" / "source-state.json"))
        if baseline != build_source_state() or revision != build_hydraulic_revision_source_state(variant.revision_id):
            raise ValueError("embedded hydraulic source mismatch")
        if _read_json(package / "hidden" / "lifecycle-operation-resolutions.json") != _resolution_manifest(variant):
            raise ValueError("operation resolution mismatch")
    except (OSError, ValueError, json.JSONDecodeError, KeyError) as exc:
        raise ValueError("hydraulic interaction variant identity does not match materialized content") from exc
    return variant.model_dump(mode="json")


def verify_ssc03_hydraulic_interaction_lifecycle(package_dir: Path, run_dir: Path) -> dict[str, Any]:
    """Verify operation lineage, physical evidence, propagation, readiness, and claim boundaries."""
    from aec_bench.task_world_templates.lifecycles.ssc03_hydraulic_interaction_verifier import (
        verify_hydraulic_interaction_lifecycle,
    )

    variant = validated_ssc03_hydraulic_interaction_variant(package_dir)
    return verify_hydraulic_interaction_lifecycle(
        package_dir,
        run_dir,
        variant_id=str(variant["variant_id"]),
    )


def _resolution_manifest(variant: Ssc03HydraulicInteractionVariantSpec) -> dict[str, Any]:
    operations = []
    for scenario_id in ("design-10yr", "major-100yr"):
        operations.extend(
            [
                {
                    "operation_id": f"hydrology.{scenario_id}",
                    "kind": "run_hydrology",
                    "scenario_id": scenario_id,
                },
                {
                    "operation_id": f"detention-outlet.{scenario_id}.declared-outlet",
                    "kind": "run_detention_outlet",
                    "scenario_id": scenario_id,
                    "option_id": "declared-outlet",
                },
                {
                    "operation_id": f"network-hgl.{scenario_id}.declared-tailwater",
                    "kind": "run_network_hgl",
                    "scenario_id": scenario_id,
                    "boundary_id": "declared-tailwater",
                },
            ]
        )
    operations.append(
        {
            "operation_id": "source-revision.current",
            "kind": "request_source_revision",
            "revision_id": variant.revision_id,
        }
    )
    return {
        "schema_version": "1",
        "lifecycle_id": LIFECYCLE_ID,
        "variant_id": variant.variant_id,
        "baseline_package_path": "hidden/hydraulic/packages/baseline",
        "revision_package_path": "hidden/hydraulic/packages/revision",
        "operations": sorted(operations, key=lambda item: item["operation_id"]),
    }


def _instructions(template: CompositeTaskWorldTemplate) -> dict[str, str]:
    claim = (
        "Do not describe these synthetic screening calculations as SWMM, authority approval, standards "
        "compliance, project design evidence, transfer, or continual learning."
    )
    assert template.evidence_lifecycle is not None
    checkpoints = {checkpoint.checkpoint_id: checkpoint for checkpoint in template.evidence_lifecycle.checkpoints}
    return {
        "baseline_analysis": (
            "# Baseline hydraulic analysis\n\nExecute the declared baseline hydrology, coupled detention/outlet, "
            "and HGL "
            "operations for both scenarios. Submit cumulative source-bound decisions. "
            f"{claim}\n\n{_submission_contract(checkpoints['baseline_analysis'])}"
        ),
        "revision_analysis": (
            "# Revision analysis\n\nActivate the declared revision, retain still-current evidence, "
            "recompute stale evidence, "
            f"and submit explicit supersession lineage. {claim}\n\n"
            f"{_submission_contract(checkpoints['revision_analysis'])}"
        ),
        "closeout_review": (
            "# Closeout review\n\nReconcile the selected run, report, memo, physical criteria, and readiness without "
            f"inventing missing evidence. {claim}\n\n"
            f"{_submission_contract(checkpoints['closeout_review'])}"
        ),
    }


def _submission_contract(checkpoint: EvidenceCheckpointSpec) -> str:
    top_level_fields = "\n".join(f"- `{field}`" for field in checkpoint.required_submission_fields)
    selected_operations = {
        "baseline_analysis": """Use `visible_source_state_sha256` from
`workspace/hydraulics/current-source.json`. `selected_operations` is the exact map from every required baseline
operation ID to the action ID returned for this checkpoint.
""",
        "revision_analysis": """Use `visible_source_state_sha256` from
`workspace/hydraulics/current-source.json`. `selected_operations` includes the source-revision action and every
required revision operation. Use each current-checkpoint action ID even when its outcome is `already_current`.
""",
        "closeout_review": """Use `visible_source_state_sha256` from
`workspace/hydraulics/current-source.json`. Execute no new operation at closeout. Preserve the revision checkpoint's
`selected_operations` map exactly.
""",
    }
    decisions = """`accepted_decisions` contains exactly one record for `design-10yr` and one for `major-100yr`.
Each record contains exactly `decision_id`, `scenario_id`, `hydrology_action_id`, `detention_action_id`,
`hgl_action_id`, `hydraulic_run_id`, `screening_outcome`, and `failed_criteria`. Use canonical computation action IDs
rather than an `already_current` wrapper. Use `criteria_met` or `criteria_not_met` for `screening_outcome`, and sort
`failed_criteria`.
"""
    checkpoint_contracts = {
        "baseline_analysis": (
            "Use `decision.<scenario>.baseline` decision IDs. No revision, supersession, run/report reference, or "
            "memo fields belong in this checkpoint.\n"
        ),
        "revision_analysis": (
            "Set `revision_id` to the activated public revision. Retain an unaffected decision byte-for-byte. For "
            "each affected scenario, use `decision.<scenario>.revision` for the replacement and add exactly one "
            "`supersession_lineage` record containing `scenario_id`, `superseded_decision_id`, and "
            "`replacement_decision_id`.\n"
        ),
        "closeout_review": """Preserve revision `selected_operations`, `accepted_decisions`, and
`supersession_lineage` exactly. `run_reference` and `report_reference` are two-entry maps keyed by scenario. Each run
entry contains exactly `selected_operation_action_id`, `canonical_detention_action_id`, `hydraulic_run_id`, and
`run_manifest_sha256`. Each report entry contains exactly `selected_operation_action_id`, `canonical_hgl_action_id`,
`hydraulic_run_id`, and `report_sha256`.

`memo` contains exactly these keys and no others:

- `visible_source_state_sha256`
- `run_reference`
- `report_reference`
- `decision_ids`
- `supersession_lineage`
- `readiness_decision`
- `claim_boundary`

`decision_ids` is the two-entry scenario-to-current-decision-ID map. The memo repeats the top-level reference maps,
supersession lineage, readiness decision, and claim boundary exactly.
""",
    }
    return f"""## Structured submission contract

Use exactly these top-level keys and no others:

{top_level_fields}

{selected_operations[checkpoint.checkpoint_id]}

{decisions}

{checkpoint_contracts[checkpoint.checkpoint_id]}

Use `screening_ready` only when every current scenario criterion passes; otherwise use `not_screening_ready`.
At every checkpoint, use this exact `claim_boundary` object:

```json
{{
  "evidence_class": "benchmark_owned_synthetic_screening",
  "solver_fidelity": "not_swmm_equivalent",
  "authority_status": "no_authority_approval",
  "standards_status": "no_standards_compliance_claim",
  "project_evidence_status": "not_project_design_evidence",
  "model_evidence_status": "no_model_performance_holdout_or_transfer_result",
  "learning_status": "no_post_training_or_continual_learning_result"
}}
```
"""


def _releases(variant: Ssc03HydraulicInteractionVariantSpec) -> dict[str, str]:
    return {
        "baseline_analysis": "The canonical public SSC-03 hydraulic source is available for bounded analysis.\n",
        "revision_analysis": (
            f"A public revision named `{variant.revision_id}` is available through the declared operation catalogue.\n"
        ),
        "closeout_review": "Prepare the final source-bound run, report, memo, and readiness record.\n",
    }


def _readme() -> str:
    return (
        "# SSC-03 Hydraulic Interaction Lifecycle\n\n"
        "This public calibration package connects host-owned bounded lifecycle operations to the deterministic "
        "PR18 hydraulic screening world. It contains no model result, provider call, private target, or project "
        "approval.\n"
    )


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload
