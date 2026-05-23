# ABOUTME: Tests for the compaction input builder — structured trajectory extraction.
# ABOUTME: Validates that compaction input is built from REPL state and trajectory data.

from aec_bench.agents.compaction import build_compaction_input, build_compaction_prompt


def test_build_compaction_input_minimal() -> None:
    result = build_compaction_input(
        variables={"x": 42, "docs": ["a.pdf"]},
        scratchpad={"key_facts": "some facts"},
        template_status={"total": 9, "completed": 3, "pending": ["design", "cost"]},
        trajectory_steps=[],
        turn_count=25,
        tokens_used=600_000,
    )
    assert result["variables"] == {"x": 42, "docs": ["a.pdf"]}
    assert result["scratchpad"] == {"key_facts": "some facts"}
    assert result["template_status"]["completed"] == 3
    assert result["turn_count"] == 25
    assert result["tokens_used"] == 600_000


def test_build_compaction_input_extracts_documents_from_trajectory() -> None:
    steps = [
        {"tool": "repl", "code": 'open("/workspace/brief.pdf").read()', "subcalls": []},
        {
            "tool": "repl",
            "code": 'x = extract(doc, ["name"])',
            "subcalls": [{"type": "extract", "fields": ["name"], "text_length": 5000}],
        },
        {
            "tool": "repl",
            "code": 'result = llm_query("Write intro")',
            "subcalls": [{"type": "llm_query", "prompt": "Write intro"}],
        },
    ]
    result = build_compaction_input(
        variables={},
        scratchpad={},
        template_status=None,
        trajectory_steps=steps,
        turn_count=10,
        tokens_used=300_000,
    )
    assert len(result["documents_read"]) >= 1
    assert len(result["extract_calls"]) >= 1
    assert len(result["composition_calls"]) >= 1


def test_build_compaction_prompt_contains_structured_sections() -> None:
    compaction_input = {
        "variables": {"facts": {"name": "Project X"}},
        "scratchpad": {"brief_facts": "scope is electrical"},
        "template_status": {"total": 9, "completed": 3, "pending": ["design"]},
        "documents_read": ["brief.pdf"],
        "extract_calls": [{"fields": ["name"], "text_length": 5000}],
        "composition_calls": [{"prompt": "Write intro"}],
        "errors": [],
        "turn_count": 25,
        "tokens_used": 600_000,
    }
    prompt = build_compaction_prompt(compaction_input)
    assert "Documents read" in prompt
    assert "Variables" in prompt or "Extracted data" in prompt
    assert "Work completed" in prompt or "sections" in prompt.lower()
    assert "Work remaining" in prompt or "pending" in prompt.lower()
    assert isinstance(prompt, str)
    assert len(prompt) > 100
