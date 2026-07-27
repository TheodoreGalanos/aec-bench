# ABOUTME: Builds the RLM system prompt, tool description, and injected help surface.
# ABOUTME: Keeps prompt-facing capability declarations synchronized with the live REPL.

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from aec_bench.adapters.rlm.config import SubcallConfig
from aec_bench.adapters.rlm.engine import ReplEnvironment
from aec_bench.contracts.constitution import ConstitutionManifest

REPL_TOOL_NAME = "repl"
REPL_TOOL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "code": {
            "type": "string",
            "description": "Python code to execute in the persistent REPL",
        }
    },
    "required": ["code"],
}

_SYSTEM_PROMPT = """\
{external_system_prompt}\
You are an RLM (Recursive Language Model) agent. The REPL is your extended \
cognition — not a tool you occasionally use, but HOW you think.

You begin with no knowledge of the task evidence beyond the supplied context. \
Read and extract evidence through the available Python/data surfaces before \
forming conclusions; an ungrounded answer is a hallucination.

Your REPL variables persist forever, but your conversation history may be \
compacted. What you store in variables is your durable working state.

CONTEXT MODEL — how your REPL output works:
- Tool results over 2000 chars are NOT shown to you in full. You receive \
a summary (type, size, preview) instead. The full data lives in your \
REPL variables — that is where your data is.
- grep() results are shown up to 10,000 chars with line numbers for navigation.
- Errors are always shown in full.
- print() of large data returns a summary, not the content. Do not try to \
force output by slicing, chunking, or looping — it will not work. Your \
data is already in variables. Use grep() to access it.
- Call SHOW_VARS() to see all variables with types and sizes.
- Call print(HELP()) to see the exact commands available in this run.

{iteration_budget_section}\
{workflow_section}\
{scratchpad_section}\
{subcall_section}\
{template_section}\

Do NOT:
- Print large variables or paginate with slicing — it returns a summary
- Spend many turns gathering data before writing — work section by section
- Invent commands that are not shown by print(HELP())

Always: data in variables, compose from variables, never from memory.

{prohibited_section}\
{hints_section}\
{variables_section}\
"""

_SUBCALL_HELP: dict[str, str] = {
    "extract": (
        "  result = extract(doc, section='section_id')\n"
        "    → ExtractResult(.values: dict, .error: str|None)\n"
        "    Reads the full document and extracts data relevant to the section.\n"
        "    Uses writing guidance from the template to decide what to extract.\n"
        "    Also works without section: extract(doc, ['field1', 'field2'])\n"
    ),
    "summarise": ("  result = summarise(content=...)\n    → SummariseResult(.summary: str, .error: str|None)\n"),
    "calculate": (
        "  result = calculate(expression=..., parameters={})\n    → CalculateResult(.values: dict, .error: str|None)\n"
    ),
    "retrieve": (
        "  result = retrieve(query=..., max_results=5, source=None)\n"
        "    → RetrieveResult(.results: list[dict], .error: str|None)\n"
    ),
    "verify": (
        "  result = verify(value=..., criterion=..., standard=None)\n"
        "    → VerificationResult(.passed: bool, .confidence: float, "
        ".explanation: str, .error: str|None)\n"
    ),
    "reason": (
        "  result = reason(question=..., context=...)\n"
        "    → ReasoningResult(.conclusion: str, .confidence: float, "
        ".rationale: str, .error: str|None)\n"
    ),
    "review": (
        "  result = review(section_content=..., writing_guidance=[...], extracted_data={...})\n"
        "    → SectionReviewResult(.status: str, .gaps: list, .risks: list, .error: str|None)\n"
        "    Use after composing a section to check it against writing guidance.\n"
    ),
    "advisor": (
        "  result = ADVISOR(goal=..., problem=..., attempt=...)\n"
        "    → AdvisorResult(.response: AdvisorResponse, .error: str|None)\n"
        "    .response.advice: str, .response.suggested_action: str,\n"
        "    .response.confidence: float, .response.reasoning: str\n"
    ),
}

_KNOWN_SUBCALL_NAMES = frozenset(_SUBCALL_HELP) - {"advisor"}


def _information_minimality_line(manifest: ConstitutionManifest) -> list[str]:
    params = manifest.information_minimality
    if params is None:
        return []
    return [
        f"- Information Minimality: Tool results over {params.default_threshold:,} "
        f"chars are summarised. Your data lives in REPL variables. "
        f"Use grep() to search (up to {params.search_threshold:,} chars)."
    ]


def _state_persistence_line(manifest: ConstitutionManifest) -> list[str]:
    params = manifest.state_persistence
    if params is None:
        return []
    return [
        f"- State Persistence: Variables and scratchpad survive compaction "
        f"(strategy: {params.compaction_strategy}). Store anything worth keeping."
    ]


def _progress_obligation_line(manifest: ConstitutionManifest) -> list[str]:
    params = manifest.progress_obligation
    if params is None:
        return []
    return [
        f"- Progress Obligation: Produce output within {params.gentle_nudge_turns} turns. "
        f"Extended data gathering without writing is considered speculation."
    ]


def _source_fidelity_lines(manifest: ConstitutionManifest) -> list[str]:
    params = manifest.source_fidelity
    if params is None:
        return []
    lines: list[str] = []
    if params.require_source_tracing:
        lines.append("- Source Fidelity: Every fact in your output must trace to extracted data.")
    if params.gap_framing == "exclude":
        lines.append(
            f"  When a source has no data for a topic, omit it entirely "
            f"or write {params.tbd_placeholder}. Do NOT fabricate."
        )
    elif params.gap_framing == "tbd":
        lines.append(
            f"  Use {params.tbd_placeholder} placeholder for any missing information. "
            f"A placeholder is always better than a fabrication."
        )
    elif params.gap_framing == "omit":
        lines.append("  Omit any topic that lacks source data entirely. Do not fabricate to fill gaps.")
    return lines


def _earned_autonomy_line(manifest: ConstitutionManifest) -> list[str]:
    params = manifest.earned_autonomy
    if params is None:
        return []
    return [f"- Earned Autonomy: Start in '{params.initial_mode}' mode. Freedom is earned by demonstrated progress."]


_CONSTITUTION_RENDERERS: tuple[
    tuple[str, Callable[[ConstitutionManifest], list[str]]],
    ...,
] = (
    ("information_minimality", _information_minimality_line),
    ("state_persistence", _state_persistence_line),
    ("progress_obligation", _progress_obligation_line),
    ("source_fidelity", _source_fidelity_lines),
    ("earned_autonomy", _earned_autonomy_line),
)


def build_constitution_section(manifest: ConstitutionManifest | None) -> str:
    """Generate the enabled constitutional principles for the agent prompt."""
    if manifest is None or not manifest.principles:
        return ""
    enabled_names = {principle.name for principle in manifest.principles if principle.enabled}
    if not enabled_names:
        return ""
    lines: list[str] = ["CONSTITUTION — principles governing this session:"]
    for name, renderer in _CONSTITUTION_RENDERERS:
        if name in enabled_names:
            lines.extend(renderer(manifest))
    return "\n".join(lines) + "\n"


def _optional_list_section(label: str, values: list[str] | None) -> str:
    if not values:
        return ""
    formatted = "\n".join(f"- {value}" for value in values)
    return f"{label}:\n{formatted}\n\n"


def _variables_section(variables: dict[str, str] | None) -> str:
    if not variables:
        return ""
    var_list = ", ".join(f"{name} ({type_name})" for name, type_name in sorted(variables.items()))
    return f"Pre-loaded variables: {var_list}\n\n"


def _iteration_budget_section(max_iterations: int | None) -> str:
    if max_iterations is None:
        return ""
    return (
        f"ITERATION BUDGET: You have at most {max_iterations} model turns. "
        "Budget messages report turns already consumed. Start writing before "
        "the finalization warning; the hard cap does not grant an extra turn.\n\n"
    )


def _workflow_section(template_enabled: bool) -> str:
    if template_enabled:
        return (
            "TEMPLATE WORKFLOW:\n"
            "- Use report.get_status() and report.get_writing_guidance(section_id) "
            "to inspect the declared structure.\n"
            "- Fill available sections with report.fill_section(section_id, content_dict).\n"
            "- Compose from stored source data and submit only after checking the report status.\n\n"
        )
    return (
        "FLAT-TASK WORKFLOW:\n"
        "- Use standard Python and pathlib for task files. When the task owns "
        "/workspace/sources, load all regular UTF-8 files in one REPL block:\n"
        "  from pathlib import Path\n"
        '  source_dir = Path("/workspace/sources")\n'
        '  docs = {path.name: path.read_text(encoding="utf-8") '
        "for path in sorted(source_dir.iterdir()) if path.is_file()}\n"
        "- Analyze related checks together, then write and validate the declared "
        "output early enough to finalize within the iteration budget.\n\n"
    )


def _scratchpad_section(enabled: bool) -> str:
    if not enabled:
        return ""
    return (
        "SCRATCHPAD:\n"
        "- NOTE(key, value) persists a fact across compaction.\n"
        "- RECALL(key) retrieves it; call RECALL() to list stored keys.\n\n"
    )


def _subcall_section(enabled_subcalls: set[str] | frozenset[str] | None) -> str:
    enabled = set(enabled_subcalls or ())
    if not enabled:
        return ""
    names = ", ".join(f"{name}()" for name in sorted(enabled))
    return (
        f"ENABLED SUB-CALLS: {names}\n"
        "Use only these listed sub-calls, and avoid repeating the same extraction "
        "or analysis without new evidence.\n\n"
    )


def _template_section(enabled: bool) -> str:
    if not enabled:
        return ""
    return (
        "REPORT SURFACE: report.fill_section(), report.get_status(), "
        "report.get_section_context(), report.get_writing_guidance(), and "
        "fill_parallel() are available.\n\n"
    )


def build_system_prompt(
    *,
    hints: list[str] | None = None,
    variables: dict[str, str] | None = None,
    prohibited: list[str] | None = None,
    external_system_prompt: str = "",
    constitution: ConstitutionManifest | None = None,
    max_iterations: int | None = None,
    scratchpad_enabled: bool = False,
    enabled_subcalls: set[str] | frozenset[str] | None = None,
    template_enabled: bool = False,
) -> str:
    """Assemble the system prompt from the declared runtime capabilities."""
    external = external_system_prompt.rstrip() + "\n\n" if external_system_prompt else ""
    constitution_section = build_constitution_section(constitution)
    if constitution_section:
        constitution_section = "\n" + constitution_section + "\n"
    return (
        _SYSTEM_PROMPT.format(
            external_system_prompt=external,
            iteration_budget_section=_iteration_budget_section(max_iterations),
            workflow_section=_workflow_section(template_enabled),
            scratchpad_section=_scratchpad_section(scratchpad_enabled),
            subcall_section=_subcall_section(enabled_subcalls),
            template_section=_template_section(template_enabled),
            prohibited_section=_optional_list_section("You MUST NOT", prohibited),
            hints_section=_optional_list_section("Suggested approach", hints),
            variables_section=_variables_section(variables),
        )
        + constitution_section
    )


def format_code_preview(code: str) -> str:
    """Format the first executable statement for the progress log."""
    first_line = code.strip().split("\n")[0]
    if "extract(" not in first_line:
        return first_line[:80]
    match = re.search(r"fields\s*=\s*\[([^\]]*)\]", code, re.DOTALL)
    if match is None:
        return first_line[:80]
    field_names = re.findall(r'["\']([^"\']+)["\']', match.group(1))
    fields_str = ", ".join(field_names)
    var_match = re.match(r"(\w+)\s*=\s*extract\((\w+)", first_line)
    if var_match is not None:
        return f"{var_match.group(1)} = extract({var_match.group(2)}, [{fields_str}])"
    return f"extract(..., [{fields_str}])"


def make_final_var(
    repl: ReplEnvironment,
    *,
    output_commit_required: bool = False,
) -> Callable[[Any], str]:
    """Create the explicit final-value command bound to one REPL."""

    def final_var(value: Any) -> str:
        if output_commit_required:
            return "FINAL_VAR ignored: this harness requires COMMIT_OUTPUT() after the final artifact write."
        repl.final_value = value
        repl.final_called = True
        return f"FINAL_VAR set: {type(value).__name__}"

    return final_var


def make_show_vars(repl: ReplEnvironment) -> Callable[[], list[str]]:
    """Create the variable-listing command bound to one REPL."""

    def show_vars() -> list[str]:
        return sorted(repl.list_variables().keys())

    return show_vars


def enabled_subcall_names(configs: dict[str, SubcallConfig] | None) -> set[str]:
    """Return configured sub-call names that the runtime can inject."""
    return {name for name, config in (configs or {}).items() if config.enabled and name in _KNOWN_SUBCALL_NAMES}


def build_repl_tool_description(
    *,
    max_iterations: int,
    scratchpad_enabled: bool,
    enabled_subcalls: set[str] | frozenset[str],
    template_enabled: bool,
    output_commit_enabled: bool,
    advisor_enabled: bool = False,
) -> str:
    """Describe only the commands injected into this REPL execution."""
    completion_command = (
        "COMMIT_OUTPUT() binds and finishes the declared output; FINAL_VAR() cannot finish this run"
        if output_commit_enabled
        else "FINAL_VAR(value) declares the final result"
    )
    parts = [
        "Execute standard Python in a persistent REPL. Variables persist across calls. "
        f"The hard iteration budget is {max_iterations} model turns. "
        "Use print(HELP()) to print the exact command surface. "
        f"Core commands: SHOW_VARS(), grep(), parallel(), SUBCALL_LOG, and {completion_command}. "
    ]
    if scratchpad_enabled:
        parts.append("Scratchpad commands: NOTE(key, value) and RECALL(key). ")
    if enabled_subcalls:
        names = ", ".join(f"{name}()" for name in sorted(enabled_subcalls))
        parts.append(f"Enabled sub-calls: {names}. ")
    if template_enabled:
        parts.append("Template commands: report.fill_section(), report.get_status(), and fill_parallel(). ")
    if advisor_enabled:
        parts.append("Advisor command: ADVISOR(goal=..., problem=..., attempt=...). ")
    return "".join(parts).strip()


def iteration_budget_warning(
    *,
    iteration: int,
    max_iterations: int,
    output_path: str,
    output_commit_enabled: bool,
) -> str | None:
    """Return the one-time finalization warning once 80% of turns are consumed."""
    warning_turn = max(1, (max_iterations * 4 + 4) // 5)
    if iteration < warning_turn:
        return None
    consumed_percent = round(iteration / max_iterations * 100)
    remaining = max_iterations - iteration
    remaining_label = "turn remains" if remaining == 1 else "turns remain"
    if output_commit_enabled:
        finalization = (
            f"Stop exploration now. Write and validate {output_path}, then call "
            "COMMIT_OUTPUT() to bind the exact artifact. The hard cap will not "
            "auto-commit it."
        )
    else:
        finalization = (
            f"Stop exploration now. Produce the declared result at {output_path} "
            "when applicable, verify it, and call FINAL_VAR(...) explicitly."
        )
    return (
        "\n\n[Iteration budget warning] "
        f"{iteration}/{max_iterations} model turns consumed ({consumed_percent}%); "
        f"{remaining} {remaining_label}. {finalization}"
    )


def make_help(
    enabled_subcalls: set[str] | None = None,
    *,
    output_commit_enabled: bool = False,
    scratchpad_enabled: bool = False,
    template_enabled: bool = False,
    advisor_enabled: bool = False,
    max_iterations: int | None = None,
) -> Callable[[], str]:
    """Create a HELP command listing only injected runtime capabilities."""
    enabled = set(enabled_subcalls or ())

    def help_fn() -> str:
        completion_commands = (
            "  COMMIT_OUTPUT() — bind the exact declared artifact and end the task\n"
            "  FINAL_VAR(value) — unavailable; this harness requires COMMIT_OUTPUT()\n"
            if output_commit_enabled
            else "  FINAL_VAR(value) — declare the final output and end the task\n"
        )
        budget_line = (
            f"ITERATION BUDGET: {max_iterations} model turns (hard cap)\n\n" if max_iterations is not None else ""
        )
        parts = [
            "Available REPL commands:\n\n" + budget_line + "CORE:\n"
            "  print(HELP()) — print this exact command surface\n"
            "  SHOW_VARS() — list all REPL variables with types and sizes\n"
            + completion_commands
            + "  grep(text, pattern, context=3) — search text for regex, returns matching lines\n"
            "  SUBCALL_LOG — history of all sub-call invocations\n"
            "    .all() → list[dict]  |  .last(n) → list  |  .by_type(name) → list\n",
        ]
        if scratchpad_enabled:
            parts.append(
                "\nSCRATCHPAD:\n"
                "  NOTE(key, value) — persist data to scratchpad (survives compaction)\n"
                "  RECALL(key) → str — retrieve from scratchpad (no args = list all keys)\n"
            )
        subcall_lines = [_SUBCALL_HELP[name] for name in _SUBCALL_HELP if name in enabled]
        if subcall_lines:
            parts.append("\nSUB-CALLS (use an LLM to process data):\n" + "".join(subcall_lines))
        if advisor_enabled:
            parts.append("\nADVISOR:\n" + _SUBCALL_HELP["advisor"])
        parts.append(
            "\nPARALLEL EXECUTION:\n"
            "  results = parallel([lambda: fn1(), lambda: fn2(), ...])\n"
            "    Run callables concurrently. Returns results in input order.\n"
            "    Failed items are ParallelError(index, error) — check with isinstance().\n"
        )
        if template_enabled:
            parts.append(
                "  fill_parallel(generator, section_ids=None)\n"
                "    Fill unlocked template sections in parallel.\n"
                "    generator(section_id, context, guidance) → dict of field values.\n"
                "\nREPORT TEMPLATE:\n"
                "  report.fill_section(section_id, content_dict) → str\n"
                "    Returns a message string. Check for errors by reading the return value.\n"
                "  report.get_status() → TemplateStatus\n"
                "    .total_sections, .completed_sections, .unlocked, .pending, .completed\n"
                "  report.get_section_context(section_id) → dict\n"
                "  report.get_writing_guidance(section_id) → list[str]\n"
                "  report.get_dependencies(section_id) → list[str]\n"
                "  report.submit() → str — submit the completed report\n"
            )
        return "".join(parts)

    return help_fn


def build_var_summary(repl: ReplEnvironment) -> dict[str, str]:
    """Build a type-hint summary of current REPL variables."""
    summary: dict[str, str] = {}
    for name, type_name in repl.list_variables().items():
        value = repl.get_variable(name)
        if value is None:
            summary[name] = "None"
        elif isinstance(value, str):
            summary[name] = f"str({len(value):,})"
        elif isinstance(value, dict):
            summary[name] = f"dict({len(value)})"
        elif isinstance(value, list | tuple):
            summary[name] = f"list({len(value)})"
        else:
            summary[name] = type_name
    return summary
