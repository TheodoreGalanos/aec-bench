# ABOUTME: Tests for scratch-only candidate variation and child submission.
# ABOUTME: Proves canonical workspaces remain unchanged through no-op and rejected variation.

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from aec_bench.contracts.evolution import (
    CandidateAssessment,
    EvolutionObservation,
    FieldScore,
    MutationStrategy,
    ObservationEnrichment,
    SkillEntry,
    WorkspaceSnapshot,
)
from aec_bench.evolution.analysis import BehavioralPattern, EvolutionAnalysis, GraduatedScope
from aec_bench.evolution.core import EvaluatedCandidate, SelectionPlan, VariationRequest, VariationStatus
from aec_bench.evolution.variation import run_structured_variation
from aec_bench.evolution.workspace import Workspace, scratch_workspace_from
from tests.support.trial_record_factories import make_trial_record


def _workspace(root: Path) -> Workspace:
    root.mkdir(parents=True)
    (root / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "name": "variation-test",
                "agent_adapter": "tool_loop",
                "evolvable_layers": ["prompts", "skills"],
            }
        ),
        encoding="utf-8",
    )
    (root / "prompts").mkdir()
    (root / "prompts" / "system.md").write_text("Canonical prompt", encoding="utf-8")
    return Workspace(root)


def _request(
    workspace: Workspace,
    *,
    patterns: tuple[BehavioralPattern, ...] = (),
    parent_id: str = "parent",
    inspiration: WorkspaceSnapshot | None = None,
) -> VariationRequest:
    trial = make_trial_record(
        trial_id="trial-1",
        evaluation={
            "reward": 0.4,
            "validity": {"output_parseable": True, "schema_valid": True, "verifier_completed": True},
        },
    )
    observation = EvolutionObservation(
        trial=trial,
        enrichment=ObservationEnrichment(
            field_scores=[FieldScore(field_name="voltage", reward=0.0, expected="1", actual="2")]
        ),
        candidate_id=parent_id,
        discipline="electrical",
    )
    assessment = CandidateAssessment(
        candidate_id=parent_id,
        batch_score=0.4,
        structural_score=None,
        discipline_scores={"electrical": 0.4},
        trial_ids=("trial-1",),
        evaluation_case_ids=("case-1",),
        valid=True,
    )
    parent = EvaluatedCandidate(
        snapshot=workspace.export_snapshot(parent_id),
        observations=(observation,),
        assessment=assessment,
    )
    return VariationRequest(
        selection=SelectionPlan(
            parent_id,
            () if inspiration is None else (inspiration.candidate_id,),
            MutationStrategy.CONSERVATIVE,
            "Improve checks",
            "test",
        ),
        parent=parent,
        inspirations=() if inspiration is None else (inspiration,),
        analysis=EvolutionAnalysis([], list(patterns), GraduatedScope.TARGETED, None, 0.4),
        scope=GraduatedScope.TARGETED,
        history=(),
        graveyard=(),
    )


class _ResponseLLM:
    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []

    def complete(self, prompt: str, *, temperature: float = 0.0, max_tokens: int = 4000) -> str:
        self.prompts.append(prompt)
        return self.response


def test_scratch_workspace_materialises_parent_and_cleans(tmp_path: Path) -> None:
    source = _workspace(tmp_path / "source")
    source.write_prompt("Source prompt must not leak")
    source.write_skill(SkillEntry(name="source-skill", description="Source", body="Source body is long enough"))
    (source.root / "program.md").write_text("Workspace program", encoding="utf-8")
    for relative in ("reports", "archive.json", "graveyard.json", "history"):
        path = source.root / relative
        if "." in path.name:
            path.write_text("private", encoding="utf-8")
        else:
            path.mkdir()
            (path / "run.json").write_text("private", encoding="utf-8")
    (source.root / ".git").mkdir()

    parent = WorkspaceSnapshot(
        system_prompt="Parent prompt",
        skills=(SkillEntry(name="parent-skill", description="Parent", body="Parent body is long enough"),),
        candidate_id="parent",
    )
    scratch_root: Path | None = None
    with scratch_workspace_from(source, parent, "child") as scratch:
        scratch_root = scratch.root
        assert scratch.read_prompt() == parent.system_prompt
        assert scratch.list_skills() == list(parent.skills)
        assert (scratch.root / "manifest.yaml").exists()
        assert (scratch.root / "program.md").read_text(encoding="utf-8") == "Workspace program"
        assert not (scratch.root / "reports").exists()
        assert not (scratch.root / "archive.json").exists()
        assert not (scratch.root / "graveyard.json").exists()
        assert not (scratch.root / "history").exists()
        assert not (scratch.root / ".git").exists()
    assert scratch_root is not None
    assert not scratch_root.exists()


def test_empty_variation_abstains_without_changing_canonical_workspace(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "workspace")
    workspace.write_skill(SkillEntry(name="existing", description="Existing", body="Existing body is long enough"))
    request = _request(workspace)
    before = workspace.export_snapshot("parent")

    result = run_structured_variation(
        request,
        workspace,
        "child",
        evolver_llm=_ResponseLLM('{"actions": [], "reasoning": "No change needed."}'),
    )

    assert result.status is VariationStatus.ABSTAINED
    assert result.child is None
    assert workspace.export_snapshot("parent") == before


def test_auto_seed_and_model_mutation_are_submitted_from_scratch(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "workspace")
    request = _request(
        workspace,
        patterns=(
            BehavioralPattern(
                name="blind_action",
                count=2,
                description="blind action",
                affected_trial_ids=("trial-1",),
            ),
        ),
    )
    before = workspace.export_snapshot("parent")
    result = run_structured_variation(
        request,
        workspace,
        "child",
        evolver_llm=_ResponseLLM(
            '{"actions": [{"type": "write_skill", "name": "domain-check", '
            '"description": "Domain check", "body": "Apply this domain check before submission."}], '
            '"reasoning": "Added a domain check."}'
        ),
    )

    assert result.status is VariationStatus.SUBMITTED
    assert result.child is not None
    assert result.child.candidate_id == "child"
    assert {skill.name for skill in result.child.skills} == {"verification-checkpoint", "domain-check"}
    assert result.mutation is not None
    assert "verification-checkpoint" in result.mutation.skills_added
    assert "domain-check" in result.mutation.skills_added
    assert workspace.export_snapshot("parent") == before


def test_same_content_mutation_is_abstention(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "workspace")
    request = _request(workspace)
    result = run_structured_variation(
        request,
        workspace,
        "child",
        evolver_llm=_ResponseLLM('{"actions": [{"type": "modify_prompt", "content": "Canonical prompt"}]}'),
    )

    assert result.status is VariationStatus.ABSTAINED
    assert result.child is None


def test_variation_exception_still_leaves_canonical_workspace_unchanged(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "workspace")
    request = _request(workspace)

    class FailingLLM:
        def complete(self, prompt: str, *, temperature: float = 0.0, max_tokens: int = 4000) -> str:
            raise RuntimeError("proposal failed")

    with pytest.raises(RuntimeError, match="proposal failed"):
        run_structured_variation(request, workspace, "child", evolver_llm=FailingLLM())
    assert workspace.read_prompt() == "Canonical prompt"


def test_fallback_receives_field_details_and_inspiration_material(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "workspace")
    inspiration = WorkspaceSnapshot(
        system_prompt="Inspiration system prompt",
        skills=(SkillEntry(name="inspiration-skill", description="Inspiration", body="Inspiration skill body"),),
        candidate_id="inspiration",
    )
    request = _request(workspace, inspiration=inspiration)
    llm = _ResponseLLM('{"actions": [], "reasoning": "No change needed."}')

    run_structured_variation(request, workspace, "child", evolver_llm=llm)

    assert len(llm.prompts) == 1
    prompt = llm.prompts[0]
    assert "agent's value was significantly too high" in prompt
    assert "Candidate inspiration" in prompt
    assert "Inspiration system prompt" in prompt
    assert "inspiration-skill" in prompt
    assert "Inspiration skill body" in prompt


def test_structured_path_receives_inspiration_material(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = _workspace(tmp_path / "workspace")
    inspiration = WorkspaceSnapshot(
        system_prompt="Structured inspiration prompt",
        skills=(SkillEntry(name="structured-skill", description="Structured", body="Structured skill body"),),
        candidate_id="inspiration",
    )
    request = _request(workspace, inspiration=inspiration)
    captured: dict[str, str] = {}

    def fake_structured_call(**kwargs: object) -> object:
        captured["brief"] = str(kwargs["analysis_brief"])
        from aec_bench.evolution.mutation import ParsedMutationResponse

        return ParsedMutationResponse(actions=(), reasoning="No change needed.")

    monkeypatch.setattr(
        "aec_bench.evolution.structured_evolver.call_structured_evolver_with_tools",
        fake_structured_call,
    )
    result = run_structured_variation(request, workspace, "child", evolver_model_name="test:model")

    assert result.status is VariationStatus.ABSTAINED
    brief = captured["brief"]
    assert "Candidate inspiration" in brief
    assert "Structured inspiration prompt" in brief
    assert "structured-skill" in brief
    assert "Structured skill body" in brief
