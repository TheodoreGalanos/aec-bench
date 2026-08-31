# ABOUTME: Tests effect-free artifact attempt recipe and selector policies.
# ABOUTME: Proves selectors use runtime-provided values without reading attempt workspaces.

from pathlib import Path

import pytest

from aec_bench.adapters.base import AdapterRequest, AdapterResult
from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.harness.artifact.recipes import best_of, self_select, single_attempt
from aec_bench.harness.artifact.values import SelectorDecision, TaskAttempt


def _attempt(attempt_id: str, output: bytes | None) -> TaskAttempt:
    request = AdapterRequest(instruction="instruction", output_path="/workspace/output.md")
    result = AdapterResult(
        adapter_name="direct",
        resolved_model="test-model",
        configuration_record={},
        agent_output=AgentOutput(
            status=AgentOutputStatus.COMPLETED if output else AgentOutputStatus.FAILED,
            output_path=request.output_path,
            output_format="markdown",
        ),
        transcript=[],
    )
    return TaskAttempt(
        attempt_id=attempt_id,
        trial_id="trial-1",
        parent_attempt_id=None,
        workspace=Path("/workspace-does-not-exist"),
        request=request,
        result=result,
        elapsed_seconds=0.1,
        selector_visible_output=output,
    )


def test_best_of_selector_uses_attempt_values_without_workspace_reads() -> None:
    attempts = [_attempt("attempt-0", None), _attempt("attempt-1", b"complete")]

    def run_once(*, attempt_id: str, parent=None, instruction=None) -> TaskAttempt:  # noqa: ANN001
        return attempts[int(attempt_id.rsplit("-", maxsplit=1)[1])]

    selection = best_of(k=2, selector=self_select())(run_once)

    assert selection.attempt is attempts[1]
    assert selection.evidence is not None
    assert [candidate.eligible for candidate in selection.evidence.candidates] == [False, True]


def test_single_attempt_runs_once_and_selects_the_attempt() -> None:
    attempt = _attempt("attempt-0", b"complete")
    calls: list[str] = []

    def run_once(*, attempt_id: str, parent=None, instruction=None) -> TaskAttempt:  # noqa: ANN001
        calls.append(attempt_id)
        return attempt

    selection = single_attempt()(run_once)

    assert calls == ["attempt-0"]
    assert selection.attempt is attempt
    assert selection.reason == "single attempt"


def test_best_of_reports_failure_when_no_candidate_is_eligible() -> None:
    attempts = [_attempt("attempt-0", None), _attempt("attempt-1", None)]

    def run_once(*, attempt_id: str, parent=None, instruction=None) -> TaskAttempt:  # noqa: ANN001
        return attempts[int(attempt_id.rsplit("-", maxsplit=1)[1])]

    selection = best_of(k=2, selector=self_select())(run_once)

    assert selection.attempt is None
    assert selection.decision == "failed"
    assert selection.evidence is not None
    assert selection.evidence.selected_index is None


def test_best_of_rejects_out_of_range_selector_choice() -> None:
    def selector(_candidates):  # noqa: ANN001
        return SelectorDecision(selected_index=2, reason="bad", configuration={})

    with pytest.raises(ValueError, match="out-of-range"):
        best_of(k=2, selector=selector)(lambda **kwargs: _attempt(kwargs["attempt_id"], b"complete"))


def test_best_of_rejects_ineligible_selector_choice() -> None:
    def selector(_candidates):  # noqa: ANN001
        return SelectorDecision(selected_index=0, reason="bad", configuration={})

    def run_once(*, attempt_id: str, parent=None, instruction=None) -> TaskAttempt:  # noqa: ANN001
        return _attempt(attempt_id, None if attempt_id == "attempt-0" else b"complete")

    with pytest.raises(ValueError, match="ineligible"):
        best_of(k=2, selector=selector)(run_once)
