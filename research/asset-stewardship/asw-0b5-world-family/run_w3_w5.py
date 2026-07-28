# ABOUTME: Orchestrates the research-only B5-W3 through B5-W5 execution boundary.
# ABOUTME: Emits content-addressed rejection evidence without creating production or promoted payloads.

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from certifier import boundary as certifier_boundary
from generator import boundary as generator_boundary
from generator import engine, execution, request, transfer
from lineage import receipts
from promotion import decision
from repairs import c_r02, control_edge_trajectory, solver_convergence
from sensitivity import (
    amendment,
    catalogue,
    family,
    selection_amendment,
    successor,
)

B5_ROOT = Path(__file__).resolve().parent
W1_DECLARATION = B5_ROOT / "declarations" / "w1-member-authority.json"
W2_CATALOGUE = B5_ROOT / "declarations" / "w2-case-catalogue.json"
W2_W4_REPAIR = B5_ROOT / "declarations" / "w2-w4-engine-mapping-repair.json"
C_R02_AMENDMENT = (
    B5_ROOT / "declarations" / "w4-c-r02-routing-integration-amendment.json"
)
SOLVER_CONVERGENCE = (
    B5_ROOT / "declarations" / "solver-convergence-amendment.json"
)
CONTROL_EDGE_AMENDMENT = (
    B5_ROOT / "declarations" / "control-edge-trajectory-amendment.json"
)
FAMILY_SELECTION_AMENDMENT = (
    B5_ROOT
    / "declarations"
    / "family-member-selection-amendment.json"
)
C_R07_AMENDMENT = (
    B5_ROOT / "declarations" / "w4-c-r07-composition-amendment.json"
)
W4_AMENDMENT = B5_ROOT / "declarations" / "w4-c-r08-ceiling-amendment.json"
W4_PROBES = B5_ROOT / "declarations" / "w4-probe-catalogue.json"


def _digest(label: bytes, value: bytes) -> str:
    return hashlib.sha256(label + value).hexdigest()


def _source_paths(directory: str) -> tuple[str, ...]:
    return tuple(sorted(path.relative_to(B5_ROOT).as_posix() for path in (B5_ROOT / directory).glob("*.py")))


def _sensitivity_source_id() -> str:
    paths = tuple(
        sorted(
            (
                *_source_paths("sensitivity"),
                *_source_paths("promotion"),
                *_source_paths("lineage"),
                "run_w3_w5.py",
            )
        )
    )
    inventory = [
        {
            "content_sha256": hashlib.sha256((B5_ROOT / path).read_bytes()).hexdigest(),
            "path": path,
        }
        for path in paths
    ]
    return _digest(
        b"asw-0b5.w3-w5-source-inventory.v1\0",
        generator_boundary.canonical_json_bytes({"files": inventory}),
    )


def _write_absent(path: Path, raw: bytes) -> None:
    if path.exists() or path.is_symlink():
        raise ValueError(f"output path must be absent: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


def _isolated_certification(
    *,
    authority_bytes: bytes,
    bundle_bytes: bytes,
    workspace: Path,
) -> bytes:
    if workspace.exists() or workspace.is_symlink():
        raise ValueError("isolated certifier workspace must be absent")
    workspace.mkdir(parents=True)
    shutil.copytree(B5_ROOT / "certifier", workspace / "certifier")
    (workspace / "w1.json").write_bytes(authority_bytes)
    (workspace / "bundle.json").write_bytes(bundle_bytes)
    script = (
        "from pathlib import Path\n"
        "from certifier import certification\n"
        "result=certification.certify_bundle("
        "Path('bundle.json').read_bytes(),Path('w1.json').read_bytes())\n"
        "Path('result.json').write_bytes("
        "certification.certification_result_bytes(result))\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        cwd=workspace,
        env={
            "LC_ALL": "C",
            "PYTHONHASHSEED": "0",
            "PYTHONPATH": str(workspace),
        },
        capture_output=True,
    )
    if completed.returncode != 0:
        raise RuntimeError("isolated certifier failed: " + completed.stderr.decode("utf-8", errors="replace"))
    result_path = workspace / "result.json"
    if not result_path.is_file() or result_path.is_symlink():
        raise RuntimeError("isolated certifier did not emit one result")
    raw = result_path.read_bytes()
    if b"generator" in completed.stdout or b"swmm" in completed.stdout.lower():
        raise RuntimeError("isolated certifier emitted forbidden dependency text")
    return raw


def build_generation_declaration(
    *,
    authority_bytes: bytes,
    c_r02_amendment_bytes: bytes,
    c_r07_amendment_bytes: bytes,
    c_r08_amendment_bytes: bytes,
    catalogue_bytes: bytes,
    control_edge_amendment_bytes: bytes,
    family_selection_amendment_bytes: bytes,
    repair_bytes: bytes,
    solver_convergence_bytes: bytes,
    engine_identity: dict[str, str],
    generator_source_id: str,
    certifier_source_id: str,
    sensitivity_source_id: str,
) -> bytes:
    """Freeze one exact W3-W5 attempt before engine execution."""
    amendment.read_c_r07_amendment(c_r07_amendment_bytes)
    amendment.read_amendment(c_r08_amendment_bytes)
    c_r02.read_amendment(c_r02_amendment_bytes)
    control_edge_trajectory.read_amendment(
        control_edge_amendment_bytes
    )
    selection_amendment.read(family_selection_amendment_bytes)
    solver_convergence.read_amendment(solver_convergence_bytes)
    requests = [
        request.read_request(
            request.build_anchor_request(
                authority_bytes=authority_bytes,
                catalogue_bytes=catalogue_bytes,
                case_id=case_id,
                engine_identity=engine_identity,
                repair_bytes=repair_bytes,
                solver_convergence_bytes=solver_convergence_bytes,
            ),
            authority_bytes=authority_bytes,
            catalogue_bytes=catalogue_bytes,
            repair_bytes=repair_bytes,
            solver_convergence_bytes=solver_convergence_bytes,
        )
        for case_id in request.CASE_IDS
    ]
    member_id = requests[0]["member"]["member_content_id"]
    if any(item["member"]["member_content_id"] != member_id for item in requests):
        raise ValueError("generation declaration member identity differs")
    engine_configuration = _digest(
        b"asw-0b5.engine-configuration.v1\0",
        request.canonical_json_bytes(engine_identity),
    )
    generator_configuration = _digest(
        b"asw-0b5.generator-configuration.v1\0",
        (
            request.MAPPING_REPAIR_SHA256
            + catalogue.PROBE_CATALOGUE_SHA256
            + c_r02.AMENDMENT_SHA256
            + solver_convergence.AMENDMENT_SHA256
            + control_edge_trajectory.AMENDMENT_SHA256
            + selection_amendment.AMENDMENT_SHA256
            + sensitivity_source_id
        ).encode("ascii"),
    )
    generator_dependencies = _digest(
        b"asw-0b5.generator-dependencies.v1\0",
        b"python-standard-library",
    )
    certifier_dependencies = _digest(
        b"asw-0b5.certifier-dependencies.v1\0",
        b"python-standard-library",
    )
    certifier_environment = _digest(
        b"asw-0b5.certifier-environment.v1\0",
        b"isolated-copy-no-generator-no-swmm",
    )
    declaration: dict[str, Any] = {
        "authorities": [
            {"role": role, "sha256": sha256}
            for role, sha256 in generator_boundary.FAMILY_AUTHORITY_HASHES
        ],
        "cases": [
            {
                "case_id": item["case"]["case_id"],
                "content_id": item["case"]["case_content_id"],
            }
            for item in requests
        ],
        "certifier": {
            "dependency_inventory_id": certifier_dependencies,
            "environment_id": certifier_environment,
            "source_inventory_id": certifier_source_id,
        },
        "engine": {
            "commit": engine_identity["commit"],
            "configuration_id": engine_configuration,
            "patch_sha256": engine_identity["patch_sha256"],
            "repository": engine_identity["repository"],
            "version": engine_identity["version"],
        },
        "generator": {
            "configuration_id": generator_configuration,
            "dependency_inventory_id": generator_dependencies,
            "source_inventory_id": generator_source_id,
        },
        "manifest_specification_id": ("asw-0b5.promotion-manifest-specification.v1"),
        "member_content_id": member_id,
        "package_profile_id": "asw-au-nsw-lh-syn-sps.package.v1",
        "profile_id": generator_boundary.PROFILE_ID,
        "receipt_profile": {
            "identity": "asw-0b5.research-receipts.v1",
            "kinds": list(generator_boundary.RECEIPT_KINDS),
        },
        "replay_policy": {
            "ordinals": [0, 1],
            "workspace_policy": "fresh-absent-root",
        },
        "schema_id": "asw-0b5.generation-declaration.v5",
        "w4_probe_catalogue_content_id": catalogue.PROBE_CATALOGUE_SHA256,
    }
    raw = generator_boundary.canonical_json_bytes(declaration)
    generator_boundary.read_generation_declaration(raw)
    return raw


def _receipt(
    *,
    generation_id: str,
    kind: str,
    parents: tuple[str, ...],
    inputs: tuple[tuple[str, str], ...],
    outputs: tuple[tuple[str, str], ...],
    terminal_state: str,
    failure_code: str = "none",
    failure_owner: str = "none",
) -> receipts.IdentifiedReceipt:
    return receipts.build_receipt(
        {
            "authorities": [
            {"role": role, "sha256": sha256}
            for role, sha256 in generator_boundary.FAMILY_AUTHORITY_HASHES
            ],
            "first_failure": {
                "code": failure_code,
                "owner": failure_owner,
            },
            "generation_id": generation_id,
            "inputs": [{"content_id": content_id, "role": role} for role, content_id in inputs],
            "outputs": [{"content_id": content_id, "role": role} for role, content_id in outputs],
            "parent_receipt_ids": list(parents),
            "profile_id": generator_boundary.PROFILE_ID,
            "promotable": False,
            "receipt_kind": kind,
            "receipt_version": receipts.RECEIPT_VERSION,
            "terminal_state": terminal_state,
            "visibility": "certification-private",
        }
    )


def build_rejection_receipt_chain(
    *,
    generation_id: str,
    engine_build_content_id: str,
    generator_bundle_content_id: str,
    certifier_result_content_id: str,
    composition_result_content_id: str,
    analytical_inventory_content_id: str,
    family_result_content_id: str,
    promotion_decision_content_id: str,
    composition_terminal_state: str = "w4-numerical-reject",
    composition_first_failure: str = "C-R02-corrected-residual",
) -> tuple[receipts.IdentifiedReceipt, ...]:
    """Build the connected amended-generation receipt chain through refusal."""
    root = _receipt(
        generation_id=generation_id,
        kind="generation-declaration",
        parents=(),
        inputs=((("generation"), generation_id),),
        outputs=((("generation-declaration"), generation_id),),
        terminal_state="attempt-frozen",
    )
    engine = _receipt(
        generation_id=generation_id,
        kind="engine-build",
        parents=(root.receipt_id,),
        inputs=(("engine-build", engine_build_content_id),),
        outputs=(("verified-engine-build", engine_build_content_id),),
        terminal_state="engine-build-verified",
    )
    generated = _receipt(
        generation_id=generation_id,
        kind="generator-case",
        parents=(root.receipt_id, engine.receipt_id),
        inputs=(
            ("generation", generation_id),
            ("engine-build", engine_build_content_id),
        ),
        outputs=(("certifier-input-bundle", generator_bundle_content_id),),
        terminal_state="generator-catalogue-replayed",
    )
    certified = _receipt(
        generation_id=generation_id,
        kind="certifier-case",
        parents=(root.receipt_id, generated.receipt_id),
        inputs=(("certifier-input-bundle", generator_bundle_content_id),),
        outputs=(("certifier-result", certifier_result_content_id),),
        terminal_state="quantitative-pending-w4",
    )
    composed = _receipt(
        generation_id=generation_id,
        kind="w4-case",
        parents=(certified.receipt_id,),
        inputs=(("certifier-result", certifier_result_content_id),),
        outputs=(("w4-composition-result", composition_result_content_id),),
        terminal_state=composition_terminal_state,
        failure_code=composition_first_failure.lower(),
        failure_owner="w4",
    )
    sensitivity = _receipt(
        generation_id=generation_id,
        kind="sensitivity-member",
        parents=(root.receipt_id, composed.receipt_id),
        inputs=(("w4-composition-result", composition_result_content_id),),
        outputs=(("w4-analytical-inventory", analytical_inventory_content_id),),
        terminal_state="pre-engine-inventory-frozen",
    )
    family = _receipt(
        generation_id=generation_id,
        kind="family-decision",
        parents=(composed.receipt_id, sensitivity.receipt_id),
        inputs=(
            ("w4-composition-result", composition_result_content_id),
            ("w4-analytical-inventory", analytical_inventory_content_id),
        ),
        outputs=(("family-decision", family_result_content_id),),
        terminal_state="family-member-reject",
        failure_code="anchor-w4-reject",
        failure_owner="w4",
    )
    promotion = _receipt(
        generation_id=generation_id,
        kind="promotion-decision",
        parents=(family.receipt_id,),
        inputs=(("family-decision", family_result_content_id),),
        outputs=(("promotion-decision", promotion_decision_content_id),),
        terminal_state="promotion-generation-reject",
        failure_code="family-member-reject",
        failure_owner="w5",
    )
    chain = (
        root,
        engine,
        generated,
        certified,
        composed,
        sensitivity,
        family,
        promotion,
    )
    receipts.validate_receipt_graph(chain)
    return chain


def execute(
    *,
    engine_receipt: Path,
    output_root: Path,
) -> dict[str, Any]:
    """Execute the amended ordered W3-W5 rejection path in one absent root."""
    output_root = output_root.resolve()
    if output_root.exists() or output_root.is_symlink():
        raise ValueError("W3-W5 output root must be absent")
    output_root.mkdir(parents=True)
    authority_bytes = W1_DECLARATION.read_bytes()
    catalogue_bytes = W2_CATALOGUE.read_bytes()
    repair_bytes = W2_W4_REPAIR.read_bytes()
    c_r02_amendment_bytes = C_R02_AMENDMENT.read_bytes()
    solver_convergence_bytes = SOLVER_CONVERGENCE.read_bytes()
    control_edge_amendment_bytes = CONTROL_EDGE_AMENDMENT.read_bytes()
    family_selection_amendment_bytes = (
        FAMILY_SELECTION_AMENDMENT.read_bytes()
    )
    engine_identity = engine.request_engine_identity(engine_receipt)
    generator_source_id = generator_boundary.capture_source_identity(
        B5_ROOT,
        _source_paths("generator"),
    )
    certifier_source_id = certifier_boundary.capture_source_identity(
        B5_ROOT,
        _source_paths("certifier"),
    )
    sensitivity_source_id = _sensitivity_source_id()
    generation_bytes = build_generation_declaration(
        authority_bytes=authority_bytes,
        c_r02_amendment_bytes=c_r02_amendment_bytes,
        c_r07_amendment_bytes=C_R07_AMENDMENT.read_bytes(),
        c_r08_amendment_bytes=W4_AMENDMENT.read_bytes(),
        catalogue_bytes=catalogue_bytes,
        control_edge_amendment_bytes=control_edge_amendment_bytes,
        family_selection_amendment_bytes=(
            family_selection_amendment_bytes
        ),
        repair_bytes=repair_bytes,
        solver_convergence_bytes=solver_convergence_bytes,
        engine_identity=engine_identity,
        generator_source_id=generator_source_id,
        certifier_source_id=certifier_source_id,
        sensitivity_source_id=sensitivity_source_id,
    )
    generation_id = generator_boundary.world_generation_id(generation_bytes)
    compact = output_root / "compact"
    _write_absent(
        compact / "generation-declaration.json",
        generation_bytes,
    )

    generated = execution.execute_catalogue(
        authority_bytes=authority_bytes,
        catalogue_bytes=catalogue_bytes,
        receipt_path=engine_receipt,
        repair_bytes=repair_bytes,
        solver_convergence_bytes=solver_convergence_bytes,
        workspace=output_root / "raw-generation",
    )
    bundle_bytes = transfer.build_certifier_bundle(generated)
    _write_absent(
        output_root / "certifier-input-bundle.json",
        bundle_bytes,
    )
    certifier_result_bytes = _isolated_certification(
        authority_bytes=authority_bytes,
        bundle_bytes=bundle_bytes,
        workspace=output_root / "isolated-certifier",
    )
    certifier_result = json.loads(certifier_result_bytes)
    _write_absent(
        compact / "w3-certifier-result.json",
        certifier_result_bytes,
    )

    composition_result = successor.compose_predecessor_generation(
        bundle_bytes=bundle_bytes,
        certifier_result_bytes=certifier_result_bytes,
    )
    composition_bytes = (
        successor.predecessor_composition_result_bytes(
            composition_result
        )
    )
    _write_absent(
        compact / "w4-composition-result.json",
        composition_bytes,
    )
    analytical_inventory = family.build_analytical_inventory(
        authority_bytes=authority_bytes,
        probe_catalogue_bytes=W4_PROBES.read_bytes(),
    )
    analytical_bytes = family.analytical_inventory_bytes(analytical_inventory)
    _write_absent(
        compact / "w4-analytical-inventory.json",
        analytical_bytes,
    )
    family_result = family.freeze_family_decision(
        analytical_inventory=analytical_inventory,
        composition_result_content_id=composition_result["result_content_id"],
        composition_terminal_state=composition_result["terminal_state"],
        composition_first_failure=composition_result["first_failure"],
    )
    family_bytes = family.family_result_bytes(family_result)
    _write_absent(compact / "family-decision.json", family_bytes)
    promotion_result = decision.refuse_v3(family_bytes)
    promotion_bytes = decision.promotion_decision_bytes(promotion_result)
    _write_absent(
        compact / "promotion-decision.json",
        promotion_bytes,
    )

    chain = build_rejection_receipt_chain(
        generation_id=generation_id,
        engine_build_content_id=engine_identity["build_receipt_sha256"],
        generator_bundle_content_id=hashlib.sha256(bundle_bytes).hexdigest(),
        certifier_result_content_id=certifier_result["result_content_id"],
        composition_result_content_id=composition_result["result_content_id"],
        analytical_inventory_content_id=analytical_inventory["content_id"],
        family_result_content_id=family_result["result_content_id"],
        promotion_decision_content_id=promotion_result["decision_content_id"],
        composition_terminal_state=composition_result["terminal_state"],
        composition_first_failure=composition_result["first_failure"],
    )
    receipt_root = compact / "receipts"
    receipt_index: list[dict[str, str]] = []
    for ordinal, item in enumerate(chain):
        name = f"{ordinal:02d}-{item.envelope['receipt_kind']}.json"
        _write_absent(receipt_root / name, item.canonical_bytes)
        receipt_index.append(
            {
                "receipt_id": item.receipt_id,
                "receipt_kind": item.envelope["receipt_kind"],
                "relative_path": f"receipts/{name}",
                "sha256": hashlib.sha256(item.canonical_bytes).hexdigest(),
            }
        )
    receipt_index_bytes = generator_boundary.canonical_json_bytes(
        {
            "generation_id": generation_id,
            "receipts": receipt_index,
            "schema_id": "asw-0b5.receipt-index.v1",
        }
    )
    _write_absent(compact / "receipt-index.json", receipt_index_bytes)
    summary: dict[str, Any] = {
        "analytical_inventory_content_id": analytical_inventory["content_id"],
        "bundle_sha256": hashlib.sha256(bundle_bytes).hexdigest(),
        "certifier_result_content_id": certifier_result["result_content_id"],
        "composition_result_content_id": composition_result["result_content_id"],
        "engine_build_receipt_sha256": engine_identity["build_receipt_sha256"],
        "family_result_content_id": family_result["result_content_id"],
        "family_terminal_state": family_result["terminal_state"],
        "generation_id": generation_id,
        "manifest_content_ids": [],
        "package_content_ids": [],
        "profile_id": generator_boundary.PROFILE_ID,
        "promotion_decision_content_id": promotion_result["decision_content_id"],
        "promotion_terminal_state": promotion_result["terminal_state"],
        "receipt_index_sha256": hashlib.sha256(receipt_index_bytes).hexdigest(),
        "schema_id": "asw-0b5.w3-w5-decision-summary.v2",
        "v3": "refused",
        "v4": "unclaimed",
        "w4_first_failure": composition_result["first_failure"],
        "w4_terminal_state": composition_result["terminal_state"],
    }
    summary_bytes = generator_boundary.canonical_json_bytes(summary)
    _write_absent(compact / "decision-summary.json", summary_bytes)
    return {
        "compact_root": compact,
        "decision_summary": summary,
        "output_root": output_root,
        "receipt_count": len(chain),
    }


def main(arguments: list[str] | None = None) -> int:
    """Run W3-W5 from explicit real-engine evidence and one absent output root."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine-receipt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parsed = parser.parse_args(arguments)
    result = execute(
        engine_receipt=parsed.engine_receipt,
        output_root=parsed.output,
    )
    sys.stdout.write(
        json.dumps(
            result["decision_summary"],
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
