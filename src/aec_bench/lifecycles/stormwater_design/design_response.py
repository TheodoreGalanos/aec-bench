# ABOUTME: Materializes and validates the public stormwater design-response lifecycle.
# ABOUTME: Binds a prior structured selection to one exact hydraulic source transition.

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import UUID

from aec_bench.contracts.evidence_lifecycle import (
    ConditionalOperationSpec,
    EvidenceCheckpointSpec,
    EvidenceLifecycleSpec,
    LifecycleOperationSpec,
    LifecycleTaskMetadata,
)
from aec_bench.contracts.identity import EntityIdentity, EntityKey
from aec_bench.lifecycles.runtime.definition import (
    LifecycleDefinition,
    LifecycleOwnerDescriptor,
    shared_executable_source_roots,
)
from aec_bench.lifecycles.runtime.episode import LifecycleEpisodeEnvironment
from aec_bench.lifecycles.stormwater_design.hydraulics.interventions import (
    build_hydraulic_intervention_source_state,
    build_hydraulic_problem_source_state,
    get_hydraulic_intervention,
    list_hydraulic_intervention_ids,
)
from aec_bench.lifecycles.stormwater_design.hydraulics.models import HydraulicSourceState
from aec_bench.lifecycles.stormwater_design.hydraulics.package import (
    build_hydraulic_run_request,
    materialize_hydraulic_package,
)

TEMPLATE_ID = "hydraulic-design-response-lifecycle-review"
LIFECYCLE_ID = "hydraulic-design-response"
METADATA = LifecycleTaskMetadata(
    identity=EntityIdentity(
        id=UUID("01a056f1-af83-730c-8202-7d9e49df1fc2"),
        key=EntityKey("stormwater/hydraulic-design-response"),
        version=1,
    ),
    template_id=TEMPLATE_ID,
    name="Hydraulic Design Response Lifecycle Review",
    discipline="civil",
)


def _calculation_operations(source_prerequisites: tuple[str, ...] = ()) -> list[LifecycleOperationSpec]:
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


def _intervention_operations() -> ConditionalOperationSpec:
    operation_id = "source-intervention.selected"
    operations = [
        LifecycleOperationSpec(
            operation_id=operation_id,
            kind="activate_source_intervention",
            title="Activate the selected source intervention",
            description="Activate only the bounded intervention archived at the prior selection checkpoint.",
        ),
        *_calculation_operations((operation_id,)),
    ]
    return ConditionalOperationSpec(operation_budget=len(operations), operations=tuple(operations))


LIFECYCLE = EvidenceLifecycleSpec(
    lifecycle_id=LIFECYCLE_ID,
    checkpoints=[
        EvidenceCheckpointSpec(
            checkpoint_id="problem_analysis",
            title="Issued hydraulic problem analysis",
            release_path="releases/problem_analysis",
            instruction_path="instructions/problem_analysis.md",
            submission_path="submissions/problem_analysis.json",
            required_submission_fields=[
                "checkpoint_id",
                "visible_source_state_sha256",
                "selected_operations",
                "accepted_decisions",
                "readiness_decision",
                "claim_boundary",
            ],
            allow_additional_submission_fields=False,
            conditional_operations=ConditionalOperationSpec(
                operation_budget=6,
                operations=tuple(_calculation_operations()),
            ),
        ),
        EvidenceCheckpointSpec(
            checkpoint_id="intervention_selection",
            title="Bounded intervention selection",
            release_path="releases/intervention_selection",
            instruction_path="instructions/intervention_selection.md",
            submission_path="submissions/intervention_selection.json",
            depends_on=["problem_analysis"],
            required_submission_fields=[
                "checkpoint_id",
                "visible_source_state_sha256",
                "selected_intervention_id",
                "selection_basis",
                "claim_boundary",
            ],
            allow_additional_submission_fields=False,
        ),
        EvidenceCheckpointSpec(
            checkpoint_id="intervention_analysis",
            title="Selected intervention analysis",
            release_path="releases/intervention_analysis",
            instruction_path="instructions/intervention_analysis.md",
            submission_path="submissions/intervention_analysis.json",
            depends_on=["intervention_selection"],
            required_submission_fields=[
                "checkpoint_id",
                "selected_intervention_id",
                "visible_source_state_sha256",
                "selected_operations",
                "accepted_decisions",
                "supersession_lineage",
                "readiness_decision",
                "claim_boundary",
            ],
            allow_additional_submission_fields=False,
            conditional_operations=_intervention_operations(),
        ),
        EvidenceCheckpointSpec(
            checkpoint_id="closeout_review",
            title="Hydraulic design-response closeout",
            release_path="releases/closeout_review",
            instruction_path="instructions/closeout_review.md",
            submission_path="submissions/closeout_review.json",
            depends_on=["intervention_analysis"],
            required_submission_fields=[
                "checkpoint_id",
                "selected_intervention_id",
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


def build_hydraulic_design_response_resolver(package_dir: Path, run_dir: Path) -> Any:
    """Build the task-owned resolver for one validated design-response package."""
    from aec_bench.lifecycles.stormwater_design.design_response_operations import (
        HydraulicDesignResponseResolver,
    )

    validated_hydraulic_design_response_package(package_dir)
    return HydraulicDesignResponseResolver(package_dir, run_dir)


def materialize_hydraulic_design_response_lifecycle(
    output_dir: Path,
) -> Path:
    """Materialize one deterministic four-checkpoint design-response package."""
    output = Path(output_dir)
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError(f"output directory must be empty: {output}")

    _write_json(output / "template.json", METADATA.model_dump(mode="json"))
    _write_json(output / "lifecycle.json", LIFECYCLE.model_dump(mode="json"))
    (output / "README.md").parent.mkdir(parents=True, exist_ok=True)
    (output / "README.md").write_text(_readme(), encoding="utf-8")
    for checkpoint_id, instruction in _instructions().items():
        path = output / "instructions" / f"{checkpoint_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(instruction, encoding="utf-8")
    for checkpoint_id, notice in _release_notices().items():
        path = output / "releases" / checkpoint_id / "notice.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(notice, encoding="utf-8")

    public_catalogue = _public_intervention_catalogue()
    _write_json(
        output / "releases" / "intervention_selection" / "interventions.json",
        public_catalogue,
    )
    problem = build_hydraulic_problem_source_state()
    materialize_hydraulic_package(
        problem,
        output / "hidden" / "hydraulic" / "packages" / "problem",
    )
    for intervention_id in list_hydraulic_intervention_ids():
        source = build_hydraulic_intervention_source_state(intervention_id)
        materialize_hydraulic_package(
            source,
            output / "hidden" / "hydraulic" / "packages" / "interventions" / intervention_id,
        )
    _write_json(
        output / "hidden" / "lifecycle-operation-resolutions.json",
        _resolution_manifest(public_catalogue),
    )
    return output


def validated_hydraulic_design_response_package(package_dir: Path) -> dict[str, Any]:
    """Validate the public catalogue, operation map, and every immutable source package."""
    package = Path(package_dir)
    intervention_ids = list_hydraulic_intervention_ids()
    try:
        if _read_json(package / "template.json") != METADATA.model_dump(mode="json"):
            raise ValueError("template mismatch")
        if _read_json(package / "lifecycle.json") != LIFECYCLE.model_dump(mode="json"):
            raise ValueError("lifecycle mismatch")
        public_catalogue = _read_json(package / "releases" / "intervention_selection" / "interventions.json")
        if public_catalogue != _public_intervention_catalogue():
            raise ValueError("public intervention catalogue mismatch")
        problem_package = package / "hidden" / "hydraulic" / "packages" / "problem"
        build_hydraulic_run_request(problem_package, scenario_id="design-10yr")
        problem = HydraulicSourceState.model_validate(_read_json(problem_package / "source" / "source-state.json"))
        if problem != build_hydraulic_problem_source_state():
            raise ValueError("problem source mismatch")
        for intervention_id in intervention_ids:
            option_package = package / "hidden" / "hydraulic" / "packages" / "interventions" / intervention_id
            build_hydraulic_run_request(option_package, scenario_id="design-10yr")
            source = HydraulicSourceState.model_validate(_read_json(option_package / "source" / "source-state.json"))
            if source != build_hydraulic_intervention_source_state(intervention_id):
                raise ValueError("intervention source mismatch")
        if _read_json(package / "hidden" / "lifecycle-operation-resolutions.json") != _resolution_manifest(
            public_catalogue
        ):
            raise ValueError("operation resolution mismatch")
    except (OSError, ValueError, json.JSONDecodeError, KeyError, AssertionError) as exc:
        raise ValueError("hydraulic intervention package identity does not match materialized content") from exc
    return {
        "schema_version": "1",
        "template_id": TEMPLATE_ID,
        "lifecycle_id": LIFECYCLE_ID,
        "intervention_ids": list(intervention_ids),
        "public_catalogue_sha256": _canonical_json_sha256(public_catalogue),
    }


def verify_hydraulic_design_response_lifecycle(package_dir: Path, run_dir: Path) -> dict[str, Any]:
    """Verify selection, source transition, calculations, decisions, and closeout."""
    from aec_bench.lifecycles.stormwater_design.design_response_verifier import (
        verify_hydraulic_intervention_lifecycle,
    )

    validated_hydraulic_design_response_package(package_dir)
    return verify_hydraulic_intervention_lifecycle(package_dir, run_dir)


def _public_intervention_catalogue() -> dict[str, Any]:
    return {
        "schema_version": "1",
        "selection_rule": (
            "Select exactly one declared intervention from the issued descriptions before its calculated "
            "hydraulic consequences are exposed."
        ),
        "interventions": [
            get_hydraulic_intervention(intervention_id).model_dump(mode="json")
            for intervention_id in list_hydraulic_intervention_ids()
        ],
    }


def _resolution_manifest(public_catalogue: dict[str, Any]) -> dict[str, Any]:
    operations: list[dict[str, Any]] = [
        {
            "operation_id": "source-intervention.selected",
            "kind": "activate_source_intervention",
            "selection_checkpoint_id": "intervention_selection",
        }
    ]
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
                    "option_id": "selected-intervention-outlet",
                },
                {
                    "operation_id": f"network-hgl.{scenario_id}.declared-tailwater",
                    "kind": "run_network_hgl",
                    "scenario_id": scenario_id,
                    "boundary_id": "declared-tailwater",
                },
            ]
        )
    return {
        "schema_version": "1",
        "lifecycle_id": LIFECYCLE_ID,
        "problem_package_path": "hidden/hydraulic/packages/problem",
        "intervention_package_paths": {
            intervention_id: f"hidden/hydraulic/packages/interventions/{intervention_id}"
            for intervention_id in list_hydraulic_intervention_ids()
        },
        "public_catalogue_sha256": _canonical_json_sha256(public_catalogue),
        "operations": sorted(operations, key=lambda item: item["operation_id"]),
    }


def _instructions() -> dict[str, str]:
    checkpoints = {checkpoint.checkpoint_id: checkpoint for checkpoint in LIFECYCLE.checkpoints}
    claim = (
        "Do not describe these synthetic screening calculations as SWMM, authority approval, standards "
        "compliance, project design evidence, model transfer, post-training, or continual learning."
    )
    return {
        "problem_analysis": (
            "# Issued hydraulic problem\n\nRun both declared scenario chains and diagnose the current physical "
            "criteria. "
            f"{claim}\n\n{_submission_contract(checkpoints['problem_analysis'])}"
        ),
        "intervention_selection": (
            "# Bounded intervention selection\n\nRead `interventions.json` and select exactly one intervention before "
            "its calculated outcomes are available. Preserve the current source hash and give a concise engineering "
            f"basis for the selection. {claim}\n\n{_submission_contract(checkpoints['intervention_selection'])}"
        ),
        "intervention_analysis": (
            "# Selected intervention analysis\n\nActivate the archived selection, retain current hydrology, recompute "
            "outlet-dependent evidence, and replace both source-bound decisions. Report failure honestly if the "
            f"selected option remains inadequate. {claim}\n\n"
            f"{_submission_contract(checkpoints['intervention_analysis'])}"
        ),
        "closeout_review": (
            "# Design-response closeout\n\nExecute no new operations. Reconcile the selected intervention, source, "
            "runs, reports, decisions, replacement lineage, readiness, and claim boundary in the final memo. "
            f"{claim}\n\n{_submission_contract(checkpoints['closeout_review'])}"
        ),
    }


def _submission_contract(checkpoint: EvidenceCheckpointSpec) -> str:
    fields = "\n".join(f"- `{field}`" for field in checkpoint.required_submission_fields)
    return f"""## Structured submission contract

Use exactly these top-level keys and no others:

{fields}

Use the exact IDs and source hashes exposed by the host. `selection_basis` is a non-empty concise explanation, not
an authority claim. `accepted_decisions` contains exactly the design and major scenarios. Use `screening_ready` only
when all current criteria pass; otherwise use `not_screening_ready`. The closeout `memo` must repeat the selected
intervention, source, run and report references, decision IDs, supersession lineage, readiness, and claim boundary.
"""


def _release_notices() -> dict[str, str]:
    return {
        "problem_analysis": "The issued major-rainfall source is active. Diagnose it before selecting a response.\n",
        "intervention_selection": (
            "The public intervention catalogue is available. Calculated option outcomes remain unavailable.\n"
        ),
        "intervention_analysis": "The host can now activate only the intervention archived at selection.\n",
        "closeout_review": "No new hydraulic operation is permitted at closeout.\n",
    }


def _readme() -> str:
    return """# Stormwater Hydraulic Design Response Lifecycle

This public successor task starts from a checked hydraulic problem, asks the reviewer to choose one of two bounded
source interventions, and makes that selection control the later physical source. The model cannot supply arbitrary
geometry or hidden paths. A task-owned verifier independently checks the resulting calculations and closeout.

This is a deterministic synthetic screening task, not project design evidence, post-training, or continual learning.
"""


def _canonical_json_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _build_smoke_environment(package_dir: Path) -> LifecycleEpisodeEnvironment:
    from aec_bench.lifecycles.stormwater_design.design_response_smoke import (
        build_hydraulic_design_response_smoke_environment,
    )

    return build_hydraulic_design_response_smoke_environment(package_dir)


LIFECYCLE_DESCRIPTOR = LifecycleOwnerDescriptor(
    definition=LifecycleDefinition(
        metadata=METADATA,
        lifecycle=LIFECYCLE,
        materializer=materialize_hydraulic_design_response_lifecycle,
        verifier=verify_hydraulic_design_response_lifecycle,
        executable_source_roots=(
            *shared_executable_source_roots(),
            Path(__file__).resolve().parent / "__init__.py",
            Path(__file__).resolve(),
            Path(__file__).resolve().parent / "design_response_smoke.py",
            Path(__file__).resolve().parent / "hydraulic_smoke.py",
            Path(__file__).resolve().parent / "design_response_operations.py",
            Path(__file__).resolve().parent / "design_response_verifier.py",
            Path(__file__).resolve().parent / "hydraulic_evidence.py",
            Path(__file__).resolve().parent / "hydraulic_operations.py",
            Path(__file__).resolve().parent / "hydraulics",
        ),
        operation_resolver=build_hydraulic_design_response_resolver,
        smoke_environment=_build_smoke_environment,
    ),
    conformance_entry_point=(
        "aec_bench.lifecycles.stormwater_design.design_response_conformance:"
        "lifecycle_conformance_case"
    ),
)
