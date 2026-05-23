# ABOUTME: Shell quoting utility shared by ScriptAgent and ToolLoopAgent.
# ABOUTME: Wraps Python scripts in single quotes for safe execution via env.exec().


def quote_for_shell(script: str) -> str:
    """Wrap a Python script in single quotes for shell execution.

    Handles embedded single quotes by ending the current quoted segment,
    inserting an escaped quote, and starting a new quoted segment.
    """
    escaped = script.replace("'", "'\"'\"'")
    return f"'{escaped}'"
