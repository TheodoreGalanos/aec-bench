# ABOUTME: PydanticAI-based RLM REPL script for multi-provider container execution.
# ABOUTME: Uses PydanticAI for provider routing and tool protocol, RLM logic is ours.

# DEPRECATED: This file is superseded by agents/entrypoint_agent.py (EntrypointAgent).
# It uses inline scripts instead of the library adapter layer. Kept for rollback
# safety during the transition. Will be removed in a future cleanup pass.


def build_rlm_script() -> str:
    """Return the PydanticAI RLM REPL script for container execution."""
    return _RLM_SCRIPT


_RLM_SCRIPT = r"""
import io
import json
import logging
import os
import sys
import time
import tomllib
import traceback

# Enable logging so PydanticAI retries and provider errors are visible
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stderr,
)

from pydantic_ai import Agent, RunContext
from pydantic_ai.usage import UsageLimits
from trajectory_writer import TrajectoryWriter

# ===== CONFIG =====

model_name = os.environ.get("AGENT_MODEL", "")
instruction = os.environ.get("AGENT_INSTRUCTION", "")
max_iterations = 100
token_budget = 500_000
max_output_chars = 2000

if not instruction:
    print("FATAL: AGENT_INSTRUCTION not set", file=sys.stderr)
    sys.exit(1)

system_prompt_text = ""
if os.path.exists("/workspace/system_prompt.md"):
    with open("/workspace/system_prompt.md") as _sp:
        system_prompt_text = _sp.read().strip()

# Append SME notes if present
_notes_path = "/workspace/notes.md"
if os.path.exists(_notes_path):
    with open(_notes_path) as _nf:
        _notes = _nf.read().strip()
    if _notes and not _notes.startswith("<!--"):
        system_prompt_text += f"\n\n## Project-Specific Instructions\n\n{_notes}\n\nApply these instructions throughout the proposal."

# Load rlm.toml if present
rlm_config = {}
hints = []
_execution = {}
_scaffolding_enabled = True
if os.path.exists("/workspace/rlm.toml"):
    with open("/workspace/rlm.toml", "rb") as f:
        rlm_config = tomllib.load(f)
    guardrails = rlm_config.get("guardrails", {})
    max_iterations = guardrails.get("max_iterations", max_iterations)
    token_budget = guardrails.get("token_budget", token_budget)
    hints = rlm_config.get("hints", {}).get("phases", [])
    _execution = rlm_config.get("execution", {})
    _scaffolding_enabled = _execution.get("scaffolding", True)

# Load report template if referenced
template_sections = []
template_deps = {}
template_guidance = {}
template_def = rlm_config.get("template", {}).get("definition", "")
if template_def:
    template_path = f"/workspace/{template_def}"
    if os.path.exists(template_path):
        with open(template_path, "rb") as f:
            tpl_data = tomllib.load(f)
        for sec in tpl_data.get("sections", []):
            sid = sec["id"]
            template_sections.append(sid)
            template_deps[sid] = sec.get("depends_on", [])
            template_guidance[sid] = sec.get("writing_guidance", [])

# ===== PROVIDER SETUP (PydanticAI handles everything) =====

_azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
_azure_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
_azure_api_version = os.environ.get("AZURE_OPENAI_API_VERSION",
                                     os.environ.get("AGENT_API_VERSION", "2024-10-21"))
_bedrock_token = os.environ.get("AWS_BEARER_TOKEN_BEDROCK", "")
_aws_region = os.environ.get("AWS_REGION", "") or os.environ.get("AWS_DEFAULT_REGION", "")

# Detect provider from MODEL NAME first (disambiguates when multiple
# provider credentials are present in the environment).
_model_lower = model_name.lower()
_is_bedrock_model = any(
    _model_lower.startswith(p) for p in (
        "anthropic.claude", "au.anthropic.", "us.anthropic.",
        "eu.anthropic.", "ap.anthropic.", "amazon.", "us.amazon.",
        "meta.llama", "us.meta.", "mistral.", "us.mistral.",
        "cohere.", "us.cohere.", "ai21.", "us.ai21.",
    )
)
_is_azure_model = any(
    _model_lower.startswith(p) for p in ("gpt-", "gpt4", "o1-", "o3-", "o4-")
)

if _is_bedrock_model and (_bedrock_token or _aws_region):
    from pydantic_ai.models.bedrock import BedrockConverseModel
    from pydantic_ai.providers.bedrock import BedrockProvider
    provider_kwargs = {}
    if _aws_region:
        provider_kwargs["region_name"] = _aws_region
    _model = BedrockConverseModel(model_name, provider=BedrockProvider(**provider_kwargs))
    print(f"Provider: Bedrock ({_aws_region or 'default region'})", file=sys.stderr)
elif _is_azure_model and _azure_endpoint and _azure_key:
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.azure import AzureProvider
    _model = OpenAIChatModel(
        model_name,
        provider=AzureProvider(
            azure_endpoint=_azure_endpoint,
            api_version=_azure_api_version,
            api_key=_azure_key,
        ),
    )
    print(f"Provider: Azure OpenAI ({_azure_endpoint})", file=sys.stderr)
elif _azure_endpoint and _azure_key:
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.azure import AzureProvider
    _model = OpenAIChatModel(
        model_name,
        provider=AzureProvider(
            azure_endpoint=_azure_endpoint,
            api_version=_azure_api_version,
            api_key=_azure_key,
        ),
    )
    print(f"Provider: Azure OpenAI ({_azure_endpoint})", file=sys.stderr)
elif _bedrock_token or _aws_region:
    from pydantic_ai.models.bedrock import BedrockConverseModel
    from pydantic_ai.providers.bedrock import BedrockProvider
    provider_kwargs = {}
    if _aws_region:
        provider_kwargs["region_name"] = _aws_region
    _model = BedrockConverseModel(model_name, provider=BedrockProvider(**provider_kwargs))
    print(f"Provider: Bedrock ({_aws_region or 'default region'})", file=sys.stderr)
else:
    _model = model_name  # PydanticAI infers from model string
    print(f"Provider: auto ({model_name})", file=sys.stderr)


# ===== REPL STATE =====

class ReplState:
    # Persistent REPL state carried across tool calls.
    def __init__(self, max_chars=2000):
        self._globals = {"__builtins__": __builtins__}
        self._max = max_chars
        self._vars = set()
        self._protected = set()
        self.final_value = None
        self.final_called = False

    def execute(self, code):
        capture = io.StringIO()
        old = sys.stdout
        before = set(self._globals.keys())
        try:
            sys.stdout = capture
            exec(code, self._globals)
            sys.stdout = old
            raw = capture.getvalue()
            new = list(set(self._globals.keys()) - before)
            self._vars.update(new)
            out = raw if len(raw) <= self._max else raw[:self._max] + "\n...[truncated]...\n"
            return out, None
        except Exception:
            sys.stdout = old
            return capture.getvalue(), traceback.format_exc()

    def inject(self, name, obj, protected=False):
        self._globals[name] = obj
        self._vars.add(name)
        if protected:
            self._protected.add(name)

    def restore_protected(self, scaffolds):
        for name, obj in scaffolds.items():
            self._globals[name] = obj

    def var_names(self):
        return [n for n in sorted(self._vars)
                if n in self._globals and n not in self._protected]

    def snapshot(self, max_repr=200):
        result = {}
        for n in sorted(self._vars):
            if n not in self._globals or n in self._protected:
                continue
            v = self._globals[n]
            if v is None or isinstance(v, (bool, int, float, str)):
                result[n] = v
            elif isinstance(v, dict):
                try:
                    json.dumps(v)
                    result[n] = v
                except (TypeError, ValueError, OverflowError):
                    result[n] = repr(v)[:max_repr]
            elif isinstance(v, (list, tuple)):
                try:
                    json.dumps(v)
                    result[n] = list(v)
                except (TypeError, ValueError, OverflowError):
                    result[n] = repr(v)[:max_repr]
            else:
                result[n] = repr(v)[:max_repr]
        return result


# ===== TEMPLATE =====

class Template:
    def __init__(self, section_ids, deps, guidance):
        self._ids = section_ids
        self._deps = deps
        self._guidance = guidance
        self._filled = {}

    def fill_section(self, sid, content):
        if sid not in self._ids:
            return f"ERROR: Unknown section '{sid}'. Valid: {', '.join(self._ids)}"
        missing = [d for d in self._deps.get(sid, []) if d not in self._filled]
        if missing:
            return f"ERROR: Section '{sid}' depends on unfilled: {', '.join(missing)}"
        self._filled[sid] = dict(content)
        filled = len(self._filled)
        return f"OK: Section '{sid}' filled ({filled}/{len(self._ids)} complete)"

    def get_status(self):
        completed = list(self._filled.keys())
        pending = [s for s in self._ids if s not in self._filled]
        unlocked = [s for s in self._ids
                     if s not in self._filled and all(d in self._filled for d in self._deps.get(s, []))]
        return {"total": len(self._ids), "completed": len(completed),
                "unlocked": unlocked, "pending": pending}

    def get_context(self, sid):
        return {d: self._filled[d] for d in self._deps.get(sid, []) if d in self._filled}

    def get_guidance(self, sid):
        return self._guidance.get(sid, [])

    def submit(self):
        gaps = [s for s in self._ids if s not in self._filled]
        return {"complete": len(gaps) == 0, "sections": dict(self._filled), "gaps": gaps}

    def __getattr__(self, name):
        suggestions = {
            "get_section_context": "Use CONTEXT(section_id) instead of report.get_section_context()",
            "section_context": "Use CONTEXT(section_id) instead of report.section_context",
            "completed_sections": "Use STATUS() to see completed sections",
            "total_sections": "Use STATUS() to see total sections",
            "sections": "Use SUBMIT() to get all sections, or STATUS() to see progress",
            "complete": "Use STATUS() to check completion, or SUBMIT() to finalise",
            "gaps": "Use STATUS() to see pending sections",
            "unlocked": "Use STATUS() to see unlocked sections",
            "pending": "Use STATUS() to see pending sections",
            "fill": "Use FILL(section_id, content_dict) instead of report.fill()",
            "status": "Use STATUS() instead of report.status",
            "guidance": "Use GUIDANCE(section_id) instead of report.guidance",
        }
        hint = suggestions.get(name, f"Use HELP() to see available commands")
        raise AttributeError(f"'Template' has no attribute '{name}'. {hint}")


# ===== SETUP =====

repl = ReplState(max_chars=max_output_chars)
traj = TrajectoryWriter()

# FINAL_VAR callable
def _final_var(value):
    repl.final_value = value
    repl.final_called = True
    return f"FINAL_VAR set: {type(value).__name__}"

# Sub-call log — captures prompts and responses for trajectory visibility
_subcall_log = []
_subcall_token_total = [0]  # mutable counter, accumulated in repl_tool
_turn_metrics = {}  # written by main loop, read by repl_tool for trajectory

# llm_query callable — uses a separate PydanticAI agent for sub-calls
def _llm_query(prompt):
    print(f"[subcall] llm_query: {len(prompt)} chars", file=sys.stderr)
    sub = Agent(_model, system_prompt="You are a helpful assistant.")
    result = sub.run_sync(prompt)
    print(f"[subcall] llm_query done: {result.usage().input_tokens}in/{result.usage().output_tokens}out", file=sys.stderr)
    _subcall_log.append({
        "type": "llm_query",
        "prompt": prompt[:2000],
        "response": result.output[:2000] if isinstance(result.output, str) else str(result.output)[:2000],
        "input_tokens": result.usage().input_tokens if result.usage() else 0,
        "output_tokens": result.usage().output_tokens if result.usage() else 0,
    })
    return result.output

# extract() — structured field extraction via sub-LLM call
def _extract(text, fields, context=None):
    ctx_line = f"\nContext: {context}" if context else ""
    prompt = (
        "Extract the following fields from the text below and return them as a JSON object.\n"
        f"Fields: {', '.join(fields)}{ctx_line}\n\nText:\n{text[:8000]}\n\n"
        "Return ONLY a valid JSON object, no explanation."
    )
    print(f"[subcall] extract: {len(text)} chars, fields={fields}", file=sys.stderr)
    sub = Agent(_model, system_prompt="You are a precise data extraction assistant. Return only JSON.")
    result = sub.run_sync(prompt)
    print(f"[subcall] extract done: {result.usage().input_tokens}in/{result.usage().output_tokens}out", file=sys.stderr)
    resp = result.output
    _subcall_log.append({
        "type": "extract",
        "fields": fields,
        "context": context,
        "text_length": len(text),
        "response_preview": resp[:500] if isinstance(resp, str) else str(resp)[:500],
        "input_tokens": result.usage().input_tokens if result.usage() else 0,
        "output_tokens": result.usage().output_tokens if result.usage() else 0,
    })
    import re as _re
    json_match = _re.findall(r'```(?:json)?\s*\n(.*?)```', resp, _re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match[-1])
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(resp)
    except json.JSONDecodeError:
        return {"_raw": resp[:500], "_error": "Failed to parse JSON"}

# summarise() — compress text to key points via sub-LLM call
def _summarise(text, max_points=10, focus=None):
    focus_line = f" Focus on: {focus}." if focus else ""
    prompt = (
        f"Summarise the following text into at most {max_points} key points.{focus_line}\n"
        "Return a concise bullet list — facts, numbers, and names only. No preamble.\n\n"
        f"Text:\n{text[:8000]}"
    )
    print(f"[subcall] summarise: {len(text)} chars, focus={focus}", file=sys.stderr)
    sub = Agent(_model, system_prompt="You are a concise summarisation assistant.")
    result = sub.run_sync(prompt)
    print(f"[subcall] summarise done: {result.usage().input_tokens}in/{result.usage().output_tokens}out", file=sys.stderr)
    _subcall_log.append({
        "type": "summarise",
        "focus": focus,
        "text_length": len(text),
        "max_points": max_points,
        "response_preview": result.output[:500] if isinstance(result.output, str) else str(result.output)[:500],
        "input_tokens": result.usage().input_tokens if result.usage() else 0,
        "output_tokens": result.usage().output_tokens if result.usage() else 0,
    })
    return result.output

# NOTE() / RECALL() — persistent scratchpad for RLM working memory.
# Survives context trimming because it reads/writes a file, not conversation history.
_SCRATCHPAD_PATH = "/workspace/.scratchpad.json"

def _note(key, value):
    notes = {}
    if os.path.exists(_SCRATCHPAD_PATH):
        with open(_SCRATCHPAD_PATH) as f:
            try:
                notes = json.load(f)
            except json.JSONDecodeError:
                notes = {}
    notes[key] = value
    with open(_SCRATCHPAD_PATH, "w") as f:
        json.dump(notes, f, indent=2, default=str)
    return f"Noted: {key} ({type(value).__name__})"

def _recall(key=None):
    if not os.path.exists(_SCRATCHPAD_PATH):
        return "Scratchpad is empty. Use NOTE(key, value) to store data."
    with open(_SCRATCHPAD_PATH) as f:
        try:
            notes = json.load(f)
        except json.JSONDecodeError:
            return "Scratchpad is empty."
    if not notes:
        return "Scratchpad is empty."
    if key is None:
        lines = ["Scratchpad contents:"]
        for k, v in notes.items():
            preview = str(v)[:150]
            if len(str(v)) > 150:
                preview += "..."
            lines.append(f"  {k}: {preview}")
        return "\n".join(lines)
    if key not in notes:
        return f"No note found for '{key}'. Available: {', '.join(notes.keys())}"
    return notes[key]

def _show_vars():
    return repl.var_names()

# Inject scaffolds into REPL
repl.inject("context", instruction, protected=True)
repl.inject("FINAL_VAR", _final_var, protected=True)
repl.inject("FINAL", _final_var, protected=True)
repl.inject("llm_query", _llm_query, protected=True)
repl.inject("extract", _extract)
repl.inject("summarise", _summarise)
repl.inject("NOTE", _note)
repl.inject("RECALL", _recall)
repl.inject("SHOW_VARS", _show_vars, protected=True)
repl.inject("history", "", protected=True)

_scaffolds = {
    "context": instruction, "FINAL_VAR": _final_var, "FINAL": _final_var,
    "llm_query": _llm_query, "extract": _extract, "summarise": _summarise,
    "NOTE": _note, "RECALL": _recall, "SHOW_VARS": _show_vars, "history": "",
}

# Template — only inject report object when scaffolding is enabled
report = None
if template_sections and _scaffolding_enabled:
    report = Template(template_sections, template_deps, template_guidance)
    repl.inject("report", report, protected=True)
    _scaffolds["report"] = report

# Load REPL commands if scaffolding is enabled and file exists
_repl_commands_path = "/workspace/repl_commands.py"
if _scaffolding_enabled and os.path.exists(_repl_commands_path):
    import importlib.util
    _spec = importlib.util.spec_from_file_location("repl_commands", _repl_commands_path)
    _repl_mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_repl_mod)
    if hasattr(_repl_mod, "init_commands"):
        _tpl_data = {}
        _val_data = {}
        if os.path.exists("/workspace/report_template.toml"):
            with open("/workspace/report_template.toml", "rb") as _f:
                _tpl_data = tomllib.load(_f)
        if os.path.exists("/workspace/validation_rules.toml"):
            with open("/workspace/validation_rules.toml", "rb") as _f:
                _val_data = tomllib.load(_f)
        _repl_mod.init_commands(repl, report, _tpl_data, _val_data, workspace=os.path.dirname(_repl_commands_path))
        print("REPL commands loaded from /workspace/repl_commands.py", file=sys.stderr)
elif not _scaffolding_enabled:
    print("Scaffolding disabled — REPL commands not loaded", file=sys.stderr)

# Build system prompt
sys_parts = []
if system_prompt_text:
    sys_parts.append(system_prompt_text)

sys_parts.append(
    "You are an RLM (Recursive Language Model) agent with a persistent Python REPL.\n\n"
    "How you work:\n"
    "- Your REPL variables persist across turns, but your conversation history may be compacted.\n"
    "- Store everything you need in variables. Use NOTE(key, value) to persist data to the scratchpad.\n"
    "- Type HELP() to discover all available commands and tools.\n"
    "- Start by reading your task: print(context)\n\n"
    "Working pattern:\n"
    "1. Read source material and extract structured data into variables\n"
    "2. Use extract() and summarise() to compress documents into reusable facts\n"
    "3. Use NOTE() to persist extracted data to the scratchpad after each extraction\n"
    "4. Compose each output section using llm_query() with your stored variables as input\n"
    "5. Call FINAL_VAR(result) when done\n\n"
    "IMPORTANT — Compose, do not write from memory:\n"
    "When creating output sections, ALWAYS pass your extracted data explicitly to llm_query().\n"
    "Do NOT write section text as literal strings from memory — the data may be wrong or stale.\n\n"
    "Example of the correct pattern:\n"
    "  facts = extract(doc, ['name', 'location', 'scope'])\n"
    "  NOTE('brief_facts', facts)  # persist to scratchpad\n"
    "  section = llm_query(f'Write Background section using: {facts}')\n\n"
    "Persistent memory:\n"
    "  NOTE(key, value) — save data to scratchpad (survives context compaction)\n"
    "  RECALL(key) — retrieve data from scratchpad (RECALL() with no args lists all keys)\n"
    "  Use NOTE after every extract() call to persist the results.\n"
    "  Use RECALL when you need data from earlier turns.\n\n"
    "Key principle: Your scratchpad IS your memory. NOTE important data, RECALL when needed."
)

if hints:
    sys_parts.append("Suggested approach:\n" + "\n".join(f"- {h}" for h in hints))

full_system = "\n\n".join(sys_parts)


# ===== COMPACTION CONFIG =====
_compaction_threshold_pct = _execution.get("compaction_threshold_pct", 0.85)
_hard_ceiling_pct = _execution.get("hard_ceiling_pct", 0.95)
_compaction_model_name = _execution.get("compaction_model", None)
_context_limit = _execution.get("context_limit", 1_000_000)
_compaction_threshold = int(_context_limit * _compaction_threshold_pct)
_hard_ceiling = int(_context_limit * _hard_ceiling_pct)


# ===== PYDANTIC AI AGENT =====

# Enable prompt caching — system prompt, tool schema, and conversation prefix.
# Cache slides forward each turn: only new tokens pay 1.25x write, entire
# prefix from previous turn is a cache read at 0.1x (85-90% saving per turn).
_agent_settings = {}
if _is_bedrock_model:
    from pydantic_ai.models.bedrock import BedrockModelSettings
    _agent_settings = BedrockModelSettings(
        bedrock_cache_instructions=True,
        bedrock_cache_tool_definitions=True,
        bedrock_cache_messages=True,
    )
elif not _is_azure_model:
    # Direct Anthropic API
    try:
        from pydantic_ai.models.anthropic import AnthropicModelSettings
        _agent_settings = AnthropicModelSettings(
            anthropic_cache_instructions=True,
            anthropic_cache_tool_definitions=True,
            anthropic_cache_messages=True,
        )
    except ImportError:
        pass

rlm_agent = Agent(
    _model,
    system_prompt=full_system,
    retries=2,
    model_settings=_agent_settings if _agent_settings else None,
)


# ===== PROGRESSIVE SCAFFOLDING =====
_compacted = False
_first_post_compaction = True
_turns_since_progress = 0
_last_completed_count = 0


def _build_footer():
    '''Progressive scaffolding footer (Option C: quiet then active).'''
    global _first_post_compaction
    if not _scaffolding_enabled or not report:
        return ""
    try:
        st = report.get_status()
    except Exception:
        return ""
    completed = st.get("completed", 0) if isinstance(st, dict) else 0
    total = st.get("total", 0) if isinstance(st, dict) else 0
    unlocked = st.get("unlocked", []) if isinstance(st, dict) else []
    next_sec = unlocked[0] if unlocked else None
    # Read scratchpad keys
    sp_keys = []
    if os.path.exists(_SCRATCHPAD_PATH):
        try:
            with open(_SCRATCHPAD_PATH) as _sf:
                sp_keys = list(json.load(_sf).keys())
        except (json.JSONDecodeError, OSError):
            pass
    if _compacted:
        lines = ["\n---"]
        if _first_post_compaction:
            lines.append("[Context was compacted. Your conversation history has been summarised.]")
            _first_post_compaction = False
        lines.append(f"[Template progress: {completed}/{total} sections filled]")
        if sp_keys:
            lines.append(f"[Scratchpad has {len(sp_keys)} keys — use RECALL() to retrieve extracted data]")
        if next_sec:
            lines.append(f"[Next unlocked: '{next_sec}'. Use START('{next_sec}') for guidance.]")
        return "\n".join(lines)
    if _turns_since_progress >= 3 and next_sec:
        return f"\n---\n[Hint: '{next_sec}' is unlocked. Use START('{next_sec}') to continue.]"
    if completed > 0:
        return f"\n---\n[{completed}/{total} sections filled]"
    return ""


_prev_var_names = [set()]  # mutable, tracks previous step variable names
_last_repl_info = {"code": "", "new_vars": [], "subcalls": []}  # last repl execution info for stderr

@rlm_agent.tool_plain
def repl_tool(code: str) -> str:
    '''Execute Python code in a persistent REPL. Variables persist across calls.

    Available variables: `context` (your task), `llm_query(prompt)` (sub-LLM call),
    `FINAL_VAR(value)` (declare final answer), `SHOW_VARS()` (list variables).

    Args:
        code: Python code to execute in the persistent REPL.
    '''
    # Clear sub-call log for this step
    step_subcalls = list(_subcall_log)
    _subcall_log.clear()

    stdout, error = repl.execute(code)
    repl.restore_protected(_scaffolds)

    # Capture any sub-calls made during execution
    step_subcalls.extend(_subcall_log)
    _subcall_log.clear()

    # Accumulate sub-call tokens for budget tracking
    for sc in step_subcalls:
        _subcall_token_total[0] += sc.get("input_tokens", 0) + sc.get("output_tokens", 0)

    # Build result
    parts = []
    if stdout:
        parts.append(stdout)
    if error:
        parts.append(error)
        print(f"REPL error: {error.strip().splitlines()[-1]}", file=sys.stderr)
    var_names = repl.var_names()
    if var_names:
        parts.append(f"REPL variables: {var_names}")
    exec_result = "\n\n".join(parts) if parts else "No output"

    # Compute variable diff
    current_vars = set(var_names) if var_names else set()
    new_vars = list(current_vars - _prev_var_names[0])
    removed_vars = list(_prev_var_names[0] - current_vars)
    _prev_var_names[0] = current_vars

    # Update last repl info for stderr logging
    _code_preview = code.strip().split("\n")[0][:80]
    _sc_types = [sc.get("type", "?") for sc in step_subcalls]
    _last_repl_info["code"] = _code_preview
    _last_repl_info["new_vars"] = new_vars
    _last_repl_info["subcalls"] = _sc_types

    # Read scratchpad state
    scratchpad_keys = []
    if os.path.exists(_SCRATCHPAD_PATH):
        try:
            with open(_SCRATCHPAD_PATH) as _sf:
                scratchpad_keys = list(json.load(_sf).keys())
        except (json.JSONDecodeError, OSError):
            pass

    # Log to trajectory — each REPL call is its own step
    traj.new_step()
    traj.tool_call("repl", code)
    traj_out = exec_result

    # Build step metadata as a structured dict
    step_meta = {
        "var_diff": {"new": new_vars, "removed": removed_vars},
        "scratchpad_keys": scratchpad_keys,
    }
    if step_subcalls:
        step_meta["subcalls"] = step_subcalls

    # Add template progress
    _tpl_progress = None
    if report:
        try:
            _st = report.get_status()
            _tpl_progress = {
                "completed": _st.get("completed", 0) if isinstance(_st, dict) else 0,
                "total": _st.get("total", 0) if isinstance(_st, dict) else 0,
                "filled": list(report._filled.keys()) if hasattr(report, "_filled") else [],
                "unlocked": _st.get("unlocked", []) if isinstance(_st, dict) else [],
            }
        except Exception:
            pass
    if _tpl_progress:
        step_meta["template_progress"] = _tpl_progress

    # Variable summary (name -> type hint string)
    var_summary = {}
    for _vn in (var_names or []):
        _vv = repl._globals.get(_vn)
        if _vv is None:
            var_summary[_vn] = "None"
        elif isinstance(_vv, str):
            var_summary[_vn] = f"str({len(_vv):,})"
        elif isinstance(_vv, dict):
            var_summary[_vn] = f"dict({len(_vv)})"
        elif isinstance(_vv, (list, tuple)):
            var_summary[_vn] = f"list({len(_vv)})"
        else:
            var_summary[_vn] = type(_vv).__name__
    step_meta["variables"] = var_summary

    # Per-turn token/cost metrics from the main loop
    if _turn_metrics:
        step_meta["tokens"] = dict(_turn_metrics)

    traj.tool_result("repl", stdout=traj_out, metadata=step_meta)

    # Append progressive scaffolding footer
    footer = _build_footer()
    return exec_result + footer


# ===== COMPACTION =====
async def _compact(repl_state):
    '''Build structured compaction input and ask a sub-LLM to summarise.'''
    variables = repl_state.snapshot()
    sp = {}
    if os.path.exists(_SCRATCHPAD_PATH):
        try:
            with open(_SCRATCHPAD_PATH) as f:
                sp = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    tpl_status = report.get_status() if report else None

    input_parts = [
        "Summarise the agent's progress so far. Produce a structured summary with:",
        "1. Documents read — what was read, key facts",
        "2. Extracted data — variable name, contents, importance",
        "3. Work completed — sections filled, key content",
        "4. Work remaining — unfilled sections, dependencies",
        "5. Approach taken — strategies chosen",
        "6. Known issues — errors, dead ends",
        "",
        "--- Agent State ---",
    ]
    if variables:
        input_parts.append(f"Variables: {json.dumps(variables, indent=2, default=str)}")
    if sp:
        input_parts.append(f"Scratchpad: {json.dumps(sp, indent=2, default=str)}")
    if tpl_status:
        input_parts.append(f"Template status: {json.dumps(tpl_status, default=str)}")
    prompt = "\n".join(input_parts)

    # Build compaction model — reuse the same provider setup as the main agent
    if _compaction_model_name:
        _cm_lower = _compaction_model_name.lower()
        _cm_is_bedrock = any(
            _cm_lower.startswith(p) for p in (
                "anthropic.", "au.anthropic.", "us.anthropic.",
                "eu.anthropic.", "ap.anthropic.", "amazon.",
            )
        )
        if _cm_is_bedrock and (_bedrock_token or _aws_region):
            from pydantic_ai.models.bedrock import BedrockConverseModel as _BCM
            from pydantic_ai.providers.bedrock import BedrockProvider as _BP
            _bp_kwargs = {}
            if _aws_region:
                _bp_kwargs["region_name"] = _aws_region
            compact_model = _BCM(_compaction_model_name, provider=_BP(**_bp_kwargs))
        else:
            compact_model = _compaction_model_name
    else:
        compact_model = _model
    compact_agent = Agent(compact_model, system_prompt="You summarise AI agent work sessions concisely.")
    result = await compact_agent.run(prompt)
    return result.output


# ===== RUN =====
import asyncio
from pydantic_graph import End

async def main():
    global _compacted, _first_post_compaction, _turns_since_progress, _last_completed_count

    history = []
    compaction_count = 0
    grand_total_tokens = 0  # running total across all iter() runs
    prev_run_input = 0  # previous cumulative input — for computing per-call delta
    turn = 0
    done = False
    final_run = None
    all_usage = None
    prompt = "Task loaded into `context` variable. Begin by reading it with the repl tool."

    traj.system(full_system)
    traj.user(prompt)

    while not done:
        try:
            async with rlm_agent.iter(
                prompt,
                message_history=history,
                usage_limits=UsageLimits(request_limit=max_iterations),
            ) as run:
                async for node in run:
                    if isinstance(node, End):
                        done = True
                        break

                    # Only log and check budgets after tool execution nodes,
                    # not after model request nodes (which just mean "LLM is thinking").
                    # CallToolsNode means the agent called a tool and we have results.
                    from pydantic_ai.agent import CallToolsNode
                    if not isinstance(node, CallToolsNode):
                        continue

                    turn += 1
                    all_usage = run.usage()

                    # Current run tokens (for compaction threshold check)
                    run_tokens = (all_usage.total_tokens if all_usage else 0) + _subcall_token_total[0]
                    # Per-call input tokens (this LLM call's context size)
                    run_input_cumulative = all_usage.input_tokens if all_usage else 0
                    call_input = run_input_cumulative - prev_run_input
                    prev_run_input = run_input_cumulative

                    # Track template progress for scaffolding
                    if report:
                        try:
                            st = report.get_status()
                            current_completed = st.get("completed", 0) if isinstance(st, dict) else 0
                        except Exception:
                            current_completed = _last_completed_count
                        if current_completed > _last_completed_count:
                            _turns_since_progress = 0
                            _last_completed_count = current_completed
                        else:
                            _turns_since_progress += 1

                    # Real-time stderr logging
                    filled = _last_completed_count
                    total_secs = 0
                    if report:
                        try:
                            total_secs = report.get_status().get("total", 0)
                        except Exception:
                            pass
                    var_count = len(repl.var_names())
                    # Cache metrics and cost estimate
                    cache_read = getattr(all_usage, "cache_read_tokens", 0) or 0
                    cache_write = getattr(all_usage, "cache_write_tokens", 0) or 0
                    out_tokens = all_usage.output_tokens if all_usage else 0
                    uncached_in = max((all_usage.input_tokens if all_usage else 0) - cache_read, 0)
                    # Cumulative cost estimate (Sonnet: $3/$15 in/out, $0.30/$3.75 cache r/w per MTok)
                    _cost = (
                        uncached_in * 3.0 / 1_000_000
                        + out_tokens * 15.0 / 1_000_000
                        + cache_read * 0.30 / 1_000_000
                        + cache_write * 3.75 / 1_000_000
                    )
                    _turn_metrics["call_input"] = call_input
                    _turn_metrics["cache_read"] = cache_read
                    _turn_metrics["cache_write"] = cache_write
                    _turn_metrics["cost_cumulative"] = round(_cost, 4)
                    _turn_metrics["grand_total"] = grand_total_tokens + run_tokens

                    cache_hint = ""
                    if cache_read > 0 or cache_write > 0:
                        cache_hint = f" cache: {cache_read:,}r/{cache_write:,}w |"
                    code_hint = _last_repl_info.get("code", "")
                    new_v = _last_repl_info.get("new_vars", [])
                    sc_types = _last_repl_info.get("subcalls", [])
                    extras = ""
                    if new_v:
                        extras += f" +{','.join(new_v)}"
                    if sc_types:
                        extras += f" [{','.join(sc_types)}]"
                    print(
                        f"[Turn {turn}] ${_cost:.2f} | "
                        f"ctx: {call_input:,} in |{cache_hint} "
                        f"{filled}/{total_secs} sections | "
                        f"vars: {var_count}{extras} | "
                        f"{code_hint}",
                        file=sys.stderr,
                    )

                    # Check compaction threshold (per-call context size, not cumulative)
                    if call_input > _compaction_threshold:
                        print(
                            f"\n{'=' * 60}\n"
                            f"[COMPACTION #{compaction_count + 1}] Context {call_input:,} tokens "
                            f"> threshold {_compaction_threshold:,} "
                            f"(total spent: {grand_total_tokens + run_tokens:,})\n"
                            f"{'=' * 60}",
                            file=sys.stderr,
                        )
                        # Show what we're sending to the compaction agent
                        sp_keys = []
                        if os.path.exists(_SCRATCHPAD_PATH):
                            try:
                                with open(_SCRATCHPAD_PATH) as _csf:
                                    sp_keys = list(json.load(_csf).keys())
                            except (json.JSONDecodeError, OSError):
                                pass
                        tpl_st = report.get_status() if report else {}
                        _c_filled = tpl_st.get("completed", 0) if isinstance(tpl_st, dict) else 0
                        _c_total = tpl_st.get("total", 0) if isinstance(tpl_st, dict) else 0
                        _c_vars = repl.var_names()
                        print(
                            f"  Sections: {_c_filled}/{_c_total} filled\n"
                            f"  Variables: {len(_c_vars)} ({', '.join(_c_vars[:10])}{'...' if len(_c_vars) > 10 else ''})\n"
                            f"  Scratchpad: {len(sp_keys)} keys ({', '.join(sp_keys[:8])}{'...' if len(sp_keys) > 8 else ''})\n"
                            f"  Compacting with: {_compaction_model_name or 'same model'}",
                            file=sys.stderr,
                        )
                        from pydantic_ai.messages import ModelRequest, UserPromptPart
                        messages = run.all_messages()
                        summary = await _compact(repl)
                        # Show compaction summary
                        print(
                            f"\n{'─' * 60}\n"
                            f"  COMPACTION SUMMARY ({len(summary):,} chars):\n"
                            f"{'─' * 60}",
                            file=sys.stderr,
                        )
                        for line in summary.strip().split("\n")[:20]:
                            print(f"  {line}", file=sys.stderr)
                        if summary.count("\n") > 20:
                            print(f"  ... ({summary.count(chr(10)) - 20} more lines)", file=sys.stderr)
                        print(f"{'─' * 60}", file=sys.stderr)
                        # Start fresh with just the summary — don't carry trailing
                        # messages as they may contain unprocessed tool calls that
                        # PydanticAI rejects when paired with a new user prompt.
                        history = [
                            ModelRequest(parts=[
                                UserPromptPart(content=f"[Progress Summary]\n{summary}")
                            ])
                        ]
                        grand_total_tokens += run_tokens  # accumulate before reset
                        compaction_count += 1
                        _compacted = True
                        _first_post_compaction = True
                        _subcall_token_total[0] = 0  # reset sub-call counter for new run
                        prev_run_input = 0  # reset per-call delta tracker
                        prompt = "Continue working on the task. Use RECALL() to retrieve your extracted data."
                        # Log compaction event to trajectory
                        traj.new_step()
                        traj.tool_result("compaction", stdout=f"Compacted {len(messages)} messages to summary ({len(summary):,} chars)", metadata={
                            "compaction": {
                                "number": compaction_count,
                                "pre_messages": len(messages),
                                "summary_chars": len(summary),
                                "model": str(_compaction_model_name or "same"),
                            }
                        })
                        print(
                            f"\n[COMPACTION #{compaction_count}] Complete. "
                            f"History: {len(messages)} msgs -> {len(history)} msgs. "
                            f"Restarting iter()...\n"
                            f"{'=' * 60}\n",
                            file=sys.stderr,
                        )
                        break  # restart iter() with compacted history

                    # Check hard ceiling (95%) — per-call context check
                    if call_input > _hard_ceiling:
                        grand_total_tokens += run_tokens
                        print(
                            f"[HARD CEILING] ctx: {call_input:,} > {_hard_ceiling:,} | "
                            f"total: {grand_total_tokens:,}. Forcing finalisation.",
                            file=sys.stderr,
                        )
                        done = True
                        break

            # If iter() ended naturally (End node or hard ceiling), done is
            # already True.  If we broke out for compaction, done is still
            # False and the while-loop should continue with the compacted
            # history — so we must NOT force done=True here.
            if done:
                final_run = run

        except Exception as e:
            print(f"Agent error: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            done = True

    return final_run, all_usage, compaction_count

try:
    _final_run, _final_usage, _compaction_count = asyncio.run(main())
    if _final_run and hasattr(_final_run, 'result') and _final_run.result:
        final_text = _final_run.result.output if isinstance(_final_run.result.output, str) else str(_final_run.result.output)
    else:
        final_text = ""
    usage = _final_usage
    status = "ok"
except Exception as e:
    final_text = f"Agent failed: {e}"
    usage = None
    status = "error"
    _compaction_count = 0
    print(f"Agent error: {e}", file=sys.stderr)
finally:
    traj.close()

# Write symbolic state
symbolic_state = repl.snapshot()
if symbolic_state:
    with open("/workspace/symbolic_state.json", "w") as f:
        json.dump(symbolic_state, f, indent=2, default=str)

# Output priority chain
_output_path = "/workspace/output.md"
_agent_wrote_output = os.path.exists(_output_path) and os.path.getsize(_output_path) > 0
_output_source = "none"

if _agent_wrote_output:
    _output_source = "direct_write"
    print("output.md written directly by agent — preserving", file=sys.stderr)
elif report:
    r = report.submit()
    if r.get("sections"):
        output_text = json.dumps(r, indent=2)
        with open(_output_path, "w") as f:
            f.write(output_text)
        _output_source = "template_submit"
    elif repl.final_called:
        fv = repl.final_value
        output_text = fv if isinstance(fv, str) else json.dumps(fv, indent=4, default=str)
        with open(_output_path, "w") as f:
            f.write(output_text)
        _output_source = "final_var"
    else:
        with open(_output_path, "w") as f:
            f.write(final_text or "")
        _output_source = "fallback"
elif repl.final_called:
    fv = repl.final_value
    if isinstance(fv, dict):
        output_text = "```json\n" + json.dumps(fv, indent=4, default=str) + "\n```\n"
    elif isinstance(fv, str):
        output_text = fv
    else:
        output_text = repr(fv)
    with open(_output_path, "w") as f:
        f.write(output_text)
    _output_source = "final_var"
else:
    with open(_output_path, "w") as f:
        f.write(final_text or "")
    _output_source = "fallback"

print(f"Output source: {_output_source}", file=sys.stderr)

# Conversation log
try:
    if status == "ok" and _final_run and hasattr(_final_run, 'result') and _final_run.result:
        msgs = _final_run.result.all_messages()
        with open("/workspace/conversation.jsonl", "w") as f:
            for msg in msgs:
                f.write(msg.model_dump_json() + "\n")
except Exception:
    pass

# Agent result
_cache_read = getattr(usage, "cache_read_tokens", 0) or 0 if usage else 0
_cache_write = getattr(usage, "cache_write_tokens", 0) or 0 if usage else 0
agent_result = {
    "status": status,
    "model": model_name,
    "input_tokens": usage.input_tokens if usage else 0,
    "output_tokens": usage.output_tokens if usage else 0,
    "cache_read_tokens": _cache_read,
    "cache_write_tokens": _cache_write,
    "turns_used": usage.requests if usage else 0,
    "max_turns": max_iterations,
    "output_source": _output_source,
    "compaction_count": _compaction_count,
}
with open("/workspace/agent_result.json", "w") as f:
    json.dump(agent_result, f)
_cache_info = f" (cache: {_cache_read:,}r/{_cache_write:,}w)" if _cache_read or _cache_write else ""
print(f"OK: {agent_result['input_tokens']} in / {agent_result['output_tokens']} out over {agent_result['turns_used']} turns{_cache_info}")
"""
