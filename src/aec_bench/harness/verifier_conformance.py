# ABOUTME: Runs the maintained local verifier and evaluation conformance matrix.
# ABOUTME: Exercises production receipt execution and evaluation mapping without provider services.

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.trial_record import EvaluationStatus
from aec_bench.evaluation.verifier_outcome import map_verifier_execution
from aec_bench.harness.verifier_execution import MAX_CAPTURE_BYTES, execute_verifier, redact_verifier_arguments

REQUIRED_GUARANTEES = frozenset(
    {
        "valid_verifier_receipt_and_evaluation",
        "malformed_reward_is_invalid",
        "missing_reward_is_failed",
        "nonzero_process_is_failed",
        "timeout_is_failed",
        "cancelled_process_is_failed",
        "verifier_identity_mismatch_is_invalid",
        "bounded_and_redacted_output",
    }
)


def run_verifier_conformance(*, seed: int = 0) -> dict[str, Any]:
    """Run the local verifier receipt and evaluation mapping matrix.

    The scripts are created in a temporary trial workspace and are invoked by
    :func:`execute_verifier`. This keeps the check on the production process
    boundary while avoiding provider credentials or task-specific fixtures.
    """

    del seed  # The matrix is deterministic. Keep the argument aligned with other conformance kits.
    with TemporaryDirectory(prefix="aec-bench-verifier-conformance-") as temporary:
        root = Path(temporary).resolve()
        valid = _run(root / "valid", "_write_reward(0.75)")
        assert valid.status is EvaluationStatus.COMPLETED
        assert valid.evaluation.reward == 0.75
        assert valid.evaluation.validity.verifier_completed
        valid_receipt = valid.execution.receipt
        assert valid_receipt.verifier_key == "conformance/verifier"
        assert valid_receipt.verifier_version == 1
        assert valid_receipt.started_at <= valid_receipt.finished_at
        assert valid_receipt.duration_seconds >= 0
        assert valid_receipt.command_name
        assert valid_receipt.arguments
        assert valid_receipt.working_directory_role == "trial_workspace"
        assert valid_receipt.exit_code == 0
        assert not valid_receipt.timed_out
        assert not valid_receipt.cancelled
        assert valid_receipt.reward_artifact is not None
        assert valid_receipt.output_parse_status.value == "valid"
        assert valid_receipt.failure_kind is None
        assert valid_receipt.failure_message is None
        assert valid_receipt.runtime_transform_version == 1

        malformed = _run(root / "malformed", "_write_text('logs/verifier/reward.json', '{bad')")
        assert malformed.status is EvaluationStatus.INVALID
        assert malformed.evaluation.reward == 0.0

        missing = _run(root / "missing", "pass")
        assert missing.status is EvaluationStatus.FAILED
        assert missing.evaluation.reward == 0.0

        nonzero = _run(root / "nonzero", "_write_reward(1.0)\nraise SystemExit(3)")
        assert nonzero.status is EvaluationStatus.FAILED
        assert nonzero.evaluation.reward == 0.0

        timed_out = _run(root / "timeout", "import time\ntime.sleep(2)", timeout_seconds=1)
        assert timed_out.status is EvaluationStatus.FAILED
        assert timed_out.execution.receipt.timed_out

        cancelled = _run(root / "cancelled", "raise SystemExit('must not run')", cancelled=True)
        assert cancelled.status is EvaluationStatus.FAILED
        assert cancelled.execution.receipt.cancelled

        mismatched = _run(root / "mismatch", "_write_reward(1.0)", expected_key="different/verifier")
        assert mismatched.status is EvaluationStatus.INVALID
        assert mismatched.evaluation.reward == 0.0

        bounded = _run(
            root / "bounded",
            f"import sys\nsys.stdout.write('o' * {MAX_CAPTURE_BYTES + 100})\n"
            f"sys.stderr.write('e' * {MAX_CAPTURE_BYTES + 100})\n_write_reward(1.0)",
        )
        receipt = bounded.execution.receipt
        assert receipt.stdout_truncated and receipt.stderr_truncated
        assert len((root / "bounded/logs/verifier/stdout.log").read_bytes()) == MAX_CAPTURE_BYTES
        assert len((root / "bounded/logs/verifier/stderr.log").read_bytes()) == MAX_CAPTURE_BYTES
        persisted = (root / "bounded/logs/verifier/receipt.json").read_text(encoding="utf-8")
        assert "private-token" not in persisted
        assert str(root) not in persisted
        redacted = redact_verifier_arguments(
            ("--token", "private-token", str(root / "bounded" / "output.md")),
            workspace=root / "bounded",
        )
        assert redacted == ("--token", "<redacted>", "<workspace-path>")

    return {"proven": sorted(REQUIRED_GUARANTEES)}


class _MappedExecution:
    def __init__(self, execution: Any, mapping: Any) -> None:
        self.execution = execution
        self.status = mapping.status
        self.evaluation = mapping.evaluation


def _run(
    root: Path,
    body: str,
    *,
    timeout_seconds: int = 120,
    cancelled: bool = False,
    expected_key: str = "conformance/verifier",
) -> _MappedExecution:
    root.mkdir(parents=True)
    verifier = root / "verifier.py"
    verifier.write_text(
        "import json\n"
        "from pathlib import Path\n"
        "def _write_text(path, value):\n"
        "    target = Path(path)\n"
        "    target.parent.mkdir(parents=True, exist_ok=True)\n"
        "    target.write_text(value)\n"
        "def _write_reward(value):\n"
        "    _write_text('logs/verifier/reward.json', json.dumps({'reward': value}))\n"
        f"{body}\n",
        encoding="utf-8",
    )
    execution = execute_verifier(
        verifier_path=verifier.relative_to(root),
        workspace=root,
        output_path=root / "output.md",
        reward_path=root / "logs/verifier/reward.json",
        details_path=None,
        verifier_key="conformance/verifier",
        verifier_version=1,
        runtime_transform_version=1,
        cancelled=cancelled,
        timeout_seconds=timeout_seconds,
    )
    base = EvaluationResult(
        reward=(float(execution.reward_payload["reward"]) if execution.reward_payload is not None else 0.5),
        validity=ValidityCheck(output_parseable=True, schema_valid=True, verifier_completed=True),
    )
    mapping = map_verifier_execution(
        receipt=execution.receipt,
        evaluation=base,
        expected_verifier_key=expected_key,
        expected_verifier_version=1,
    )
    return _MappedExecution(execution, mapping)


__all__ = ("REQUIRED_GUARANTEES", "run_verifier_conformance")
