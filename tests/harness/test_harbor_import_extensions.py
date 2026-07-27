# ABOUTME: Tests execution-kind selection and dependency boundaries for Harbor import evidence extensions.
# ABOUTME: Ensures the generic importer remains proposal-agnostic while its legacy facade stays byte-compatible.

from __future__ import annotations

import ast
from pathlib import Path

from aec_bench.harness.harbor_import import (
    import_harbor_trial,
    load_proposal_harbor_import_evidence,
)
from aec_bench.harness.harbor_importing.core import (
    import_harbor_trial as import_harbor_trial_core,
)
from aec_bench.harness.harbor_importing.proposal import (
    load_proposal_harbor_import_evidence as load_proposal_evidence_direct,
)
from aec_bench.harness.harbor_importing.registry import (
    resolve_import_evidence_extension,
)
from tests.harness.test_harbor_import import (
    _write_current_entrypoint_trial,
    _write_proposal_harbor_trial,
)


def test_standard_execution_kind_has_no_evidence_extension() -> None:
    assert resolve_import_evidence_extension("tool_loop") is None


def test_proposal_execution_kind_selects_proposal_evidence_extension() -> None:
    extension = resolve_import_evidence_extension("proposal_session")

    assert extension is not None
    assert extension.execution_kind == "proposal_session"


def test_generic_core_has_no_proposal_module_dependency() -> None:
    core_path = Path(__file__).parents[2] / "src" / "aec_bench" / "harness" / "harbor_importing" / "core.py"
    tree = ast.parse(core_path.read_text(encoding="utf-8"))
    imported_modules = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    imported_modules.update(
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module is not None
    )

    assert all("proposal" not in module for module in imported_modules)


def test_compatibility_facade_preserves_generic_trial_record_bytes(
    tmp_path: Path,
) -> None:
    repo_root, trial_dir = _write_current_entrypoint_trial(tmp_path)

    facade_record = import_harbor_trial(
        trial_dir=trial_dir,
        repo_root=repo_root,
    )
    core_record = import_harbor_trial_core(
        trial_dir=trial_dir,
        repo_root=repo_root,
    )

    assert facade_record.model_dump_json() == core_record.model_dump_json()


def test_compatibility_facade_preserves_proposal_record_and_evidence_bytes(
    tmp_path: Path,
) -> None:
    repo_root, trial_dir, _expected = _write_proposal_harbor_trial(tmp_path)

    facade_record = import_harbor_trial(
        trial_dir=trial_dir,
        repo_root=repo_root,
    )
    core_record = import_harbor_trial_core(
        trial_dir=trial_dir,
        repo_root=repo_root,
    )
    facade_evidence = load_proposal_harbor_import_evidence(
        trial_dir=trial_dir,
        repo_root=repo_root,
    )
    direct_evidence = load_proposal_evidence_direct(
        trial_dir=trial_dir,
        repo_root=repo_root,
    )

    assert facade_record.model_dump_json() == core_record.model_dump_json()
    assert facade_evidence == direct_evidence
