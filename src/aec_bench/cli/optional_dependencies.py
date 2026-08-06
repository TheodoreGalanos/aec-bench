# ABOUTME: Reports missing CLI feature extras before importing their optional runtimes.
# ABOUTME: Keeps optional commands visible without masking failures inside installed packages.

from importlib.util import find_spec
from shutil import which

import typer


def require_optional_extra(
    feature: str, extra: str, modules: tuple[str, ...] = (), commands: tuple[str, ...] = ()
) -> None:
    if all(find_spec(module) is not None for module in modules) and all(which(command) for command in commands):
        return
    typer.echo(f'{feature} is not installed.\nInstall it with: pip install "aec-bench[{extra}]"', err=True)
    raise typer.Exit(1)
