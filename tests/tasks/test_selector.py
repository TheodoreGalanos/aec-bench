# ABOUTME: Tests for task selection helpers in the aec-bench Python implementation.
# ABOUTME: Covers filtering by domain, lifecycle, visibility, tags, and glob patterns.

from aec_bench.contracts.task_definition import Difficulty, Lifecycle, Visibility
from aec_bench.tasks.selector import select_tasks
from tests.support.task_factories import make_task_definition


def test_selector_filters_by_domain_and_difficulty() -> None:
    tasks = [
        make_task_definition(
            task_id="mechanical/heat-load/a",
            domain="mechanical",
            difficulty=Difficulty.MEDIUM,
        ),
        make_task_definition(
            task_id="electrical/voltage-drop/a",
            domain="electrical",
            difficulty=Difficulty.EASY,
        ),
    ]

    selected = select_tasks(tasks, domains=["mechanical"], difficulties=[Difficulty.MEDIUM])

    assert [task.task_id for task in selected] == ["mechanical/heat-load/a"]


def test_selector_returns_all_lifecycles_when_unfiltered() -> None:
    tasks = [
        make_task_definition(task_id="mechanical/heat-load/a", lifecycle=Lifecycle.ACTIVE),
        make_task_definition(task_id="mechanical/heat-load/b", lifecycle=Lifecycle.PROPOSED),
    ]

    selected = select_tasks(tasks)

    assert len(selected) == 2


def test_selector_filters_by_explicit_lifecycle() -> None:
    tasks = [
        make_task_definition(task_id="mechanical/heat-load/a", lifecycle=Lifecycle.ACTIVE),
        make_task_definition(task_id="mechanical/heat-load/b", lifecycle=Lifecycle.PROPOSED),
    ]

    selected = select_tasks(tasks, lifecycle=[Lifecycle.ACTIVE])

    assert [task.task_id for task in selected] == ["mechanical/heat-load/a"]


def test_selector_filters_tags_and_patterns() -> None:
    tasks = [
        make_task_definition(
            task_id="mechanical/heat-load/audit-office-building/sydney-8rm",
            tags=["au", "office"],
        ),
        make_task_definition(
            task_id="mechanical/heat-load/audit-mixed-use/perth-15rm",
            tags=["us"],
        ),
    ]

    selected = select_tasks(
        tasks,
        tags=["au"],
        include_patterns=["*sydney-8rm"],
        visibility=[Visibility.PUBLIC],
    )

    assert [task.task_id for task in selected] == ["mechanical/heat-load/audit-office-building/sydney-8rm"]


def test_selector_returns_empty_for_empty_input() -> None:
    selected = select_tasks([])

    assert selected == []


def test_selector_exclude_patterns_override_include() -> None:
    tasks = [
        make_task_definition(task_id="mechanical/heat-load/a"),
        make_task_definition(task_id="mechanical/heat-load/b"),
    ]

    selected = select_tasks(
        tasks,
        include_patterns=["mechanical/*"],
        exclude_patterns=["*/b"],
    )

    assert [task.task_id for task in selected] == ["mechanical/heat-load/a"]
