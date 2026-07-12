# ABOUTME: Exercises the installed CLI across the complete public hydraulic-world journey.
# ABOUTME: Verifies materialize, run, and independent verification from outside the repository.

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast


def _run_cli(*args: str, cwd: Path) -> dict[str, Any]:
    executable = Path(sys.executable).parent / "aec-bench"
    completed = subprocess.run(
        [str(executable), "--json", "task", "hydraulic-world", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    return cast(dict[str, Any], json.loads(completed.stdout))


def _run_composite_cli(*args: str, cwd: Path) -> dict[str, Any]:
    executable = Path(sys.executable).parent / "aec-bench"
    completed = subprocess.run(
        [str(executable), "--json", "task", "composite-template", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    return cast(dict[str, Any], json.loads(completed.stdout))


def test_installed_cli_materializes_runs_and_verifies_public_world(tmp_path: Path) -> None:
    package = tmp_path / "package"
    run = tmp_path / "run"

    listed = _run_cli("list", cwd=tmp_path)
    materialized = _run_cli(
        "materialize",
        "ssc03.public.detention-network.v1",
        "--output",
        str(package),
        cwd=tmp_path,
    )
    executed = _run_cli(
        "run",
        str(package),
        "--scenario",
        "major-100yr",
        "--output",
        str(run),
        cwd=tmp_path,
    )
    verified = _run_cli("verify", str(package), str(run), cwd=tmp_path)

    assert "ssc03.public.detention-network.v1" in listed["data"]["world_ids"]
    assert materialized["data"]["package_dir"] == str(package)
    assert executed["data"]["run_dir"] == str(run)
    assert verified["data"]["passed"] is True
    assert not (package / "conditional_releases").exists()


def test_installed_cli_lists_and_materializes_hydraulic_interaction_variant(tmp_path: Path) -> None:
    package = tmp_path / "interaction-package"

    listed = _run_composite_cli(
        "list-lifecycle-variants",
        "hydraulic-interaction-lifecycle-review",
        cwd=tmp_path,
    )
    materialized = _run_composite_cli(
        "materialize-lifecycle",
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
