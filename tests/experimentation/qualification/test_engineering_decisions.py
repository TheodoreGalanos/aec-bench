# ABOUTME: Tests qualification report publication through an aliased installed package path.
# ABOUTME: Exercises real local controls and prevents path aliases from breaking source provenance.

from pathlib import Path

import pytest

from aec_bench.experimentation.qualification import engineering_decisions


def test_qualification_reports_from_an_aliased_package_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = Path(engineering_decisions.__file__)
    alias = tmp_path / "package-alias"
    alias.symlink_to(module.parent, target_is_directory=True)
    monkeypatch.setattr(engineering_decisions, "__file__", str(alias / module.name))
    result = engineering_decisions.qualify_engineering_decisions(tmp_path / "result", seeds=(2,))
    assert result["passed"]
    assert "source_sha256" not in result
    assert (tmp_path / "result" / "qualification.json").is_file()
