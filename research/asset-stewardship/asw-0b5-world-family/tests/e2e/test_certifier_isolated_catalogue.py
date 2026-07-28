# ABOUTME: Generates the complete real W2 catalogue and certifies it in a generator-free subprocess.
# ABOUTME: Proves W3 reaches only quantitative-pending-w4 with exact replay, cases, residuals, and no paths.

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from generator import execution, request, transfer

B5_ROOT = Path(__file__).parents[2]
W1_DECLARATION = B5_ROOT / "declarations" / "w1-member-authority.json"
W2_CATALOGUE = B5_ROOT / "declarations" / "w2-case-catalogue.json"
W2_W4_REPAIR = B5_ROOT / "declarations" / "w2-w4-engine-mapping-repair.json"
SOLVER_CONVERGENCE = (
    B5_ROOT / "declarations" / "solver-convergence-amendment.json"
)


def _mutate_first_semantic(
    bundle: bytes,
    mutation: object,
) -> bytes:
    value = json.loads(bundle)
    mutate = mutation
    assert callable(mutate)
    for replay in value["replays"]:
        role = replay["cases"][0]["segments"][0]["roles"][-1]
        semantic = json.loads(bytes.fromhex(role["bytes_hex"]))
        mutate(semantic)
        raw = request.canonical_json_bytes(semantic)
        role["bytes_hex"] = raw.hex()
        role["sha256"] = hashlib.sha256(raw).hexdigest()
    return request.canonical_json_bytes(value)


def _make_simultaneous(semantic: dict[str, object]) -> None:
    series = semantic["series"]
    assert isinstance(series, dict)
    pump_a = series["pump_a_setting"]
    pump_b = series["pump_b_setting"]
    assert isinstance(pump_a, dict)
    assert isinstance(pump_b, dict)
    values_a = pump_a["values"]
    values_b = pump_b["values"]
    assert isinstance(values_a, list)
    assert isinstance(values_b, list)
    values_a[0] = 1
    trace = {"pump_a": values_a, "pump_b": values_b}
    semantic["setting_trace_sha256"] = hashlib.sha256(
        request.canonical_json_bytes(trace)
    ).hexdigest()


def test_complete_real_catalogue_is_certified_without_generator_or_engine(
    tmp_path: Path,
) -> None:
    receipt_value = os.environ.get("ASW_B5_ENGINE_RECEIPT")
    assert receipt_value, "ASW_B5_ENGINE_RECEIPT must name the fresh real B5 build receipt"
    generated = execution.execute_catalogue(
        authority_bytes=W1_DECLARATION.read_bytes(),
        catalogue_bytes=W2_CATALOGUE.read_bytes(),
        receipt_path=Path(receipt_value),
        repair_bytes=W2_W4_REPAIR.read_bytes(),
        solver_convergence_bytes=SOLVER_CONVERGENCE.read_bytes(),
        workspace=tmp_path / "generation",
    )
    bundle = transfer.build_certifier_bundle(generated)
    sensitivity_bundle = transfer.build_sensitivity_bundle(
        generated,
        case_ids=(
            "G12_CLEAN_ASSESS",
            "G21_OBSTRUCTION_TRIGGER",
        ),
        probe_id="INT.test-subset",
    )

    isolated = tmp_path / "isolated-certifier"
    isolated.mkdir()
    shutil.copytree(B5_ROOT / "certifier", isolated / "certifier")
    (isolated / "bundle.json").write_bytes(bundle)
    (isolated / "promotable.json").write_bytes(
        _mutate_first_semantic(
            bundle,
            lambda semantic: semantic.update({"promotable": True}),
        )
    )
    (isolated / "simultaneous.json").write_bytes(
        _mutate_first_semantic(bundle, _make_simultaneous)
    )
    (isolated / "sensitivity.json").write_bytes(
        sensitivity_bundle
    )
    (isolated / "w1.json").write_bytes(W1_DECLARATION.read_bytes())
    script = (
        "from pathlib import Path\n"
        "from certifier import certification\n"
        "import sys\n"
        "authority=Path('w1.json').read_bytes()\n"
        "for name in ('bundle.json','promotable.json','simultaneous.json'):\n"
        " result=certification.certify_bundle(Path(name).read_bytes(),authority)\n"
        " sys.stdout.buffer.write(certification.certification_result_bytes(result))\n"
        "result=certification.certify_sensitivity_bundle("
        "Path('sensitivity.json').read_bytes(),authority)\n"
        "sys.stdout.buffer.write("
        "certification.certification_result_bytes(result))\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        cwd=isolated,
        env={
            "LC_ALL": "C",
            "PYTHONHASHSEED": "0",
            "PYTHONPATH": str(isolated),
        },
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr.decode("utf-8")
    result, promotable, simultaneous, sensitivity = [
        json.loads(line) for line in completed.stdout.splitlines()
    ]
    assert result["terminal_state"] == "quantitative-pending-w4"
    assert result["first_failing_stage"] == "w4-tolerance-required"
    assert result["promotable"] is False
    assert [case["case_id"] for case in result["cases"]] == list(request.CASE_IDS)
    assert sum(len(case["segments"]) for case in result["cases"]) == 23
    assert [record["check_id"] for record in result["residual_register"]] == [
        f"C-R{index:02d}" for index in range(1, 25)
    ]
    assert all(check["outcome"] == "satisfied" for check in result["checks"])
    assert promotable["terminal_state"] == "structural-reject"
    assert promotable["first_failing_stage"] == "semantic-maturity"
    assert simultaneous["terminal_state"] == "exact-reject"
    assert simultaneous["first_failing_stage"] == "observation"
    assert sensitivity["terminal_state"] == "quantitative-pending-w4"
    assert [item["case_id"] for item in sensitivity["cases"]] == [
        "G12_CLEAN_ASSESS",
        "G21_OBSTRUCTION_TRIGGER",
    ]
    assert b"/Users/" not in completed.stdout
    assert b"/private/" not in completed.stdout
    assert b'"pass"' not in completed.stdout
    assert b'"accepted"' not in completed.stdout
    assert b'"certified"' not in completed.stdout
