# ABOUTME: Tests generic Harbor-compatible command execution for meta-harness task runs.
# ABOUTME: Verifies real subprocess execution and artifact discovery without mock mode.

from __future__ import annotations

import json
import sys
from pathlib import Path

from aec_bench.meta_harness.harbor import build_harbor_task_run_resolver, run_harbor_command


def test_run_harbor_command_executes_real_command_and_reads_artifacts(tmp_path: Path) -> None:
    output_dir = tmp_path / "harbor"

    result = run_harbor_command(
        command=_writer_command(output_dir, status="complete", reward=1.0),
        artifact_dir=output_dir,
    )

    result_json = json.loads((output_dir / "result.json").read_text(encoding="utf-8"))
    assert result["status"] == "complete"
    assert result["returncode"] == 0
    assert result_json["status"] == "complete"
    assert "result.json" in result["artifacts"]


def test_task_run_resolver_converts_real_command_result_to_evidence(tmp_path: Path) -> None:
    output_dir = tmp_path / "harbor"
    resolver = build_harbor_task_run_resolver(
        command=_writer_command(output_dir, status="complete", reward=1.0),
        artifact_dir=output_dir,
    )

    task_run = resolver({"process_id": "process.demo"})

    assert task_run["run_id"] == "process.demo.harbor"
    assert task_run["evidence"]["score"]["reward"] == 1.0
    assert task_run["evidence"]["harbor"]["returncode"] == 0
    assert "result.json" in task_run["evidence"]["artifacts"]


def _writer_command(output_dir: Path, *, status: str, reward: float) -> list[str]:
    script = (
        "import json, pathlib; "
        f"path = pathlib.Path({str(output_dir)!r}); "
        "path.mkdir(parents=True, exist_ok=True); "
        "(path / 'job.yaml').write_text('task_id: demo\\n'); "
        "(path / 'agent').mkdir(exist_ok=True); "
        "(path / 'agent' / 'input.json').write_text('{}\\n'); "
        "(path / 'agent' / 'output.md').write_text('done\\n'); "
        "(path / 'agent_result.json').write_text('{}\\n'); "
        f"(path / 'result.json').write_text(json.dumps({{'status': {status!r}, 'reward': {reward}}}))"
    )
    return [sys.executable, "-c", script]
