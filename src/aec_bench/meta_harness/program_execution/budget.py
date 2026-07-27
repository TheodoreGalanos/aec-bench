# ABOUTME: Accounts global attempt, parallelism, recursion, and handler-context limits.
# ABOUTME: Exposes only bounded execution capabilities to trusted operation handlers.


from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from aec_bench.contracts.execution_program import (
    CompiledExecutionProgram,
)
from aec_bench.contracts.harness_instance import ProgramOperationRef


@dataclass(frozen=True)
class OperationExecutionContext:
    """Identity and bounded recursion surface supplied to one trusted handler call."""

    program_sha256: str
    node_id: str
    operation_ref: ProgramOperationRef
    binding_ids: tuple[str, ...]
    attempt_index: int
    fanout_index: int | None
    recursion: BoundedRecursionContext


class BoundedRecursionContext:
    """Capability that accounts every handler-declared recursive call against node and global limits."""

    def __init__(
        self,
        budget: _RuntimeBudget,
        node_state: _NodeRecursionState,
    ) -> None:
        self._budget = budget
        self._node_state = node_state
        self._calls = 0
        self._maximum_depth = 0

    @property
    def max_depth(self) -> int:
        return self._node_state.max_depth

    @property
    def max_calls(self) -> int:
        return self._node_state.max_calls

    @property
    def calls_used(self) -> int:
        return self._calls

    @property
    def maximum_depth_used(self) -> int:
        return self._maximum_depth

    def claim(self, *, depth: int) -> None:
        """Account one recursive call before trusted handler code performs it."""

        self._budget.claim_recursion(self._node_state, depth)
        self._calls += 1
        self._maximum_depth = max(self._maximum_depth, depth)


@dataclass
class _NodeRecursionState:
    max_depth: int
    max_calls: int
    calls: int = 0


class _RuntimeFault(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class _RuntimeBudget:
    def __init__(self, program: CompiledExecutionProgram) -> None:
        self.max_attempts = program.limits.max_total_attempts
        self.max_parallelism = program.limits.max_parallelism
        self.max_recursive_calls = program.limits.max_recursive_calls
        self.max_recursion_depth = program.limits.max_recursion_depth
        self.total_attempts = 0
        self.current_parallelism = 0
        self.maximum_parallelism_observed = 0
        self.recursive_calls = 0
        self.maximum_recursion_depth_observed = 0
        self._lock = threading.Lock()

    def claim_attempt(self) -> None:
        with self._lock:
            if self.total_attempts >= self.max_attempts:
                raise _RuntimeFault(
                    "global_attempt_budget_exhausted",
                    f"program attempt limit {self.max_attempts} exhausted",
                )
            self.total_attempts += 1

    @contextmanager
    def operation_slot(self) -> Iterator[None]:
        with self._lock:
            if self.current_parallelism >= self.max_parallelism:
                raise _RuntimeFault(
                    "global_parallelism_budget_exhausted",
                    f"program parallelism limit {self.max_parallelism} exhausted",
                )
            self.current_parallelism += 1
            self.maximum_parallelism_observed = max(
                self.maximum_parallelism_observed,
                self.current_parallelism,
            )
        try:
            yield
        finally:
            with self._lock:
                self.current_parallelism -= 1

    def claim_recursion(self, node_state: _NodeRecursionState, depth: int) -> None:
        if isinstance(depth, bool) or depth < 1:
            raise _RuntimeFault("invalid_recursion_depth", "recursive-call depth must be a positive integer")
        with self._lock:
            if node_state.max_calls == 0 or node_state.max_depth == 0:
                raise _RuntimeFault("recursion_not_declared", "program node did not declare recursive execution")
            if depth > node_state.max_depth:
                raise _RuntimeFault(
                    "node_recursion_depth_exhausted",
                    f"recursive depth {depth} exceeds node limit {node_state.max_depth}",
                )
            if depth > self.max_recursion_depth:
                raise _RuntimeFault(
                    "global_recursion_depth_exhausted",
                    f"recursive depth {depth} exceeds program limit {self.max_recursion_depth}",
                )
            if node_state.calls >= node_state.max_calls:
                raise _RuntimeFault(
                    "node_recursive_call_budget_exhausted",
                    f"node recursive-call limit {node_state.max_calls} exhausted",
                )
            if self.recursive_calls >= self.max_recursive_calls:
                raise _RuntimeFault(
                    "global_recursive_call_budget_exhausted",
                    f"program recursive-call limit {self.max_recursive_calls} exhausted",
                )
            node_state.calls += 1
            self.recursive_calls += 1
            self.maximum_recursion_depth_observed = max(self.maximum_recursion_depth_observed, depth)
