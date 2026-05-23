# ABOUTME: Tests the verifier re-invocation helper with synthesised workspaces.
# ABOUTME: Integration-style: uses a fake verify.py that writes a known reward.json.

from pathlib import Path

from aec_bench.remediation.verifier_runner import run_verifier


def test_run_verifier_reads_reward_and_details(tmp_path: Path) -> None:
    """Set up a minimal task + workspace, run a fake verifier that writes reward.json."""
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    (task_dir / "documents").mkdir()
    (task_dir / "documents" / "sample.md").write_text("Sample.")
    (task_dir / "report_template.toml").write_text("[[sections]]\nid = 'x'\ntitle = 'X'\n")
    (task_dir / "validation_rules.toml").write_text("")

    (task_dir / "tests").mkdir()
    (task_dir / "tests" / "verify.py").write_text(
        """
import json
import sys
from pathlib import Path

WORKSPACE = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/workspace")
REWARD = WORKSPACE / "logs" / "verifier" / "reward.json"
DETAILS = WORKSPACE / "logs" / "verifier" / "details.json"
REWARD.parent.mkdir(parents=True, exist_ok=True)
text = (WORKSPACE / "output.md").read_text()
reward = 0.9 if "fixed" in text else 0.5
REWARD.write_text(json.dumps({"reward": reward}))
DETAILS.write_text(json.dumps({"reward": reward, "completeness": {"score": 10, "max_score": 10}}))
"""
    )

    output_md = "This is a fixed document."
    result = run_verifier(
        task_dir=task_dir,
        output_md_text=output_md,
        workspace_root=tmp_path / "ws",
    )
    assert result.reward == 0.9
    assert "completeness" in result.details
    assert result.details["completeness"]["score"] == 10


def test_run_verifier_handles_missing_optional_files(tmp_path: Path) -> None:
    """validation_rules.toml and reference_data/ can be absent; runner should still work."""
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    (task_dir / "documents").mkdir()
    (task_dir / "report_template.toml").write_text("[[sections]]\nid = 'x'\ntitle = 'X'\n")
    (task_dir / "tests").mkdir()
    (task_dir / "tests" / "verify.py").write_text(
        """
import json
import sys
from pathlib import Path
WORKSPACE = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/workspace")
REWARD = WORKSPACE / "logs" / "verifier" / "reward.json"
REWARD.parent.mkdir(parents=True, exist_ok=True)
REWARD.write_text(json.dumps({"reward": 0.42}))
(WORKSPACE / "logs" / "verifier" / "details.json").write_text(json.dumps({}))
"""
    )

    result = run_verifier(
        task_dir=task_dir,
        output_md_text="anything",
        workspace_root=tmp_path / "ws",
    )
    assert result.reward == 0.42


def test_run_verifier_patches_hardcoded_workspace_paths(tmp_path: Path) -> None:
    """verify.py with module-level Path('/workspace/...') constants must still run.

    Regression: report-style task verifiers can hardcode WORKSPACE = Path('/workspace')
    at module level and ignore sys.argv[1]. run-local patches these; remediation's
    verifier_runner must do the same or the subprocess crashes on read-only '/workspace/'.
    """
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    (task_dir / "documents").mkdir()
    (task_dir / "report_template.toml").write_text("[[sections]]\nid = 'x'\ntitle = 'X'\n")
    (task_dir / "tests").mkdir()
    (task_dir / "tests" / "verify.py").write_text(
        """
import json
from pathlib import Path

WORKSPACE = Path("/workspace")
REWARD_PATH = WORKSPACE / "logs" / "verifier" / "reward.json"
DETAILS_PATH = WORKSPACE / "logs" / "verifier" / "details.json"

REWARD_PATH.parent.mkdir(parents=True, exist_ok=True)
output_text = (WORKSPACE / "output.md").read_text()
reward = 0.77 if "hello" in output_text else 0.0
REWARD_PATH.write_text(json.dumps({"reward": reward}))
DETAILS_PATH.write_text(json.dumps({"note": "patched"}))
"""
    )

    result = run_verifier(
        task_dir=task_dir,
        output_md_text="hello world",
        workspace_root=tmp_path / "ws",
    )
    assert result.reward == 0.77
    assert result.details == {"note": "patched"}


def test_run_verifier_surfaces_stderr_on_failure(tmp_path: Path) -> None:
    """When verify.py crashes, the raised error must include its stderr for debuggability."""
    import pytest

    task_dir = tmp_path / "task"
    task_dir.mkdir()
    (task_dir / "documents").mkdir()
    (task_dir / "report_template.toml").write_text("")
    (task_dir / "tests").mkdir()
    (task_dir / "tests" / "verify.py").write_text(
        """
import sys
sys.stderr.write("MY_MARKER_TRACE_123\\n")
raise SystemExit(1)
"""
    )

    with pytest.raises(RuntimeError, match="MY_MARKER_TRACE_123"):
        run_verifier(
            task_dir=task_dir,
            output_md_text="anything",
            workspace_root=tmp_path / "ws",
        )


def test_run_verifier_raises_when_verify_py_missing(tmp_path: Path) -> None:
    import pytest

    task_dir = tmp_path / "task"
    task_dir.mkdir()
    # No tests/verify.py
    with pytest.raises(FileNotFoundError):
        run_verifier(
            task_dir=task_dir,
            output_md_text="x",
            workspace_root=tmp_path / "ws",
        )
