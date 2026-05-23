# ABOUTME: Tests for LLM-based skill compaction in the sanitiser.
# ABOUTME: Covers preserve mode (mild overage), summarise mode (heavy overage), and soft budget.

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from aec_bench.contracts.evolution import SkillEntry
from aec_bench.evolution.sanitiser import (
    COMPACTION_TARGET_CHARS,
    compact_skill,
    sanitise_workspace,
)
from aec_bench.evolution.workspace import Workspace

# ---------------------------------------------------------------------------
# Fake LLM client for testing
# ---------------------------------------------------------------------------


class FakeLLMClient:
    """Records calls and returns a predetermined response."""

    def __init__(self, response: str = "compacted content") -> None:
        self.calls: list[dict[str, Any]] = []
        self.response = response

    def complete(
        self,
        prompt: str,
        *,
        temperature: float = 0.0,
        max_tokens: int = 4000,
    ) -> str:
        self.calls.append({"prompt": prompt, "temperature": temperature, "max_tokens": max_tokens})
        return self.response


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _scaffold_workspace(root: Path, skill_budget: int = 10) -> Workspace:
    """Create minimal workspace directory structure and return a Workspace."""
    root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": "test-workspace",
        "agent_adapter": "tool_loop",
        "evolvable_layers": ["prompts", "skills"],
        "skill_budget": skill_budget,
    }
    (root / "manifest.yaml").write_text(yaml.dump(manifest))
    prompts_dir = root / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "system.md").write_text("You are an engineering agent.")
    return Workspace(root)


def _add_skill(ws: Workspace, name: str, body: str) -> None:
    """Create a SkillEntry and write it to the workspace."""
    skill = SkillEntry(
        name=name,
        description=f"Description for {name}",
        body=body,
    )
    ws.write_skill(skill)


# ---------------------------------------------------------------------------
# Tests: compact_skill function
# ---------------------------------------------------------------------------


class TestCompactSkill:
    def test_preserve_mode_for_mild_overage(self) -> None:
        """Skill at 1.3x budget uses preserve mode (mentions 'preserve')."""
        llm = FakeLLMClient(response="a" * 3800)
        body = "x" * int(COMPACTION_TARGET_CHARS * 1.3)

        result = compact_skill(body, budget=COMPACTION_TARGET_CHARS, llm=llm)

        assert len(llm.calls) == 1
        prompt = llm.calls[0]["prompt"]
        assert "preserve" in prompt.lower() or "verbatim" in prompt.lower()
        assert result == "a" * 3800

    def test_summarise_mode_for_heavy_overage(self) -> None:
        """Skill at 2.5x budget uses summarise mode (mentions 'prioriti')."""
        llm = FakeLLMClient(response="b" * 3900)
        body = "y" * int(COMPACTION_TARGET_CHARS * 2.5)

        result = compact_skill(body, budget=COMPACTION_TARGET_CHARS, llm=llm)

        assert len(llm.calls) == 1
        prompt = llm.calls[0]["prompt"]
        assert "prioriti" in prompt.lower()
        assert result == "b" * 3900

    def test_trusts_llm_output_even_if_over_budget(self) -> None:
        """If LLM returns content still over budget, trust it — no truncation."""
        llm = FakeLLMClient(response="c" * 5000)
        body = "z" * 6000

        result = compact_skill(body, budget=COMPACTION_TARGET_CHARS, llm=llm)

        # Result is the full LLM output — not truncated
        assert len(result) == 5000
        assert result == "c" * 5000

    def test_preserves_table_content_in_prompt(self) -> None:
        """The compaction prompt includes the original skill body."""
        llm = FakeLLMClient(response="compacted")
        body = "| mm² | vc |\n|------|----|\n| 1.5 | 24.0 |" + "x" * 4500

        compact_skill(body, budget=COMPACTION_TARGET_CHARS, llm=llm)

        prompt = llm.calls[0]["prompt"]
        assert "| mm²" in prompt

    def test_budget_passed_to_prompt(self) -> None:
        """The target character budget appears in the LLM prompt."""
        llm = FakeLLMClient(response="short")
        body = "w" * 5000

        compact_skill(body, budget=4000, llm=llm)

        prompt = llm.calls[0]["prompt"]
        assert "4000" in prompt


# ---------------------------------------------------------------------------
# Tests: sanitise_workspace with compaction
# ---------------------------------------------------------------------------


class TestSanitiseWithCompaction:
    def test_uses_compaction_when_llm_provided(self, tmp_path: Path) -> None:
        """When compaction_llm is provided, oversized skills are compacted not truncated."""
        ws = _scaffold_workspace(tmp_path / "ws")
        _add_skill(ws, "big-skill", "important data " * 400)  # ~5600 chars, over 4000

        llm = FakeLLMClient(response="compacted important data reference table")
        result = sanitise_workspace(ws, compaction_llm=llm)

        assert "big-skill" in result.skills_compacted
        assert "big-skill" not in result.skills_truncated
        assert len(llm.calls) == 1

        skill = ws.read_skill("big-skill")
        assert skill is not None
        assert skill.body == "compacted important data reference table"

    def test_no_compaction_when_under_budget(self, tmp_path: Path) -> None:
        """Skills under 4000 chars are left alone even with compaction_llm."""
        ws = _scaffold_workspace(tmp_path / "ws")
        _add_skill(ws, "fine-skill", "x" * 3000)  # Under 4000

        llm = FakeLLMClient(response="should not be called")
        result = sanitise_workspace(ws, compaction_llm=llm)

        assert result.skills_compacted == []
        assert result.skills_truncated == []
        assert len(llm.calls) == 0

    def test_trusts_llm_even_if_still_over_target(self, tmp_path: Path) -> None:
        """If LLM compacts but result is still over target, keep it — no truncation."""
        ws = _scaffold_workspace(tmp_path / "ws")
        _add_skill(ws, "data-heavy", "d" * 8000)

        # LLM returns 4500 chars — over 4000 target but trusted
        llm = FakeLLMClient(response="d" * 4500)
        result = sanitise_workspace(ws, compaction_llm=llm)

        assert "data-heavy" in result.skills_compacted
        skill = ws.read_skill("data-heavy")
        assert skill is not None
        assert len(skill.body) == 4500  # Kept as-is, not truncated

    def test_no_truncation_without_llm_below_old_limit(self, tmp_path: Path) -> None:
        """Without compaction_llm, skills under the target are untouched."""
        ws = _scaffold_workspace(tmp_path / "ws")
        _add_skill(ws, "normal", "x" * 3500)

        result = sanitise_workspace(ws)

        assert result.skills_truncated == []
        assert result.skills_compacted == []

    def test_compaction_mode_in_result(self, tmp_path: Path) -> None:
        """SanitiseResult reports which skills were compacted."""
        ws = _scaffold_workspace(tmp_path / "ws")
        _add_skill(ws, "mild", "m" * 5000)  # 1.25x — preserve mode
        _add_skill(ws, "heavy", "h" * 10000)  # 2.5x — summarise mode

        llm = FakeLLMClient(response="short enough")
        result = sanitise_workspace(ws, compaction_llm=llm)

        assert "mild" in result.skills_compacted
        assert "heavy" in result.skills_compacted
        assert len(llm.calls) == 2
