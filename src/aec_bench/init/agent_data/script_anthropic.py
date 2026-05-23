# ABOUTME: Single-turn Anthropic agent — calls Messages API directly, no tools.
# ABOUTME: Subclasses Harbor's BaseAgent directly, composes aec_bench utility functions.

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

api_key = os.environ.get("ANTHROPIC_API_KEY", "")
model = os.environ.get("AGENT_MODEL", "claude-sonnet-4-20250514")
max_tokens = int(os.environ.get("AGENT_MAX_TOKENS", "16384"))
instruction = os.environ.get("AGENT_INSTRUCTION", "")

if not api_key:
    print("FATAL: ANTHROPIC_API_KEY not set", file=sys.stderr)
    sys.exit(1)
if not instruction:
    print("FATAL: AGENT_INSTRUCTION not set", file=sys.stderr)
    sys.exit(1)

url = "https://api.anthropic.com/v1/messages"
payload = json.dumps(
    {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": instruction}],
    }
).encode()
headers = {
    "x-api-key": api_key,
    "anthropic-version": "2023-06-01",
    "content-type": "application/json",
}

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
            text = "\n".join(p.get("text", "") for p in body.get("content", []) if p.get("type") == "text")
            usage = body.get("usage", {})
            with open("/workspace/output.md", "w") as f:
                f.write(text)
            result = {
                "status": "ok",
                "model": body.get("model", model),
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
            }
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
            retry_after = e.headers.get("retry-after")
            wait = (
                min(float(retry_after), MAX_BACKOFF_SEC)
                if retry_after
                else min(INITIAL_BACKOFF_SEC * (2 ** (attempt - 1)), MAX_BACKOFF_SEC)
            )
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


class ScriptAnthropicAgent(BaseAgent):
    """Single-turn Anthropic agent using the Messages API."""

    @staticmethod
    def name() -> str:
        return "script-anthropic"

    def version(self) -> str | None:
        return "1.0.0"

    async def setup(self, environment) -> None:  # type: ignore[override]
        result = await environment.exec("python3 --version")
        if result.return_code != 0:
            raise RuntimeError(f"Python3 not available in sandbox.\nstdout: {result.stdout}\nstderr: {result.stderr}")

    async def run(self, instruction, environment, context) -> None:  # type: ignore[override]
        env_vars = build_provider_env("anthropic", instruction, self.model_name)
        exec_result = await environment.exec(
            f"python3 -c {quote_for_shell(_SCRIPT)}",
            env=env_vars,
            timeout_sec=300,
        )
        result = await read_agent_result(environment, exec_result)
        context.n_input_tokens = result.input_tokens
        context.n_output_tokens = result.output_tokens
        context.metadata = result.metadata
