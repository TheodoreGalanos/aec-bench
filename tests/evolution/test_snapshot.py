# ABOUTME: Tests for the workspace snapshot serialiser.
# ABOUTME: Covers prompt-only, single skill, multiple skills, and description formatting.

from aec_bench.contracts.evolution import SkillEntry, WorkspaceSnapshot
from aec_bench.evolution.snapshot import serialise_snapshot


def _make_snapshot(
    prompt: str = "You are an engineering agent.",
    skills: list[SkillEntry] | None = None,
) -> WorkspaceSnapshot:
    return WorkspaceSnapshot(
        system_prompt=prompt,
        skills=skills or [],
        workspace_version="evo-0",
    )


def _make_skill(
    name: str = "voltage-formulas",
    description: str = "Voltage drop calculation reference",
    body: str = "## Voltage Drop\nV_d = mV/A/m * I * L / 1000",
) -> SkillEntry:
    return SkillEntry(
        name=name,
        description=description,
        discipline="electrical",
        body=body,
    )


class TestSerialiseSnapshot:
    def test_prompt_only_no_skills(self) -> None:
        snapshot = _make_snapshot(prompt="You are a structural engineer.", skills=[])
        result = serialise_snapshot(snapshot)
        assert result == "You are a structural engineer."

    def test_prompt_with_one_skill(self) -> None:
        skill = _make_skill(
            name="cable-sizing",
            description="Cable sizing reference formulas",
            body="## Cable Sizing\nI_z >= I_b",
        )
        snapshot = _make_snapshot(prompt="You are an electrical engineer.", skills=[skill])
        result = serialise_snapshot(snapshot)

        assert result.startswith("You are an electrical engineer.")
        assert "## Domain Knowledge" in result
        assert "### cable-sizing" in result
        assert "*Cable sizing reference formulas*" in result
        assert "I_z >= I_b" in result

    def test_prompt_with_multiple_skills(self) -> None:
        skills = [
            _make_skill(name="skill-a", body="Body A"),
            _make_skill(name="skill-b", body="Body B"),
        ]
        snapshot = _make_snapshot(skills=skills)
        result = serialise_snapshot(snapshot)

        assert "### skill-a" in result
        assert "Body A" in result
        assert "### skill-b" in result
        assert "Body B" in result

    def test_skill_description_included(self) -> None:
        skill = _make_skill(
            name="slope-stability",
            description="Bishop method slope stability",
            body="FS = sum(c'b + (W - ub) tan(phi')) / sum(W sin(alpha))",
        )
        snapshot = _make_snapshot(skills=[skill])
        result = serialise_snapshot(snapshot)

        assert "*Bishop method slope stability*" in result
