# ABOUTME: Synthetic conformance tests for shared report assets and validation.
# ABOUTME: Covers distinct source layouts, visibility, dependency state, and rejected fills.

import json
from pathlib import Path

import pytest

from aec_bench.contracts.repl import DependencyTreeSchema, TreeSection
from aec_bench.templates.report.assets import load_report_assets
from aec_bench.templates.report.session import ReportSession


@pytest.mark.parametrize("source_path", ["documents/brief.md", "inputs/evidence/facts.txt"])
def test_public_rules_sources_and_rubric_share_one_report(tmp_path: Path, source_path: str) -> None:
    source = tmp_path / source_path
    source.parent.mkdir(parents=True)
    source.write_text("The inspection records 12 items.")
    (tmp_path / "sources.toml").write_text(f'''[sources.brief]
path = "{source_path}"
visibility = "public"
''')
    (tmp_path / "rules.toml").write_text("""visibility = "public"
[[rules]]
id = "evidence"
kind = "required_pattern"
pattern = "12"
message = "Include the observed count"
[[rules]]
id = "tone"
kind = "forbidden_pattern"
pattern = "obviously"
message = "Avoid unsupported emphasis"
severity = "warning"
[[rules]]
id = "clarity"
kind = "prose"
message = "Explain the finding clearly"
""")
    template = tmp_path / "template.toml"
    template.write_text("""[[sections]]
id = "findings"
title = "Findings"
input_mapping = ["brief"]
fields = [{name="text", dtype="str", required=true}]
[rubric]
visibility = "public"
[[rubric.dimensions]]
id = "accuracy"
weight = 2
eval_method = "llm_judge"
eval_references = ["brief"]
criteria = [{text="Trace the observed count", category="essential"}]
""")
    assets = load_report_assets(
        template, workspace=tmp_path, source_mapping="sources.toml", validation_rules="rules.toml"
    )
    assert assets.sources.read("brief") == source.read_text()
    bad = assets.session.fill_section("findings", {"text": "Several items"})
    assert not bad.success and not assets.session.submit().complete
    good = assets.session.fill_section("findings", {"text": "Obviously 12 items".lower()})
    assert good.success
    assert good.validation.warnings[0].rule_id == "tone"
    assert good.validation.unchecked[0].rule_id == "clarity"
    assert assets.session.submit().complete
    context = assets.session.get_extraction_context("findings")
    assert context is not None
    assert "accuracy" in context["criteria"]
    assert not assets.session.fresh().submit().complete
    configuration = json.loads(json.dumps(assets.session.configuration()))
    assert configuration["template"]["sections"][0]["fields"]["text"]["required"] is True
    assert configuration["rules"][0]["id"] == "evidence"
    assert configuration["rubric"]["dimensions"][0]["weight"] == 2
    assert configuration["source_ids"] == ["brief"]
    configuration["template"]["sections"][0]["fields"]["text"]["required"] = False
    assert assets.session.schema.sections[0].fields["text"].required is True


@pytest.mark.parametrize("visibility", ["", 'visibility = "private"', 'visibility = "holdout"'])
def test_unapproved_rubric_never_enters_actor_context(tmp_path: Path, visibility: str) -> None:
    path = tmp_path / "template.toml"
    path.write_text(f"""[[sections]]
id="summary"
title="Summary"
[rubric]
{visibility}
[[rubric.dimensions]]
id="private"
criteria=["HIDDEN_VERIFIER_MARKER"]
""")
    assets = load_report_assets(path, workspace=tmp_path)
    assert assets.session.rubric is None
    assert assets.session.configuration()["rubric"] is None
    assert "HIDDEN_VERIFIER_MARKER" not in str(assets.session.get_extraction_context("summary"))


def test_symlink_source_escape_is_rejected(tmp_path: Path) -> None:
    workspace = tmp_path / "actor"
    workspace.mkdir()
    (workspace / "documents").mkdir()
    secret = tmp_path / "private.txt"
    secret.write_text("HIDDEN_VERIFIER_MARKER")
    (workspace / "documents" / "brief.txt").symlink_to(secret)
    template = workspace / "template.toml"
    template.write_text('[[sections]]\nid="s"\ntitle="S"')
    with pytest.raises(ValueError, match="escapes"):
        load_report_assets(template, workspace=workspace)


@pytest.mark.parametrize(
    "sections",
    [
        [TreeSection("a", "A", {}, depends_on=("missing",))],
        [TreeSection("a", "A", {}, depends_on=("b",)), TreeSection("b", "B", {}, depends_on=("a",))],
        [TreeSection("a", "A", {}), TreeSection("a", "Duplicate", {})],
    ],
)
def test_invalid_graph_is_rejected_before_execution(sections: list[TreeSection]) -> None:
    with pytest.raises(ValueError):
        ReportSession(DependencyTreeSchema(sections))
