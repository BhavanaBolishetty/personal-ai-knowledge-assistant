import io

from fastapi.testclient import TestClient

from app.main import app
from tests.docx_fixtures import make_docx_bytes

client = TestClient(app)


def test_docx_extraction_preserves_heading_and_paragraphs():
    docx_bytes = make_docx_bytes(
        heading="Project Architecture",
        paragraphs=["Backend: FastAPI", "Database: PostgreSQL"],
    )
    response = client.post(
        "/documents",
        files={
            "file": (
                "architecture.docx",
                io.BytesIO(docx_bytes),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "completed"

    detail = client.get(f"/documents/{body['id']}").json()
    assert "# Project Architecture" in detail["extracted_text"]
    assert "Backend: FastAPI" in detail["extracted_text"]


def test_docx_extraction_preserves_table_content():
    docx_bytes = make_docx_bytes(
        heading="Comparison",
        paragraphs=["See table below."],
        table_rows=[["Name", "Value"], ["Alpha", "1"], ["Beta", "2"]],
    )
    response = client.post(
        "/documents",
        files={
            "file": (
                "table-test.docx",
                io.BytesIO(docx_bytes),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 201
    document_id = response.json()["id"]
    detail = client.get(f"/documents/{document_id}").json()
    assert "Alpha" in detail["extracted_text"]
    assert "Beta" in detail["extracted_text"]


def test_docx_has_no_page_number():
    docx_bytes = make_docx_bytes(heading="No Pages", paragraphs=["DOCX has no reliable page concept."])
    response = client.post(
        "/documents",
        files={
            "file": (
                "no-pages.docx",
                io.BytesIO(docx_bytes),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    document_id = response.json()["id"]
    chunks = client.get(f"/documents/{document_id}/chunks").json()["chunks"]
    assert all(c["page_number"] is None for c in chunks)
