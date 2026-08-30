# ABOUTME: Tests local verifier process receipts and staged verifier containment.
# ABOUTME: Proves process truth, bounded evidence, explicit redaction, and failure semantics.

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aec_bench.contracts.identity import EntityKind, new_entity_id
from aec_bench.contracts.trial_extensions import VerifierExecutionReceipt, VerifierOutputParseStatus
from aec_bench.harness.verifier_execution import (
    MAX_CAPTURE_BYTES,
    VerifierExecution,
    execute_verifier,
    localise_staged_verifier_paths,
    redact_verifier_arguments,
)


def _run(
    tmp_path: Path,
    source: str,
    *,
    timeout_seconds: int = 120,
    details_path: str | None = None,
) -> VerifierExecution:
    workspace = tmp_path / "workspace"
    verifier = workspace / "tests" / "verify.py"
    verifier.parent.mkdir(parents=True)
    verifier.write_text(source, encoding="utf-8")
    reward_path = workspace / "logs" / "verifier" / "reward.json"
    return execute_verifier(
        verifier_path=verifier,
        workspace=workspace,
        output_path=workspace / "output.md",
        reward_path=reward_path,
        details_path=None if details_path is None else workspace / details_path,
        verifier_key="civil/check/verifier",
        verifier_version=1,
        runtime_transform_version=1,
        timeout_seconds=timeout_seconds,
    )


def test_success_receipt_requires_process_and_valid_reward(tmp_path: Path) -> None:
    execution = _run(
        tmp_path,
        "import json\n"
        "print('diagnostic')\n"
        "from pathlib import Path\n"
        "Path('logs/verifier/reward.json').write_text(json.dumps({'reward': 0.75}))\n"
        "Path('logs/verifier/custom-details.json').write_text(json.dumps({'matched': 2}))\n",
        details_path="logs/verifier/custom-details.json",
    )

    assert execution.receipt.completed
    assert execution.receipt.exit_code == 0
    assert execution.receipt.output_parse_status is VerifierOutputParseStatus.VALID
    assert execution.reward_payload == {"reward": 0.75}
    assert execution.details_payload == {"matched": 2}
    assert execution.receipt.stdout_artifact is not None
    assert execution.receipt.details_artifact is not None
    assert execution.receipt.details_artifact.path == "logs/verifier/custom-details.json"
    assert execution.receipt.working_directory_role == "trial_workspace"
    persisted = VerifierExecutionReceipt.model_validate_json(
        (tmp_path / "workspace/logs/verifier/receipt.json").read_text(encoding="utf-8")
    )
    assert persisted == execution.receipt
    assert str(tmp_path) not in json.dumps(execution.receipt.model_dump(mode="json"))


def test_non_zero_process_with_reward_is_not_complete(tmp_path: Path) -> None:
    execution = _run(
        tmp_path,
        "import json\n"
        "from pathlib import Path\n"
        "Path('logs/verifier/reward.json').write_text(json.dumps({'reward': 1.0}))\n"
        "raise SystemExit(3)\n",
    )

    assert not execution.receipt.completed
    assert execution.receipt.failure_kind == "non_zero_exit"
    assert execution.receipt.exit_code == 3
    assert execution.receipt.reward_artifact is not None


def test_empty_failure_output_has_no_dangling_artifact_references(tmp_path: Path) -> None:
    execution = _run(tmp_path, "raise SystemExit(4)\n")

    assert execution.receipt.failure_kind == "non_zero_exit"
    assert execution.receipt.stdout_artifact is None
    assert execution.receipt.stderr_artifact is None
    assert (tmp_path / "workspace/logs/verifier/receipt.json").is_file()
    assert not (tmp_path / "workspace/logs/verifier/stdout.log").exists()
    assert not (tmp_path / "workspace/logs/verifier/stderr.log").exists()


def test_timeout_is_recorded_even_when_no_reward_exists(tmp_path: Path) -> None:
    execution = _run(tmp_path, "import time\ntime.sleep(1)\n", timeout_seconds=1)

    assert execution.receipt.timed_out
    assert not execution.receipt.completed
    assert execution.receipt.failure_kind == "timeout"
    assert execution.receipt.reward_artifact is None


def test_timeout_records_compatibility_fallback_command(tmp_path: Path) -> None:
    execution = _run(
        tmp_path,
        "import sys\nimport time\nif '--input' in sys.argv:\n    raise SystemExit(0)\ntime.sleep(2)\n",
        timeout_seconds=1,
    )

    assert execution.receipt.timed_out
    assert execution.receipt.command_name == Path(sys.executable).name
    assert execution.receipt.arguments == ("<workspace-path>", "<workspace-path>")
    assert execution.receipt.exit_code is None


def test_fallback_start_failure_is_not_reclassified_as_missing_reward(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        nonlocal calls
        calls += 1
        if calls == 1:
            return subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
        raise FileNotFoundError

    monkeypatch.setattr("aec_bench.harness.verifier_execution.subprocess.run", run)
    execution = _run(tmp_path, "raise SystemExit(0)\n")

    assert calls == 2
    assert execution.receipt.failure_kind == "verifier_not_found"
    assert execution.receipt.exit_code is None


def test_cancelled_execution_does_not_start_process(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    verifier = workspace / "tests" / "verify.py"
    verifier.parent.mkdir(parents=True)
    verifier.write_text("raise SystemExit('must not run')\n", encoding="utf-8")

    execution = execute_verifier(
        verifier_path=verifier,
        workspace=workspace,
        output_path=workspace / "output.md",
        reward_path=workspace / "logs/verifier/reward.json",
        details_path=None,
        verifier_key="civil/check/verifier",
        verifier_version=1,
        runtime_transform_version=1,
        cancelled=True,
    )

    assert execution.receipt.cancelled
    assert execution.receipt.failure_kind == "cancelled"
    assert not (workspace / "logs/verifier/reward.json").exists()


@pytest.mark.parametrize(
    ("source", "status", "failure"),
    [
        ("raise SystemExit(0)\n", VerifierOutputParseStatus.MISSING, "missing_reward"),
        (
            "from pathlib import Path\nPath('logs/verifier/reward.json').write_text('{bad')\n",
            VerifierOutputParseStatus.MALFORMED,
            "malformed_reward",
        ),
    ],
)
def test_reward_presence_does_not_bypass_reward_validation(
    tmp_path: Path,
    source: str,
    status: VerifierOutputParseStatus,
    failure: str,
) -> None:
    execution = _run(tmp_path, source)

    assert execution.receipt.output_parse_status is status
    assert execution.receipt.failure_kind == failure
    assert not execution.receipt.completed


def test_redaction_covers_paths_and_secret_argument_forms(tmp_path: Path) -> None:
    result = redact_verifier_arguments(
        ("--input", str(tmp_path / "output.md"), "--token", "secret", "--secret=value", "literal"),
        workspace=tmp_path,
    )

    assert result == ("--input", "<workspace-path>", "--token", "<redacted>", "--secret=<redacted>", "literal")


def test_output_capture_is_bounded_and_marked(tmp_path: Path) -> None:
    execution = _run(
        tmp_path,
        "import sys\n"
        f"sys.stdout.write('o' * {MAX_CAPTURE_BYTES + 100})\n"
        f"sys.stderr.write('e' * {MAX_CAPTURE_BYTES + 100})\n"
        "raise SystemExit(2)\n",
    )

    assert execution.receipt.stdout_truncated
    assert execution.receipt.stderr_truncated
    assert execution.receipt.stdout_artifact is not None
    assert execution.receipt.stderr_artifact is not None
    assert len((tmp_path / "workspace/logs/verifier/stdout.log").read_bytes()) == MAX_CAPTURE_BYTES
    assert len((tmp_path / "workspace/logs/verifier/stderr.log").read_bytes()) == MAX_CAPTURE_BYTES


def test_transform_rejects_symlink_outside_staged_verifier_area(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    tests = workspace / "tests"
    tests.mkdir(parents=True)
    outside = tmp_path / "outside.py"
    outside.write_text('Path("/workspace")\n', encoding="utf-8")
    (tests / "verify.py").symlink_to(outside)

    with pytest.raises(ValueError, match="must not be symlinks"):
        localise_staged_verifier_paths(workspace=workspace, verifier_root=tests)
    assert outside.read_text(encoding="utf-8") == 'Path("/workspace")\n'


def test_execution_rejects_verifier_and_output_paths_outside_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside_verifier = tmp_path / "verify.py"
    outside_verifier.write_text("raise SystemExit(0)\n", encoding="utf-8")

    with pytest.raises(ValueError, match="must resolve inside the workspace"):
        execute_verifier(
            verifier_path=outside_verifier,
            workspace=workspace,
            output_path=tmp_path / "output.md",
            reward_path=workspace / "logs/verifier/reward.json",
            details_path=None,
            verifier_key="civil/check/verifier",
            verifier_version=1,
            runtime_transform_version=1,
        )

    inside_verifier = workspace / "tests" / "verify.py"
    inside_verifier.parent.mkdir()
    inside_verifier.write_text("raise SystemExit(0)\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must resolve inside the workspace"):
        execute_verifier(
            verifier_path=inside_verifier,
            workspace=workspace,
            output_path=tmp_path / "output.md",
            reward_path=workspace / "logs/verifier/reward.json",
            details_path=None,
            verifier_key="civil/check/verifier",
            verifier_version=1,
            runtime_transform_version=1,
        )


def test_receipt_versions_are_strict_positive_integers() -> None:
    payload = {
        "receipt_id": str(new_entity_id(EntityKind.RECEIPT)),
        "verifier_key": "civil/check/verifier",
        "verifier_version": 1,
        "started_at": datetime.now(UTC),
        "finished_at": datetime.now(UTC),
        "duration_seconds": 0.0,
        "command_name": "python",
        "exit_code": 0,
        "timed_out": False,
        "cancelled": False,
        "output_parse_status": "missing",
    }

    with pytest.raises(ValidationError):
        VerifierExecutionReceipt.model_validate({**payload, "verifier_version": 1.0})
    with pytest.raises(ValidationError):
        VerifierExecutionReceipt.model_validate({**payload, "verifier_version": "1"})
    with pytest.raises(ValidationError):
        VerifierExecutionReceipt.model_validate({**payload, "verifier_version": True})
    with pytest.raises(ValidationError):
        VerifierExecutionReceipt.model_validate({**payload, "runtime_transform_version": 1.0})
    with pytest.raises(ValidationError):
        VerifierExecutionReceipt.model_validate({**payload, "runtime_transform_version": "1"})
    with pytest.raises(ValidationError):
        VerifierExecutionReceipt.model_validate({**payload, "runtime_transform_version": False})
