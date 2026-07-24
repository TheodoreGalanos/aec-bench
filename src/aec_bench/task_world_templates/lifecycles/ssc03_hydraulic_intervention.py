# ABOUTME: Materializes and validates the public SSC-03 model-selected intervention lifecycle.
# ABOUTME: Binds a prior structured selection to one exact hydraulic source transition.

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from aec_bench.task_world_templates.catalogue import get_template
from aec_bench.task_world_templates.contracts import CompositeTaskWorldTemplate, EvidenceCheckpointSpec
from aec_bench.task_world_templates.hydraulics import build_hydraulic_run_request, materialize_hydraulic_world
from aec_bench.task_world_templates.hydraulics.contracts import HydraulicSourceState
from aec_bench.task_world_templates.hydraulics.interventions import (
    build_hydraulic_intervention_source_state,
    build_hydraulic_problem_source_state,
    get_hydraulic_intervention,
    list_hydraulic_intervention_ids,
)

TEMPLATE_ID = "hydraulic-design-response-lifecycle-review"
LIFECYCLE_ID = "ssc03.hydraulic-design-response-lifecycle"


def build_ssc03_hydraulic_intervention_resolver(package_dir: Path, run_dir: Path) -> Any:
    """Build the task-owned resolver for one validated design-response package."""
    from aec_bench.task_world_templates.hydraulics.intervention_operations import (
        Ssc03HydraulicInterventionResolver,
    )

    validated_ssc03_hydraulic_intervention_package(package_dir)
    return Ssc03HydraulicInterventionResolver(package_dir, run_dir)


def materialize_ssc03_hydraulic_intervention_lifecycle(
    output_dir: Path,
    *,
    template: CompositeTaskWorldTemplate | None = None,
) -> Path:
    """Materialize one deterministic four-checkpoint design-response package."""
    output = Path(output_dir)
    template = template or get_template(TEMPLATE_ID)
    if template.template_id != TEMPLATE_ID or template.evidence_lifecycle is None:
        raise ValueError(f"unexpected hydraulic intervention template: {template.template_id}")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError(f"output directory must be empty: {output}")

    _write_json(output / "template.json", template.model_dump(mode="json"))
    _write_json(output / "world.json", template.compile_task_world_payload())
    _write_json(output / "lifecycle.json", template.evidence_lifecycle.model_dump(mode="json"))
    (output / "README.md").parent.mkdir(parents=True, exist_ok=True)
    (output / "README.md").write_text(_readme(), encoding="utf-8")
    for checkpoint_id, instruction in _instructions(template).items():
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
    materialize_hydraulic_world(
        problem.world_id,
        output / "hidden" / "hydraulic" / "packages" / "problem",
        source_state=problem,
    )
    for intervention_id in list_hydraulic_intervention_ids():
        source = build_hydraulic_intervention_source_state(intervention_id)
        materialize_hydraulic_world(
            source.world_id,
            output / "hidden" / "hydraulic" / "packages" / "interventions" / intervention_id,
            source_state=source,
        )
    _write_json(
        output / "hidden" / "lifecycle-operation-resolutions.json",
        _resolution_manifest(public_catalogue),
    )
    return output


def validated_ssc03_hydraulic_intervention_package(package_dir: Path) -> dict[str, Any]:
    """Validate the public catalogue, operation map, and every immutable source package."""
    package = Path(package_dir)
    intervention_ids = list_hydraulic_intervention_ids()
    try:
        template = get_template(TEMPLATE_ID)
        if _read_json(package / "template.json") != template.model_dump(mode="json"):
            raise ValueError("template mismatch")
        assert template.evidence_lifecycle is not None
        if _read_json(package / "lifecycle.json") != template.evidence_lifecycle.model_dump(mode="json"):
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


def verify_ssc03_hydraulic_intervention_lifecycle(package_dir: Path, run_dir: Path) -> dict[str, Any]:
    """Verify selection, source transition, calculations, decisions, and closeout."""
    from aec_bench.task_world_templates.lifecycles.ssc03_hydraulic_intervention_verifier import (
        verify_hydraulic_intervention_lifecycle,
    )

    validated_ssc03_hydraulic_intervention_package(package_dir)
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


def _instructions(template: CompositeTaskWorldTemplate) -> dict[str, str]:
    assert template.evidence_lifecycle is not None
    checkpoints = {checkpoint.checkpoint_id: checkpoint for checkpoint in template.evidence_lifecycle.checkpoints}
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
    return """# SSC-03 Hydraulic Design Response Lifecycle

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
