# ABOUTME: Tests technical inspection routes for exact artifact bytes and provider qualification.
# ABOUTME: Keeps full digests out of routine evidence responses and behind explicit integrity expansion.

from pathlib import Path

from fastapi.testclient import TestClient

from aec_bench.contracts.authority_evidence import AuthorityEvidenceKind
from aec_bench.contracts.trial_record import AuthorityExpectation, EvidenceStatus
from aec_bench.ledger.writer import write_trial_record
from aec_bench.web.app import create_app
from tests.support.trial_record_factories import make_trial_record


def _inspection_client(tmp_path: Path) -> tuple[TestClient, dict[str, str]]:
    world_evidence = tmp_path / "world-evidence.json"
    world_evidence.write_text('{"world":"verified"}\n', encoding="utf-8")
    provider_evidence = tmp_path / "provider-evidence.json"
    provider_evidence.write_text('{"provider":"verified"}\n', encoding="utf-8")

    record = make_trial_record(
        evidence_status=EvidenceStatus.PENDING,
        expected_authorities=(
            AuthorityExpectation(
                authority_kind=AuthorityEvidenceKind.WORLD,
                protocol="aec-bench/world-evidence/1",
            ),
            AuthorityExpectation(
                authority_kind=AuthorityEvidenceKind.PROVIDER,
                protocol="aec-bench/provider-evidence-manifest/1",
            ),
        ),
    )
    record.attach_artifact(
        "authority:world:aec-bench/world-evidence/1",
        world_evidence,
        media_type="application/json",
    )
    record.attach_artifact(
        "provider_evidence",
        provider_evidence,
        media_type="application/json",
    )
    ledger_root = tmp_path / "ledger"
    write_trial_record(ledger_root=ledger_root, record=record)

    app = create_app(
        ledger_root=ledger_root,
        tasks_root=tmp_path / "tasks",
        internal_token="secret-token",
    )
    return TestClient(app), {"X-AEC-BENCH-Internal-Token": "secret-token"}


def test_trial_evidence_lists_authorities_without_full_digests(tmp_path: Path) -> None:
    client, headers = _inspection_client(tmp_path)

    forbidden = client.get("/api/trials/experiment-001/trial-001/evidence")
    response = client.get("/api/trials/experiment-001/trial-001/evidence", headers=headers)

    assert forbidden.status_code == 403
    assert response.status_code == 200
    data = response.json()
    assert data["evidence_status"] == "verified"
    assert {item["authority_kind"] for item in data["evidence"]} == {"world", "provider"}
    assert all("sha256" not in item for item in data["evidence"])
    assert all(item["integrity_url"].endswith("/integrity") for item in data["evidence"])


def test_artifact_integrity_expansion_verifies_full_digest_and_content(tmp_path: Path) -> None:
    client, headers = _inspection_client(tmp_path)
    evidence = client.get(
        "/api/trials/experiment-001/trial-001/evidence",
        headers=headers,
    ).json()["evidence"][0]

    integrity = client.get(evidence["integrity_url"], headers=headers)
    content = client.get(evidence["content_url"], headers=headers)

    assert integrity.status_code == 200
    assert integrity.json() == {
        "artifact_id": evidence["artifact_id"],
        "algorithm": "sha256",
        "sha256": integrity.json()["sha256"],
        "size_bytes": evidence["size_bytes"],
        "verified": True,
        "verified_at": integrity.json()["verified_at"],
    }
    assert len(integrity.json()["sha256"]) == 64
    assert content.status_code == 200
    assert content.headers["content-type"].startswith("application/json")


def test_provider_qualification_exposes_exact_versions_without_routine_digests(tmp_path: Path) -> None:
    client, headers = _inspection_client(tmp_path)

    response = client.get("/api/provider-qualification", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["matrix_id"]
    assert data["cells"]
    cell = data["cells"][0]
    assert {
        "provider_route",
        "feature",
        "adapter_identity",
        "sdk",
        "runtime",
        "evidence_level",
        "qualification_status",
        "qualified_at",
        "reason",
        "evidence",
    } <= set(cell)
    assert "package_version" in cell["adapter_identity"]
    assert "distribution_version" in cell["sdk"]
    assert all("sha256" not in item for candidate in data["cells"] for item in candidate["evidence"])

    evidence = next(item for candidate in data["cells"] for item in candidate["evidence"])
    integrity = client.get(evidence["integrity_url"], headers=headers)
    assert integrity.status_code == 200
    assert len(integrity.json()["sha256"]) == 64


def test_openapi_documents_v2_vocabulary_and_label_authority(tmp_path: Path) -> None:
    client, _headers = _inspection_client(tmp_path)

    document = client.get("/openapi.json").json()
    schemas = document["components"]["schemas"]

    assert document["info"]["version"] == "2.0"
    assert "version" not in schemas["EvolutionTreeResponse"]["properties"]
    assert "candidate_id" in schemas["EvolutionTreeResponse"]["properties"]
    candidate_description = schemas["EvolutionTreeResponse"]["properties"]["candidate_id"]["description"]
    assert candidate_description == "Stable candidate identity."
    assert "legacy" not in candidate_description
    assert "display" in schemas["EvolutionTreeResponse"]["properties"]["label"]["description"]
    assert "sha256" not in schemas["TrialEvidenceItemSchema"]["properties"]

    forbidden_generic_fields = {"hash", "digest", "version", "timestamp", "content_hash", "content_sha256"}
    for schema_name, schema in schemas.items():
        assert forbidden_generic_fields.isdisjoint(schema.get("properties", {})), schema_name
