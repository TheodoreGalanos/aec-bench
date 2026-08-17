# ABOUTME: Proves manifest discovery across registered sinks, mapping composition, and exact registry locators.
# ABOUTME: Protects scanner precision, bootstrap comparison, and high-confidence provenance duplication rules.

from __future__ import annotations

import json
import subprocess
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


def _write_registry(repository_root: Path, content: str = "") -> Path:
    path = repository_root / "provenance-registry.toml"
    path.write_text(f"schema_version = 1\n{dedent(content).lstrip()}", encoding="utf-8")
    return path


def _write_baseline(
    repository_root: Path,
    symbols: list[str] | None = None,
    *,
    source_revision: str = "a" * 40,
) -> Path:
    path = repository_root / "provenance-baseline.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "aec-bench/provenance-baseline/1",
                "source_revision": source_revision,
                "symbols": sorted(symbols or []),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _qualification_registration(symbol: str, *, status: str = "current") -> str:
    return f'''
    [[field]]
    symbol = "{symbol}"
    surface = "pydantic_model"
    wire_name = "evidence"
    category = "qualification_attestation"
    domain_owner = "test"
    authority = "qualification"
    authoritative = true
    exposure = "persisted"
    status = "{status}"
    payload_contract = "test/qualification/1"
    canonicalization = "ordered evidence references"
    consumer = "test reader"
    validation_behavior = "passed requires evidence"
    mismatch_behavior = "reject"
    retention = "fixture_lifetime"
    rationale = "Qualification evidence is an explicit reviewed reference."
    duplication = "unique"
    version_scope = "one route and version"
    evidence_levels = ["fixture"]
    missing_evidence_behavior = "do not infer qualification"
    provider_route_scope = "one fixture route"
    qualification_state_behavior = "missing evidence is not passed"
    '''


def _semantic_registration(symbol: str, *, fail_closed: bool = True, status: str = "current") -> str:
    return f'''
    [[field]]
    symbol = "{symbol}"
    surface = "pydantic_model"
    wire_name = "content_hash"
    category = "semantic_commitment"
    domain_owner = "test"
    authority = "semantic compiler"
    authoritative = true
    exposure = "persisted"
    status = "{status}"
    payload_contract = "test/semantic/1"
    canonicalization = "canonical fixture JSON"
    consumer = "test reader"
    validation_behavior = "recompute and compare"
    mismatch_behavior = "reject"
    retention = "fixture_lifetime"
    rationale = "The fixture exercises semantic commitment policy."
    duplication = "unique"
    algorithm = "sha256"
    canonicalizer = "tests.fixture"
    fail_closed = {str(fail_closed).lower()}
    '''


def _compatibility_registration(
    symbol: str,
    *,
    wire_name: str,
    surface: str = "pydantic_model",
    aliases: list[str] | None = None,
) -> str:
    aliases_line = ""
    if aliases:
        rendered_aliases = ", ".join(f'"{alias}"' for alias in sorted(aliases))
        aliases_line = f"aliases = [{rendered_aliases}]\n"
    return f'''
    [[field]]
    symbol = "{symbol}"
    {aliases_line.rstrip()}
    surface = "{surface}"
    wire_name = "{wire_name}"
    category = "compatibility"
    domain_owner = "test"
    authority = "fixture schema"
    authoritative = true
    exposure = "persisted"
    status = "current"
    payload_contract = "test/schema/1"
    canonicalization = "literal schema identifier"
    consumer = "test reader"
    validation_behavior = "validate before use"
    mismatch_behavior = "reject"
    retention = "fixture_lifetime"
    rationale = "The fixture exercises compatibility metadata."
    duplication = "unique"
    compatibility_behavior = "reject unsupported schema"
    compatibility_kind = "external_schema"
    '''


def _domain_identity_registration(symbol: str, *, wire_name: str) -> str:
    return f'''
    [[field]]
    symbol = "{symbol}"
    surface = "pydantic_model"
    wire_name = "{wire_name}"
    category = "domain_identity"
    domain_owner = "test"
    authority = "fixture domain"
    authoritative = true
    exposure = "persisted"
    status = "current"
    payload_contract = "test/domain/1"
    canonicalization = "literal value"
    consumer = "test reader"
    validation_behavior = "validate before use"
    mismatch_behavior = "reject"
    retention = "fixture_lifetime"
    rationale = "The fixture exercises registry scope validation."
    duplication = "unique"
    '''


def _artifact_registration(symbol: str, *, wire_name: str) -> str:
    return f'''
    [[field]]
    symbol = "{symbol}"
    surface = "pydantic_model"
    wire_name = "{wire_name}"
    category = "artifact_integrity"
    domain_owner = "test"
    authority = "fixture source tree"
    authoritative = true
    exposure = "persisted"
    status = "current"
    payload_contract = "test/source-tree/1"
    canonicalization = "sorted source tree bytes"
    consumer = "test reader"
    validation_behavior = "recompute before use"
    mismatch_behavior = "reject"
    retention = "fixture_lifetime"
    rationale = "The fixture exercises mixed registered and legacy duplication."
    duplication = "duplicates source revision"
    algorithm = "sha256"
    artifact_boundary = "one source tree snapshot"
    fail_closed = true
    read_verification = "recompute and compare"
    '''


def test_registered_method_sink_owns_literal_records_and_unpacked_schema(tmp_path: Path) -> None:
    _write_source(
        tmp_path,
        "src/aec_bench/harness/authority.py",
        """
        import json

        EVIDENCE_SCHEMA = "aec-bench/example-evidence/1"


        class Authority:
            def emit(self) -> None:
                record = {
                    "record_type": "result",
                    "result_sha256": "0" * 64,
                }
                self._append_evidence(record)

            def _append_evidence(self, record: dict[str, object]) -> None:
                payload = {
                    "schema": EVIDENCE_SCHEMA,
                    **record,
                }
                self.stream.write(json.dumps(payload))
        """,
    )
    _write_registry(
        tmp_path,
        """
        [[manifest]]
        contract = "aec-bench/example-evidence/1"
        sink = "aec_bench.harness.authority.Authority._append_evidence"
        """,
    )

    symbols = {candidate.symbol for candidate in provenance.discover_candidates(tmp_path)}

    assert "manifest:aec-bench/example-evidence/1[result].result_sha256" in symbols
    assert "manifest:aec-bench/example-evidence/1[*].schema" in symbols
    assert "mapping:aec_bench.harness.authority.Authority.emit.result_sha256" not in symbols


def test_schema_precedes_semantics_and_unpacked_record_keeps_header_carrier(tmp_path: Path) -> None:
    _write_source(
        tmp_path,
        "src/aec_bench/harness/header.py",
        """
        def evidence_header() -> dict[str, object]:
            record = {"record_type": "header"}
            return {
                "schema": "aec-bench/example-evidence/1",
                **record,
                "semantics": "aec-bench/actor-invocation/1",
            }
        """,
    )

    symbols = {candidate.symbol for candidate in provenance.discover_candidates(tmp_path)}

    assert "manifest:aec-bench/example-evidence/1[*].schema" in symbols
    assert "manifest:aec-bench/example-evidence/1[header].semantics" in symbols
    assert not any(symbol.startswith("manifest:aec-bench/actor-invocation/1") for symbol in symbols)


def test_literal_method_argument_resolves_record_type_for_registered_sink(tmp_path: Path) -> None:
    _write_source(
        tmp_path,
        "src/aec_bench/harness/authority.py",
        """
        class Authority:
            def observe(self) -> None:
                self._append_error("observe")

            def _append_error(self, operation: str) -> None:
                self._append_evidence(
                    {
                        "record_type": operation,
                        "error_sha256": "0" * 64,
                    }
                )

            def _append_evidence(self, record: dict[str, object]) -> None:
                self.stream.write(record)
        """,
    )
    _write_registry(
        tmp_path,
        """
        [[manifest]]
        contract = "aec-bench/example-evidence/1"
        sink = "aec_bench.harness.authority.Authority._append_evidence"
        """,
    )

    symbols = {candidate.symbol for candidate in provenance.discover_candidates(tmp_path)}

    assert "manifest:aec-bench/example-evidence/1[observe].error_sha256" in symbols


def test_imported_schema_constant_surfaces_literal_header(tmp_path: Path) -> None:
    _write_source(
        tmp_path,
        "src/aec_bench/contracts/protocol.py",
        """
        EVIDENCE_SCHEMA = "aec-bench/example-evidence/1"
        """,
    )
    _write_source(
        tmp_path,
        "src/aec_bench/harness/header.py",
        """
        import json

        from aec_bench.contracts.protocol import EVIDENCE_SCHEMA


        def start_evidence() -> None:
            header = {
                "record_type": "header",
                "schema": EVIDENCE_SCHEMA,
                "started_at": "2026-08-17T00:00:00Z",
            }
            stream.write(json.dumps(header))
        """,
    )

    symbols = {candidate.symbol for candidate in provenance.discover_candidates(tmp_path)}

    assert "manifest:aec-bench/example-evidence/1[header].started_at" in symbols
    assert "manifest:aec-bench/example-evidence/1[*].schema" in symbols


def test_exact_registry_locator_extends_model_discovery_without_broad_evidence_token(tmp_path: Path) -> None:
    symbol = "aec_bench.qualification.QualificationCell.evidence"
    _write_source(
        tmp_path,
        "src/aec_bench/qualification.py",
        """
        from pydantic import BaseModel


        class QualificationCell(BaseModel):
            evidence: tuple[str, ...]
        """,
    )
    _write_registry(tmp_path, _qualification_registration(symbol))

    symbols = {candidate.symbol for candidate in provenance.discover_candidates(tmp_path)}

    assert symbol in symbols


def test_local_mapping_name_alone_does_not_make_a_surface(tmp_path: Path) -> None:
    _write_source(
        tmp_path,
        "src/aec_bench/contracts/local.py",
        """
        def calculate() -> int:
            evidence = {"content_sha256": "0" * 64}
            return len(evidence)
        """,
    )

    assert provenance.discover_candidates(tmp_path) == ()


def test_ordinary_list_append_does_not_make_a_mapping_persistent(tmp_path: Path) -> None:
    _write_source(
        tmp_path,
        "src/aec_bench/contracts/local.py",
        """
        def collect_rows() -> list[dict[str, str]]:
            rows: list[dict[str, str]] = []
            rows.append({"content_sha256": "0" * 64})
            return rows
        """,
    )

    assert provenance.discover_candidates(tmp_path) == ()


def test_returned_hash_only_mapping_and_simple_copies_are_discovered(tmp_path: Path) -> None:
    _write_source(
        tmp_path,
        "src/aec_bench/contracts/returned.py",
        """
        def direct() -> dict[str, str]:
            return {"content_sha256": "0" * 64}


        def alias() -> dict[str, str]:
            payload = {"result_sha256": "0" * 64}
            returned = payload
            return returned


        def copied() -> dict[str, str]:
            payload = {"receipt_sha256": "0" * 64}
            return dict(payload)
        """,
    )

    symbols = {candidate.symbol for candidate in provenance.discover_candidates(tmp_path)}

    assert "mapping:aec_bench.contracts.returned.direct.content_sha256" in symbols
    assert "mapping:aec_bench.contracts.returned.alias.result_sha256" in symbols
    assert "mapping:aec_bench.contracts.returned.copied.receipt_sha256" in symbols


@pytest.mark.parametrize(
    ("arguments_value", "extra_entry"),
    [
        ("request.arguments", '"request_id": request.request_id,'),
        ("request.transport", ""),
    ],
)
def test_actor_request_fingerprint_rejects_forbidden_identity_inputs(
    tmp_path: Path,
    arguments_value: str,
    extra_entry: str,
) -> None:
    _write_source(
        tmp_path,
        "src/aec_bench/harness/world_actor/authority.py",
        f"""
        ACTOR_INVOCATION_SEMANTICS = "aec-bench/actor-invocation/1"


        def _request_fingerprint(actor_principal_id: str, request: object) -> str:
            return _json_sha256(
                {{
                    "semantics": ACTOR_INVOCATION_SEMANTICS,
                    "actor_principal_id": actor_principal_id,
                    "decision_id": request.decision_id,
                    "action_name": request.action_name,
                    "arguments": {arguments_value},
                    {extra_entry}
                }}
            )
        """,
    )

    violations = provenance.inspect_actor_request_fingerprint(tmp_path)

    assert any(violation.code == "PROV008" for violation in violations)


def test_actor_request_fingerprint_rejects_forbidden_alias_indirection(tmp_path: Path) -> None:
    _write_source(
        tmp_path,
        "src/aec_bench/harness/world_actor/authority.py",
        """
        ACTOR_INVOCATION_SEMANTICS = "aec-bench/actor-invocation/1"


        def _request_fingerprint(actor_principal_id: str, request: object) -> str:
            logical_arguments = request.correlation
            return _json_sha256(
                {
                    "semantics": ACTOR_INVOCATION_SEMANTICS,
                    "actor_principal_id": actor_principal_id,
                    "decision_id": request.decision_id,
                    "action_name": request.action_name,
                    "arguments": logical_arguments,
                }
            )
        """,
    )

    violations = provenance.inspect_actor_request_fingerprint(tmp_path)

    assert any(
        violation.code == "PROV008"
        and "logical_arguments" in violation.message
        and "request.arguments" in violation.message
        for violation in violations
    )


@pytest.mark.parametrize(
    ("mutated_key", "alias_expression"),
    [
        ("semantics", "ACTOR_INVOCATION_SEMANTICS"),
        ("actor_principal_id", "actor_principal_id"),
        ("decision_id", "request.decision_id"),
        ("action_name", "request.action_name"),
        ("arguments", "request.arguments"),
    ],
)
def test_actor_request_fingerprint_requires_direct_expression_for_each_reviewed_key(
    tmp_path: Path,
    mutated_key: str,
    alias_expression: str,
) -> None:
    expressions = {
        "semantics": "ACTOR_INVOCATION_SEMANTICS",
        "actor_principal_id": "actor_principal_id",
        "decision_id": "request.decision_id",
        "action_name": "request.action_name",
        "arguments": "request.arguments",
    }
    expressions[mutated_key] = "canonical_alias"
    _write_source(
        tmp_path,
        "src/aec_bench/harness/world_actor/authority.py",
        f"""
        ACTOR_INVOCATION_SEMANTICS = "aec-bench/actor-invocation/1"


        def _request_fingerprint(actor_principal_id: str, request: object) -> str:
            canonical_alias = {alias_expression}
            return _json_sha256(
                {{
                    "semantics": {expressions["semantics"]},
                    "actor_principal_id": {expressions["actor_principal_id"]},
                    "decision_id": {expressions["decision_id"]},
                    "action_name": {expressions["action_name"]},
                    "arguments": {expressions["arguments"]},
                }}
            )
        """,
    )

    violations = provenance.inspect_actor_request_fingerprint(tmp_path)

    assert any(
        violation.code == "PROV008" and mutated_key in violation.message and "canonical_alias" in violation.message
        for violation in violations
    )


def test_production_actor_request_fingerprint_keeps_reviewed_canonical_shape() -> None:
    assert provenance.inspect_actor_request_fingerprint(REPOSITORY_ROOT) == ()


def test_embedded_child_and_parent_repeating_same_digest_are_flagged(tmp_path: Path) -> None:
    _write_source(
        tmp_path,
        "src/aec_bench/contracts/embedded.py",
        """
        from pydantic import BaseModel


        class ChildEvidence(BaseModel):
            evidence_sha256: str


        class ParentEvidence(BaseModel):
            child: ChildEvidence
            evidence_sha256: str
        """,
    )
    registry = _write_registry(tmp_path)
    baseline = _write_baseline(tmp_path)

    report = provenance.build_audit(tmp_path, registry, baseline)
    violations = cast(list[dict[str, Any]], report["violations"])

    assert any(
        violation["code"] == "PROV006"
        and set(violation["symbols"])
        == {
            "aec_bench.contracts.embedded.ChildEvidence.evidence_sha256",
            "aec_bench.contracts.embedded.ParentEvidence.evidence_sha256",
        }
        for violation in violations
    )


def test_registered_semantic_commitment_cannot_use_generic_content_hash(tmp_path: Path) -> None:
    symbol = "aec_bench.contracts.generic.GenericCommitment.content_hash"
    _write_source(
        tmp_path,
        "src/aec_bench/contracts/generic.py",
        """
        from pydantic import BaseModel


        class GenericCommitment(BaseModel):
            content_hash: str
        """,
    )
    registry = _write_registry(tmp_path, _semantic_registration(symbol))
    baseline = _write_baseline(tmp_path)

    report = provenance.build_audit(tmp_path, registry, baseline)
    violations = cast(list[dict[str, Any]], report["violations"])

    assert any(violation["code"] == "PROV006" and violation["symbol"] == symbol for violation in violations)


def test_current_semantic_commitment_cannot_disable_fail_closed(tmp_path: Path) -> None:
    symbol = "aec_bench.contracts.generic.GenericCommitment.content_hash"
    registry = _write_registry(tmp_path, _semantic_registration(symbol, fail_closed=False))

    with pytest.raises(provenance.ProvenanceInputError, match="fail_closed"):
        provenance.load_registry(registry)


def test_registry_status_is_closed_to_current_and_temporary_exception(tmp_path: Path) -> None:
    symbol = "aec_bench.qualification.QualificationCell.evidence"
    registry = _write_registry(tmp_path, _qualification_registration(symbol, status="legacy"))

    with pytest.raises(provenance.ProvenanceInputError, match="status"):
        provenance.load_registry(registry)


@pytest.mark.parametrize("field_name", ["version", "version_tag", "version_id", "schema_version_id"])
def test_version_token_registry_field_requires_compatibility_or_qualification_scope(
    tmp_path: Path,
    field_name: str,
) -> None:
    symbol = f"aec_bench.contracts.release.ReleaseIdentity.{field_name}"
    registry = _write_registry(tmp_path, _domain_identity_registration(symbol, wire_name=field_name))

    with pytest.raises(provenance.ProvenanceInputError, match="version-shaped"):
        provenance.load_registry(registry)


def test_registry_wire_name_drift_follows_serialization_alias(tmp_path: Path) -> None:
    symbol = "aec_bench.contracts.alias.AliasedSchema.schema_id"
    _write_source(
        tmp_path,
        "src/aec_bench/contracts/alias.py",
        """
        from pydantic import BaseModel, Field


        class AliasedSchema(BaseModel):
            schema_id: str = Field(serialization_alias="schema")
        """,
    )
    registry = _write_registry(
        tmp_path,
        _compatibility_registration(symbol, wire_name="schema_id"),
    )
    baseline = _write_baseline(tmp_path)

    report = provenance.build_audit(tmp_path, registry, baseline)
    violations = cast(list[dict[str, Any]], report["violations"])
    drift = next(violation for violation in violations if violation["code"] == "PROV012")

    assert drift["symbol"] == symbol
    assert "wire_name is" in cast(str, drift["message"])
    assert "surface is" not in cast(str, drift["message"])


def test_registry_surface_drift_is_compared_after_conceptual_normalization(tmp_path: Path) -> None:
    symbol = "aec_bench.contracts.alias.AliasedSchema.schema_id"
    _write_source(
        tmp_path,
        "src/aec_bench/contracts/alias.py",
        """
        from pydantic import BaseModel, Field


        class AliasedSchema(BaseModel):
            schema_id: str = Field(serialization_alias="schema")
        """,
    )
    registry = _write_registry(
        tmp_path,
        _compatibility_registration(symbol, wire_name="schema", surface="dataclass"),
    )
    baseline = _write_baseline(tmp_path)

    report = provenance.build_audit(tmp_path, registry, baseline)
    violations = cast(list[dict[str, Any]], report["violations"])
    drift = next(violation for violation in violations if violation["code"] == "PROV012")

    assert drift["symbol"] == symbol
    assert "surface is" in cast(str, drift["message"])
    assert "wire_name is" not in cast(str, drift["message"])


def test_registry_wire_name_drift_checks_discovered_alias_carrier(tmp_path: Path) -> None:
    primary_symbol = "aec_bench.contracts.alias.PrimarySchema.schema_id"
    alias_symbol = "aec_bench.contracts.alias.SecondarySchema.schema_id"
    _write_source(
        tmp_path,
        "src/aec_bench/contracts/alias.py",
        """
        from pydantic import BaseModel, Field


        class PrimarySchema(BaseModel):
            schema_id: str = Field(serialization_alias="schema")


        class SecondarySchema(BaseModel):
            schema_id: str = Field(serialization_alias="schema_tag")
        """,
    )
    registry = _write_registry(
        tmp_path,
        _compatibility_registration(
            primary_symbol,
            wire_name="schema",
            aliases=[alias_symbol],
        ),
    )
    baseline = _write_baseline(tmp_path)

    report = provenance.build_audit(tmp_path, registry, baseline)
    violations = cast(list[dict[str, Any]], report["violations"])
    drift = next(
        violation for violation in violations if violation["code"] == "PROV012" and violation["symbol"] == alias_symbol
    )

    assert "wire_name is" in cast(str, drift["message"])
    assert "surface is" not in cast(str, drift["message"])


def test_registry_alias_can_cross_surface_when_wire_leaf_matches(tmp_path: Path) -> None:
    primary_symbol = "aec_bench.contracts.alias.PrimarySchema.schema_id"
    alias_symbol = "aec_bench.contracts.alias.SecondarySchema.schema_id"
    _write_source(
        tmp_path,
        "src/aec_bench/contracts/alias.py",
        """
        from dataclasses import dataclass

        from pydantic import BaseModel


        class PrimarySchema(BaseModel):
            schema_id: str


        @dataclass(frozen=True)
        class SecondarySchema:
            schema_id: str
        """,
    )
    registry = _write_registry(
        tmp_path,
        _compatibility_registration(
            primary_symbol,
            wire_name="schema_id",
            aliases=[alias_symbol],
        ),
    )
    baseline = _write_baseline(tmp_path)

    report = provenance.build_audit(tmp_path, registry, baseline)
    violations = cast(list[dict[str, Any]], report["violations"])

    assert not any(violation["code"] == "PROV012" and violation["symbol"] == alias_symbol for violation in violations)


def test_baseline_update_growth_returns_policy_failure_without_check(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_source(
        tmp_path,
        "src/aec_bench/contracts/current.py",
        """
        from pydantic import BaseModel


        class CurrentArtifact(BaseModel):
            artifact_sha256: str
        """,
    )
    _write_registry(tmp_path)
    _write_baseline(tmp_path)

    exit_code = provenance.main(
        [
            "--repository-root",
            str(tmp_path),
            "--update-baseline",
            "--format",
            "json",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Deletion-only baseline update rejected new symbols" in captured.err


def test_registered_source_tree_digest_and_legacy_revision_are_still_flagged(tmp_path: Path) -> None:
    revision_symbol = "aec_bench.contracts.source.SourceIdentity.source_revision"
    tree_symbol = "aec_bench.contracts.source.SourceIdentity.source_tree_sha256"
    _write_source(
        tmp_path,
        "src/aec_bench/contracts/source.py",
        """
        from pydantic import BaseModel


        class SourceIdentity(BaseModel):
            source_revision: str
            source_tree_sha256: str
        """,
    )
    registry = _write_registry(
        tmp_path,
        _artifact_registration(tree_symbol, wire_name="source_tree_sha256"),
    )
    baseline = _write_baseline(tmp_path, [revision_symbol])

    report = provenance.build_audit(tmp_path, registry, baseline)
    violations = cast(list[dict[str, Any]], report["violations"])

    assert any(
        violation["code"] == "PROV006" and set(violation["symbols"]) == {revision_symbol, tree_symbol}
        for violation in violations
    )


def test_embedded_digest_flags_mixed_legacy_pair(tmp_path: Path) -> None:
    child_symbol = "aec_bench.contracts.embedded.ChildEvidence.evidence_sha256"
    parent_symbol = "aec_bench.contracts.embedded.ParentEvidence.evidence_sha256"
    _write_source(
        tmp_path,
        "src/aec_bench/contracts/embedded.py",
        """
        from pydantic import BaseModel


        class ChildEvidence(BaseModel):
            evidence_sha256: str


        class ParentEvidence(BaseModel):
            child: ChildEvidence
            evidence_sha256: str
        """,
    )
    registry = _write_registry(tmp_path)
    baseline = _write_baseline(tmp_path, [child_symbol])

    report = provenance.build_audit(tmp_path, registry, baseline)
    violations = cast(list[dict[str, Any]], report["violations"])

    assert any(
        violation["code"] == "PROV006" and set(violation["symbols"]) == {child_symbol, parent_symbol}
        for violation in violations
    )


def test_initial_baseline_matches_base_source_when_base_has_no_baseline(tmp_path: Path) -> None:
    symbol = "aec_bench.contracts.legacy.Legacy.content_hash"
    _write_source(
        tmp_path,
        "src/aec_bench/contracts/legacy.py",
        """
        from pydantic import BaseModel


        class Legacy(BaseModel):
            content_hash: str
        """,
    )
    registry = _write_registry(tmp_path)
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
            "base without provenance baseline",
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
    baseline = tmp_path / "provenance-baseline.json"
    baseline.write_text(
        json.dumps(
            {
                "schema_version": "aec-bench/provenance-baseline/1",
                "source_revision": base_revision,
                "symbols": [symbol],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    report = provenance.build_audit(tmp_path, registry, baseline, base_revision=base_revision)
    violations = cast(list[dict[str, Any]], report["violations"])

    assert not any(violation["code"] == "PROV002" for violation in violations)
