# ABOUTME: Executes the complete real-engine certification and certified reference package workflow.
# ABOUTME: Retains private research evidence while issuing only the checked four-file package.

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import IO, Any

from adversarial import evaluation as mutation_evaluation
from adversarial import mutations
from certifier import boundary as certifier_boundary
from generator import boundary as generator_boundary
from generator import engine, execution, rendering, transfer
from lineage import receipts
from promotion import (
    decision,
    package_builder,
    package_checker,
    reviews,
)
from run_w3_w5 import build_generation_declaration
from sensitivity import (
    engine_variants,
    family,
    member_evaluation,
    successor,
)

B5_ROOT = Path(__file__).resolve().parent
DECLARATIONS = B5_ROOT / "declarations"
W1_DECLARATION = DECLARATIONS / "w1-member-authority.json"
W2_CATALOGUE = DECLARATIONS / "w2-case-catalogue.json"
ENGINE_MAPPING = DECLARATIONS / "w2-w4-engine-mapping-repair.json"
MASS_AMENDMENT = (
    DECLARATIONS / "w4-c-r02-routing-integration-amendment.json"
)
COMPOSITION_AMENDMENT = (
    DECLARATIONS / "w4-c-r07-composition-amendment.json"
)
CEILING_AMENDMENT = (
    DECLARATIONS / "w4-c-r08-ceiling-amendment.json"
)
SOLVER_CONVERGENCE = (
    DECLARATIONS / "solver-convergence-amendment.json"
)
CONTROL_EDGE_AMENDMENT = (
    DECLARATIONS / "control-edge-trajectory-amendment.json"
)
MEMBER_SELECTION = (
    DECLARATIONS / "family-member-selection-amendment.json"
)
PROBE_CATALOGUE = DECLARATIONS / "w4-probe-catalogue.json"
ABSENCE_RESULT_DOMAIN = b"asw-0b5.absence-proof.v1\0"


class ReferenceCertificationError(RuntimeError):
    """Raised when the complete reference certification cannot continue."""


def _progress(message: str) -> None:
    sys.stderr.write(f"{message}\n")
    sys.stderr.flush()


def _write_absent(path: Path, raw: bytes) -> None:
    if path.exists() or path.is_symlink():
        raise ReferenceCertificationError(
            f"output path already exists: {path}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


def _canonical(value: object) -> bytes:
    return generator_boundary.canonical_json_bytes(value)


def _source_paths(directory: str) -> tuple[str, ...]:
    return tuple(
        sorted(
            path.relative_to(B5_ROOT).as_posix()
            for path in (B5_ROOT / directory).glob("*.py")
        )
    )


def _research_source_id() -> str:
    paths = tuple(
        sorted(
            {
                *(
                    path
                    for directory in (
                        "adversarial",
                        "lineage",
                        "promotion",
                        "repairs",
                        "sensitivity",
                    )
                    for path in _source_paths(directory)
                ),
                "run_reference_certification.py",
                "run_w3_w5.py",
            }
        )
    )
    inventory = [
        {
            "path": path,
            "sha256": hashlib.sha256(
                (B5_ROOT / path).read_bytes()
            ).hexdigest(),
        }
        for path in paths
    ]
    return hashlib.sha256(
        b"asw-0b5.research-source-inventory.v1\0"
        + _canonical({"files": inventory})
    ).hexdigest()


def _read_exact(stream: IO[bytes], size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            raise ReferenceCertificationError(
                "isolated certifier ended before its result"
            )
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


class IsolatedCertifier:
    """Runs many certifications in one generator-free Python process."""

    def __init__(
        self,
        *,
        authority_bytes: bytes,
        workspace: Path,
    ) -> None:
        self.workspace = workspace.resolve()
        if self.workspace.exists() or self.workspace.is_symlink():
            raise ReferenceCertificationError(
                "isolated certifier workspace must be absent"
            )
        self.workspace.mkdir(parents=True)
        shutil.copytree(
            B5_ROOT / "certifier",
            self.workspace / "certifier",
        )
        (self.workspace / "w1.json").write_bytes(authority_bytes)
        driver = (
            "import json,sys\n"
            "from pathlib import Path\n"
            "from certifier import certification\n"
            "authority=Path('w1.json').read_bytes()\n"
            "source=sys.stdin.buffer\n"
            "sink=sys.stdout.buffer\n"
            "while True:\n"
            " header=source.read(16)\n"
            " if not header: break\n"
            " size=int(header,16)\n"
            " chunks=[]\n"
            " while size:\n"
            "  chunk=source.read(size)\n"
            "  if not chunk: raise RuntimeError('short input')\n"
            "  chunks.append(chunk)\n"
            "  size-=len(chunk)\n"
            " raw_bundle=b''.join(chunks)\n"
            " schema=json.loads(raw_bundle)['schema_id']\n"
            " certify=(certification.certify_sensitivity_bundle "
            "if schema=='asw-0b5.certifier-sensitivity-bundle.v1' "
            "else certification.certify_bundle)\n"
            " result=certify(raw_bundle,authority)\n"
            " raw=certification.certification_result_bytes(result)\n"
            " sink.write(f'{len(raw):016x}'.encode('ascii'))\n"
            " sink.write(raw)\n"
            " sink.flush()\n"
        )
        self.process = subprocess.Popen(
            [sys.executable, "-u", "-c", driver],
            cwd=self.workspace,
            env={
                "LC_ALL": "C",
                "PYTHONHASHSEED": "0",
                "PYTHONPATH": str(self.workspace),
            },
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def certify(self, bundle_bytes: bytes) -> bytes:
        """Certify one bundle through the isolated persistent process."""
        if self.process.stdin is None or self.process.stdout is None:
            raise ReferenceCertificationError(
                "isolated certifier pipes are unavailable"
            )
        self.process.stdin.write(
            f"{len(bundle_bytes):016x}".encode("ascii")
        )
        self.process.stdin.write(bundle_bytes)
        self.process.stdin.flush()
        header = _read_exact(self.process.stdout, 16)
        try:
            size = int(header, 16)
        except ValueError as error:
            raise ReferenceCertificationError(
                "isolated certifier result header differs"
            ) from error
        return _read_exact(self.process.stdout, size)

    def close(self) -> None:
        """Close the certifier and require clean, silent completion."""
        if self.process.stdin is not None:
            self.process.stdin.close()
        return_code = self.process.wait()
        stderr = (
            self.process.stderr.read()
            if self.process.stderr is not None
            else b""
        )
        if return_code != 0 or stderr:
            raise ReferenceCertificationError(
                "isolated certifier did not finish cleanly: "
                + stderr.decode("utf-8", errors="replace")
            )


def _identified(
    value: dict[str, Any],
    *,
    domain: bytes,
) -> dict[str, Any]:
    payload = {
        key: child
        for key, child in value.items()
        if key != "result_content_id"
    }
    value["result_content_id"] = hashlib.sha256(
        domain + _canonical(payload)
    ).hexdigest()
    return value


def _absence_proof(
    *,
    engine_receipt: Path,
    package_root: Path,
    workspace: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    workspace = workspace.resolve()
    if workspace.exists() or workspace.is_symlink():
        raise ReferenceCertificationError(
            "absence workspace must be absent"
        )
    workspace.mkdir(parents=True)
    isolated_package = workspace / "package"
    shutil.copytree(package_root, isolated_package)
    checker_path = workspace / "package_checker.py"
    shutil.copy2(
        B5_ROOT / "promotion" / "package_checker.py",
        checker_path,
    )
    policy_path = workspace.parent / "absence-policy.sb"
    if policy_path.exists() or policy_path.is_symlink():
        raise ReferenceCertificationError(
            "absence sandbox policy path must be absent"
        )
    policy_path.write_text(
        "(version 1)\n"
        "(allow default)\n"
        "(deny network*)\n"
        f'(deny file-read* (subpath "{B5_ROOT}"))\n'
        f'(deny file-read* (subpath "{engine_receipt.parent}"))\n',
        encoding="utf-8",
    )
    completed = subprocess.run(
        [
            "/usr/bin/sandbox-exec",
            "-f",
            str(policy_path),
            sys.executable,
            str(checker_path),
            str(isolated_package),
        ],
        cwd=workspace,
        env={
            "LC_ALL": "C",
            "PYTHONHASHSEED": "0",
            "PYTHONPATH": "",
        },
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0 or completed.stderr:
        raise ReferenceCertificationError(
            "package-only absence check failed: "
            + completed.stderr.decode("utf-8", errors="replace")
        )
    try:
        conformance = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ReferenceCertificationError(
            "package-only checker output differs"
        ) from error
    if (
        not isinstance(conformance, dict)
        or conformance.get("terminal_state")
        != "package-conformance-pass"
    ):
        raise ReferenceCertificationError(
            "package-only conformance did not pass"
        )
    proof: dict[str, Any] = {
        "checker_source_sha256": hashlib.sha256(
            checker_path.read_bytes()
        ).hexdigest(),
        "compact_reference_count": conformance[
            "compact_reference_count"
        ],
        "first_failure": "none",
        "forbidden_dependencies_absent": [
            "certifier",
            "generator",
            "network",
            "research-tree",
            "swmm",
        ],
        "manifest_content_id": conformance[
            "manifest_content_id"
        ],
        "network_access": "denied",
        "package_content_id": conformance["package_content_id"],
        "profile_id": generator_boundary.PROFILE_ID,
        "promotable": False,
        "result_content_id": "",
        "schema_id": "asw-0b5.absence-proof.v1",
        "terminal_state": "absence-proof-pass",
    }
    return _identified(
        proof,
        domain=ABSENCE_RESULT_DOMAIN,
    ), conformance


def _receipt(
    *,
    generation_id: str,
    kind: str,
    parents: tuple[str, ...],
    inputs: tuple[tuple[str, str], ...],
    outputs: tuple[tuple[str, str], ...],
    terminal_state: str,
    promotable: bool = False,
) -> receipts.IdentifiedReceipt:
    return receipts.build_receipt(
        {
            "authorities": [
                {"role": role, "sha256": sha256}
                for role, sha256 in (
                    generator_boundary.FAMILY_AUTHORITY_HASHES
                )
            ],
            "first_failure": {"code": "none", "owner": "none"},
            "generation_id": generation_id,
            "inputs": [
                {"content_id": content_id, "role": role}
                for role, content_id in inputs
            ],
            "outputs": [
                {"content_id": content_id, "role": role}
                for role, content_id in outputs
            ],
            "parent_receipt_ids": list(parents),
            "profile_id": generator_boundary.PROFILE_ID,
            "promotable": promotable,
            "receipt_kind": kind,
            "receipt_version": receipts.RECEIPT_VERSION,
            "terminal_state": terminal_state,
            "visibility": "certification-private",
        }
    )


def _receipt_chain(
    *,
    absence_proof_id: str,
    anchor_result_id: str,
    bundle_sha256: str,
    certifier_result_id: str,
    engine_build_id: str,
    family_result_id: str,
    gate_review_id: str,
    generation_id: str,
    manifest_id: str,
    mutation_result_id: str,
    package_conformance_id: str,
    package_id: str,
    promotion_decision_id: str,
    rights_review_id: str,
    sensitivity_inventory_id: str,
    visibility_review_id: str,
) -> tuple[receipts.IdentifiedReceipt, ...]:
    root = _receipt(
        generation_id=generation_id,
        kind="generation-declaration",
        parents=(),
        inputs=(("generation", generation_id),),
        outputs=(("generation-declaration", generation_id),),
        terminal_state="attempt-frozen",
    )
    engine_receipt = _receipt(
        generation_id=generation_id,
        kind="engine-build",
        parents=(root.receipt_id,),
        inputs=(("engine-build", engine_build_id),),
        outputs=(("verified-engine-build", engine_build_id),),
        terminal_state="engine-build-verified",
    )
    generated = _receipt(
        generation_id=generation_id,
        kind="generator-case",
        parents=(root.receipt_id, engine_receipt.receipt_id),
        inputs=(("generation", generation_id),),
        outputs=(("certifier-input-bundle", bundle_sha256),),
        terminal_state="generator-family-replayed",
    )
    certified = _receipt(
        generation_id=generation_id,
        kind="certifier-case",
        parents=(generated.receipt_id,),
        inputs=(("certifier-input-bundle", bundle_sha256),),
        outputs=(("certifier-result", certifier_result_id),),
        terminal_state="certifier-checks-pass",
    )
    physical = _receipt(
        generation_id=generation_id,
        kind="w4-case",
        parents=(certified.receipt_id,),
        inputs=(("certifier-result", certifier_result_id),),
        outputs=(("physical-result", anchor_result_id),),
        terminal_state="physical-checks-pass",
    )
    sensitivity = _receipt(
        generation_id=generation_id,
        kind="sensitivity-member",
        parents=(root.receipt_id, physical.receipt_id),
        inputs=(("physical-result", anchor_result_id),),
        outputs=(
            ("sensitivity-inventory", sensitivity_inventory_id),
            ("mutation-result", mutation_result_id),
        ),
        terminal_state="sensitivity-checks-pass",
    )
    family_receipt = _receipt(
        generation_id=generation_id,
        kind="family-decision",
        parents=(physical.receipt_id, sensitivity.receipt_id),
        inputs=(
            ("physical-result", anchor_result_id),
            ("sensitivity-inventory", sensitivity_inventory_id),
        ),
        outputs=(("family-decision", family_result_id),),
        terminal_state="family-checks-pass",
    )
    gate = _receipt(
        generation_id=generation_id,
        kind="gate-decision",
        parents=(family_receipt.receipt_id,),
        inputs=(("family-decision", family_result_id),),
        outputs=(("gate-review", gate_review_id),),
        terminal_state="gate-review-pass",
    )
    rights = _receipt(
        generation_id=generation_id,
        kind="rights-review",
        parents=(gate.receipt_id,),
        inputs=(("gate-review", gate_review_id),),
        outputs=(("rights-review", rights_review_id),),
        terminal_state="rights-review-pass",
    )
    visibility = _receipt(
        generation_id=generation_id,
        kind="visibility-review",
        parents=(rights.receipt_id,),
        inputs=(("rights-review", rights_review_id),),
        outputs=(("visibility-review", visibility_review_id),),
        terminal_state="visibility-review-pass",
    )
    conformance = _receipt(
        generation_id=generation_id,
        kind="package-conformance",
        parents=(visibility.receipt_id,),
        inputs=(
            ("manifest", manifest_id),
            ("package", package_id),
        ),
        outputs=(
            ("package-conformance", package_conformance_id),
        ),
        terminal_state="package-conformance-pass",
    )
    absence = _receipt(
        generation_id=generation_id,
        kind="absence-proof",
        parents=(conformance.receipt_id,),
        inputs=(("package-conformance", package_conformance_id),),
        outputs=(("absence-proof", absence_proof_id),),
        terminal_state="absence-proof-pass",
    )
    promotion = _receipt(
        generation_id=generation_id,
        kind="promotion-decision",
        parents=(absence.receipt_id,),
        inputs=(
            ("absence-proof", absence_proof_id),
            ("manifest", manifest_id),
            ("package", package_id),
        ),
        outputs=(("promotion-decision", promotion_decision_id),),
        terminal_state="promotion-issued",
        promotable=True,
    )
    chain = (
        root,
        engine_receipt,
        generated,
        certified,
        physical,
        sensitivity,
        family_receipt,
        gate,
        rights,
        visibility,
        conformance,
        absence,
        promotion,
    )
    receipts.validate_receipt_graph(chain)
    return chain


def execute_reference_certification(
    *,
    engine_receipt: Path,
    output_root: Path,
) -> dict[str, Any]:
    """Execute the complete certification and package issuance workflow."""
    output_root = output_root.resolve()
    if output_root.exists() or output_root.is_symlink():
        raise ReferenceCertificationError(
            "certification output root must be absent"
        )
    output_root.mkdir(parents=True)
    compact_root = output_root / "certification-record"
    private_root = output_root / "private-evidence"
    authority_bytes = W1_DECLARATION.read_bytes()
    catalogue_bytes = W2_CATALOGUE.read_bytes()
    mapping_bytes = ENGINE_MAPPING.read_bytes()
    convergence_bytes = SOLVER_CONVERGENCE.read_bytes()
    probe_bytes = PROBE_CATALOGUE.read_bytes()
    engine_identity = engine.request_engine_identity(engine_receipt)

    generator_source_id = generator_boundary.capture_source_identity(
        B5_ROOT,
        _source_paths("generator"),
    )
    certifier_source_id = certifier_boundary.capture_source_identity(
        B5_ROOT,
        _source_paths("certifier"),
    )
    research_source_id = _research_source_id()
    generation_bytes = build_generation_declaration(
        authority_bytes=authority_bytes,
        c_r02_amendment_bytes=MASS_AMENDMENT.read_bytes(),
        c_r07_amendment_bytes=COMPOSITION_AMENDMENT.read_bytes(),
        c_r08_amendment_bytes=CEILING_AMENDMENT.read_bytes(),
        catalogue_bytes=catalogue_bytes,
        control_edge_amendment_bytes=(
            CONTROL_EDGE_AMENDMENT.read_bytes()
        ),
        family_selection_amendment_bytes=(
            MEMBER_SELECTION.read_bytes()
        ),
        repair_bytes=mapping_bytes,
        solver_convergence_bytes=convergence_bytes,
        engine_identity=engine_identity,
        generator_source_id=generator_source_id,
        certifier_source_id=certifier_source_id,
        sensitivity_source_id=research_source_id,
    )
    generation_id = generator_boundary.world_generation_id(
        generation_bytes
    )
    _write_absent(
        compact_root / "generation-declaration.json",
        generation_bytes,
    )
    generation = json.loads(generation_bytes)

    _progress("Running the full anchor catalogue with the real engine.")
    anchor_generation = execution.execute_catalogue(
        authority_bytes=authority_bytes,
        catalogue_bytes=catalogue_bytes,
        receipt_path=engine_receipt,
        repair_bytes=mapping_bytes,
        solver_convergence_bytes=convergence_bytes,
        workspace=private_root / "anchor-engine-runs",
    )
    anchor_bundle = transfer.build_certifier_bundle(
        anchor_generation
    )
    _write_absent(
        private_root / "anchor-certifier-input.json",
        anchor_bundle,
    )

    certifier = IsolatedCertifier(
        authority_bytes=authority_bytes,
        workspace=private_root / "isolated-certifier",
    )
    try:
        _progress("Certifying the anchor in the isolated process.")
        anchor_certifier_bytes = certifier.certify(anchor_bundle)
        anchor_certifier = json.loads(anchor_certifier_bytes)
        _write_absent(
            compact_root / "anchor-certifier-result.json",
            anchor_certifier_bytes,
        )
        anchor_result = successor.compose_generation(
            c_r02_amendment_bytes=MASS_AMENDMENT.read_bytes(),
            bundle_bytes=anchor_bundle,
            certifier_result_bytes=anchor_certifier_bytes,
            control_edge_amendment_bytes=(
                CONTROL_EDGE_AMENDMENT.read_bytes()
            ),
            probe_catalogue_bytes=probe_bytes,
            solver_convergence_bytes=convergence_bytes,
        )
        if anchor_result["terminal_state"] != "w4-checks-pass":
            raise ReferenceCertificationError(
                "anchor physical checks did not pass: "
                + str(anchor_result["first_failure"])
            )
        anchor_result_bytes = successor.composition_result_bytes(
            anchor_result
        )
        _write_absent(
            compact_root / "anchor-physical-result.json",
            anchor_result_bytes,
        )
        analytical_inventory = (
            family.build_amended_analytical_inventory(
                authority_bytes=authority_bytes,
                probe_catalogue_bytes=probe_bytes,
                selection_amendment_bytes=(
                    MEMBER_SELECTION.read_bytes()
                ),
            )
        )
        _write_absent(
            compact_root / "analytical-inventory.json",
            family.analytical_inventory_bytes(
                analytical_inventory
            ),
        )

        interaction_map = {
            item["probe_id"]: item
            for item in analytical_inventory["interactions"]
        }
        selected_probe_ids = (
            "INT.01.hydraulic-supporting",
            "INT.02.hydraulic-opposing",
            "INT.03.primary-dominant",
        )
        member_results: dict[str, dict[str, Any]] = {}
        for probe_id in selected_probe_ids:
            _progress(f"Running approved family member {probe_id}.")
            item = interaction_map[probe_id]
            case_ids = tuple(item["case_ids"])
            member_generation = execution.execute_member_cases(
                authority_bytes=authority_bytes,
                catalogue_bytes=catalogue_bytes,
                case_ids=case_ids,
                member=item["member"],
                receipt_path=engine_receipt,
                repair_bytes=mapping_bytes,
                solver_convergence_bytes=convergence_bytes,
                workspace=(
                    private_root / "family-engine-runs" / probe_id
                ),
            )
            member_bundle = transfer.build_sensitivity_bundle(
                member_generation,
                case_ids=case_ids,
                probe_id=probe_id,
            )
            member_certifier_bytes = certifier.certify(member_bundle)
            member_result = member_evaluation.evaluate_member(
                c_r02_amendment_bytes=MASS_AMENDMENT.read_bytes(),
                bundle_bytes=member_bundle,
                certifier_result_bytes=member_certifier_bytes,
                control_edge_amendment_bytes=(
                    CONTROL_EDGE_AMENDMENT.read_bytes()
                ),
                probe_catalogue_bytes=probe_bytes,
                solver_convergence_bytes=convergence_bytes,
            )
            if member_result["terminal_state"] != "w4-checks-pass":
                raise ReferenceCertificationError(
                    f"{probe_id} did not pass: "
                    + str(member_result["first_failure"])
                )
            member_results[probe_id] = member_result
            safe_name = probe_id.lower().replace(".", "-")
            _write_absent(
                compact_root / f"member-{safe_name}.json",
                member_evaluation.member_evaluation_bytes(
                    member_result
                ),
            )

        probe_declaration = json.loads(probe_bytes)
        variant_results: dict[str, dict[str, Any]] = {}
        for variant in probe_declaration["engine_variants"]:
            variant_id = variant["variant_id"]
            _progress(f"Running engine variation {variant_id}.")
            configuration = rendering.EngineConfiguration(
                **variant["configuration"]
            )
            variant_results[variant_id] = (
                execution.execute_diagnostic_cases(
                    authority_bytes=authority_bytes,
                    catalogue_bytes=catalogue_bytes,
                    case_ids=tuple(
                        probe_declaration["engine_case_ids"]
                    ),
                    configuration=configuration,
                    receipt_path=engine_receipt,
                    repair_bytes=mapping_bytes,
                    solver_convergence_bytes=convergence_bytes,
                    workspace=(
                        private_root
                        / "engine-variation-runs"
                        / variant_id
                    ),
                )
            )
        variant_ids = tuple(
            variant["variant_id"]
            for variant in probe_declaration["engine_variants"]
        )
        engine_result = engine_variants.evaluate(
            probe_catalogue_bytes=probe_bytes,
            variant_results=variant_results,
            required_variant_ids=variant_ids,
        )
        if engine_result["terminal_state"] != "engine-variants-pass":
            raise ReferenceCertificationError(
                "engine variations did not pass: "
                + str(engine_result["first_failure"])
            )
        _write_absent(
            compact_root / "engine-variation-result.json",
            engine_variants.evaluation_bytes(engine_result),
        )

        _progress("Building and certifying all thirty bad inputs.")
        mutated_bundles = mutations.build_bundle_mutations(
            anchor_bundle
        )
        mutation_certifier_results: dict[str, bytes] = {}
        for mutation_id, mutation_bundle in mutated_bundles.items():
            _progress(f"Checking bad input {mutation_id}.")
            mutation_certifier_results[mutation_id] = (
                certifier.certify(mutation_bundle)
            )
        mutation_result = mutation_evaluation.evaluate(
            base_bundle_bytes=anchor_bundle,
            base_certifier_result_bytes=anchor_certifier_bytes,
            bundle_mutations=mutated_bundles,
            certifier_results=mutation_certifier_results,
            c_r02_amendment_bytes=MASS_AMENDMENT.read_bytes(),
            solver_convergence_bytes=convergence_bytes,
        )
        if (
            mutation_result["terminal_state"]
            != "mutation-catalogue-pass"
        ):
            raise ReferenceCertificationError(
                "bad-input catalogue did not pass: "
                + str(mutation_result["first_failure"])
            )
        _write_absent(
            compact_root / "bad-input-result.json",
            mutation_evaluation.evaluation_bytes(
                mutation_result
            ),
        )
    finally:
        certifier.close()

    family_result = family.freeze_passing_family_decision(
        analytical_inventory=analytical_inventory,
        anchor_result=anchor_result,
        member_results=member_results,
        engine_result=engine_result,
        mutation_result=mutation_result,
        selection_amendment_bytes=MEMBER_SELECTION.read_bytes(),
    )
    family_bytes = family.family_result_bytes(family_result)
    _write_absent(
        compact_root / "family-decision.json",
        family_bytes,
    )

    certifier_environment = {
        "dependency_inventory_id": generation["certifier"][
            "dependency_inventory_id"
        ],
        "environment_id": generation["certifier"]["environment_id"],
        "execution_mode": "isolated-copy",
        "forbidden_dependencies_absent": ["generator", "swmm"],
        "source_inventory_id": generation["certifier"][
            "source_inventory_id"
        ],
    }
    gate_review = reviews.review_construct_validity(
        anchor_result=anchor_result,
        authority_bytes=authority_bytes,
        certifier_environment=certifier_environment,
        certifier_result=anchor_certifier,
        engine_result=engine_result,
        family_result=family_result,
        generation_id=generation_id,
        mutation_result=mutation_result,
    )
    _write_absent(
        compact_root / "construct-validity-review.json",
        reviews.review_bytes(
            gate_review,
            domain=reviews.GATE_DOMAIN,
        ),
    )
    reference_checks = (
        package_builder.build_compact_reference_checks(
            anchor_result=anchor_result,
            certifier_result=anchor_certifier,
        )
    )

    _progress("Building the certified reference package twice.")
    built = package_builder.build_certified_reference_package(
        authority_bytes=authority_bytes,
        family_result_bytes=family_bytes,
        gate_review=gate_review,
        generation_id=generation_id,
        reference_checks=reference_checks,
        target=output_root / "certified-reference-package",
    )
    rebuilt = package_builder.build_certified_reference_package(
        authority_bytes=authority_bytes,
        family_result_bytes=family_bytes,
        gate_review=gate_review,
        generation_id=generation_id,
        reference_checks=reference_checks,
        target=private_root / "package-rebuild",
    )
    if (
        built.package_content_id != rebuilt.package_content_id
        or built.manifest_content_id
        != rebuilt.manifest_content_id
        or any(
            (built.root / name).read_bytes()
            != (rebuilt.root / name).read_bytes()
            for name in package_checker.EXPECTED_FILES
        )
    ):
        raise ReferenceCertificationError(
            "the two fresh package builds differ"
        )
    conformance = package_checker.check_package(built.root)
    _write_absent(
        compact_root / "package-conformance.json",
        _canonical(conformance),
    )
    _write_absent(
        compact_root / "rights-review.json",
        reviews.review_bytes(
            built.rights_review,
            domain=reviews.RIGHTS_DOMAIN,
        ),
    )
    _write_absent(
        compact_root / "visibility-review.json",
        reviews.review_bytes(
            built.visibility_review,
            domain=reviews.VISIBILITY_DOMAIN,
        ),
    )

    _progress("Checking the package with research, SWMM, and network blocked.")
    absence, isolated_conformance = _absence_proof(
        engine_receipt=engine_receipt.resolve(),
        package_root=built.root,
        workspace=private_root / "package-only-check",
    )
    if (
        isolated_conformance["result_content_id"]
        != conformance["result_content_id"]
    ):
        raise ReferenceCertificationError(
            "package-only and local conformance results differ"
        )
    _write_absent(
        compact_root / "absence-proof.json",
        _canonical(absence),
    )

    manifest = json.loads(
        (built.root / "promotion-manifest.json").read_bytes()
    )
    payload_ids = tuple(
        row["payload_content_id"]
        for row in manifest["package"]["payloads"]
    )
    if len(payload_ids) != 3:
        raise ReferenceCertificationError(
            "promoted payload identity inventory differs"
        )
    promotion = decision.issue_certified_reference_package(
        absence_proof_content_id=absence["result_content_id"],
        family_result_bytes=family_bytes,
        gate_review_content_id=gate_review["result_content_id"],
        manifest_content_id=built.manifest_content_id,
        package_conformance_content_id=conformance[
            "result_content_id"
        ],
        package_content_id=built.package_content_id,
        payload_content_ids=payload_ids,
        rights_review_content_id=built.rights_review[
            "result_content_id"
        ],
        visibility_review_content_id=built.visibility_review[
            "result_content_id"
        ],
    )
    promotion_bytes = decision.promotion_decision_bytes(promotion)
    _write_absent(
        compact_root / "promotion-decision.json",
        promotion_bytes,
    )

    chain = _receipt_chain(
        absence_proof_id=absence["result_content_id"],
        anchor_result_id=anchor_result["result_content_id"],
        bundle_sha256=hashlib.sha256(anchor_bundle).hexdigest(),
        certifier_result_id=anchor_certifier["result_content_id"],
        engine_build_id=engine_identity["build_receipt_sha256"],
        family_result_id=family_result["result_content_id"],
        gate_review_id=gate_review["result_content_id"],
        generation_id=generation_id,
        manifest_id=built.manifest_content_id,
        mutation_result_id=mutation_result["result_content_id"],
        package_conformance_id=conformance["result_content_id"],
        package_id=built.package_content_id,
        promotion_decision_id=promotion["decision_content_id"],
        rights_review_id=built.rights_review["result_content_id"],
        sensitivity_inventory_id=analytical_inventory["content_id"],
        visibility_review_id=built.visibility_review[
            "result_content_id"
        ],
    )
    receipt_index: list[dict[str, str]] = []
    for ordinal, receipt in enumerate(chain):
        name = f"{ordinal:02d}-{receipt.envelope['receipt_kind']}.json"
        _write_absent(
            compact_root / "receipts" / name,
            receipt.canonical_bytes,
        )
        receipt_index.append(
            {
                "receipt_id": receipt.receipt_id,
                "receipt_kind": receipt.envelope["receipt_kind"],
                "relative_path": f"receipts/{name}",
                "sha256": hashlib.sha256(
                    receipt.canonical_bytes
                ).hexdigest(),
            }
        )
    _write_absent(
        compact_root / "receipt-index.json",
        _canonical(
            {
                "generation_id": generation_id,
                "receipts": receipt_index,
                "schema_id": "asw-0b5.receipt-index.v1",
            }
        ),
    )
    summary = {
        "family_terminal_state": family_result["terminal_state"],
        "generation_id": generation_id,
        "manifest_content_id": built.manifest_content_id,
        "package_content_id": built.package_content_id,
        "package_relative_path": "certified-reference-package",
        "profile_id": generator_boundary.PROFILE_ID,
        "promotion_decision_content_id": promotion[
            "decision_content_id"
        ],
        "promotion_terminal_state": promotion["terminal_state"],
        "receipt_count": len(chain),
        "schema_id": "asw-0b5.reference-certification-summary.v1",
        "v3": "issued",
        "v4": "unclaimed",
    }
    _write_absent(
        compact_root / "certification-summary.json",
        _canonical(summary),
    )
    return summary


def main(arguments: list[str] | None = None) -> int:
    """Run the real reference certification from explicit paths."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine-receipt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parsed = parser.parse_args(arguments)
    summary = execute_reference_certification(
        engine_receipt=parsed.engine_receipt,
        output_root=parsed.output,
    )
    sys.stdout.buffer.write(_canonical(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
