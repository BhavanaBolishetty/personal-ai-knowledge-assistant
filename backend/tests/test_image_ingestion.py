import io

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

FAKE_IMAGE_BYTES = b"fake png bytes for testing purposes only"


def test_image_upload_uses_vision_description(monkeypatch):
    import app.extraction.image as image_module

    monkeypatch.setattr(
        image_module, "describe_image", lambda **kwargs: "A solid red square, one pixel in size."
    )

    response = client.post(
        "/documents", files={"file": ("pixel.png", io.BytesIO(FAKE_IMAGE_BYTES), "image/png")}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "completed"

    detail = client.get(f"/documents/{body['id']}").json()
    assert "red square" in detail["extracted_text"]


def test_image_description_failure_marks_document_failed_not_fabricated(monkeypatch):
    import app.extraction.image as image_module
    from app.llm import LLMError

    def _broken(**kwargs):
        raise LLMError("simulated vision failure")

    monkeypatch.setattr(image_module, "describe_image", _broken)

    response = client.post(
        "/documents", files={"file": ("broken.png", io.BytesIO(FAKE_IMAGE_BYTES), "image/png")}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "failed"
    assert body["error_message"]


def test_image_has_no_page_number(monkeypatch):
    import app.extraction.image as image_module

    monkeypatch.setattr(image_module, "describe_image", lambda **kwargs: "A description of an image.")

    response = client.post(
        "/documents", files={"file": ("no-pages.png", io.BytesIO(FAKE_IMAGE_BYTES), "image/png")}
    )
    document_id = response.json()["id"]
    chunks = client.get(f"/documents/{document_id}/chunks").json()["chunks"]
    assert all(c["page_number"] is None for c in chunks)
