# ABOUTME: Runs fresh pinned-engine probes twice and assembles B3 replay evidence.
# ABOUTME: Fails on stale paths, identity drift, warnings, convergence failures, or independent-check failures.

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from asw_b3_swmm.build import (
    BuildBoundaryError,
    assert_absent_workspace,
    sha256_file,
    validate_version_output,
    verify_build_receipt,
)
from asw_b3_swmm.constants import SWMM_COMMIT, SWMM_VERSION
from asw_b3_swmm.output import OutputApi, canonical_semantic_hash
from asw_b3_swmm.rendering import render_probe
from asw_b3_swmm.specification import load_specification
from asw_b3_swmm.verification import verify_mirrored_probes, verify_probe


class ExecutionError(RuntimeError):
    """Raised when a real SWMM probe cannot produce valid B3 evidence."""


def spike_root() -> Path:
    """Return the research source root without making it a runtime contract."""
    return Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _dynamic_library_environment(bin_directory: Path) -> dict[str, str]:
    environment = dict(os.environ)
    variable = "DYLD_LIBRARY_PATH" if sys.platform == "darwin" else "LD_LIBRARY_PATH"
    existing = environment.get(variable)
    environment[variable] = str(bin_directory) if not existing else f"{bin_directory}{os.pathsep}{existing}"
    return environment


def _run_engine(executable: Path, input_path: Path, report_path: Path, output_path: Path) -> str:
    if report_path.exists() or output_path.exists():
        raise ExecutionError("refusing to run with stale report or output paths")
    completed = subprocess.run(
        (str(executable), str(input_path), str(report_path), str(output_path)),
        env=_dynamic_library_environment(executable.parent),
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if completed.returncode != 0:
        raise ExecutionError(
            f"runswmm exited {completed.returncode}\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    if not report_path.is_file() or not output_path.is_file():
        raise ExecutionError("runswmm returned without producing both report and binary output")
    return completed.stdout + completed.stderr


def _report_summary(report_path: Path, console_output: str) -> dict[str, object]:
    report = report_path.read_text(encoding="latin-1", errors="strict")
    combined = f"{console_output}\n{report}"
    errors = sorted(set(re.findall(r"\bERROR\s+\d+\b[^\n]*", combined)))
    warnings = sorted(set(re.findall(r"\bWARNING\s+\d+\b[^\n]*", combined)))
    if errors:
        raise ExecutionError(f"SWMM report contains errors: {errors!r}")
    if warnings:
        raise ExecutionError(f"SWMM report contains unapproved warnings: {warnings!r}")
    if "Simulation complete" not in console_output or "Analysis ended on:" not in report:
        raise ExecutionError("SWMM completion markers are absent")

    continuity_match = re.search(r"Continuity Error \(%\)\s+\.+\s+(-?\d+(?:\.\d+)?)", report)
    nonconverging_match = re.search(
        r"% of Steps Not Converging\s+:\s+(\d+(?:\.\d+)?)",
        report,
    )
    if continuity_match is None or nonconverging_match is None:
        raise ExecutionError("SWMM report omits required convergence or continuity metadata")
    not_converging_percent = float(nonconverging_match.group(1))
    if not_converging_percent != 0.0 or "Convergence obtained at all time steps." not in report:
        raise ExecutionError(f"SWMM did not converge at all steps; percent not converging={not_converging_percent}")
    return {
        "errors": [],
        "warnings": [],
        "flow_routing_continuity_error_percent": float(continuity_match.group(1)),
        "steps_not_converging_percent": not_converging_percent,
        "convergence_obtained_at_all_steps": True,
    }


def _artifact(receipt: dict[str, Any], name: str) -> tuple[Path, str]:
    raw = receipt["artifacts"][name]
    if not isinstance(raw, dict):
        raise BuildBoundaryError(f"invalid artifact receipt for {name}")
    return Path(raw["path"]), str(raw["sha256"])


def _execute_probe(
    *,
    executable: Path,
    output_library: Path,
    run_directory: Path,
    probe_id: str,
    specification_path: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    run_directory.mkdir()
    specification = load_specification(specification_path)
    probe = specification.probe(probe_id)
    input_path = run_directory / f"{probe_id}.inp"
    report_path = run_directory / f"{probe_id}.rpt"
    output_path = run_directory / f"{probe_id}.out"
    input_path.write_text(render_probe(specification, probe_id), encoding="utf-8")

    console_output = _run_engine(executable, input_path, report_path, output_path)
    report_summary = _report_summary(report_path, console_output)
    semantic_result = OutputApi(output_library).extract(output_path, specification, probe)
    findings = verify_probe(
        semantic_result,
        wet_well_plan_area_m2=specification.diagnostic_geometry.wet_well_plan_area_m2,
    )
    semantic_hash = canonical_semantic_hash(semantic_result)
    result_path = run_directory / f"{probe_id}.semantic.json"
    _write_json(result_path, semantic_result)
    run_record: dict[str, object] = {
        "probe_id": probe_id,
        "input_sha256": sha256_file(input_path),
        "report_sha256": sha256_file(report_path),
        "binary_output_sha256": sha256_file(output_path),
        "semantic_output_sha256": semantic_hash,
        "semantic_result_sha256": sha256_file(result_path),
        "report": report_summary,
        "independent_diagnostic_checks": findings,
    }
    return semantic_result, run_record


def reproduce(build_receipt_path: Path, run_root: Path) -> dict[str, Any]:
    """Run both probes twice and issue a fail-closed local verification receipt."""
    run_root = run_root.resolve()
    assert_absent_workspace(run_root)
    run_root.mkdir(parents=True)
    receipt = verify_build_receipt(build_receipt_path.resolve())
    executable, executable_hash = _artifact(receipt, "runswmm")
    output_library, output_library_hash = _artifact(receipt, "swmm_output_library")
    solver_library, solver_library_hash = _artifact(receipt, "swmm_solver_library")
    version = subprocess.run(
        (str(executable), "--version"),
        env=_dynamic_library_environment(executable.parent),
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if version.returncode != 0:
        raise ExecutionError(f"version check failed with exit code {version.returncode}")
    validate_version_output(version.stdout)

    specification_path = spike_root() / "fixtures" / "spike-probes.json"
    replay_records: dict[str, object] = {}
    semantic_results: dict[str, dict[str, dict[str, object]]] = {}
    for replay_index in (1, 2):
        replay_id = f"replay_{replay_index}"
        replay_directory = run_root / replay_id
        replay_directory.mkdir()
        probe_results: dict[str, dict[str, object]] = {}
        probe_records: dict[str, object] = {}
        for probe_id in ("a_duty", "b_duty_label_probe"):
            result, record = _execute_probe(
                executable=executable,
                output_library=output_library,
                run_directory=replay_directory / probe_id,
                probe_id=probe_id,
                specification_path=specification_path,
            )
            probe_results[probe_id] = result
            probe_records[probe_id] = record
        mirror_findings = verify_mirrored_probes(
            probe_results["a_duty"],
            probe_results["b_duty_label_probe"],
        )
        semantic_results[replay_id] = probe_results
        replay_records[replay_id] = {
            "probes": probe_records,
            "independent_label_symmetry_checks": mirror_findings,
        }

    replay_hashes_match = all(
        canonical_semantic_hash(semantic_results["replay_1"][probe_id])
        == canonical_semantic_hash(semantic_results["replay_2"][probe_id])
        for probe_id in ("a_duty", "b_duty_label_probe")
    )
    if not replay_hashes_match:
        raise ExecutionError("second run produced a different semantic output hash")
    input_hashes_match = all(
        replay_records["replay_1"]["probes"][probe_id]["input_sha256"]
        == replay_records["replay_2"]["probes"][probe_id]["input_sha256"]
        for probe_id in ("a_duty", "b_duty_label_probe")
    )
    if not input_hashes_match:
        raise ExecutionError("replay inputs differ")

    evidence: dict[str, Any] = {
        "record_version": "asw-0b3.engine-verification.v1",
        "status": "pass",
        "authority": {
            "stage": "ASW-0B3",
            "scope": "research_only",
            "promotable": False,
            "world_parameters_selected": False,
            "raw_outputs_promoted": False,
        },
        "engine": {
            "version": SWMM_VERSION,
            "commit": SWMM_COMMIT,
            "runswmm_sha256": executable_hash,
            "output_library_sha256": output_library_hash,
            "solver_library_sha256": solver_library_hash,
            "build_receipt_sha256": sha256_file(build_receipt_path),
        },
        "fixture": {
            "sha256": sha256_file(specification_path),
            "scope": "spike_only",
            "promotable": False,
        },
        "runs": replay_records,
        "replay": {
            "semantic_hashes_match": True,
            "input_hashes_match": True,
            "semantic_hashes": {
                probe_id: canonical_semantic_hash(semantic_results["replay_1"][probe_id])
                for probe_id in ("a_duty", "b_duty_label_probe")
            },
        },
        "verification": {
            "all_checks_passed": True,
            "claims_physical_world_certification": False,
            "claims_benchmark_validity": False,
        },
    }
    evidence_path = run_root / "engine-verification-receipt.json"
    _write_json(evidence_path, evidence)
    evidence["local_receipt_path"] = str(evidence_path)
    return evidence
