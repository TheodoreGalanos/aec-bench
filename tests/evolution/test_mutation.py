# ABOUTME: Tests for evolution mutation response parsing and application.
# ABOUTME: Covers JSON extraction, action validation, and error handling for LLM output.

from __future__ import annotations

import json
from pathlib import Path

import yaml

from aec_bench.evolution.mutation import (
    MutationAction,
    ParsedMutationResponse,
    _repair_json_strings,
    apply_mutations,
    parse_evolver_response,
)
from aec_bench.evolution.workspace import Workspace

# ---------------------------------------------------------------------------
# Helpers shared with workspace tests (inlined to avoid cross-test imports)
# ---------------------------------------------------------------------------


def _scaffold_workspace(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": "test-workspace",
        "agent_adapter": "tool_loop",
        "evolvable_layers": ["prompts", "skills"],
    }
    (root / "manifest.yaml").write_text(yaml.dump(manifest))
    prompts_dir = root / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "system.md").write_text("You are an engineering agent.")
    return root


class TestRepairJsonStrings:
    def test_escapes_literal_newlines_in_strings(self) -> None:
        raw = '{"body": "line1\nline2\nline3"}'
        repaired = _repair_json_strings(raw)
        parsed = json.loads(repaired)
        assert parsed["body"] == "line1\nline2\nline3"

    def test_preserves_already_escaped_newlines(self) -> None:
        raw = '{"body": "line1\\nline2"}'
        repaired = _repair_json_strings(raw)
        parsed = json.loads(repaired)
        assert parsed["body"] == "line1\nline2"

    def test_handles_multiline_markdown_body(self) -> None:
        raw = '{"actions": [{"type": "write_skill", "body": "## Title\n\nSome content\n- bullet 1\n- bullet 2"}]}'
        repaired = _repair_json_strings(raw)
        parsed = json.loads(repaired)
        assert "## Title" in parsed["actions"][0]["body"]
        assert "- bullet 1" in parsed["actions"][0]["body"]

    def test_handles_nested_code_fences_in_body(self) -> None:
        """The evolver wraps JSON in ```json but skill bodies also contain ``` blocks."""
        raw = (
            "Some preamble text.\n\n```json\n"
            '{"actions": [{"type": "write_skill", "name": "calc", '
            '"body": "## Formula\\n```\\nVd = Vc * I * L / 1000\\n```\\nUse this."}], '
            '"reasoning": "added skill"}\n```'
        )
        result = parse_evolver_response(raw)
        assert len(result.actions) == 1
        assert "Formula" in result.actions[0].skill_body
        assert len(result.parse_errors) == 0

    def test_parses_evolver_response_with_newlines(self) -> None:
        """Full integration: parse_evolver_response handles unescaped newlines."""
        raw = (
            '{"actions": [{"type": "write_skill", "name": "test", '
            '"body": "## Skill\n\nContent here\n- item"}], "reasoning": "test"}'
        )
        result = parse_evolver_response(raw)
        assert len(result.actions) == 1
        assert result.actions[0].skill_body is not None
        assert "## Skill" in result.actions[0].skill_body


class TestParseEvolverResponse:
    def test_parses_valid_response(self) -> None:
        payload = {
            "actions": [
                {
                    "type": "write_skill",
                    "name": "compliance-verification",
                    "description": "Verify compliance flags match calculated values",
                    "discipline": "electrical",
                    "body": "## Compliance Verification\n\nAfter calculating voltage drop...",
                },
                {
                    "type": "modify_prompt",
                    "content": "Updated system prompt text...",
                },
            ],
            "reasoning": "The compliance field fails at 45%. Adding a verification skill...",
        }
        response = json.dumps(payload)

        result = parse_evolver_response(response)

        assert isinstance(result, ParsedMutationResponse)
        assert len(result.actions) == 2
        expected_reasoning = "The compliance field fails at 45%. Adding a verification skill..."
        assert result.reasoning == expected_reasoning
        assert len(result.parse_errors) == 0

        write_action = result.actions[0]
        assert write_action.action_type == "write_skill"
        assert write_action.skill_name == "compliance-verification"
        assert write_action.skill_description == "Verify compliance flags match calculated values"
        assert write_action.skill_discipline == "electrical"
        expected_body = "## Compliance Verification\n\nAfter calculating voltage drop..."
        assert write_action.skill_body == expected_body
        assert write_action.prompt_content is None

        prompt_action = result.actions[1]
        assert prompt_action.action_type == "modify_prompt"
        assert prompt_action.prompt_content == "Updated system prompt text..."
        assert prompt_action.skill_name is None

    def test_parses_json_in_markdown_fence(self) -> None:
        payload = {
            "actions": [
                {
                    "type": "modify_skill",
                    "name": "voltage-formulas",
                    "body": "## Updated Voltage Drop\n\nNew content...",
                }
            ],
            "reasoning": "Updating the formula skill.",
        }
        response = f"```json\n{json.dumps(payload)}\n```"

        result = parse_evolver_response(response)

        assert len(result.actions) == 1
        assert result.actions[0].action_type == "modify_skill"
        assert result.actions[0].skill_name == "voltage-formulas"
        assert len(result.parse_errors) == 0

    def test_handles_preamble_text(self) -> None:
        payload = {
            "actions": [
                {
                    "type": "delete_skill",
                    "name": "outdated-skill",
                }
            ],
            "reasoning": "Removing outdated skill.",
        }
        response = f"Here are my changes:\n\n{json.dumps(payload)}"

        result = parse_evolver_response(response)

        assert len(result.actions) == 1
        assert result.actions[0].action_type == "delete_skill"
        assert result.actions[0].skill_name == "outdated-skill"
        assert len(result.parse_errors) == 0

    def test_skips_invalid_action_type(self) -> None:
        payload = {
            "actions": [
                {
                    "type": "modify_prompt",
                    "content": "Valid prompt update.",
                },
                {
                    "type": "unknown_action",
                    "name": "some-skill",
                },
            ],
            "reasoning": "Testing unknown type handling.",
        }
        response = json.dumps(payload)

        result = parse_evolver_response(response)

        assert len(result.actions) == 1
        assert result.actions[0].action_type == "modify_prompt"
        assert len(result.parse_errors) == 1

    def test_skips_action_missing_required_fields(self) -> None:
        payload = {
            "actions": [
                {
                    "type": "write_skill",
                    "name": "incomplete-skill",
                    "description": "Missing body field",
                    # "body" is missing
                }
            ],
            "reasoning": "Testing missing required field handling.",
        }
        response = json.dumps(payload)

        result = parse_evolver_response(response)

        assert len(result.actions) == 0
        assert len(result.parse_errors) == 1

    def test_returns_empty_on_invalid_json(self) -> None:
        response = "I couldn't determine what to change."

        result = parse_evolver_response(response)

        assert len(result.actions) == 0
        assert len(result.parse_errors) == 1

    def test_empty_actions_list(self) -> None:
        payload = {
            "actions": [],
            "reasoning": "No changes needed.",
        }
        response = json.dumps(payload)

        result = parse_evolver_response(response)

        assert len(result.actions) == 0
        assert len(result.parse_errors) == 0
        assert result.reasoning == "No changes needed."

    def test_handles_write_skill_with_all_fields(self) -> None:
        payload = {
            "actions": [
                {
                    "type": "write_skill",
                    "name": "full-skill",
                    "description": "A fully specified skill",
                    "discipline": "structural",
                    "body": "## Full Skill\n\nComplete body content.",
                }
            ],
            "reasoning": "Adding a complete skill.",
        }
        response = json.dumps(payload)

        result = parse_evolver_response(response)

        assert len(result.actions) == 1
        action = result.actions[0]
        assert action.action_type == "write_skill"
        assert action.skill_name == "full-skill"
        assert action.skill_description == "A fully specified skill"
        assert action.skill_discipline == "structural"
        assert action.skill_body == "## Full Skill\n\nComplete body content."
        assert action.prompt_content is None

    def test_handles_delete_skill(self) -> None:
        payload = {
            "actions": [
                {
                    "type": "delete_skill",
                    "name": "old-skill",
                }
            ],
            "reasoning": "Removing obsolete skill.",
        }
        response = json.dumps(payload)

        result = parse_evolver_response(response)

        assert len(result.actions) == 1
        action = result.actions[0]
        assert action.action_type == "delete_skill"
        assert action.skill_name == "old-skill"
        assert action.skill_body is None
        assert action.skill_description is None
        assert action.prompt_content is None


# ---------------------------------------------------------------------------
# TestApplyMutations
# ---------------------------------------------------------------------------


class TestApplyMutations:
    def test_write_skill_action(self, tmp_path: Path) -> None:
        ws = Workspace(_scaffold_workspace(tmp_path / "ws"))
        actions = [
            MutationAction(
                action_type="write_skill",
                skill_name="voltage-formulas",
                skill_description="Voltage drop reference",
                skill_discipline="electrical",
                skill_body="## Voltage Drop\nV_d = mV/A/m * I * L / 1000",
            )
        ]

        summary = apply_mutations(actions, ws)

        skill_names = [s.name for s in ws.list_skills()]
        assert "voltage-formulas" in skill_names
        assert "voltage-formulas" in summary.skills_added
        assert summary.skills_modified == []
        assert summary.skills_removed == []
        assert summary.prompt_modified is False

    def test_modify_existing_skill(self, tmp_path: Path) -> None:
        from aec_bench.contracts.evolution import SkillEntry

        ws = Workspace(_scaffold_workspace(tmp_path / "ws"))
        ws.write_skill(
            SkillEntry(
                name="voltage-formulas",
                description="Old description",
                discipline="electrical",
                body="## Old Body",
            )
        )
        actions = [
            MutationAction(
                action_type="modify_skill",
                skill_name="voltage-formulas",
                skill_body="## New Body",
            )
        ]

        summary = apply_mutations(actions, ws)

        updated = ws.read_skill("voltage-formulas")
        assert updated is not None
        assert updated.body == "## New Body"
        assert "voltage-formulas" in summary.skills_modified
        assert summary.skills_added == []

    def test_modify_nonexistent_skill_creates_it(self, tmp_path: Path) -> None:
        ws = Workspace(_scaffold_workspace(tmp_path / "ws"))
        actions = [
            MutationAction(
                action_type="modify_skill",
                skill_name="brand-new",
                skill_description="Created via modify",
                skill_body="## Brand New Skill",
            )
        ]

        summary = apply_mutations(actions, ws)

        skill = ws.read_skill("brand-new")
        assert skill is not None
        assert "brand-new" in summary.skills_added
        assert summary.skills_modified == []

    def test_delete_skill_action(self, tmp_path: Path) -> None:
        from aec_bench.contracts.evolution import SkillEntry

        ws = Workspace(_scaffold_workspace(tmp_path / "ws"))
        ws.write_skill(
            SkillEntry(
                name="to-delete",
                description="Will be removed",
                body="## Goodbye",
            )
        )
        actions = [
            MutationAction(
                action_type="delete_skill",
                skill_name="to-delete",
            )
        ]

        summary = apply_mutations(actions, ws)

        assert ws.read_skill("to-delete") is None
        assert "to-delete" in summary.skills_removed
        assert summary.skills_added == []
        assert summary.skills_modified == []

    def test_delete_nonexistent_skill_no_error(self, tmp_path: Path) -> None:
        ws = Workspace(_scaffold_workspace(tmp_path / "ws"))
        actions = [
            MutationAction(
                action_type="delete_skill",
                skill_name="ghost-skill",
            )
        ]

        summary = apply_mutations(actions, ws)

        assert summary.skills_removed == []

    def test_modify_prompt_action(self, tmp_path: Path) -> None:
        ws = Workspace(_scaffold_workspace(tmp_path / "ws"))
        new_content = "You are a structural engineering specialist."
        actions = [
            MutationAction(
                action_type="modify_prompt",
                prompt_content=new_content,
            )
        ]

        summary = apply_mutations(actions, ws)

        assert ws.read_prompt() == new_content
        assert summary.prompt_modified is True

    def test_multiple_actions(self, tmp_path: Path) -> None:
        ws = Workspace(_scaffold_workspace(tmp_path / "ws"))
        actions = [
            MutationAction(
                action_type="write_skill",
                skill_name="skill-alpha",
                skill_description="First skill",
                skill_body="## Alpha",
            ),
            MutationAction(
                action_type="write_skill",
                skill_name="skill-beta",
                skill_description="Second skill",
                skill_body="## Beta",
            ),
            MutationAction(
                action_type="modify_prompt",
                prompt_content="Updated prompt.",
            ),
        ]

        summary = apply_mutations(actions, ws)

        assert "skill-alpha" in summary.skills_added
        assert "skill-beta" in summary.skills_added
        assert summary.prompt_modified is True
        skill_names = [s.name for s in ws.list_skills()]
        assert "skill-alpha" in skill_names
        assert "skill-beta" in skill_names

    def test_empty_actions(self, tmp_path: Path) -> None:
        ws = Workspace(_scaffold_workspace(tmp_path / "ws"))

        summary = apply_mutations([], ws)

        assert summary.prompt_modified is False
        assert summary.skills_added == []
        assert summary.skills_modified == []
        assert summary.skills_removed == []
        assert summary.memory_entries_added == 0
