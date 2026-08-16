# ABOUTME: Enforces explicit RLM output completion and byte-stable artifact commitment.
# ABOUTME: Owns the mutable commit lifecycle independently from turn orchestration.

from __future__ import annotations

from dataclasses import dataclass, replace

from aec_bench.adapters.base import (
    AdapterCompletionReason,
    AdapterRequest,
    OutputCompletionAssistance,
)
from aec_bench.adapters.output_commit import (
    build_output_commit_attestation,
    changed_output_completion_contract_satisfied,
    configured_output_completion_commit,
    configured_output_completion_contract,
    read_output_completion_content,
    validate_stable_output_commit,
)
from aec_bench.adapters.rlm.engine import ExecutionResult, ReplEnvironment
from aec_bench.contracts.output_completion import (
    OutputCommitAttestation,
    OutputCompletionContract,
)

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


def append_execution_message(result: ExecutionResult, message: str | None) -> ExecutionResult:
    """Append one commit decision to REPL stdout exactly once."""
    if not message or message in result.stdout:
        return result
    separator = "" if not result.stdout or result.stdout.endswith("\n") else "\n"
    return replace(result, stdout=f"{result.stdout}{separator}{message}\n")


def _commit_decision_message(attestation: OutputCommitAttestation | None, diagnostic: str) -> str:
    status = "accepted" if attestation is not None else "rejected"
    return f"COMMIT_OUTPUT {status}: {diagnostic}"


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
            self.attestation, diagnostic = build_output_commit_attestation(
                contract,
                initial_content=self.initial_content,
                commit_turn=self.commit_turn,
            )
            self.commit_message = _commit_decision_message(self.attestation, diagnostic)
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
            self.commit_message = f"COMMIT_OUTPUT rejected after block: {rejection}"
        if self.attestation is None:
            repl.final_value = None
            repl.final_called = False
        return append_execution_message(result, self.commit_message)

    def _post_block_rejection(self, result: ExecutionResult) -> str | None:
        if self.attestation is None:
            return None
        if result.error is not None:
            return "the REPL block raised an error after the commit call."
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
