import io

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

client = TestClient(app)

# Only runs when a real GEMINI_API_KEY is configured, so the normal test
# suite never spends free-tier quota. Run explicitly with:
#   pytest tests/test_ask_integration.py -v
pytestmark = pytest.mark.skipif(
    not settings.gemini_api_key,
    reason="GEMINI_API_KEY not configured — skipping live Gemini integration test.",
)


def test_real_gemini_call_produces_a_grounded_answer():
    client.post(
        "/documents",
        files={
            "file": (
                "integration-binary-search.txt",
                io.BytesIO(
                    b"Binary search finds a target value in a sorted array in O(log n) "
                    b"time by repeatedly halving the search interval."
                ),
                "text/plain",
            )
        },
    )

    response = client.post(
        "/ask", json={"query": "What is the time complexity of binary search?"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["answer"]
    assert body["sources"]
    assert body["model"] == settings.gemini_model
