# ABOUTME: Runs closeout preparation and review through the installed JSON command.
# ABOUTME: Proves transport parity, exact retry, reviewer redaction, and strict evaluation.

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

from test_closeout_review_case_derivation import _request
from test_rich_work_harbor_parity_e2e import _execute_direct

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review import (
    PumpStationReviewPublicCase,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review_control import (
    PUMP_STATION_REVIEW_TASK_ID,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review_session import (
    PumpStationReviewSessionOpenMode,
    PumpStationReviewSessionRequest,
    build_reference_review_submission,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review_verifier import (
    verify_pump_station_review,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PumpStationWorldSessionFactory,
)


def _write_request(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _run_review_interface(
    *,
    source_run_dir: Path,
    review_dir: Path,
    request_path: Path,
    cwd: Path,
    host_authority_id: str | None = None,
) -> dict[str, Any]:
    executable = Path(sys.executable).parent / "aec-bench"
    command = [
        str(executable),
        "--json",
        "task",
        "pump-station-world",
        "review-interface",
        "--source-run-dir",
        str(source_run_dir),
        "--review-dir",
        str(review_dir),
        "--request-path",
        str(request_path),
    ]
    if host_authority_id is not None:
        command.extend(("--host-authority-id", host_authority_id))
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    return cast(dict[str, Any], json.loads(completed.stdout)["data"])


def _run_reviewer_private_action(
    *,
    source_run_dir: Path,
    review_dir: Path,
    request_path: Path,
    cwd: Path,
) -> subprocess.CompletedProcess[str]:
    executable = Path(sys.executable).parent / "aec-bench"
    return subprocess.run(
        [
            str(executable),
            "--json",
            "task",
            "pump-station-world",
            "review-interface",
            "--source-run-dir",
            str(source_run_dir),
            "--review-dir",
            str(review_dir),
            "--request-path",
            str(request_path),
        ],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_installed_json_prepares_observes_submits_and_verifies_review(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source-world"
    review_root = tmp_path / "review-cases"
    completed = _execute_direct(
        PumpStationWorldSessionFactory(
            source_root,
            evidence_health=True,
        )
    )
    preparation = _request(completed.run.snapshot())
    control_payload = {
        "surface": "control",
        "operation": "execute",
        "control_request": {
            "request_id": preparation.request_id,
            "operation": "prepare_case",
            "task_review_id": PUMP_STATION_REVIEW_TASK_ID,
            "authority_id": "host-installed-review",
            "preparation_request": preparation.model_dump(mode="json"),
        },
    }

    prepared = _run_review_interface(
        source_run_dir=source_root,
        review_dir=review_root,
        request_path=_write_request(
            tmp_path / "prepare-review.json",
            control_payload,
        ),
        cwd=tmp_path,
        host_authority_id="host-installed-review",
    )
    repeated = _run_review_interface(
        source_run_dir=source_root,
        review_dir=review_root,
        request_path=_write_request(
            tmp_path / "retry-review.json",
            control_payload,
        ),
        cwd=tmp_path,
        host_authority_id="host-installed-review",
    )
    public_case = PumpStationReviewPublicCase.model_validate(prepared["public_case"])
    session_request = PumpStationReviewSessionRequest(
        open_mode=PumpStationReviewSessionOpenMode.OPEN,
        session_id="installed-review-session",
        case_id=public_case.case_id,
        public_case_content_sha256=public_case.content_sha256,
        reviewer_tenure_id="installed-review-tenure",
    )
    observed = _run_review_interface(
        source_run_dir=source_root,
        review_dir=review_root,
        request_path=_write_request(
            tmp_path / "observe-review.json",
            {
                "surface": "reviewer",
                "operation": "observe",
                "session_request": session_request.model_dump(mode="json"),
            },
        ),
        cwd=tmp_path,
    )
    reference = build_reference_review_submission(
        public_case,
        review_id="installed-review-001",
        reviewer_tenure_id="installed-review-tenure",
    )
    submission_arguments = reference.model_dump(
        mode="json",
        exclude={
            "schema_version",
            "content_sha256",
            "case_id",
            "public_case_content_sha256",
            "pack_content_sha256",
            "reviewer_tenure_id",
        },
    )
    submitted = _run_review_interface(
        source_run_dir=source_root,
        review_dir=review_root,
        request_path=_write_request(
            tmp_path / "submit-review.json",
            {
                "surface": "reviewer",
                "operation": "invoke",
                "session_request": session_request.model_dump(mode="json"),
                "action_name": "submit_closeout_review",
                "arguments": submission_arguments,
            },
        ),
        cwd=tmp_path,
    )
    verified = verify_pump_station_review(
        source_run_root=source_root,
        review_repository_root=review_root,
        case_id=public_case.case_id,
        review_id=reference.review_id,
    )
    public_text = json.dumps(observed, sort_keys=True)
    denied = _run_reviewer_private_action(
        source_run_dir=source_root,
        review_dir=review_root,
        request_path=_write_request(
            tmp_path / "denied-private-review-action.json",
            {
                "surface": "reviewer",
                "operation": "invoke",
                "session_request": session_request.model_dump(mode="json"),
                "action_name": "prepare_case",
                "arguments": {},
            },
        ),
        cwd=tmp_path,
    )

    assert repeated == prepared
    assert observed["public_case"] == prepared["public_case"]
    assert submitted["status"] == "accepted"
    assert verified.valid is True
    assert "issue_class" not in public_text
    assert "verifier_target" not in public_text
    assert "unaffected_control_ids" not in public_text
    assert "scheduled_events" not in public_text
    assert denied.returncode != 0
    assert "reviewer action is unavailable" in (denied.stderr + denied.stdout)
