# ABOUTME: Provides the standalone JSON command-line interface for world actor calls.
# ABOUTME: Writes one machine-readable object and suppresses tracebacks for expected failures.

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from typing import Any, Never

from . import ActorError, capabilities, invoke, observe


class _CliUsageError(ValueError):
    pass


class _JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        raise _CliUsageError(message)


def _parser() -> argparse.ArgumentParser:
    parser = _JsonArgumentParser(prog="python -m aec_world")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("capabilities")
    commands.add_parser("observe")
    invoke_parser = commands.add_parser("invoke")
    invoke_parser.add_argument("--action", required=True)
    invoke_parser.add_argument("--decision-id", required=True)
    invoke_parser.add_argument("--arguments-json", required=True)
    invoke_parser.add_argument("--request-id")
    return parser


async def _run(arguments: argparse.Namespace) -> dict[str, Any]:
    if arguments.command == "capabilities":
        return await capabilities()
    if arguments.command == "observe":
        return await observe()
    try:
        action_arguments = json.loads(arguments.arguments_json)
    except json.JSONDecodeError as exc:
        raise _CliUsageError("--arguments-json must contain valid JSON") from exc
    if not isinstance(action_arguments, dict):
        raise _CliUsageError("--arguments-json must contain one JSON object")
    return await invoke(
        arguments.action,
        action_arguments,
        decision_id=arguments.decision_id,
        request_id=arguments.request_id,
    )


def main(argv: Sequence[str] | None = None) -> int:
    try:
        arguments = _parser().parse_args(argv)
        result = asyncio.run(_run(arguments))
    except _CliUsageError as error:
        return _write_error(
            ActorError(
                "cli-invalid",
                str(error),
                request_id=None,
                outcome="not-dispatched",
                retryable=False,
            )
        )
    except ActorError as error:
        return _write_error(error)
    except Exception:
        return _write_error(
            ActorError(
                "client-failed",
                "The world actor client failed.",
                request_id=None,
                outcome="unknown",
                retryable=False,
            )
        )
    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")
    return 0


def _write_error(error: ActorError) -> int:
    payload = {
        "ok": False,
        "error": {
            "code": error.code,
            "detail": error.detail,
            "request_id": error.request_id,
            "outcome": error.outcome,
            "retryable": error.retryable,
        },
    }
    sys.stderr.write(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
