from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import Database
from app.main import create_app


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    database = Database(tmp_path / "api-test.db")
    app = create_app(
        settings=Settings(db_path=tmp_path / "api-test.db", llm_api_key=None),
        database=database,
    )
    return TestClient(app)


def test_health_reports_deterministic_mode(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "deterministic"
    assert payload["llm_configured"] is False
    assert payload["status"] == "ok"


def test_sample_load_and_document_listing(client: TestClient) -> None:
    response = client.post("/api/demo/load-sample")
    assert response.status_code == 200
    payload = response.json()
    assert payload["loaded"] == 12
    assert payload["stats"]["documents"] == 12
    assert payload["stats"]["supersession_links"] == 2

    listing = client.get("/api/documents").json()
    assert len(listing["documents"]) == 12
    amendment = next(
        item
        for item in listing["documents"]
        if item["id"] == "doc-finance-circular-2025-07"
    )
    assert amendment["supersedes"] == ["doc-expense-policy"]
    policy = next(
        item for item in listing["documents"] if item["id"] == "doc-expense-policy"
    )
    assert policy["superseded_by"][0]["document_id"] == "doc-finance-circular-2025-07"


def test_scenarios_endpoint(client: TestClient) -> None:
    payload = client.get("/api/demo/scenarios").json()
    assert len(payload["scenarios"]) == 3
    assert payload["scenarios"][0]["expected_status"] == "resolved"
    assert "fictional" in payload["corpus_note"].lower()


def test_query_contract_for_demo_scenario(client: TestClient) -> None:
    client.post("/api/demo/load-sample")
    response = client.post(
        "/api/query",
        json={"question": "What is the current expense reimbursement limit for client entertainment in India?"},
    )
    assert response.status_code == 200
    payload = response.json()
    for field in [
        "answer",
        "status",
        "claims",
        "citations",
        "conflicts",
        "critic_findings",
        "resolution_reason",
        "pipeline_trace",
        "validation",
        "retrieved_passages",
    ]:
        assert field in payload
    assert payload["status"] == "resolved"
    assert len(payload["pipeline_trace"]) == 5
    assert [stage["id"] for stage in payload["pipeline_trace"]] == [
        "retrieval",
        "synthesis",
        "critique",
        "resolution",
        "validation",
    ]
    assert "₹8,000" in payload["answer"]
    assert payload["mode"] == "deterministic"


def test_unresolved_query_via_api(client: TestClient) -> None:
    client.post("/api/demo/load-sample")
    response = client.post(
        "/api/query",
        json={
            "question": "What approval threshold applies to contractor purchases in India?",
            "as_of": "2026-10-23",
        },
    )
    payload = response.json()
    assert payload["status"] == "conflict_unresolved"
    assert len(payload["conflicts"]) == 1
    assert payload["conflicts"][0]["resolution"] == "unresolved"
    assert payload["validation"]["valid"] is True


def test_empty_corpus_query(client: TestClient) -> None:
    response = client.post(
        "/api/query", json={"question": "What is the expense reimbursement limit?"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "no_relevant_evidence"


def test_question_validation(client: TestClient) -> None:
    response = client.post("/api/query", json={"question": "  "})
    assert response.status_code == 422


def test_upload_text_document(client: TestClient) -> None:
    response = client.post(
        "/api/documents/upload",
        files={
            "file": (
                "travel-policy.txt",
                b"Section 6.1 Hotel limits. Hotel accommodation is reimbursed up to INR 6,000 per night in Tier-1 cities.",
                "text/plain",
            )
        },
        data={
            "title": "Uploaded Travel Policy",
            "doc_type": "policy",
            "version": "3.0",
            "published_date": "2026-01-01",
            "effective_date": "2026-02-01",
            "scope": "All employees in India",
            "authority_rank": "70",
            "authority_label": "Standing policy",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["document"]["title"] == "Uploaded Travel Policy"
    assert payload["document"]["doc_type"] == "policy"
    assert payload["document"]["passage_count"] >= 1
    assert payload["document"]["passages"][0]["page"] == 1
    assert "6,000" in payload["document"]["passages"][0]["text"]

    listing = client.get("/api/documents").json()
    assert listing["stats"]["uploaded_documents"] == 1


def test_upload_pdf_document(client: TestClient) -> None:
    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "Contractor purchases above INR 50,000 require CFO approval.")
    data = pdf.tobytes()
    pdf.close()
    response = client.post(
        "/api/documents/upload",
        files={"file": ("procurement.pdf", data, "application/pdf")},
        data={"title": "Uploaded Procurement PDF"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["document"]["page_count"] == 1
    assert payload["document"]["passage_count"] >= 1
    assert "CFO" in payload["document"]["passages"][0]["text"]


def test_upload_rejects_unsupported_extension(client: TestClient) -> None:
    response = client.post(
        "/api/documents/upload",
        files={"file": ("malware.exe", b"not a document", "application/octet-stream")},
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_upload_rejects_invalid_doctype(client: TestClient) -> None:
    response = client.post(
        "/api/documents/upload",
        files={"file": ("policy.txt", b"Some policy text.", "text/plain")},
        data={"doc_type": "not-a-type"},
    )
    assert response.status_code == 422


def test_delete_document(client: TestClient) -> None:
    client.post("/api/demo/load-sample")
    response = client.delete("/api/documents/doc-travel-policy")
    assert response.status_code == 200
    assert response.json()["deleted_id"] == "doc-travel-policy"
    assert client.delete("/api/documents/doc-travel-policy").status_code == 404
