# ABOUTME: Tests for the full-text search index module.
# ABOUTME: Covers index building, search matching, and filtering by discipline/kind.

from pathlib import Path

from aec_bench.generation.discovery import LibrarySeed, LibraryTemplate
from aec_bench.search import build_index, search


def _make_seed(
    task_id: str = "test-task",
    discipline: str = "civil",
    category: str = "hydraulics",
    description: str = "Test description",
    standards: tuple[str, ...] = ("AS 1234",),
    inputs: tuple[str, ...] = ("Flow rate (L/s)",),
    outputs: tuple[str, ...] = ("Head loss (m)",),
) -> LibrarySeed:
    return LibrarySeed(
        discipline=discipline,
        category=category,
        task_id=task_id,
        task_name=task_id.replace("-", " ").title(),
        description=description,
        complexity="low",
        standards=standards,
        inputs=inputs,
        outputs=outputs,
        path=Path("/tmp/test"),
    )


def _make_template(
    task_id: str = "test-template",
    discipline: str = "civil",
    category: str = "hydraulics",
    description: str = "Template description",
    long_description: str = "",
    tags: list[str] | None = None,
    standards: list[str] | None = None,
) -> LibraryTemplate:
    meta = {
        "name": task_id,
        "description": description,
        "discipline": discipline,
        "category": category,
        "tags": tags or [],
        "standards": standards or [],
        "tool_mode": "with-tool",
    }
    if long_description:
        meta["long_description"] = long_description
    return LibraryTemplate(
        discipline=discipline,
        task_id=task_id,
        path=Path("/tmp/test"),
        params_raw={
            "meta": meta,
            "params": {"flow_rate": {"type": "float", "description": "Flow rate"}},
            "outputs": {"head_loss": {"description": "Head loss in metres"}},
        },
    )


def test_build_index_from_seeds_and_templates() -> None:
    seeds = [_make_seed(task_id="hazen-williams"), _make_seed(task_id="darcy-weisbach")]
    templates = [_make_template(task_id="hazen-williams")]
    index = build_index(seeds, templates)
    # Template replaces seed for hazen-williams, darcy-weisbach stays as seed
    assert len(index) == 2
    kinds = {e.name: e.kind for e in index}
    assert kinds["hazen-williams"] == "template"
    assert kinds["darcy-weisbach"] == "seed"


def test_search_matches_name() -> None:
    index = build_index([], [_make_template(task_id="voltage-drop")])
    results = search("voltage", index)
    assert len(results) == 1
    assert results[0].name == "voltage-drop"


def test_search_matches_description() -> None:
    index = build_index(
        [_make_seed(task_id="test", description="Calculate Manning pipe flow")],
        [],
    )
    results = search("manning", index)
    assert len(results) == 1


def test_search_matches_tags() -> None:
    index = build_index(
        [],
        [_make_template(task_id="test", tags=["geotechnical", "bearing-capacity"])],
    )
    results = search("geotechnical", index)
    assert len(results) == 1


def test_search_matches_standards() -> None:
    index = build_index(
        [_make_seed(task_id="test", standards=("AS/NZS 3008",))],
        [],
    )
    results = search("3008", index)
    assert len(results) == 1


def test_search_matches_inputs() -> None:
    index = build_index(
        [_make_seed(task_id="test", inputs=("Pipe diameter (mm)",))],
        [],
    )
    results = search("diameter", index)
    assert len(results) == 1


def test_search_matches_long_description() -> None:
    index = build_index(
        [],
        [
            _make_template(
                task_id="test",
                long_description="Uses Boussinesq elastic theory for settlement",
            )
        ],
    )
    results = search("boussinesq", index)
    assert len(results) == 1


def test_search_and_logic() -> None:
    index = build_index(
        [_make_seed(task_id="wave-breaking", description="coastal wave analysis")],
        [],
    )
    assert len(search("wave coastal", index)) == 1
    assert len(search("wave electrical", index)) == 0


def test_search_case_insensitive() -> None:
    index = build_index([], [_make_template(task_id="Voltage-Drop")])
    assert len(search("VOLTAGE", index)) == 1
    assert len(search("voltage", index)) == 1


def test_search_filter_discipline() -> None:
    index = build_index(
        [
            _make_seed(task_id="civil-task", discipline="civil"),
            _make_seed(task_id="ground-task", discipline="ground"),
        ],
        [],
    )
    results = search("task", index, discipline="civil")
    assert len(results) == 1
    assert results[0].discipline == "civil"


def test_search_filter_kind() -> None:
    seeds = [_make_seed(task_id="test-seed")]
    templates = [_make_template(task_id="test-template")]
    index = build_index(seeds, templates)
    templates_only = search("test", index, kind="template")
    seeds_only = search("test", index, kind="seed")
    assert all(e.kind == "template" for e in templates_only)
    assert all(e.kind == "seed" for e in seeds_only)


def test_search_empty_query_returns_all() -> None:
    index = build_index(
        [_make_seed(task_id="a"), _make_seed(task_id="b")],
        [_make_template(task_id="c")],
    )
    results = search("", index)
    assert len(results) == 3
