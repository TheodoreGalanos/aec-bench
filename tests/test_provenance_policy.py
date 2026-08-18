# ABOUTME: Proves provenance-field discovery, classification, and baseline enforcement.
# ABOUTME: Protects accepted authority commitments while blocking new ambient provenance.

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from textwrap import dedent
from typing import Any, cast

import pytest

from scripts import check_provenance_fields as provenance

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _write_source(repository_root: Path, relative_path: str, source: str) -> None:
    path = repository_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(source).lstrip(), encoding="utf-8")


def _symbols(repository_root: Path) -> set[str]:
    return {candidate.symbol for candidate in provenance.discover_candidates(repository_root)}


def _write_baseline(repository_root: Path, symbols: list[str] | None = None) -> Path:
    path = repository_root / "provenance-baseline.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "aec-bench/provenance-baseline/1",
                "source_revision": "a" * 40,
                "symbols": sorted(symbols or []),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _write_registry(repository_root: Path, entries: str = "") -> Path:
    path = repository_root / "provenance-registry.toml"
    path.write_text(f"schema_version = 1\n{entries}", encoding="utf-8")
    return path


def _registration(
    *,
    symbol: str,
    surface: str,
    wire_name: str,
    category: str,
    category_fields: str,
    status: str = "current",
    duplication: str = "unique",
    extra: str = "",
) -> str:
    return dedent(
        f'''

        [[field]]
        symbol = "{symbol}"
        surface = "{surface}"
        wire_name = "{wire_name}"
        category = "{category}"
        domain_owner = "test_owner"
        authority = "test_authority"
        authoritative = true
        exposure = "persisted"
        status = "{status}"
        payload_contract = "test/provenance/1"
        canonicalization = "The test fixture defines exact canonical bytes."
        consumer = "tests.test_provenance_policy"
        validation_behavior = "The fixture consumer validates the asserted value."
        mismatch_behavior = "reject"
        retention = "fixture_lifetime"
        rationale = "The fixture exercises one reviewed provenance assertion."
        duplication = "{duplication}"
        {category_fields.strip()}
        {extra.strip()}
        '''
    )


def _run_checker(repository_root: Path, capsys: pytest.CaptureFixture[str]) -> tuple[int, dict[str, Any]]:
    exit_code = provenance.main(
        [
            "--repository-root",
            str(repository_root),
            "--registry",
            str(repository_root / "provenance-registry.toml"),
            "--baseline",
            str(repository_root / "provenance-baseline.json"),
            "--format",
            "json",
            "--check",
        ]
    )
    captured = capsys.readouterr()
    output = captured.out or captured.err
    return exit_code, json.loads(output)


def test_discovers_supported_model_fields_and_persisted_manifest_keys(tmp_path: Path) -> None:
    _write_source(
        tmp_path,
        "src/aec_bench/contracts/sample.py",
        """
        from dataclasses import dataclass
        from typing import TypedDict

        from pydantic import BaseModel, Field, computed_field


        class DirectModel(BaseModel):
            content_sha256: str


        class ProjectModel(BaseModel):
            name: str


        class IndirectModel(ProjectModel):
            schema_version: str


        @dataclass(frozen=True)
        class EvidenceEvent:
            generated_at: str


        class EvidencePayload(TypedDict):
            source_revision: str


        FunctionalPayload = TypedDict("FunctionalPayload", {"protocol_version": str})


        class AliasedModel(BaseModel):
            schema_id: str = Field(alias="schema", serialization_alias="schema")


        class ComputedModel(BaseModel):
            @computed_field
            @property
            def content_hash(self) -> str:
                return "0" * 64


        def evidence_manifest() -> dict[str, object]:
            return {
                "schema": "aec-bench/example-evidence/1",
                "record_type": "result",
                "result_sha256": "0" * 64,
            }


        def local_hash_input() -> int:
            local_payload = {"content_sha256": "0" * 64}
            return len(local_payload)
        """,
    )

    symbols = _symbols(tmp_path)

    assert "aec_bench.contracts.sample.DirectModel.content_sha256" in symbols
    assert "aec_bench.contracts.sample.IndirectModel.schema_version" in symbols
    assert "aec_bench.contracts.sample.EvidenceEvent.generated_at" in symbols
    assert "aec_bench.contracts.sample.EvidencePayload.source_revision" in symbols
    assert "aec_bench.contracts.sample.FunctionalPayload.protocol_version" in symbols
    assert "aec_bench.contracts.sample.AliasedModel.schema_id" in symbols
    assert "aec_bench.contracts.sample.ComputedModel.content_hash" in symbols
    assert "manifest:aec-bench/example-evidence/1[result].result_sha256" in symbols
    assert not any(symbol.endswith("local_hash_input.content_sha256") for symbol in symbols)


@pytest.mark.parametrize("base_name", ["ContentAddressedModel", "LegacyContentAddressedModel"])
def test_synthesizes_inherited_content_address_for_each_ambient_model(tmp_path: Path, base_name: str) -> None:
    _write_source(
        tmp_path,
        "src/aec_bench/contracts/ambient.py",
        f"""
        from pydantic import BaseModel


        class {base_name}(BaseModel):
            content_sha256: str


        class EmbeddedChild({base_name}):
            name: str
        """,
    )

    symbols = _symbols(tmp_path)

    assert f"aec_bench.contracts.ambient.{base_name}.content_sha256" in symbols
    assert "aec_bench.contracts.ambient.EmbeddedChild.content_sha256" in symbols


def test_new_generic_content_digest_fails_with_remediation(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_source(
        tmp_path,
        "src/aec_bench/contracts/new_model.py",
        """
        from pydantic import BaseModel


        class NewDomainModel(BaseModel):
            content_sha256: str
        """,
    )
    _write_registry(tmp_path)
    _write_baseline(tmp_path)

    exit_code, report = _run_checker(tmp_path, capsys)

    assert exit_code == 1
    assert any(
        violation["code"] == "PROV001"
        and violation["symbol"] == "aec_bench.contracts.new_model.NewDomainModel.content_sha256"
        and violation["remediation"]
        for violation in report["violations"]
    )


def test_registered_operational_commitment_passes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_source(
        tmp_path,
        "src/aec_bench/harness/authority.py",
        """
        def evidence_record() -> dict[str, object]:
            return {
                "schema": "aec-bench/actor-invocation-evidence/1",
                "record_type": "request-admitted",
                "request_fingerprint": "0" * 64,
            }
        """,
    )
    symbol = "manifest:aec-bench/actor-invocation-evidence/1[request-admitted].request_fingerprint"
    _write_registry(
        tmp_path,
        _registration(
            symbol="manifest:aec-bench/actor-invocation-evidence/1[*].schema",
            surface="manifest_key",
            wire_name="schema",
            category="compatibility",
            category_fields="""
            compatibility_behavior = "Reject unsupported evidence schemas."
            compatibility_kind = "external_schema"
            """,
        )
        + _registration(
            symbol=symbol,
            surface="manifest_key",
            wire_name="request_fingerprint",
            category="operational_commitment",
            category_fields="""
            purpose = "idempotency_and_conflict_detection"
            algorithm = "sha256"
            canonicalizer = "tests.test_provenance_policy"
            identity_scope = "logical_actor_request_without_provider_correlation"
            """,
        ),
    )
    _write_baseline(tmp_path)

    exit_code, report = _run_checker(tmp_path, capsys)

    assert exit_code == 0
    assert report["violations"] == []


def test_registered_native_tool_surface_commitment_passes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_source(
        tmp_path,
        "src/aec_bench/adapters/native_world_tools.py",
        """
        def native_world_tool_surface_record() -> dict[str, object]:
            return {
                "schema": "aec-bench/native-world-tool-surface/1",
                "public_tool_surface_sha256": "0" * 64,
            }
        """,
    )
    symbol = "manifest:aec-bench/native-world-tool-surface/1[*].public_tool_surface_sha256"
    _write_registry(
        tmp_path,
        _registration(
            symbol=symbol,
            surface="manifest_key",
            wire_name="public_tool_surface_sha256",
            category="semantic_commitment",
            category_fields="""
            algorithm = "sha256"
            canonicalizer = "tests.test_provenance_policy"
            fail_closed = true
            """,
        )
        + _registration(
            symbol="manifest:aec-bench/native-world-tool-surface/1[*].schema",
            surface="manifest_key",
            wire_name="schema",
            category="compatibility",
            category_fields="""
            compatibility_behavior = "Reject unsupported surface schemas."
            compatibility_kind = "external_schema"
            """,
        ),
    )
    _write_baseline(tmp_path)

    exit_code, report = _run_checker(tmp_path, capsys)

    assert exit_code == 0
    assert report["violations"] == []


def test_registered_artifact_integrity_field_passes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_source(
        tmp_path,
        "src/aec_bench/contracts/artifacts.py",
        """
        from pydantic import BaseModel


        class ArtifactRef(BaseModel):
            artifact_id: str
            sha256: str
        """,
    )
    symbol = "aec_bench.contracts.artifacts.ArtifactRef.sha256"
    _write_registry(
        tmp_path,
        _registration(
            symbol=symbol,
            surface="model_field",
            wire_name="sha256",
            category="artifact_integrity",
            category_fields="""
            algorithm = "sha256"
            artifact_boundary = "retained_fixture_bytes"
            fail_closed = true
            read_verification = "The fixture reader recalculates the digest before use."
            """,
        ),
    )
    _write_baseline(tmp_path)

    exit_code, report = _run_checker(tmp_path, capsys)

    assert exit_code == 0
    assert report["violations"] == []


def test_nested_schema_version_without_a_reader_fails(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_source(
        tmp_path,
        "src/aec_bench/contracts/nested.py",
        """
        from pydantic import BaseModel


        class NestedPayload(BaseModel):
            schema_version: str


        class Envelope(BaseModel):
            payload: NestedPayload
        """,
    )
    _write_registry(tmp_path)
    _write_baseline(tmp_path)

    exit_code, report = _run_checker(tmp_path, capsys)

    assert exit_code == 1
    assert any(
        violation["code"] == "PROV001"
        and violation["symbol"] == "aec_bench.contracts.nested.NestedPayload.schema_version"
        for violation in report["violations"]
    )


def test_registered_evidence_generation_event_passes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_source(
        tmp_path,
        "src/aec_bench/contracts/evidence.py",
        """
        from pydantic import BaseModel


        class EvidenceEnvelope(BaseModel):
            evidence_generated_at: str
        """,
    )
    symbol = "aec_bench.contracts.evidence.EvidenceEnvelope.evidence_generated_at"
    _write_registry(
        tmp_path,
        _registration(
            symbol=symbol,
            surface="model_field",
            wire_name="evidence_generated_at",
            category="event_time",
            category_fields='event = "evidence envelope emitted"',
        ),
    )
    _write_baseline(tmp_path)

    exit_code, report = _run_checker(tmp_path, capsys)

    assert exit_code == 0
    assert report["violations"] == []


def test_catalogue_generation_time_fails_even_when_described_as_an_event(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_source(
        tmp_path,
        "src/aec_bench/contracts/library.py",
        """
        from pydantic import BaseModel


        class LibraryCatalogue(BaseModel):
            generated_at: str
        """,
    )
    symbol = "aec_bench.contracts.library.LibraryCatalogue.generated_at"
    _write_registry(
        tmp_path,
        _registration(
            symbol=symbol,
            surface="model_field",
            wire_name="generated_at",
            category="event_time",
            category_fields='event = "catalogue_serialization"',
        ),
    )
    _write_baseline(tmp_path)

    exit_code, report = _run_checker(tmp_path, capsys)

    assert exit_code == 1
    assert any(violation["code"] == "PROV007" for violation in report["violations"])


def test_actor_identity_rejects_provider_correlation_and_task_profile_transport(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_source(
        tmp_path,
        "src/aec_bench/contracts/identity.py",
        """
        from pydantic import BaseModel


        class ActorRequestIdentity(BaseModel):
            request_id: str
            provider_request_id: str


        class WorldTaskProfileIdentity(BaseModel):
            task_id: str
            provider_route: str
            transport: str
        """,
    )
    _write_registry(tmp_path)
    _write_baseline(tmp_path)

    exit_code, report = _run_checker(tmp_path, capsys)

    assert exit_code == 1
    codes = {violation["code"] for violation in report["violations"]}
    assert {"PROV008", "PROV009"}.issubset(codes)


def test_registry_rejects_unknown_metadata(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_source(
        tmp_path,
        "src/aec_bench/contracts/artifacts.py",
        """
        from pydantic import BaseModel


        class ArtifactRef(BaseModel):
            sha256: str
        """,
    )
    entry = _registration(
        symbol="aec_bench.contracts.artifacts.ArtifactRef.sha256",
        surface="model_field",
        wire_name="sha256",
        category="artifact_integrity",
        category_fields="""
        algorithm = "sha256"
        fail_closed = true
        invented_metadata = "must fail"
        """,
    )
    _write_registry(tmp_path, entry)
    _write_baseline(tmp_path)

    exit_code = provenance.main(
        [
            "--repository-root",
            str(tmp_path),
            "--registry",
            str(tmp_path / "provenance-registry.toml"),
            "--baseline",
            str(tmp_path / "provenance-baseline.json"),
            "--format",
            "json",
            "--check",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "invented_metadata" in captured.err


def test_temporary_claim_binding_exception_passes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_source(
        tmp_path,
        "src/aec_bench/contracts/claim.py",
        """
        from pydantic import BaseModel


        class ArtifactRef(BaseModel):
            artifact_id: str


        class ClaimBinding(BaseModel):
            artifact_ref: ArtifactRef
            artifact_sha256: str
        """,
    )
    symbol = "aec_bench.contracts.claim.ClaimBinding.artifact_sha256"
    _write_registry(
        tmp_path,
        _registration(
            symbol=symbol,
            surface="model_field",
            wire_name="artifact_sha256",
            category="artifact_integrity",
            status="temporary_exception",
            duplication="temporary_claim_binding",
            category_fields="""
            algorithm = "sha256"
            artifact_boundary = "referenced fixture artifact"
            fail_closed = true
            read_verification = "The fixture reader recalculates the artifact digest."
            """,
            extra="""
            duplicate_of = "aec_bench.contracts.claim.ClaimBinding.artifact_ref"
            exception_reason = "The fixture models the current evidence-v2 claim binding."
            removal_milestone = "A successor evidence contract removes the repeated claim."
            """,
        ),
    )
    _write_baseline(tmp_path)

    exit_code, report = _run_checker(tmp_path, capsys)

    assert exit_code == 0
    assert report["violations"] == []


def test_baseline_growth_is_rejected_against_pull_request_base(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_source(
        tmp_path,
        "src/aec_bench/contracts/legacy.py",
        """
        from pydantic import BaseModel


        class LegacyModel(BaseModel):
            content_hash: str
        """,
    )
    _write_registry(tmp_path)
    original_symbol = "aec_bench.contracts.legacy.LegacyModel.content_hash"
    _write_baseline(tmp_path, [original_symbol])
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Provenance Test",
            "-c",
            "user.email=provenance@example.invalid",
            "commit",
            "-qm",
            "baseline",
        ],
        cwd=tmp_path,
        check=True,
    )
    base_revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    _write_source(
        tmp_path,
        "src/aec_bench/contracts/added.py",
        """
        from pydantic import BaseModel


        class AddedLegacyModel(BaseModel):
            content_hash: str
        """,
    )
    added_symbol = "aec_bench.contracts.added.AddedLegacyModel.content_hash"
    _write_baseline(tmp_path, [added_symbol, original_symbol])

    exit_code = provenance.main(
        [
            "--repository-root",
            str(tmp_path),
            "--registry",
            str(tmp_path / "provenance-registry.toml"),
            "--baseline",
            str(tmp_path / "provenance-baseline.json"),
            "--base-revision",
            base_revision,
            "--format",
            "json",
            "--check",
        ]
    )
    report = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert any(
        violation["code"] == "PROV002" and violation["symbol"] == added_symbol for violation in report["violations"]
    )


def test_baseline_update_removes_stale_symbols(tmp_path: Path) -> None:
    _write_source(
        tmp_path,
        "src/aec_bench/contracts/legacy.py",
        """
        from pydantic import BaseModel


        class LegacyModel(BaseModel):
            content_hash: str
        """,
    )
    current_symbol = "aec_bench.contracts.legacy.LegacyModel.content_hash"
    _write_registry(tmp_path)
    baseline_path = _write_baseline(tmp_path, ["aec_bench.contracts.removed.Removed.content_hash", current_symbol])

    retained = provenance.update_baseline(
        tmp_path,
        tmp_path / "provenance-registry.toml",
        baseline_path,
    )

    assert retained == (current_symbol,)
    assert provenance.load_baseline(baseline_path).symbols == (current_symbol,)


def test_baseline_update_rejects_new_symbols(tmp_path: Path) -> None:
    _write_source(
        tmp_path,
        "src/aec_bench/contracts/added.py",
        """
        from pydantic import BaseModel


        class AddedModel(BaseModel):
            content_hash: str
        """,
    )
    _write_registry(tmp_path)
    baseline_path = _write_baseline(tmp_path)

    with pytest.raises(provenance.ProvenanceBaselineGrowthError, match="AddedModel.content_hash"):
        provenance.update_baseline(
            tmp_path,
            tmp_path / "provenance-registry.toml",
            baseline_path,
        )


def test_legacy_relocation_preserves_existing_debt_but_rejects_added_fields(tmp_path: Path) -> None:
    _write_source(
        tmp_path,
        "src/aec_bench/contracts/legacy_records.py",
        """
        from pydantic import BaseModel


        class LegacyModel(BaseModel):
            content_hash: str
            source_revision: str
        """,
    )
    _write_registry(
        tmp_path,
        """
        [[legacy_relocation]]
        from_prefix = "aec_bench.contracts.records."
        to_prefix = "aec_bench.contracts.legacy_records."
        """,
    )
    previous_symbol = "aec_bench.contracts.records.LegacyModel.content_hash"
    moved_symbol = "aec_bench.contracts.legacy_records.LegacyModel.content_hash"
    added_symbol = "aec_bench.contracts.legacy_records.LegacyModel.source_revision"
    baseline_path = _write_baseline(tmp_path, [previous_symbol])

    report = provenance.build_audit(
        tmp_path,
        tmp_path / "provenance-registry.toml",
        baseline_path,
    )

    report_findings = cast(list[dict[str, Any]], report["findings"])
    report_violations = cast(list[dict[str, Any]], report["violations"])
    findings = {item["symbol"]: item for item in report_findings}
    assert findings[moved_symbol]["state"] == "legacy"
    assert any(
        violation["code"] == "PROV001" and violation["symbol"] == added_symbol for violation in report_violations
    )
    with pytest.raises(provenance.ProvenanceBaselineGrowthError, match="source_revision"):
        provenance.update_baseline(tmp_path, tmp_path / "provenance-registry.toml", baseline_path)
    assert provenance.load_baseline(baseline_path).symbols == (previous_symbol,)


def test_text_and_json_reports_are_deterministic(tmp_path: Path) -> None:
    _write_source(
        tmp_path,
        "src/aec_bench/contracts/legacy.py",
        """
        from pydantic import BaseModel


        class LegacyModel(BaseModel):
            content_hash: str
        """,
    )
    _write_registry(tmp_path)
    _write_baseline(tmp_path, ["aec_bench.contracts.legacy.LegacyModel.content_hash"])

    first = provenance.build_audit(
        tmp_path,
        tmp_path / "provenance-registry.toml",
        tmp_path / "provenance-baseline.json",
    )
    second = provenance.build_audit(
        tmp_path,
        tmp_path / "provenance-registry.toml",
        tmp_path / "provenance-baseline.json",
    )

    assert first == second
    assert provenance.render_text(first) == provenance.render_text(second)
    assert str(tmp_path) not in json.dumps(first)


def test_checked_in_provenance_inventory_is_complete() -> None:
    report = provenance.build_audit(
        REPOSITORY_ROOT,
        REPOSITORY_ROOT / "provenance-registry.toml",
        REPOSITORY_ROOT / "provenance-baseline.json",
    )
    summary = cast(dict[str, Any], report["summary"])
    findings = cast(list[dict[str, Any]], report["findings"])

    assert report["violations"] == []
    assert summary["candidate_count"] == len(findings)
    assert summary["registered_count"] > 0
    assert summary["legacy_count"] > 0


def test_checker_cli_runs_from_repository_root() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/check_provenance_fields.py",
            "--check",
            "--format",
            "json",
        ],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    report = json.loads(result.stdout)
    assert report["violations"] == []
