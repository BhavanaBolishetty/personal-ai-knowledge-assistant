import io

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.db_utils import truncate_all

client = TestClient(app)

# A small, deterministic, clearly-distinct-topic knowledge base used to
# evaluate retrieval quality — not real personal documents. Each text is
# short enough to become exactly one chunk, so "the top result's document"
# is easy to reason about.
#
# The test suite runs against its own isolated, per-session database (see
# conftest.py) that no other process writes to, and the fixture below wipes
# it immediately before seeding — so these documents are guaranteed to be
# the only content in the database when these tests run, regardless of what
# earlier test files in the same run inserted.
KNOWLEDGE_BASE = {
    "quality_binary_search.txt": (
        "To locate an element in a sorted list, binary search repeatedly "
        "inspects the middle entry and discards the half of the list that "
        "cannot contain the target, narrowing the candidates until the "
        "value is found or the range is empty. Because each step halves "
        "the remaining search space, the algorithm completes in "
        "logarithmic time, making it far more efficient than checking "
        "every element one by one for large sorted collections such as a "
        "phone book or a sorted index."
    ),
    "quality_load_balancing.txt": (
        "A load balancer sits in front of a pool of backend servers and "
        "decides which server should handle each incoming request, so "
        "that traffic is spread out and no single machine gets "
        "overwhelmed. Common request-distribution policies include round "
        "robin, routing to whichever server currently has the fewest "
        "active connections, and consistent hashing so related requests "
        "land on the same server. This spreading of traffic is a key "
        "technique for keeping a web service available and responsive as "
        "usage grows."
    ),
    "quality_operating_systems.txt": (
        "When a program starts running, the operating system represents "
        "it as a process — a container that owns its own memory, a "
        "program counter tracking the next instruction, and a set of "
        "allocated resources. The kernel's scheduler decides which of the "
        "many processes competing for the CPU gets to run at any given "
        "moment. A running process can spawn child processes and "
        "exchange data with them through inter-process communication "
        "channels such as pipes."
    ),
    "quality_machine_learning.txt": (
        "Linear regression fits a straight line through a set of data "
        "points so that the line's predictions stay as close as possible "
        "to the observed values, typically by minimizing the total "
        "squared difference between predictions and reality. Once fit, "
        "the line's slope and intercept can be used to predict a "
        "continuous numeric outcome — such as a house price or a "
        "temperature — from one or more input variables."
    ),
}


@pytest.fixture(scope="module", autouse=True)
def _seed_knowledge_base():
    truncate_all()
    for filename, content in KNOWLEDGE_BASE.items():
        response = client.post(
            "/documents",
            files={"file": (filename, io.BytesIO(content.encode()), "text/plain")},
        )
        assert response.status_code == 201
        assert response.json()["status"] == "completed"
    yield


def _search(query, top_k=5):
    response = client.post("/search", json={"query": query, "top_k": top_k})
    assert response.status_code == 200
    return response.json()["results"]


# Checks membership in the top few results rather than an exact rank-1
# match: semantic similarity scores between genuinely related documents can
# be close, so asserting a specific document must win rank 1 tests an
# outcome that isn't really a correctness property. Appearing clearly in
# the top results is the property that matters.
def test_binary_search_query_surfaces_binary_search_document():
    results = _search("What is binary search?", top_k=3)
    filenames = [r["original_filename"] for r in results]
    assert "quality_binary_search.txt" in filenames


def test_load_balancing_query_surfaces_load_balancing_document():
    results = _search("How does load balancing work?", top_k=3)
    filenames = [r["original_filename"] for r in results]
    assert "quality_load_balancing.txt" in filenames


def test_operating_systems_query_surfaces_operating_systems_document():
    results = _search("What is a process in an operating system?", top_k=3)
    filenames = [r["original_filename"] for r in results]
    assert "quality_operating_systems.txt" in filenames


def test_machine_learning_query_surfaces_machine_learning_document():
    results = _search("What is linear regression?", top_k=3)
    filenames = [r["original_filename"] for r in results]
    assert "quality_machine_learning.txt" in filenames


def test_cross_topic_scalability_query_surfaces_load_balancing_document():
    # A broader question than any single document's exact wording. We check
    # the relevant document is clearly present in the top results, not
    # necessarily ranked strictly first — semantic search is not exact
    # keyword matching.
    results = _search("What are the different approaches to handling scalability?", top_k=4)
    filenames = [r["original_filename"] for r in results]
    assert "quality_load_balancing.txt" in filenames


def test_genuinely_cross_topic_query_returns_multiple_distinct_documents():
    # Unlike the vague "explain some CS concepts" a purely broad query
    # would be, this one legitimately touches two of the knowledge base's
    # topics — a genuinely cross-topic query should surface both,
    # clearing app.core.config.settings.min_relevance_score for both.
    results = _search(
        "Compare how binary search and load balancing each improve efficiency in computing systems.",
        top_k=4,
    )
    distinct_documents = {r["document_id"] for r in results}
    assert len(distinct_documents) > 1
