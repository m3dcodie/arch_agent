import requests
import pytest

# Centralized RAG service URLs (update as needed)
APP_ID = 'archapp'
RAG_SERVICE_URLS = {
    'ingest': f'http://localhost:8001/ingest/{APP_ID}',
    'chunk': f'http://localhost:8002/chunk/{APP_ID}',
    'embed': f'http://localhost:8003/embed/{APP_ID}',
    'add_vectors': f'http://localhost:8004/add_vectors/{APP_ID}',
    'query': f'http://localhost:8004/query/{APP_ID}',
    'context_augment': f'http://localhost:8000/context-augment/{APP_ID}',
}

def test_rag_pipeline():
    # 1. Ingest a document
    doc = {
        'id': 'testdoc1',
        'title': 'Test Policy',
        'content': 'All employees must comply with security policies. MFA is required for all logins.',
        'category': 'security'
    }
    ingest_payload = {
        'source_type': 'direct',
        'config': {
            'documents': [doc]
        }
    }
    print('Ingest request:', ingest_payload)
    ingest_resp = requests.post(RAG_SERVICE_URLS['ingest'], json=ingest_payload)
    print('Ingest status code:', ingest_resp.status_code)
    print('Ingest response:', ingest_resp.text)
    assert ingest_resp.status_code == 200
    ingest_data = ingest_resp.json()
    assert 'documents' in ingest_data and isinstance(ingest_data['documents'], list)
    assert len(ingest_data['documents']) > 0
    document_id = ingest_data['documents'][0].get('doc_id') or ingest_data['documents'][0].get('id')
    assert document_id is not None

    # 2. Chunk the document
    chunk_payload = {'appid': APP_ID, 'document_id': document_id}
    print('Chunk request:', chunk_payload)
    chunk_resp = requests.post(RAG_SERVICE_URLS['chunk'], json=chunk_payload)
    print('Chunk status code:', chunk_resp.status_code)
    print('Chunk response:', getattr(chunk_resp, 'text', chunk_resp))
    assert chunk_resp.status_code == 200
    chunk_data = chunk_resp.json()
    assert 'chunks' in chunk_data and len(chunk_data['chunks']) > 0

    # 3. Embed the chunks
    embed_resp = requests.post(RAG_SERVICE_URLS['embed'], json={'appid': APP_ID, 'chunks': chunk_data['chunks']})
    assert embed_resp.status_code == 200
    embed_data = embed_resp.json()
    assert 'embeddings' in embed_data and len(embed_data['embeddings']) == len(chunk_data['chunks'])

    # 4. Add vectors to the vector DB
    add_vec_resp = requests.post(RAG_SERVICE_URLS['add_vectors'], json={
        'appid': APP_ID,
        'embeddings': embed_data['embeddings'],
        'chunks': chunk_data['chunks']
    })
    assert add_vec_resp.status_code == 200
    add_vec_data = add_vec_resp.json()
    assert add_vec_data.get('success', False)

    # 5. Query the vector DB
    query_text = 'What are the security requirements for employees?'
    query_resp = requests.post(RAG_SERVICE_URLS['query'], json={
        'appid': APP_ID,
        'query': query_text
    })
    assert query_resp.status_code == 200
    query_data = query_resp.json()
    assert 'results' in query_data and len(query_data['results']) > 0

    # 6. Context augmentation
    context_resp = requests.post(RAG_SERVICE_URLS['context_augment'], json={
        'appid': APP_ID,
        'query': query_text,
        'results': query_data['results']
    })
    assert context_resp.status_code == 200
    context_data = context_resp.json()
    assert 'augmented_context' in context_data
    print('RAG pipeline functional test passed.')
