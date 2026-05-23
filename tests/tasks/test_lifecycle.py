# ABOUTME: Tests for lifecycle policy in the aec-bench Python implementation.
# ABOUTME: Covers runnable-state rules via the TaskDefinition.runnable property.

from aec_bench.contracts.task_definition import Lifecycle
from tests.support.task_factories import make_task_definition


def test_runnable_accepts_active_and_deprecated() -> None:
    active = make_task_definition(lifecycle=Lifecycle.ACTIVE)
    deprecated = make_task_definition(lifecycle=Lifecycle.DEPRECATED)
    assert active.runnable is True
    assert deprecated.runnable is True


def test_runnable_rejects_proposed_and_retired() -> None:
    proposed = make_task_definition(lifecycle=Lifecycle.PROPOSED)
    retired = make_task_definition(lifecycle=Lifecycle.RETIRED)
    assert proposed.runnable is False
    assert retired.runnable is False
