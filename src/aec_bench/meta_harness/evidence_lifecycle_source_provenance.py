# ABOUTME: Binds claimed repository provenance to the aec_bench source executing in-process.
# ABOUTME: Prevents an unrelated clean checkout from lending false commit identity to a lifecycle run.

from __future__ import annotations

from pathlib import Path

import aec_bench
from aec_bench.meta_harness.evidence_lifecycle_private_snapshot import sha256


def validate_repository_matches_loaded_source(repository_dir: Path) -> None:
    """Require one claimed checkout to contain the exact loaded package inventory."""
    loaded_init = Path(aec_bench.__file__ or "")
    if not loaded_init.is_file():
        raise ValueError("executing aec_bench source cannot be resolved")
    loaded_source = loaded_init.resolve().parent
    repository = Path(repository_dir)
    candidates = (repository / "src" / "aec_bench", repository / "aec_bench")
    matching = [candidate for candidate in candidates if candidate.is_dir()]
    if len(matching) != 1 or _source_inventory(matching[0]) != _source_inventory(loaded_source):
        raise ValueError("repository source inventory does not match the executing aec_bench package")


def _source_inventory(root: Path) -> dict[str, str]:
    inventory: dict[str, str] = {}
    for path in sorted(Path(root).rglob("*")):
        relative = path.relative_to(root)
        if "__pycache__" in relative.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        if path.is_symlink() or (path.exists() and not path.is_file() and not path.is_dir()):
            raise ValueError("repository source inventory contains a non-regular entry")
        if path.is_file():
            inventory[relative.as_posix()] = sha256(path)
    return inventory
