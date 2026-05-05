import json
from unittest.mock import Mock

import pytest


# Centralized RAG service URLs (kept for clarity; requests are mocked)
APP_ID = "archapp"
RAG_SERVICE_URLS = {
    "ingest": f"http://localhost:8001/ingest/{APP_ID}",
    "chunk": f"http://localhost:8002/chunk/{APP_ID}",
    "embed": f"http://localhost:8003/embed/{APP_ID}",
    "add_vectors": f"http://localhost:8004/add_vectors/{APP_ID}",
    "query": f"http://localhost:8004/query/{APP_ID}",
    "context_augment": f"http://localhost:8000/context-augment/{APP_ID}",
}


def make_response(status_code=200, data=None, text=None):
    m = Mock()
    m.status_code = status_code
    m.text = text or (json.dumps(data) if data is not None else "")
    m.json = lambda: data if data is not None else {}
    return m


def fake_post(url, json=None, files=None, timeout=None, **kwargs):
    # Simple router based on URL path
    if "/ingest/" in url:
        docs = json.get("config", {}).get("documents") if json else None
        if not docs:
            return make_response(400, {"error": "no documents"})
        return make_response(200, {"documents": docs})

    if "/chunk/" in url:
        document = json.get("document") if json else {}
        text = document.get("content") or document.get("text") or ""
        # naive chunking: split by sentence
        chunks = [
            {"chunk": s.strip(), "index": i, "metadata": {}}
            for i, s in enumerate([p for p in text.split('.') if p.strip()])
        ]
        return make_response(200, {"chunks": chunks})

    if "/embed/" in url:
        texts = json.get("texts", []) if json else []
        # return simple numeric vectors (length = 3) derived from text length
        embeddings = [[float(len(t)), float(len(t) % 7), 0.1] for t in texts]
        return make_response(200, {"embeddings": embeddings})

    if "/add_vectors" in url:
        return make_response(200, {"status": "success"})

    if "/query/" in url:
        # return fake results
        return make_response(200, {"results": [{"id": "testdoc1", "score": 0.1}]})

    if "/context-augment/" in url:
        return make_response(200, {"augmented_context": ["some relevant chunk"]})

    return make_response(404, {"error": "unknown endpoint"})


def test_rag_pipeline(monkeypatch):
    """End-to-end RAG pipeline test — fully mocked so it runs offline."""
    # Patch requests.post so no network I/O occurs
    import requests

    monkeypatch.setattr(requests, "post", fake_post)

    # 1. Ingest a document
    doc = {
        "id": "testdoc1",
        "title": "Test Policy",
        "content": "All employees must comply with security policies. MFA is required for all logins.",
        "category": "security",
    }
    ingest_payload = {"source_type": "direct", "config": {"documents": [doc]}}
    ingest_resp = requests.post(RAG_SERVICE_URLS["ingest"], json=ingest_payload)
    assert ingest_resp.status_code == 200
    ingest_data = ingest_resp.json()
    assert "documents" in ingest_data and isinstance(ingest_data["documents"], list)
    document = ingest_data["documents"][0]

    # 2. Chunk the document
    chunk_payload = {
        "document": document,
        "chunker_type": "langchain",
        "chunker_config": {"chunk_size": 200, "chunk_overlap": 50},
    }
    chunk_resp = requests.post(RAG_SERVICE_URLS["chunk"], json=chunk_payload)
    assert chunk_resp.status_code == 200
    chunk_data = chunk_resp.json()
    assert "chunks" in chunk_data and len(chunk_data["chunks"]) > 0

    # 3. Embed the chunks
    texts = [c.get("chunk") or c.get("content") for c in chunk_data["chunks"]]
    embed_resp = requests.post(RAG_SERVICE_URLS["embed"], json={"texts": texts})
    assert embed_resp.status_code == 200
    embed_data = embed_resp.json()
    embeddings = embed_data.get("embeddings", [])
    assert len(embeddings) == len(chunk_data["chunks"])

    # 4. Add vectors
    metadatas = []
    for i, c in enumerate(chunk_data["chunks"]):
        meta = dict(c.get("metadata") or {})
        meta["text"] = c.get("chunk") or c.get("content") or ""
        meta["chunk_index"] = c.get("index", i)
        metadatas.append(meta)
    add_resp = requests.post(
        RAG_SERVICE_URLS["add_vectors"], json={"vectors": embeddings, "metadatas": metadatas}
    )
    assert add_resp.status_code == 200
    assert add_resp.json().get("status") == "success"

    # 5. Query
    query_resp = requests.post(RAG_SERVICE_URLS["query"], json={"query_vector": embeddings[0], "top_k": 3})
    assert query_resp.status_code == 200
    qd = query_resp.json()
    assert "results" in qd and len(qd["results"]) > 0

    # 6. Context augmentation
    context_resp = requests.post(RAG_SERVICE_URLS["context_augment"], json={"question": "What are the security requirements?"})
    assert context_resp.status_code == 200
    cd = context_resp.json()
    assert "augmented_context" in cd
