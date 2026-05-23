# ABOUTME: Tests for the TaskProvider Command Palette provider.
# ABOUTME: Verifies fuzzy search returns matching task entries.

from aec_bench.tui.commands.tasks import TaskHit, search_tasks


def _entries():
    return [
        TaskHit(
            task_id="electrical/voltage-drop",
            discipline="electrical",
            description="Calculate voltage drop",
        ),
        TaskHit(
            task_id="electrical/cable-sizing",
            discipline="electrical",
            description="Size power cables",
        ),
        TaskHit(
            task_id="civil/drainage-calc",
            discipline="civil",
            description="Storm drainage calculations",
        ),
    ]


def test_search_by_task_id():
    assert len(search_tasks(_entries(), "voltage")) == 1


def test_search_by_discipline():
    assert len(search_tasks(_entries(), "electrical")) == 2


def test_search_by_description():
    assert len(search_tasks(_entries(), "drainage")) == 1


def test_search_empty_returns_all():
    assert len(search_tasks(_entries(), "")) == 3
