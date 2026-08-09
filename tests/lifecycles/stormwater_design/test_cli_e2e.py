# ABOUTME: Exercises the installed lifecycle CLI for the stormwater hydraulic family.
# ABOUTME: Verifies variant listing and materialization from outside the repository.

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast


def _run_lifecycle_cli(*args: str, cwd: Path) -> dict[str, Any]:
    executable = Path(sys.executable).parent / "aec-bench"
    completed = subprocess.run(
        [str(executable), "--json", "task", "lifecycle", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    return cast(dict[str, Any], json.loads(completed.stdout))


def test_installed_cli_lists_and_materializes_hydraulic_interaction_variant(tmp_path: Path) -> None:
    package = tmp_path / "interaction-package"

    listed = _run_lifecycle_cli(
        "list-variants",
        "hydraulic-interaction-lifecycle-review",
        cwd=tmp_path,
    )
    materialized = _run_lifecycle_cli(
        "materialize",
        "hydraulic-interaction-lifecycle-review",
        "--variant",
        "major_idf_revision",
        "--output",
        str(package),
        cwd=tmp_path,
    )

    assert listed["data"]["variants"] == [
        "administrative_no_op",
        "major_idf_revision",
        "outlet_geometry_revision",
        "tailwater_revision",
    ]
    assert materialized["data"]["package_dir"] == str(package)
    assert materialized["data"]["variant_id"] == "major_idf_revision"
    assert json.loads((package / "hidden" / "variant.json").read_text(encoding="utf-8"))["variant_id"] == (
        "major_idf_revision"
    )
