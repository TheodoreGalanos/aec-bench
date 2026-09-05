# ABOUTME: Materializes and validates the public stormwater hydraulic-review lifecycle.
# ABOUTME: Embeds immutable calculation sources while keeping verifier answers host-owned.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

import aec_bench.lifecycles.stormwater_design.hydraulic_review_variants as hydraulic_review_variants
from aec_bench.contracts.evidence_lifecycle import (
    ConditionalOperationSpec,
    EvidenceCheckpointSpec,
    EvidenceLifecycleSpec,
    LifecycleOperationSpec,
    LifecycleTaskMetadata,
)
from aec_bench.contracts.identity import EntityIdentity, EntityKey, MemberIdentity
from aec_bench.lifecycles.runtime.definition import (
    LifecycleDefinition,
    LifecycleOwnerDescriptor,
    shared_executable_source_roots,
)
from aec_bench.lifecycles.runtime.episode import LifecycleEpisodeEnvironment
from aec_bench.lifecycles.stormwater_design.hydraulic_operations import HydraulicOperationResolver
from aec_bench.lifecycles.stormwater_design.hydraulic_review_variants import (
    DEFAULT_VARIANT_ID,
    HydraulicReviewVariantSpec,
    get_hydraulic_review_variant,
)
from aec_bench.lifecycles.stormwater_design.hydraulics.lineages import HydraulicLineage
from aec_bench.lifecycles.stormwater_design.hydraulics.models import HydraulicSourceState
from aec_bench.lifecycles.stormwater_design.hydraulics.package import (
    build_hydraulic_run_request,
    materialize_hydraulic_package,
)
from aec_bench.lifecycles.stormwater_design.hydraulics.revisions import build_hydraulic_revision_source_state
from aec_bench.lifecycles.stormwater_design.hydraulics.source import build_source_state

TEMPLATE_ID = "hydraulic-interaction-lifecycle-review"
LIFECYCLE_ID = "hydraulic-interaction-review"
METADATA = LifecycleTaskMetadata(
    identity=EntityIdentity(
        id=UUID("01a056f1-af83-7ae7-81a4-d310477fe4f1"),
        key=EntityKey("stormwater/hydraulic-interaction-review"),
        version=1,
    ),
    template_id=TEMPLATE_ID,
    name="Hydraulic Interaction Lifecycle Review",
    discipline="civil",
)


def _calculation_operations(*, source_prerequisites: tuple[str, ...] = ()) -> list[LifecycleOperationSpec]:
    operations: list[LifecycleOperationSpec] = []
    for scenario_id, title in (("design-10yr", "design"), ("major-100yr", "major")):
        operations.append(
            LifecycleOperationSpec(
                operation_id=f"hydrology.{scenario_id}",
                kind="run_hydrology",
                title=f"Run {title}-scenario hydrology",
                description="Calculate bounded Rational Method hydrology for the declared scenario.",
                prerequisite_operation_ids=source_prerequisites,
            )
        )
    for scenario_id, title in (("design-10yr", "design"), ("major-100yr", "major")):
        operations.append(
            LifecycleOperationSpec(
                operation_id=f"detention-outlet.{scenario_id}.declared-outlet",
                kind="run_detention_outlet",
                title=f"Run {title}-scenario coupled detention and outlet analysis",
                description="Execute the declared coupled basin, outlet, and downstream network calculation.",
                prerequisite_operation_ids=source_prerequisites + (f"hydrology.{scenario_id}",),
            )
        )
    for scenario_id, title in (("design-10yr", "design"), ("major-100yr", "major")):
        operations.append(
            LifecycleOperationSpec(
                operation_id=f"network-hgl.{scenario_id}.declared-tailwater",
                kind="run_network_hgl",
                title=f"Project {title}-scenario network HGL",
                description="Project HGL evidence from the exact coupled run at the declared boundary.",
                prerequisite_operation_ids=source_prerequisites + (f"detention-outlet.{scenario_id}.declared-outlet",),
            )
        )
    return operations


def _operations(*, include_revision: bool) -> ConditionalOperationSpec:
    operations: list[LifecycleOperationSpec] = []
    source_prerequisites: tuple[str, ...] = ()
    if include_revision:
        operations.append(
            LifecycleOperationSpec(
                operation_id="source-revision.current",
                kind="request_source_revision",
                title="Activate the declared source revision",
                description="Activate the one public source revision bound to this calibration package.",
            )
        )
        source_prerequisites = ("source-revision.current",)
    operations.extend(_calculation_operations(source_prerequisites=source_prerequisites))
    return ConditionalOperationSpec(operation_budget=len(operations), operations=tuple(operations))


LIFECYCLE = EvidenceLifecycleSpec(
    lifecycle_id=LIFECYCLE_ID,
    checkpoints=[
        EvidenceCheckpointSpec(
            checkpoint_id="baseline_analysis",
            title="Baseline hydraulic analysis",
            release_path="releases/baseline_analysis",
            instruction_path="instructions/baseline_analysis.md",
            submission_path="submissions/baseline_analysis.json",
            required_submission_fields=[
                "checkpoint_id",
                "visible_source_state_sha256",
                "selected_operations",
                "accepted_decisions",
                "readiness_decision",
                "claim_boundary",
            ],
            allow_additional_submission_fields=False,
            conditional_operations=_operations(include_revision=False),
        ),
        EvidenceCheckpointSpec(
            checkpoint_id="revision_analysis",
            title="Revision hydraulic analysis",
            release_path="releases/revision_analysis",
            instruction_path="instructions/revision_analysis.md",
            submission_path="submissions/revision_analysis.json",
            depends_on=["baseline_analysis"],
            required_submission_fields=[
                "checkpoint_id",
                "revision_id",
                "visible_source_state_sha256",
                "selected_operations",
                "accepted_decisions",
                "supersession_lineage",
                "readiness_decision",
                "claim_boundary",
            ],
            allow_additional_submission_fields=False,
            conditional_operations=_operations(include_revision=True),
        ),
        EvidenceCheckpointSpec(
            checkpoint_id="closeout_review",
            title="Hydraulic interaction closeout",
            release_path="releases/closeout_review",
            instruction_path="instructions/closeout_review.md",
            submission_path="submissions/closeout_review.json",
            depends_on=["revision_analysis"],
            required_submission_fields=[
                "checkpoint_id",
                "visible_source_state_sha256",
                "selected_operations",
                "run_reference",
                "report_reference",
                "memo",
                "accepted_decisions",
                "supersession_lineage",
                "readiness_decision",
                "claim_boundary",
            ],
            allow_additional_submission_fields=False,
        ),
    ],
)


def build_hydraulic_operation_resolver(
    package_dir: Path,
    run_dir: Path,
) -> HydraulicOperationResolver:
    """Build the task-owned resolver for one validated interaction package."""
    validated_hydraulic_review_variant(package_dir)
    return HydraulicOperationResolver(package_dir, run_dir)


def materialize_hydraulic_review_lifecycle(
    output_dir: Path,
    *,
    variant_id: str | None = None,
    lineage: HydraulicLineage | None = None,
) -> Path:
    """Materialize one deterministic three-checkpoint hydraulic interaction package."""
    output = Path(output_dir)
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError(f"output directory must be empty: {output}")
    variant = get_hydraulic_review_variant(variant_id or DEFAULT_VARIANT_ID)

    _write_json(output / "template.json", METADATA.model_dump(mode="json"))
    _write_json(output / "lifecycle.json", LIFECYCLE.model_dump(mode="json"))
    (output / "README.md").parent.mkdir(parents=True, exist_ok=True)
    (output / "README.md").write_text(_readme(), encoding="utf-8")
    for checkpoint_id, instruction in _instructions().items():
        path = output / "instructions" / f"{checkpoint_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(instruction, encoding="utf-8")
    for checkpoint_id, release in _releases(variant).items():
        path = output / "releases" / checkpoint_id / "notice.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(release, encoding="utf-8")

    baseline_source = build_source_state() if lineage is None else lineage.source()
    revision_source = (
        build_hydraulic_revision_source_state(variant.revision_id)
        if lineage is None
        else lineage.source(variant.revision_id)
    )
    if lineage is not None:
        _write_json(output / "hidden" / "lineage.json", lineage.model_dump(mode="json"))
    materialize_hydraulic_package(
        baseline_source,
        output / "hidden" / "hydraulic" / "packages" / "baseline",
    )
    materialize_hydraulic_package(
        revision_source,
        output / "hidden" / "hydraulic" / "packages" / "revision",
    )
    _write_json(output / "hidden" / "variant.json", variant.model_dump(mode="json"))
    _write_json(output / "hidden" / "lifecycle-operation-resolutions.json", _resolution_manifest(variant))
    return output


def validated_hydraulic_review_variant(package_dir: Path) -> dict[str, Any]:
    """Validate variant identity and both embedded immutable source packages."""
    package = Path(package_dir)
    try:
        raw_variant = _read_json(package / "hidden" / "variant.json")
        variant = HydraulicReviewVariantSpec.model_validate(raw_variant)
        if variant != get_hydraulic_review_variant(variant.variant_id):
            raise ValueError("registered variant mismatch")
        baseline_package = package / "hidden" / "hydraulic" / "packages" / "baseline"
        revision_package = package / "hidden" / "hydraulic" / "packages" / "revision"
        build_hydraulic_run_request(baseline_package, scenario_id="design-10yr")
        build_hydraulic_run_request(revision_package, scenario_id="design-10yr")
        baseline = HydraulicSourceState.model_validate(_read_json(baseline_package / "source" / "source-state.json"))
        revision = HydraulicSourceState.model_validate(_read_json(revision_package / "source" / "source-state.json"))
        lineage_path = package / "hidden" / "lineage.json"
        lineage = HydraulicLineage.model_validate(_read_json(lineage_path)) if lineage_path.exists() else None
        expected_baseline = build_source_state() if lineage is None else lineage.source()
        expected_revision = (
            build_hydraulic_revision_source_state(variant.revision_id)
            if lineage is None
            else lineage.source(variant.revision_id)
        )
        if baseline != expected_baseline or revision != expected_revision:
            raise ValueError("embedded hydraulic source mismatch")
        if _read_json(package / "hidden" / "lifecycle-operation-resolutions.json") != _resolution_manifest(variant):
            raise ValueError("operation resolution mismatch")
    except (OSError, ValueError, json.JSONDecodeError, KeyError) as exc:
        raise ValueError("hydraulic interaction variant identity does not match materialized content") from exc
    return variant.model_dump(mode="json")


def verify_hydraulic_review_lifecycle(package_dir: Path, run_dir: Path) -> dict[str, Any]:
    """Verify operation lineage, physical evidence, propagation, readiness, and claim boundaries."""
    from aec_bench.lifecycles.stormwater_design.hydraulic_review_verifier import (
        verify_hydraulic_interaction_lifecycle,
    )

    variant = validated_hydraulic_review_variant(package_dir)
    return verify_hydraulic_interaction_lifecycle(
        package_dir,
        run_dir,
        variant_id=str(variant["variant_id"]),
    )


def _resolution_manifest(variant: HydraulicReviewVariantSpec) -> dict[str, Any]:
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


def _instructions() -> dict[str, str]:
    claim = (
        "Do not describe these synthetic screening calculations as SWMM, authority approval, standards "
        "compliance, project design evidence, transfer, or continual learning."
    )
    checkpoints = {checkpoint.checkpoint_id: checkpoint for checkpoint in LIFECYCLE.checkpoints}
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
`workspace/operations/current-source.json`. `selected_operations` is the exact map from every required baseline
operation ID to the action ID returned for this checkpoint.
""",
        "revision_analysis": """Use `visible_source_state_sha256` from
`workspace/operations/current-source.json`. `selected_operations` includes the source-revision action and every
required revision operation. Use each current-checkpoint action ID even when its outcome is `already_current`.
""",
        "closeout_review": """Use `visible_source_state_sha256` from
`workspace/operations/current-source.json`. Execute no new operation at closeout. Preserve the revision checkpoint's
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


def _releases(variant: HydraulicReviewVariantSpec) -> dict[str, str]:
    return {
        "baseline_analysis": "The canonical stormwater hydraulic source is available for bounded analysis.\n",
        "revision_analysis": (
            f"A public revision named `{variant.revision_id}` is available through the declared operation catalogue.\n"
        ),
        "closeout_review": "Prepare the final source-bound run, report, memo, and readiness record.\n",
    }


def _readme() -> str:
    return (
        "# Stormwater Hydraulic Review Lifecycle\n\n"
        "This public calibration package connects host-owned bounded lifecycle operations to the deterministic "
        "stormwater hydraulic screening calculation. It contains no model result, provider call, private target, "
        "or project approval.\n"
    )


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _build_smoke_environment(package_dir: Path) -> LifecycleEpisodeEnvironment:
    from aec_bench.lifecycles.stormwater_design.hydraulic_review_smoke import (
        build_hydraulic_review_smoke_environment,
    )

    return build_hydraulic_review_smoke_environment(package_dir)


LIFECYCLE_DESCRIPTOR = LifecycleOwnerDescriptor(
    definition=LifecycleDefinition(
        metadata=METADATA,
        lifecycle=LIFECYCLE,
        materializer=materialize_hydraulic_review_lifecycle,
        verifier=verify_hydraulic_review_lifecycle,
        executable_source_roots=(
            *shared_executable_source_roots(),
            Path(__file__).resolve().parent / "__init__.py",
            Path(__file__).resolve(),
            Path(hydraulic_review_variants.__file__).resolve(),
            Path(__file__).resolve().parent / "hydraulic_review_smoke.py",
            Path(__file__).resolve().parent / "hydraulic_smoke.py",
            Path(__file__).resolve().parent / "hydraulic_evidence.py",
            Path(__file__).resolve().parent / "hydraulic_operations.py",
            Path(__file__).resolve().parent / "hydraulic_review_verifier.py",
            Path(__file__).resolve().parent / "hydraulics",
        ),
        variant_identities=tuple(
            MemberIdentity(
                id=UUID(identity_id),
                key=EntityKey(f"{METADATA.identity.key}/{variant_id}"),
                version=1,
                parent_id=METADATA.identity.id,
                registration_id=variant_id,
            )
            for variant_id, identity_id in (
                ("administrative_no_op", "01a056f1-af83-7517-a1d6-2796e1c0f075"),
                ("major_idf_revision", "01a056f1-af83-7f1a-8121-6d2800314a19"),
                ("outlet_geometry_revision", "01a056f1-af83-71a1-84e7-16ed7ec1fd69"),
                ("tailwater_revision", "01a056f1-af83-7eb1-920d-acc8734ecdd5"),
            )
        ),
        variant_validator=validated_hydraulic_review_variant,
        variant_ids=hydraulic_review_variants.list_hydraulic_review_variant_ids,
        variant_metadata=hydraulic_review_variants.get_hydraulic_review_variant,
        operation_resolver=build_hydraulic_operation_resolver,
        smoke_environment=_build_smoke_environment,
    ),
    conformance_entry_point=(
        "aec_bench.lifecycles.stormwater_design.hydraulic_review_conformance:lifecycle_conformance_case"
    ),
)
