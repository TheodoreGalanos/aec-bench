# ABOUTME: Single-turn Azure OpenAI agent — calls Chat Completions API directly, no tools.
# ABOUTME: Subclasses Harbor's BaseAgent directly, composes aec_bench utility functions.

# DEPRECATED: This file is superseded by agents/entrypoint_agent.py (EntrypointAgent).
# It uses inline scripts instead of the library adapter layer. Kept for rollback
# safety during the transition. Will be removed in a future cleanup pass.

from harbor.agents.base import BaseAgent

from aec_bench.agents._shell import quote_for_shell
from aec_bench.agents.env import build_provider_env
from aec_bench.agents.results import read_agent_result

_SCRIPT = r"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
model = os.environ.get("AGENT_MODEL", "")
api_version = os.environ.get("AGENT_API_VERSION", "2024-10-21")
max_tokens = int(os.environ.get("AGENT_MAX_TOKENS", "16384"))
instruction = os.environ.get("AGENT_INSTRUCTION", "")

if not api_key:
    print("FATAL: AZURE_OPENAI_API_KEY not set", file=sys.stderr)
    sys.exit(1)
if not endpoint:
    print("FATAL: AZURE_OPENAI_ENDPOINT not set", file=sys.stderr)
    sys.exit(1)
if not model:
    print("FATAL: AGENT_MODEL not set", file=sys.stderr)
    sys.exit(1)
if not instruction:
    print("FATAL: AGENT_INSTRUCTION not set", file=sys.stderr)
    sys.exit(1)

url = f"{endpoint}/openai/deployments/{model}/chat/completions?api-version={api_version}"
payload = json.dumps({"max_tokens": max_tokens, "messages": [{"role": "user", "content": instruction}]}).encode()
headers = {"api-key": api_key, "content-type": "application/json"}

RETRY_BUDGET_SEC = 120
INITIAL_BACKOFF_SEC = 2
MAX_BACKOFF_SEC = 30
deadline = time.time() + RETRY_BUDGET_SEC
attempt = 0
last_error = ""

while time.time() < deadline:
    attempt += 1
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            body = json.loads(resp.read().decode())
            choices = body.get("choices", [])
            text = choices[0]["message"]["content"] if choices else ""
            usage = body.get("usage", {})
            with open("/workspace/output.md", "w") as f:
                f.write(text)
            result = {"status": "ok", "model": body.get("model", model), "input_tokens": usage.get("prompt_tokens", 0), "output_tokens": usage.get("completion_tokens", 0)}
            with open("/workspace/agent_result.json", "w") as f:
                json.dump(result, f)
            sys.exit(0)
    except urllib.error.HTTPError as e:
        code = e.code
        body_text = ""
        try:
            body_text = e.read().decode()
        except Exception:
            pass
        last_error = f"HTTP {code}: {body_text[:200]}"
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
        time.sleep(min(INITIAL_BACKOFF_SEC * (2 ** (attempt - 1)), MAX_BACKOFF_SEC))
        continue

with open("/workspace/agent_result.json", "w") as f:
    json.dump({"status": "error", "error": last_error, "attempts": attempt, "input_tokens": 0, "output_tokens": 0}, f)
sys.exit(1)
""".strip()


class ScriptAzureOpenAIAgent(BaseAgent):
    """Single-turn Azure OpenAI agent using the Chat Completions API."""

    @staticmethod
    def name() -> str:
        return "script-azure-openai"

    def version(self) -> str | None:
        return "1.0.0"

    async def setup(self, environment) -> None:  # type: ignore[override]
        result = await environment.exec("python3 --version")
        if result.return_code != 0:
            raise RuntimeError(
                f"Python3 not available in sandbox.\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )

    async def run(self, instruction, environment, context) -> None:  # type: ignore[override]
        env_vars = build_provider_env("azure_openai", instruction, self.model_name)
        exec_result = await environment.exec(
            f"python3 -c {quote_for_shell(_SCRIPT)}",
            env=env_vars,
            timeout_sec=300,
        )
        result = await read_agent_result(environment, exec_result)
        context.n_input_tokens = result.input_tokens
        context.n_output_tokens = result.output_tokens
        context.metadata = result.metadata
