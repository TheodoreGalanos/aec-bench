# ABOUTME: Promotes only an independently certified ASW-8 station-data candidate.
# ABOUTME: Refuses an existing destination and copies the exact four certified files.

from __future__ import annotations

import argparse
import importlib.util
import shutil
from pathlib import Path
from types import ModuleType


def _certifier() -> ModuleType:
    path = Path(__file__).with_name("certifier.py")
    specification = importlib.util.spec_from_file_location("asw_8_station_data_certifier", path)
    if specification is None or specification.loader is None:
        raise RuntimeError("certifier module cannot load")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def promote(candidate_root: Path, source_root: Path, destination_root: Path) -> None:
    """Certify and copy exact candidate bytes to a new production directory."""
    certifier = _certifier()
    certifier.certify(candidate_root, source_root)
    destination_root.mkdir(parents=True, exist_ok=False)
    for name in sorted(certifier.FILES):
        shutil.copy2(candidate_root / name, destination_root / name)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--destination-root", type=Path, required=True)
    args = parser.parse_args()
    promote(args.candidate_root, args.source_root, args.destination_root)


if __name__ == "__main__":
    main()
