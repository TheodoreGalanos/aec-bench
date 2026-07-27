# ABOUTME: Verifies rejected-family handoff into an isolated promotion-only process.
# ABOUTME: Proves V3 refusal needs no generator, certifier, sensitivity, SWMM, or research path.

import json
import shutil
import subprocess
import sys
from pathlib import Path

from sensitivity import family

B5_ROOT = Path(__file__).parents[2]
W1_DECLARATION = B5_ROOT / "declarations" / "w1-member-authority.json"
PROBE_DECLARATION = B5_ROOT / "declarations" / "w4-probe-catalogue.json"


def test_rejected_family_is_refused_in_promotion_only_process(
    tmp_path: Path,
) -> None:
    inventory = family.build_analytical_inventory(
        authority_bytes=W1_DECLARATION.read_bytes(),
        probe_catalogue_bytes=PROBE_DECLARATION.read_bytes(),
    )
    family_result = family.freeze_family_decision(
        analytical_inventory=inventory,
        composition_result_content_id="1" * 64,
        composition_terminal_state="w4-budget-reject",
        composition_first_failure=("C-R08-derived-budget-lower-bound-exceeds-relative-ceiling"),
    )
    isolated = tmp_path / "promotion-only"
    isolated.mkdir()
    shutil.copytree(B5_ROOT / "promotion", isolated / "promotion")
    (isolated / "family.json").write_bytes(family.family_result_bytes(family_result))
    script = (
        "from pathlib import Path\n"
        "from promotion import decision,package_gate\n"
        "raw=Path('family.json').read_bytes()\n"
        "try:\n"
        " package_gate.authorize_package_root("
        "family_result_bytes=raw,target=Path('package'))\n"
        "except package_gate.PackageGateError:\n"
        " pass\n"
        "else:\n"
        " raise SystemExit('rejected family created a package root')\n"
        "result=decision.refuse_v3(raw)\n"
        "Path('decision.json').write_bytes("
        "decision.promotion_decision_bytes(result))\n"
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
    assert not (isolated / "package").exists()
    result = json.loads((isolated / "decision.json").read_bytes())
    assert result["terminal_state"] == "promotion-generation-reject"
    assert result["manifest_content_ids"] == []
    assert not (isolated / "generator").exists()
    assert not (isolated / "certifier").exists()
    assert not (isolated / "sensitivity").exists()
    assert not any(path.name.lower().startswith("swmm") for path in isolated.rglob("*"))
