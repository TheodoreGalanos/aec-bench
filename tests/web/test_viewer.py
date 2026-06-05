# ABOUTME: Tests for the trial viewer API endpoints with trajectory and metadata.
# ABOUTME: Verifies step rendering, RLM detection, prev/next navigation, and artefacts.

import json
from pathlib import Path

from fastapi.testclient import TestClient

from aec_bench.contracts.trajectory import TrajectoryEntry
from aec_bench.evaluation.trajectory_reader import (
    detect_adapter_type,
    detect_rlm_trial,
    group_by_step,
)
from aec_bench.ledger.writer import write_trial_record
from aec_bench.web.app import create_app
from aec_bench.web.routes.viewer import _build_viewer_step_summaries
from tests.support.trial_record_factories import make_trial_record


def _make_client_with_trial(tmp_path: Path) -> TestClient:
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    for i in range(3):
        write_trial_record(
            ledger_root=ledger,
            record=make_trial_record(experiment_id="exp-01", trial_id=f"trial-{i}"),
        )
    return TestClient(create_app(ledger_root=ledger, tasks_root=tasks))


def _write_trajectory_jsonl(path: Path, entries: list[dict[str, object]]) -> None:
    """Write a trajectory JSONL file with version header and entry dicts."""
    lines = [json.dumps({"format": "aec-bench-trajectory", "version": 1})]
    for entry in entries:
        lines.append(json.dumps(entry))
    path.write_text("\n".join(lines), encoding="utf-8")


def _make_client_with_rlm_trial(tmp_path: Path, *, write_symbolic_state: bool = False) -> TestClient:
    """Create a test client with an RLM trial that has trajectory metadata."""
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    tasks = tmp_path / "tasks"
    tasks.mkdir()

    # Write the trajectory file first
    traj_dir = tmp_path / "output"
    traj_dir.mkdir()
    traj_path = traj_dir / "trajectory.jsonl"
    _write_trajectory_jsonl(
        traj_path,
        [
            {
                "step": 0,
                "role": "tool_call",
                "tool_name": "repl",
                "command": "load_brief()",
            },
            {
                "step": 0,
                "role": "tool_result",
                "tool_name": "repl",
                "stdout": "ok",
                "exit_code": 0,
                "metadata": {
                    "var_diff": {"new": ["brief"], "removed": []},
                    "variables": {"brief": "str(4,800)"},
                    "scratchpad_keys": ["brief_facts"],
                    "template_progress": {
                        "completed": 1,
                        "total": 9,
                        "filled": ["background"],
                        "unlocked": ["design"],
                    },
                    "tokens": {
                        "call_input": 15000,
                        "cache_read": 180000,
                        "cache_write": 15000,
                        "cost_cumulative": 0.08,
                        "grand_total": 200000,
                    },
                    "subcalls": [
                        {
                            "type": "llm_query",
                            "prompt": "Write Background section",
                            "response": "# Background\n\nThis is...",
                            "input_tokens": 500,
                            "output_tokens": 800,
                        }
                    ],
                },
            },
            {
                "step": 1,
                "role": "tool_call",
                "tool_name": "repl",
                "command": "fill_section('design')",
            },
            {
                "step": 1,
                "role": "tool_result",
                "tool_name": "repl",
                "stdout": "ok",
                "exit_code": 0,
                "metadata": {
                    "var_diff": {"new": ["design_notes"], "removed": []},
                    "variables": {
                        "brief": "str(4,800)",
                        "design_notes": "str(2,100)",
                    },
                    "scratchpad_keys": ["brief_facts", "ref_facts"],
                    "template_progress": {
                        "completed": 2,
                        "total": 9,
                        "filled": ["background", "design"],
                        "unlocked": ["vfm"],
                    },
                    "tokens": {
                        "call_input": 18000,
                        "cache_read": 190000,
                        "cache_write": 16000,
                        "cost_cumulative": 0.11,
                        "grand_total": 212000,
                    },
                },
            },
        ],
    )

    # Optionally write symbolic_state.json alongside the trajectory
    if write_symbolic_state:
        symbolic_path = traj_dir / "symbolic_state.json"
        symbolic_path.write_text(
            json.dumps(
                {
                    "brief": "This is the project brief text...",
                    "design_notes": {"key1": "val1", "key2": "val2"},
                }
            ),
            encoding="utf-8",
        )

    from aec_bench.contracts.trial_record import OutputRecord

    record = make_trial_record(
        experiment_id="exp-rlm",
        trial_id="trial-rlm-0",
        outputs=OutputRecord(
            raw_output_path=str(traj_dir / "output.jsonl"),
            trajectory_path=str(traj_path),
        ),
    )
    write_trial_record(ledger_root=ledger, record=record)

    return TestClient(create_app(ledger_root=ledger, tasks_root=tasks))


# ── Unit tests for trajectory helpers ─────────────────────────────────────


def test_detect_rlm_trial_with_metadata() -> None:
    entries = [
        TrajectoryEntry(
            step=1,
            role="tool_result",
            tool_name="repl",
            stdout="ok",
            metadata={"template_progress": {"completed": 1, "total": 9}},
        ),
    ]
    assert detect_rlm_trial(entries) is True


def test_detect_rlm_trial_without_metadata() -> None:
    entries = [
        TrajectoryEntry(step=1, role="tool_result", tool_name="bash", stdout="ok"),
    ]
    assert detect_rlm_trial(entries) is False


def test_step_summary_includes_metadata() -> None:
    entries = [
        TrajectoryEntry(step=1, role="tool_call", tool_name="repl", command="repl_tool"),
        TrajectoryEntry(
            step=1,
            role="tool_result",
            tool_name="repl",
            stdout="ok",
            metadata={
                "var_diff": {"new": ["brief"], "removed": []},
                "variables": {"brief": "str(4,800)"},
                "template_progress": {
                    "completed": 0,
                    "total": 9,
                    "filled": [],
                    "unlocked": ["background"],
                },
            },
        ),
    ]
    grouped = group_by_step(entries)
    summaries = _build_viewer_step_summaries(grouped)
    assert len(summaries) == 1
    assert summaries[0].metadata is not None
    assert summaries[0].metadata["template_progress"]["total"] == 9


def test_step_summary_without_metadata() -> None:
    entries = [
        TrajectoryEntry(step=1, role="tool_call", tool_name="bash", command="ls"),
        TrajectoryEntry(step=1, role="tool_result", tool_name="bash", stdout="file.txt", exit_code=0),
    ]
    grouped = group_by_step(entries)
    summaries = _build_viewer_step_summaries(grouped)
    assert len(summaries) == 1
    assert summaries[0].metadata is None


def test_step_summary_includes_call_type() -> None:
    entries = [
        TrajectoryEntry(step=1, role="assistant", content="warmup", call_type="warmup"),
        TrajectoryEntry(
            step=1,
            role="tool_call",
            tool_name="bash",
            command="echo hi",
            call_type="warmup",
        ),
        TrajectoryEntry(
            step=1,
            role="tool_result",
            tool_name="bash",
            stdout="hi",
            exit_code=0,
            call_type="warmup",
        ),
    ]
    grouped = group_by_step(entries)
    summaries = _build_viewer_step_summaries(grouped)
    assert len(summaries) == 1
    assert summaries[0].call_type == "warmup"


def test_step_summary_call_type_none_when_absent() -> None:
    entries = [
        TrajectoryEntry(step=1, role="tool_call", tool_name="bash", command="ls"),
        TrajectoryEntry(step=1, role="tool_result", tool_name="bash", stdout="ok", exit_code=0),
    ]
    grouped = group_by_step(entries)
    summaries = _build_viewer_step_summaries(grouped)
    assert summaries[0].call_type is None


def test_step_summary_includes_output_summary() -> None:
    entries = [
        TrajectoryEntry(step=1, role="tool_call", tool_name="bash", command="cat big.txt"),
        TrajectoryEntry(
            step=1,
            role="tool_result",
            tool_name="bash",
            stdout="x" * 500,
            exit_code=0,
            output_summary="x" * 200 + "\u2026",
        ),
    ]
    grouped = group_by_step(entries)
    summaries = _build_viewer_step_summaries(grouped)
    assert summaries[0].output_summary == "x" * 200 + "\u2026"


def test_step_summary_output_summary_none_when_absent() -> None:
    entries = [
        TrajectoryEntry(step=1, role="tool_call", tool_name="bash", command="ls"),
        TrajectoryEntry(step=1, role="tool_result", tool_name="bash", stdout="ok", exit_code=0),
    ]
    grouped = group_by_step(entries)
    summaries = _build_viewer_step_summaries(grouped)
    assert summaries[0].output_summary is None


# ── API endpoint tests ─────────────────────────────────────────────────────


def test_viewer_api_meta_returns_json(tmp_path: Path) -> None:
    """API meta endpoint returns JSON with trial metadata and step summaries."""
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    tasks = tmp_path / "tasks"
    tasks.mkdir()

    # Write the trajectory so has_trajectory is True
    traj_dir = tmp_path / "output"
    traj_dir.mkdir()
    traj_path = traj_dir / "trajectory.jsonl"
    _write_trajectory_jsonl(
        traj_path,
        [
            {"step": 0, "role": "tool_call", "tool_name": "bash", "command": "ls"},
            {"step": 0, "role": "tool_result", "tool_name": "bash", "stdout": "ok", "exit_code": 0},
        ],
    )

    from aec_bench.contracts.trial_record import EnvironmentSnapshot, OutputRecord

    record = make_trial_record(
        experiment_id="experiment-001",
        trial_id="trial-001",
        environment=EnvironmentSnapshot(
            runtime_image="ghcr.io/example/task-image:latest",
            compute_backend="morph",
            tool_versions={"codes_search": "abc123"},
        ),
        outputs=OutputRecord(
            raw_output_path=str(traj_dir / "output.jsonl"),
            trajectory_path=str(traj_path),
        ),
    )
    write_trial_record(ledger_root=ledger, record=record)

    client = TestClient(create_app(ledger_root=ledger, tasks_root=tasks))
    resp = client.get("/api/viewer/experiment-001/trial-001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["trial_id"] == "trial-001"
    assert data["experiment_id"] == "experiment-001"
    assert "steps" in data
    assert "is_rlm_trial" in data
    assert "reward" in data
    assert "reward_class" in data
    assert "artefacts" in data
    assert "has_trajectory" in data
    assert data["compute_backend"] == "morph"


def test_viewer_api_meta_404_for_missing_trial(tmp_path: Path) -> None:
    """API meta endpoint returns 404 when trial does not exist."""
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    client = TestClient(create_app(ledger_root=ledger, tasks_root=tasks))
    resp = client.get("/api/viewer/no-such-exp/no-such-trial")
    assert resp.status_code == 404


def test_viewer_api_step_returns_messages(tmp_path: Path) -> None:
    """API step endpoint returns messages for a specific step number."""
    client = _make_client_with_rlm_trial(tmp_path)
    resp = client.get("/api/viewer/exp-rlm/trial-rlm-0/steps/0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["step_num"] == 0
    assert "messages" in data
    assert isinstance(data["messages"], list)


def test_viewer_api_state_returns_rlm_data(tmp_path: Path) -> None:
    """API state endpoint returns symbolic_state and scratchpad_data."""
    client = _make_client_with_rlm_trial(tmp_path, write_symbolic_state=True)
    resp = client.get("/api/viewer/exp-rlm/trial-rlm-0/state")
    assert resp.status_code == 200
    data = resp.json()
    assert "symbolic_state" in data
    assert "scratchpad_data" in data


def test_viewer_api_meta_not_found(tmp_path: Path) -> None:
    """API returns 404 for a non-existent trial."""
    client = _make_client_with_trial(tmp_path)
    resp = client.get("/api/viewer/exp-01/nonexistent")
    assert resp.status_code == 404


def test_viewer_api_prev_next_navigation(tmp_path: Path) -> None:
    """API meta should include prev/next trial IDs for navigation."""
    client = _make_client_with_trial(tmp_path)
    resp = client.get("/api/viewer/exp-01/trial-1")
    assert resp.status_code == 200
    data = resp.json()
    assert "prev_trial" in data
    assert "next_trial" in data
    # trial-1 is in the middle, so both prev and next should be non-null
    assert data["prev_trial"] == "trial-0" or data["next_trial"] == "trial-2"


def test_viewer_api_is_rlm_trial_true(tmp_path: Path) -> None:
    """API should report is_rlm_trial=True for RLM trials with trajectory metadata."""
    client = _make_client_with_rlm_trial(tmp_path)
    resp = client.get("/api/viewer/exp-rlm/trial-rlm-0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_rlm_trial"] is True


def test_viewer_api_is_rlm_trial_false_for_plain_trial(tmp_path: Path) -> None:
    """API should report is_rlm_trial=False for trials without RLM metadata."""
    client = _make_client_with_trial(tmp_path)
    resp = client.get("/api/viewer/exp-01/trial-0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_rlm_trial"] is False


def test_viewer_api_rlm_step_has_metadata(tmp_path: Path) -> None:
    """Steps from RLM trials should include metadata in the step summaries."""
    client = _make_client_with_rlm_trial(tmp_path)
    resp = client.get("/api/viewer/exp-rlm/trial-rlm-0")
    assert resp.status_code == 200
    data = resp.json()
    steps_with_metadata = [s for s in data["steps"] if s.get("metadata") is not None]
    assert len(steps_with_metadata) > 0
    # First step with metadata should have template_progress
    meta = steps_with_metadata[0]["metadata"]
    assert "template_progress" in meta
    assert meta["template_progress"]["total"] == 9


def test_viewer_api_state_symbolic_data(tmp_path: Path) -> None:
    """When symbolic_state.json exists, the state endpoint should return it."""
    client = _make_client_with_rlm_trial(tmp_path, write_symbolic_state=True)
    resp = client.get("/api/viewer/exp-rlm/trial-rlm-0/state")
    assert resp.status_code == 200
    data = resp.json()
    # The symbolic state should contain the test variable
    assert "brief" in data["symbolic_state"]


def test_viewer_api_state_empty_when_no_symbolic_state(tmp_path: Path) -> None:
    """When no symbolic_state.json exists, state endpoint returns empty object."""
    client = _make_client_with_rlm_trial(tmp_path, write_symbolic_state=False)
    resp = client.get("/api/viewer/exp-rlm/trial-rlm-0/state")
    assert resp.status_code == 200
    data = resp.json()
    assert data["symbolic_state"] == {}


def test_detect_adapter_type_lambda_rlm() -> None:
    entries = [
        TrajectoryEntry(
            step=1,
            role="tool_result",
            tool_name="extract",
            stdout="ok",
            metadata={
                "phase": "extract",
                "section_id": "background",
                "plan_state": {"phase": "extract", "llm_calls": 1},
                "template_progress": {"completed": 0, "total": 2},
            },
        ),
    ]
    assert detect_adapter_type(entries) == "lambda-rlm"


def test_detect_adapter_type_rlm() -> None:
    entries = [
        TrajectoryEntry(
            step=1,
            role="tool_result",
            tool_name="repl",
            stdout="ok",
            metadata={"template_progress": {"completed": 1, "total": 9}},
        ),
    ]
    assert detect_adapter_type(entries) == "rlm"


def test_detect_adapter_type_other() -> None:
    entries = [
        TrajectoryEntry(step=1, role="tool_result", tool_name="bash", stdout="ok"),
    ]
    assert detect_adapter_type(entries) == "other"


def test_viewer_api_meta_includes_adapter_type(tmp_path: Path) -> None:
    """API meta endpoint returns adapter_type field."""
    client = _make_client_with_rlm_trial(tmp_path)
    resp = client.get("/api/viewer/exp-rlm/trial-rlm-0")
    assert resp.status_code == 200
    data = resp.json()
    assert "adapter_type" in data
    assert data["adapter_type"] == "rlm"


def test_viewer_api_state_includes_plan_state(tmp_path: Path) -> None:
    """API state endpoint returns plan_state field (null for RLM trials)."""
    client = _make_client_with_rlm_trial(tmp_path)
    resp = client.get("/api/viewer/exp-rlm/trial-rlm-0/state")
    assert resp.status_code == 200
    data = resp.json()
    assert "plan_state" in data
    assert data["plan_state"] is None


def test_viewer_meta_includes_dataset_id_when_present(tmp_path: Path) -> None:
    """API meta endpoint includes dataset_id when the trial belongs to a dataset run."""
    ledger = tmp_path / "ledger"
    tasks = tmp_path / "tasks"
    ledger.mkdir()
    tasks.mkdir()
    record = make_trial_record(
        trial_id="trial-001",
        experiment_id="exp-a",
        dataset_id="voltage-drop-core@1",
    )
    write_trial_record(ledger_root=ledger, record=record)

    app = create_app(ledger_root=ledger, tasks_root=tasks)
    client = TestClient(app)
    resp = client.get("/api/viewer/exp-a/trial-001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["dataset_id"] == "voltage-drop-core@1"


def test_viewer_meta_dataset_id_is_null_for_inline_trial(tmp_path: Path) -> None:
    """API meta endpoint returns null dataset_id for trials not linked to a dataset."""
    ledger = tmp_path / "ledger"
    tasks = tmp_path / "tasks"
    ledger.mkdir()
    tasks.mkdir()
    record = make_trial_record(
        trial_id="trial-002",
        experiment_id="exp-b",
        dataset_id=None,
    )
    write_trial_record(ledger_root=ledger, record=record)

    app = create_app(ledger_root=ledger, tasks_root=tasks)
    client = TestClient(app)
    resp = client.get("/api/viewer/exp-b/trial-002")
    assert resp.status_code == 200
    data = resp.json()
    assert data["dataset_id"] is None
