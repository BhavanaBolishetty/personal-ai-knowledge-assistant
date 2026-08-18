import io

from fastapi.testclient import TestClient

from app.main import app
from tests.pdf_fixtures import make_multi_page_pdf_bytes

client = TestClient(app)


def test_multipage_pdf_preserves_real_page_numbers():
    pdf_bytes = make_multi_page_pdf_bytes(
        ["First page unique content Alpha.", "Second page unique content Beta.", "Third page unique content Gamma."]
    )
    response = client.post(
        "/documents", files={"file": ("pages-test.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    )
    assert response.status_code == 201
    document_id = response.json()["id"]

    chunks = client.get(f"/documents/{document_id}/chunks").json()["chunks"]
    assert len(chunks) == 3
    pages = sorted(c["page_number"] for c in chunks)
    assert pages == [1, 2, 3]


def test_ask_citation_shows_single_page_for_pdf_source(monkeypatch):
    import app.synthesis.service as service_module

    pdf_bytes = make_multi_page_pdf_bytes(["Distinct PDF citation test content page one."])
    client.post("/documents", files={"file": ("citation-test.pdf", io.BytesIO(pdf_bytes), "application/pdf")})

    monkeypatch.setattr(service_module, "generate_answer", lambda **kwargs: "Answer. [S1]")

    response = client.post("/ask", json={"query": "Distinct PDF citation test content page one"})
    assert response.status_code == 200
    sources = response.json()["sources"]
    matching = [s for s in sources if s["filename"] == "citation-test.pdf"]
    assert matching
    assert matching[0]["page_start"] == 1
    assert matching[0]["page_end"] == 1
