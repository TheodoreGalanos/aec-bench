# ABOUTME: Embedded Python scripts for container execution — Anthropic, OpenAI, and PydanticAI.
# ABOUTME: Builder functions return script strings unchanged from the proven originals.

# DEPRECATED: This file is superseded by agents/entrypoint_agent.py (EntrypointAgent).
# It uses inline scripts instead of the library adapter layer. Kept for rollback
# safety during the transition. Will be removed in a future cleanup pass.


def build_anthropic_tool_loop_script() -> str:
    """Return the Anthropic Messages API tool-loop script for container execution."""
    return _ANTHROPIC_TOOL_LOOP_SCRIPT


def build_openai_tool_loop_script() -> str:
    """Return the OpenAI Chat Completions tool-loop script for container execution."""
    return _OPENAI_TOOL_LOOP_SCRIPT


def build_pydantic_ai_script() -> str:
    """Return the PydanticAI tool-loop script for container execution."""
    return _PYDANTIC_AI_TOOL_LOOP_SCRIPT


# ---------------------------------------------------------------------------
# Script string constants — copied verbatim from their original locations.
# Do NOT modify these unless the embedded agent logic needs to change.
# ---------------------------------------------------------------------------

_ANTHROPIC_TOOL_LOOP_SCRIPT = r"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from trajectory_writer import TrajectoryWriter

api_key = os.environ.get("ANTHROPIC_API_KEY", "")
model = os.environ.get("AGENT_MODEL", "claude-sonnet-4-20250514")
max_tokens = int(os.environ.get("AGENT_MAX_TOKENS", "16384"))
instruction = os.environ.get("AGENT_INSTRUCTION", "")
max_turns = int(os.environ.get("AGENT_MAX_TURNS", "10"))
command_timeout = int(os.environ.get("AGENT_COMMAND_TIMEOUT", "120"))
tools_json = os.environ.get("AGENT_TOOLS_JSON", "[]")
system_prompt = ""
if os.path.exists("/workspace/system_prompt.md"):
    with open("/workspace/system_prompt.md") as _sp:
        system_prompt = _sp.read().strip()

if not api_key:
    print("FATAL: ANTHROPIC_API_KEY not set", file=sys.stderr)
    sys.exit(1)
if not instruction:
    print("FATAL: AGENT_INSTRUCTION not set", file=sys.stderr)
    sys.exit(1)

# Build tool definitions — always include bash, plus any discovered tools
discovered_tools = json.loads(tools_json)
TOOLS = [{
    "name": "bash",
    "description": "Execute a bash command in /workspace and return stdout/stderr.",
    "input_schema": {
        "type": "object",
        "properties": {"command": {"type": "string", "description": "The bash command to execute"}},
        "required": ["command"],
    },
}]
for tool in discovered_tools:
    TOOLS.append({
        "name": tool["name"],
        "description": tool.get("description", f"Tool: {tool['name']}"),
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string", "description": f"Arguments for {tool['name']}"}},
            "required": ["command"],
        },
    })

API_URL = "https://api.anthropic.com/v1/messages"
HEADERS = {
    "x-api-key": api_key,
    "anthropic-version": "2023-06-01",
    "content-type": "application/json",
}
RETRY_BUDGET_SEC = 120
INITIAL_BACKOFF_SEC = 2
MAX_BACKOFF_SEC = 30

def send_request(payload_dict):
    data = json.dumps(payload_dict).encode()
    deadline = time.time() + RETRY_BUDGET_SEC
    attempt = 0
    last_error = ""
    while time.time() < deadline:
        attempt += 1
        req = urllib.request.Request(API_URL, data=data, headers=HEADERS, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            code = e.code
            body_text = ""
            try:
                body_text = e.read().decode()
            except Exception:
                pass
            last_error = f"HTTP {code}: {body_text[:300]}"
            print(f"Attempt {attempt}: {last_error}", file=sys.stderr)
            if code in (400, 401, 403, 404):
                break
            if code == 429:
                retry_after = e.headers.get("retry-after")
                wait = min(float(retry_after), MAX_BACKOFF_SEC) if retry_after else min(INITIAL_BACKOFF_SEC * (2 ** (attempt - 1)), MAX_BACKOFF_SEC)
                time.sleep(wait)
                continue
            if code >= 500:
                time.sleep(min(INITIAL_BACKOFF_SEC * (2 ** (attempt - 1)), MAX_BACKOFF_SEC))
                continue
            break
        except (urllib.error.URLError, ConnectionResetError, TimeoutError, OSError) as e:
            last_error = f"{type(e).__name__}: {e}"
            print(f"Attempt {attempt}: {last_error}", file=sys.stderr)
            time.sleep(min(INITIAL_BACKOFF_SEC * (2 ** (attempt - 1)), MAX_BACKOFF_SEC))
            continue
    print(f"FATAL: API request failed after {attempt} attempts: {last_error}", file=sys.stderr)
    sys.exit(1)

def execute_tool(tool_name, tool_input):
    command = tool_input.get("command", "")
    if tool_name == "bash":
        pass
    else:
        # For discovered tools, run as: python3 /workspace/{source} {command}
        for t in discovered_tools:
            if t["name"] == tool_name:
                command = f"python3 /workspace/{t['source']} {command}"
                break
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=command_timeout, cwd="/workspace")
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += ("\n" if output else "") + result.stderr
        if result.returncode != 0:
            output += f"\n[exit code: {result.returncode}]"
        if len(output) > 50000:
            output = output[:25000] + "\n\n[... truncated ...]\n\n" + output[-25000:]
        return output or "(no output)"
    except subprocess.TimeoutExpired:
        return f"[command timed out after {command_timeout}s]"
    except Exception as e:
        return f"[error executing command: {e}]"

traj = TrajectoryWriter()
if system_prompt:
    traj.system(system_prompt)
traj.user(instruction)

messages = [{"role": "user", "content": instruction}]
cumulative_input_tokens = 0
cumulative_output_tokens = 0
cumulative_cache_read_tokens = 0
cumulative_cache_write_tokens = 0
final_text = ""
actual_model = model

for turn in range(1, max_turns + 1):
    print(f"-- Turn {turn}/{max_turns} --", file=sys.stderr)
    payload = {"model": model, "max_tokens": max_tokens, "tools": TOOLS, "messages": messages}
    if system_prompt:
        payload["system"] = system_prompt
    body = send_request(payload)
    usage = body.get("usage", {})
    cache_read = usage.get("cache_read_input_tokens", 0)
    cache_write = usage.get("cache_creation_input_tokens", 0)
    cumulative_input_tokens += cache_read + cache_write + usage.get("input_tokens", 0)
    cumulative_output_tokens += usage.get("output_tokens", 0)
    cumulative_cache_read_tokens += cache_read
    cumulative_cache_write_tokens += cache_write
    actual_model = body.get("model", model)
    content_blocks = body.get("content", [])
    stop_reason = body.get("stop_reason", "")
    text_parts = []
    tool_uses = []
    for block in content_blocks:
        if block.get("type") == "text":
            text_parts.append(block.get("text", ""))
        elif block.get("type") == "tool_use":
            tool_uses.append(block)
    step = traj.new_step()
    if text_parts:
        final_text = "\n".join(text_parts)
        traj.thinking(final_text)
    if not tool_uses or stop_reason != "tool_use":
        break
    messages.append({"role": "assistant", "content": content_blocks})
    tool_results = []
    for tool_use in tool_uses:
        tool_name = tool_use.get("name", "")
        tool_input = tool_use.get("input", {})
        tool_input_command = tool_input.get("command", "")
        traj.tool_call(tool_name, tool_input_command, arguments=tool_input)
        start_time = time.monotonic()
        output = execute_tool(tool_name, tool_input)
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        exit_code = 0
        if "[exit code: " in output:
            try:
                exit_code = int(output.rsplit("[exit code: ", 1)[1].split("]")[0])
            except (ValueError, IndexError):
                pass
        traj.tool_result(tool_name, stdout=output, exit_code=exit_code, duration_ms=elapsed_ms)
        tool_results.append({"type": "tool_result", "tool_use_id": tool_use.get("id", ""), "content": output})
    messages.append({"role": "user", "content": tool_results})
else:
    print(f"Reached max turns ({max_turns}), stopping.", file=sys.stderr)

traj.close()

with open("/workspace/output.md", "w") as f:
    f.write(final_text)
with open("/workspace/conversation.jsonl", "w") as f:
    for msg in messages:
        f.write(json.dumps(msg) + "\n")
result = {"status": "ok", "model": actual_model, "input_tokens": cumulative_input_tokens, "output_tokens": cumulative_output_tokens, "cache_read_input_tokens": cumulative_cache_read_tokens, "cache_creation_input_tokens": cumulative_cache_write_tokens, "turns_used": turn, "max_turns": max_turns}
with open("/workspace/agent_result.json", "w") as f:
    json.dump(result, f)
print(f"OK: {cumulative_input_tokens} in / {cumulative_output_tokens} out over {turn} turn(s)")
"""


_OPENAI_TOOL_LOOP_SCRIPT = r"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from trajectory_writer import TrajectoryWriter

api_key = os.environ.get("AZURE_OPENAI_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
model = os.environ.get("AGENT_MODEL", "")
api_version = os.environ.get("AGENT_API_VERSION", "2024-10-21")
max_tokens = int(os.environ.get("AGENT_MAX_TOKENS", "16384"))
instruction = os.environ.get("AGENT_INSTRUCTION", "")
max_turns = int(os.environ.get("AGENT_MAX_TURNS", "10"))
command_timeout = int(os.environ.get("AGENT_COMMAND_TIMEOUT", "120"))
tools_json = os.environ.get("AGENT_TOOLS_JSON", "[]")
system_prompt = ""
if os.path.exists("/workspace/system_prompt.md"):
    with open("/workspace/system_prompt.md") as _sp:
        system_prompt = _sp.read().strip()

if not api_key:
    print("FATAL: No API key found (AZURE_OPENAI_API_KEY or OPENAI_API_KEY)", file=sys.stderr)
    sys.exit(1)
if not instruction:
    print("FATAL: AGENT_INSTRUCTION not set", file=sys.stderr)
    sys.exit(1)

# Determine URL and headers based on available env vars
if endpoint:
    url = f"{endpoint}/openai/deployments/{model}/chat/completions?api-version={api_version}"
    headers = {"api-key": api_key, "content-type": "application/json"}
else:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "content-type": "application/json"}

# Build tool definitions
discovered_tools = json.loads(tools_json)
TOOLS = [{
    "type": "function",
    "function": {
        "name": "bash",
        "description": "Execute a bash command in /workspace and return stdout/stderr.",
        "parameters": {
            "type": "object",
            "properties": {"command": {"type": "string", "description": "The bash command to execute"}},
            "required": ["command"],
        },
    },
}]
for tool in discovered_tools:
    TOOLS.append({
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description", f"Tool: {tool['name']}"),
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string", "description": f"Arguments for {tool['name']}"}},
                "required": ["command"],
            },
        },
    })

RETRY_BUDGET_SEC = 120
INITIAL_BACKOFF_SEC = 2
MAX_BACKOFF_SEC = 30

def send_request(payload_dict):
    data = json.dumps(payload_dict).encode()
    deadline = time.time() + RETRY_BUDGET_SEC
    attempt = 0
    last_error = ""
    while time.time() < deadline:
        attempt += 1
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            code = e.code
            body_text = ""
            try:
                body_text = e.read().decode()
            except Exception:
                pass
            last_error = f"HTTP {code}: {body_text[:300]}"
            print(f"Attempt {attempt}: {last_error}", file=sys.stderr)
            if code in (400, 401, 403, 404):
                break
            if code == 429:
                retry_after_ms = e.headers.get("retry-after-ms")
                retry_after = e.headers.get("retry-after")
                if retry_after_ms:
                    wait = min(float(retry_after_ms) / 1000.0, MAX_BACKOFF_SEC)
                elif retry_after:
                    wait = min(float(retry_after), MAX_BACKOFF_SEC)
                else:
                    wait = min(INITIAL_BACKOFF_SEC * (2 ** (attempt - 1)), MAX_BACKOFF_SEC)
                time.sleep(wait)
                continue
            if code >= 500:
                time.sleep(min(INITIAL_BACKOFF_SEC * (2 ** (attempt - 1)), MAX_BACKOFF_SEC))
                continue
            break
        except (urllib.error.URLError, ConnectionResetError, TimeoutError, OSError) as e:
            last_error = f"{type(e).__name__}: {e}"
            print(f"Attempt {attempt}: {last_error}", file=sys.stderr)
            time.sleep(min(INITIAL_BACKOFF_SEC * (2 ** (attempt - 1)), MAX_BACKOFF_SEC))
            continue
    print(f"FATAL: API request failed after {attempt} attempts: {last_error}", file=sys.stderr)
    sys.exit(1)

def execute_tool(tool_name, arguments_str):
    try:
        args = json.loads(arguments_str)
    except (json.JSONDecodeError, TypeError):
        args = {"command": arguments_str}
    command = args.get("command", "")
    if tool_name != "bash":
        for t in discovered_tools:
            if t["name"] == tool_name:
                command = f"python3 /workspace/{t['source']} {command}"
                break
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=command_timeout, cwd="/workspace")
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += ("\n" if output else "") + result.stderr
        if result.returncode != 0:
            output += f"\n[exit code: {result.returncode}]"
        if len(output) > 50000:
            output = output[:25000] + "\n\n[... truncated ...]\n\n" + output[-25000:]
        return output or "(no output)"
    except subprocess.TimeoutExpired:
        return f"[command timed out after {command_timeout}s]"
    except Exception as e:
        return f"[error executing command: {e}]"

traj = TrajectoryWriter()
if system_prompt:
    traj.system(system_prompt)
traj.user(instruction)

messages = []
if system_prompt:
    messages.append({"role": "system", "content": system_prompt})
messages.append({"role": "user", "content": instruction})
cumulative_input_tokens = 0
cumulative_output_tokens = 0
actual_model = model
final_text = ""

for turn in range(1, max_turns + 1):
    print(f"-- Turn {turn}/{max_turns} --", file=sys.stderr)
    payload = {"max_tokens": max_tokens, "tools": TOOLS, "messages": messages}
    if not endpoint:
        payload["model"] = model
    body = send_request(payload)
    usage = body.get("usage", {})
    cumulative_input_tokens += usage.get("prompt_tokens", 0)
    cumulative_output_tokens += usage.get("completion_tokens", 0)
    actual_model = body.get("model", model)
    choices = body.get("choices", [])
    if not choices:
        break
    message = choices[0].get("message", {})
    finish_reason = choices[0].get("finish_reason", "")
    content = message.get("content", "")
    tool_calls = message.get("tool_calls", [])
    step = traj.new_step()
    if content:
        final_text = content
        traj.thinking(content)
    if not tool_calls or finish_reason != "tool_calls":
        messages.append(message)
        break
    messages.append(message)
    for tc in tool_calls:
        fn = tc.get("function", {})
        tool_name = fn.get("name", "")
        arguments_str = fn.get("arguments", "{}")
        try:
            tool_input = json.loads(arguments_str)
        except (json.JSONDecodeError, TypeError):
            tool_input = {"command": arguments_str}
        tool_input_command = tool_input.get("command", "")
        traj.tool_call(tool_name, tool_input_command, arguments=tool_input)
        start_time = time.monotonic()
        output = execute_tool(tool_name, arguments_str)
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        exit_code = 0
        if "[exit code: " in output:
            try:
                exit_code = int(output.rsplit("[exit code: ", 1)[1].split("]")[0])
            except (ValueError, IndexError):
                pass
        traj.tool_result(tool_name, stdout=output, exit_code=exit_code, duration_ms=elapsed_ms)
        messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": output})
else:
    print(f"Reached max turns ({max_turns}), stopping.", file=sys.stderr)

traj.close()

with open("/workspace/output.md", "w") as f:
    f.write(final_text)
with open("/workspace/conversation.jsonl", "w") as f:
    for msg in messages:
        f.write(json.dumps(msg) + "\n")
result = {"status": "ok", "model": actual_model, "input_tokens": cumulative_input_tokens, "output_tokens": cumulative_output_tokens, "turns_used": turn, "max_turns": max_turns}
with open("/workspace/agent_result.json", "w") as f:
    json.dump(result, f)
print(f"OK: {cumulative_input_tokens} in / {cumulative_output_tokens} out over {turn} turn(s)")
"""


_PYDANTIC_AI_TOOL_LOOP_SCRIPT = r"""
import base64
import glob as _glob
import json
import os
import subprocess
import sys
import time

from pydantic_ai import Agent, BinaryContent, ToolReturn
from pydantic_ai.usage import UsageLimits
from trajectory_writer import TrajectoryWriter

# Supported input file types for multimodal injection
_IMAGE_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

_DOCUMENT_MIME = {
    ".pdf": "application/pdf",
}

_SUPPORTED_MIME = {**_IMAGE_MIME, **_DOCUMENT_MIME}

# Known agent artifact filenames to exclude from input injection
_ARTIFACT_NAMES = {
    "output.md", "agent_result.json", "conversation.jsonl",
    "task.toml", "system_prompt.md", "trajectory.jsonl",
}


def limit_output(output: str, max_bytes: int = 50_000) -> str:
    '''Truncate output to max_bytes, keeping head and tail with omission notice.'''
    raw = output.encode("utf-8")
    if len(raw) <= max_bytes:
        return output
    half = max_bytes // 2
    head = raw[:half].decode("utf-8", errors="ignore")
    tail = raw[-half:].decode("utf-8", errors="ignore")
    omitted = len(raw) - len(head.encode()) - len(tail.encode())
    return f"{head}\n[... {omitted} bytes omitted ...]\n{tail}"


model_name = os.environ.get("AGENT_MODEL", "")
instruction = os.environ.get("AGENT_INSTRUCTION", "")
max_turns = int(os.environ.get("AGENT_MAX_TURNS", "10"))
command_timeout = int(os.environ.get("AGENT_COMMAND_TIMEOUT", "120"))
tools_json = os.environ.get("AGENT_TOOLS_JSON", "[]")

if not instruction:
    print("FATAL: AGENT_INSTRUCTION not set", file=sys.stderr)
    sys.exit(1)

system_prompt = ""
if os.path.exists("/workspace/system_prompt.md"):
    with open("/workspace/system_prompt.md") as _sp:
        system_prompt = _sp.read().strip()

traj = TrajectoryWriter()
if system_prompt:
    traj.system(system_prompt)

discovered_tools = json.loads(tools_json)
image_tools = {t["name"] for t in discovered_tools if t.get("returns_image")}
tool_sources = {t["name"]: t["source"] for t in discovered_tools}

# Build provider-aware model for PydanticAI
_azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
_azure_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
_azure_api_version = os.environ.get("AZURE_OPENAI_API_VERSION", os.environ.get("AGENT_API_VERSION", "2024-10-21"))
_together_key = os.environ.get("TOGETHER_API_KEY", "")
_TOGETHER_BASE_URL = "https://api.together.ai/v1"

def _is_azure_v1_endpoint(endpoint):
    return endpoint.rstrip("/").lower().endswith("/openai/v1")

def _strip_together_prefix(model):
    prefix = "together:"
    if model.lower().startswith(prefix):
        return model[len(prefix):]
    return model

if model_name.lower().startswith("together:"):
    if not _together_key:
        print("FATAL: TOGETHER_API_KEY not set", file=sys.stderr)
        sys.exit(1)
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider
    _model = OpenAIChatModel(
        _strip_together_prefix(model_name),
        provider=OpenAIProvider(base_url=_TOGETHER_BASE_URL, api_key=_together_key),
    )
elif _azure_endpoint and _azure_key:
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.azure import AzureProvider
    _provider_kwargs = {
        "azure_endpoint": _azure_endpoint,
        "api_key": _azure_key,
    }
    if not _is_azure_v1_endpoint(_azure_endpoint):
        _provider_kwargs["api_version"] = _azure_api_version
    _model = OpenAIChatModel(
        model_name,
        provider=AzureProvider(**_provider_kwargs),
    )
else:
    _model = model_name

agent = Agent(
    _model,
    system_prompt=system_prompt or "You are a helpful engineering assistant.",
    retries=2,
)


@agent.tool_plain
def bash(command: str) -> str:
    # Execute a bash command in /workspace and return stdout/stderr.
    traj.new_step()
    traj.tool_call("bash", command)
    start_time = time.monotonic()
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=command_timeout, cwd="/workspace",
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += ("\n" if output else "") + result.stderr
        if result.returncode != 0:
            output += f"\n[exit code: {result.returncode}]"
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        traj.tool_result(
            "bash",
            stdout=result.stdout or "",
            stderr=result.stderr or "",
            exit_code=result.returncode,
            duration_ms=elapsed_ms,
        )
        output = limit_output(output)
        return output or "(no output)"
    except subprocess.TimeoutExpired:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        traj.tool_result(
            "bash",
            stdout="",
            stderr=f"timed out after {command_timeout}s",
            exit_code=-1,
            duration_ms=elapsed_ms,
        )
        return f"[command timed out after {command_timeout}s]"
    except Exception as e:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        traj.tool_result(
            "bash",
            stdout="",
            stderr=str(e),
            exit_code=-1,
            duration_ms=elapsed_ms,
        )
        return f"[error executing command: {e}]"


for tool_info in discovered_tools:
    t_name = tool_info["name"]
    t_source = tool_info["source"]
    t_desc = tool_info.get("description", f"Tool: {t_name}")
    t_image = tool_info.get("returns_image", False)

    def _make_tool_fn(source, is_image, tool_label):
        def tool_fn(command: str) -> ToolReturn | str:
            traj.new_step()
            traj.tool_call(tool_label, command)
            start_time = time.monotonic()
            raw_output = bash(f"python3 /workspace/{source} {command}")
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            if not is_image:
                traj.tool_result(tool_label, stdout=raw_output, duration_ms=elapsed_ms)
                return raw_output
            text_lines = []
            content_blocks: list[str | BinaryContent] = []
            media_paths: list[str] = []
            for line in raw_output.splitlines():
                if line.startswith("IMAGE:"):
                    image_path = line[6:].strip()
                    if os.path.exists(image_path):
                        media_paths.append(image_path)
                        with open(image_path, "rb") as f:
                            content_blocks.append(
                                BinaryContent(data=f.read(), media_type="image/png")
                            )
                    else:
                        text_lines.append(f"[image not found: {image_path}]")
                else:
                    text_lines.append(line)
            text_output = "\n".join(text_lines)
            content_blocks.insert(0, text_output)
            traj.tool_result(
                tool_label,
                stdout=text_output,
                duration_ms=elapsed_ms,
                media=media_paths or None,
            )
            return ToolReturn(return_value=text_output, content=content_blocks)
        tool_fn.__name__ = t_name.replace("-", "_")
        tool_fn.__doc__ = t_desc
        return tool_fn

    agent.tool_plain(_make_tool_fn(t_source, t_image, t_name))

# Scan workspace for input files (images, PDFs) to inject into first message
input_files = []
for ext, mime in _SUPPORTED_MIME.items():
    for fpath in _glob.glob(f"/workspace/*{ext}"):
        fname = os.path.basename(fpath)
        if fname not in _ARTIFACT_NAMES:
            input_files.append((fpath, mime))

# Sort for deterministic ordering
input_files.sort()

if input_files:
    print(f"Found {len(input_files)} input file(s) for multimodal injection:", file=sys.stderr)
    for fpath, mime in input_files:
        print(f"  {fpath} ({mime})", file=sys.stderr)

# Build the prompt — multimodal if input files exist
if input_files:
    user_prompt = [instruction]
    for fpath, mime in input_files:
        with open(fpath, "rb") as f:
            user_prompt.append(BinaryContent(data=f.read(), media_type=mime))
else:
    user_prompt = instruction

traj.user(str(instruction) if isinstance(instruction, str) else "multimodal instruction")

try:
    result = agent.run_sync(
        user_prompt,
        usage_limits=UsageLimits(request_limit=max_turns, tool_calls_limit=max_turns * 3),
    )
    final_text = result.output if isinstance(result.output, str) else str(result.output)
    usage = result.usage()
    status = "ok"
except Exception as e:
    final_text = f"Agent failed: {e}"
    usage = None
    status = "failed"
    print(f"Agent error: {e}", file=sys.stderr)
finally:
    traj.close()

with open("/workspace/output.md", "w") as f:
    f.write(final_text)

try:
    messages = result.all_messages() if status == "ok" else []
    with open("/workspace/conversation.jsonl", "w") as f:
        for msg in messages:
            f.write(msg.model_dump_json() + "\n")
except Exception:
    pass

agent_result = {
    "status": status,
    "model": model_name,
    "input_tokens": usage.input_tokens if usage else 0,
    "output_tokens": usage.output_tokens if usage else 0,
    "turns_used": usage.requests if usage else 0,
    "max_turns": max_turns,
}
with open("/workspace/agent_result.json", "w") as f:
    json.dump(agent_result, f)
print(f"OK: {agent_result['input_tokens']} in / {agent_result['output_tokens']} out")
"""
