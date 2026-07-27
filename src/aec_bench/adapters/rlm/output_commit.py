# ABOUTME: Enforces explicit RLM output completion and byte-stable artifact commitment.
# ABOUTME: Owns the mutable commit lifecycle independently from turn orchestration.

from __future__ import annotations

import hashlib
import logging
import os
import stat
from dataclasses import dataclass, replace
from pathlib import Path

from aec_bench.adapters.base import (
    AdapterCompletionReason,
    AdapterRequest,
    OutputCompletionAssistance,
)
from aec_bench.adapters.rlm.engine import ExecutionResult, ReplEnvironment
from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.contracts.output_completion import (
    OutputCommitAttestation,
    OutputCompletionContract,
    evaluate_output_completion,
)

logger = logging.getLogger(__name__)

_OUTPUT_COMPLETION_CONTRACT_KEY = "output_completion_contract"
_OUTPUT_COMPLETION_COMMIT_KEY = "output_completion_commit"
_OUTPUT_COMPLETION_MAX_BYTES = 1024 * 1024

OUTPUT_COMPLETION_FINALIZATION_REMINDER = (
    "\n\n[Output contract ready] The artifact created or changed in this run now "
    "has the declared public structure. Review its substantive content. When "
    "satisfied, call FINAL_VAR(...) explicitly; structure alone does not finish "
    "the task."
)
OUTPUT_COMMIT_FINALIZATION_REMINDER = (
    "\n\n[Output ready to commit] The artifact created or changed in this run "
    "has the declared public structure. Review its substantive content, then "
    "call COMMIT_OUTPUT() to bind and finish the exact artifact. FINAL_VAR, "
    "FINAL, and response done markers cannot finish this harness."
)
OUTPUT_COMMIT_SYSTEM_PROMPT = """

OUTPUT COMMIT POLICY:
- The task is complete only when you call COMMIT_OUTPUT() after writing the final artifact.
- COMMIT_OUTPUT() takes no arguments and binds the exact artifact bytes at the declared output path.
- FINAL_VAR(...), FINAL(...), bare FINAL text, and response done markers do not finish this task.
- Put the final artifact write and COMMIT_OUTPUT() in the same REPL block when possible.
"""


def configured_output_completion_contract(request: AdapterRequest) -> OutputCompletionContract | None:
    """Parse and bind the optional output contract to the request path."""
    raw_contract = request.configuration.get(_OUTPUT_COMPLETION_CONTRACT_KEY)
    if raw_contract is None:
        return None
    contract = OutputCompletionContract.model_validate(raw_contract)
    if contract.output_path != request.output_path:
        raise ValueError("output completion contract output_path must match the adapter request output_path")
    return contract


def configured_output_completion_commit(
    request: AdapterRequest,
    *,
    contract: OutputCompletionContract | None,
) -> bool:
    """Validate whether explicit byte commitment is enabled for this request."""
    raw_value = request.configuration.get(_OUTPUT_COMPLETION_COMMIT_KEY, False)
    if not isinstance(raw_value, bool):
        raise ValueError("output_completion_commit must be a boolean")
    if raw_value and contract is None:
        raise ValueError("output_completion_commit requires an output completion contract")
    return raw_value


def read_output_completion_content(contract: OutputCompletionContract) -> str | None:
    """Read a bounded regular UTF-8 output without following symbolic links."""
    output_path = Path(contract.output_path)
    try:
        path_stat = output_path.lstat()
    except OSError:
        return None
    if not stat.S_ISREG(path_stat.st_mode):
        logger.debug("Output completion contract rejected non-regular path: %s", output_path)
        return None

    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(output_path, flags)
    except OSError:
        return None
    try:
        opened_stat = os.fstat(fd)
        if not _same_regular_file(opened_stat, path_stat):
            logger.debug("Output completion contract rejected changed or non-regular path: %s", output_path)
            return None
        if opened_stat.st_size > _OUTPUT_COMPLETION_MAX_BYTES:
            logger.debug("Output completion contract rejected oversized artifact: %s", output_path)
            return None
        with os.fdopen(fd, "rb", closefd=False) as stream:
            content = stream.read(_OUTPUT_COMPLETION_MAX_BYTES + 1)
    except OSError:
        return None
    finally:
        try:
            os.close(fd)
        except OSError:
            pass
    if len(content) > _OUTPUT_COMPLETION_MAX_BYTES:
        logger.debug("Output completion contract rejected oversized artifact: %s", output_path)
        return None
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _same_regular_file(opened_stat: os.stat_result, path_stat: os.stat_result) -> bool:
    return (
        stat.S_ISREG(opened_stat.st_mode)
        and opened_stat.st_dev == path_stat.st_dev
        and opened_stat.st_ino == path_stat.st_ino
    )


def changed_output_completion_contract_satisfied(
    contract: OutputCompletionContract,
    *,
    initial_content: str | None,
) -> bool:
    """Return whether a changed output now satisfies the declared structure."""
    content = read_output_completion_content(contract)
    if content is None or content == initial_content:
        return False
    return evaluate_output_completion(contract, content).complete


def build_output_commit_attestation(
    contract: OutputCompletionContract,
    *,
    initial_content: str | None,
    commit_turn: int,
) -> tuple[OutputCommitAttestation | None, str]:
    """Bind the current complete artifact bytes to an immutable attestation."""
    content = read_output_completion_content(contract)
    if content is None:
        return None, "COMMIT_OUTPUT rejected: output is missing or is not a safe UTF-8 regular file."
    if content == initial_content:
        return None, "COMMIT_OUTPUT rejected: output is unchanged from the start of this run."
    evaluation = evaluate_output_completion(contract, content)
    if not evaluation.complete:
        return None, f"COMMIT_OUTPUT rejected: output contract is incomplete ({evaluation.reason.value})."

    encoded = content.encode("utf-8")
    attestation = OutputCommitAttestation(
        schema_version="aecbench.output-commit-attestation.v1",
        mechanism="agent_explicit_output_commit",
        output_path=contract.output_path,
        output_sha256=hashlib.sha256(encoded).hexdigest(),
        output_size_bytes=len(encoded),
        completion_contract_sha256=canonical_content_sha256(contract.model_dump(mode="json")),
        completion_evaluation=evaluation,
        initial_output_sha256=(
            hashlib.sha256(initial_content.encode("utf-8")).hexdigest() if initial_content is not None else None
        ),
        commit_turn=commit_turn,
    )
    return attestation, (
        "COMMIT_OUTPUT accepted: exact artifact bound at "
        f"sha256:{attestation.output_sha256} ({attestation.output_size_bytes} bytes)."
    )


def validate_stable_output_commit(
    contract: OutputCompletionContract,
    attestation: OutputCommitAttestation,
) -> str | None:
    """Reject a committed artifact if its bytes change before the block ends."""
    content = read_output_completion_content(contract)
    if content is None:
        return "COMMIT_OUTPUT rejected after block: committed artifact is no longer a safe UTF-8 regular file."
    encoded = content.encode("utf-8")
    if (
        hashlib.sha256(encoded).hexdigest() != attestation.output_sha256
        or len(encoded) != attestation.output_size_bytes
    ):
        return "COMMIT_OUTPUT rejected after block: artifact changed after the commit call."
    evaluation = evaluate_output_completion(contract, content)
    if not evaluation.complete:
        return f"COMMIT_OUTPUT rejected after block: output contract is incomplete ({evaluation.reason.value})."
    return None


def append_execution_message(result: ExecutionResult, message: str | None) -> ExecutionResult:
    """Append one commit decision to REPL stdout exactly once."""
    if not message or message in result.stdout:
        return result
    separator = "" if not result.stdout or result.stdout.endswith("\n") else "\n"
    return replace(result, stdout=f"{result.stdout}{separator}{message}\n")


@dataclass(slots=True)
class OutputCompletionState:
    """Mutable completion state shared by REPL setup and turn reduction."""

    contract: OutputCompletionContract | None
    commit_enabled: bool
    initial_content: str | None
    reminder_sent: bool = False
    reminder_turn: int | None = None
    attestation: OutputCommitAttestation | None = None
    commit_message: str | None = None
    commit_turn: int = 0

    @classmethod
    def from_request(cls, request: AdapterRequest) -> OutputCompletionState:
        """Resolve one request's output-completion policy."""
        contract = configured_output_completion_contract(request)
        commit_enabled = configured_output_completion_commit(request, contract=contract)
        initial_content = read_output_completion_content(contract) if contract is not None else None
        return cls(
            contract=contract,
            commit_enabled=commit_enabled,
            initial_content=initial_content,
        )

    @property
    def system_prompt_suffix(self) -> str:
        return OUTPUT_COMMIT_SYSTEM_PROMPT if self.commit_enabled else ""

    @property
    def reminder(self) -> str:
        return OUTPUT_COMMIT_FINALIZATION_REMINDER if self.commit_enabled else OUTPUT_COMPLETION_FINALIZATION_REMINDER

    def inject_commit_command(self, repl: ReplEnvironment, scaffolds: dict[str, object]) -> None:
        """Inject COMMIT_OUTPUT when explicit commitment is configured."""
        if not self.commit_enabled:
            return
        contract = self.contract
        if contract is None:
            raise RuntimeError("output completion commit reached execution without a contract")

        def commit_output() -> str:
            repl.final_value = None
            repl.final_called = False
            self.attestation, self.commit_message = build_output_commit_attestation(
                contract,
                initial_content=self.initial_content,
                commit_turn=self.commit_turn,
            )
            if self.attestation is not None:
                repl.final_value = self.attestation
                repl.final_called = True
            return self.commit_message

        repl.inject_object("COMMIT_OUTPUT", commit_output, protected=True)
        scaffolds["COMMIT_OUTPUT"] = commit_output

    def begin_turn(self, repl: ReplEnvironment, iteration: int) -> None:
        """Reset transient commitment state before one REPL block."""
        if not self.commit_enabled:
            return
        self.attestation = None
        self.commit_message = None
        self.commit_turn = iteration
        repl.final_value = None
        repl.final_called = False

    def finish_turn(self, repl: ReplEnvironment, result: ExecutionResult) -> ExecutionResult:
        """Revalidate one block's commitment and surface its decision."""
        if not self.commit_enabled:
            return result
        if self.contract is None:
            raise RuntimeError("output completion commit reached finalization without a contract")
        rejection = self._post_block_rejection(result)
        if rejection is not None:
            self.attestation = None
            self.commit_message = rejection
        if self.attestation is None:
            repl.final_value = None
            repl.final_called = False
        return append_execution_message(result, self.commit_message)

    def _post_block_rejection(self, result: ExecutionResult) -> str | None:
        if self.attestation is None:
            return None
        if result.error is not None:
            return "COMMIT_OUTPUT rejected after block: the REPL block raised an error after the commit call."
        if self.contract is None:
            raise RuntimeError("output completion commit reached finalization without a contract")
        return validate_stable_output_commit(self.contract, self.attestation)

    def contract_satisfied(self, result: ExecutionResult | None) -> bool:
        """Return whether this successful turn produced a changed complete output."""
        return (
            result is not None
            and not result.error
            and self.contract is not None
            and changed_output_completion_contract_satisfied(
                self.contract,
                initial_content=self.initial_content,
            )
        )

    def register_reminder(self, *, contract_satisfied: bool, final_called: bool, iteration: int) -> bool:
        """Record and report the first turn requiring an explicit finalization reminder."""
        should_remind = contract_satisfied and not self.reminder_sent and not final_called
        if should_remind:
            self.reminder_sent = True
            self.reminder_turn = iteration
        return should_remind

    def completion_assistance(
        self,
        *,
        contract_satisfied: bool,
        explicit_final_turn: int,
    ) -> OutputCompletionAssistance | None:
        """Describe structural assistance when commitment itself is not required."""
        if self.contract is None or self.commit_enabled:
            return None
        return OutputCompletionAssistance(
            contract_satisfied=contract_satisfied,
            reminder_sent=self.reminder_sent,
            reminder_turn=self.reminder_turn,
            explicit_final_turn=explicit_final_turn,
        )

    def completion_reason(
        self,
        assistance: OutputCompletionAssistance | None,
    ) -> AdapterCompletionReason | None:
        """Reduce commit or assisted completion evidence to the public reason."""
        if self.attestation is not None:
            return AdapterCompletionReason.OUTPUT_CONTRACT_COMMITTED
        if assistance is not None and assistance.supports_output_contract_completion:
            return AdapterCompletionReason.OUTPUT_CONTRACT_SATISFIED
        return None
