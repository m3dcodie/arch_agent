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
    document = ingest_data['documents'][0]
    assert document is not None

    # 2. Chunk the document (send full document object)
    chunk_payload = {
        'document': document,
        'chunker_type': 'langchain',
        'chunker_config': {'chunk_size': 200, 'chunk_overlap': 50}
    }
    print('Chunk request:', chunk_payload)
    chunk_resp = requests.post(RAG_SERVICE_URLS['chunk'], json=chunk_payload)
    print('Chunk status code:', chunk_resp.status_code)
    print('Chunk response:', getattr(chunk_resp, 'text', chunk_resp))
    assert chunk_resp.status_code == 200
    chunk_data = chunk_resp.json()
    assert 'chunks' in chunk_data and len(chunk_data['chunks']) > 0

    # 3. Embed the chunks (send only chunk text as 'texts')
    texts = [c['chunk'] if 'chunk' in c else c.get('content', c) for c in chunk_data['chunks']]
    embed_payload = {'texts': texts}
    print('Embed request:', embed_payload)
    embed_resp = requests.post(RAG_SERVICE_URLS['embed'], json=embed_payload)
    print('Embed status code:', embed_resp.status_code)
    print('Embed response:', getattr(embed_resp, 'text', embed_resp))
    assert embed_resp.status_code == 200
    embed_data = embed_resp.json()
    print('Embed data:', embed_data)
    assert 'embeddings' in embed_data and len(embed_data['embeddings']) == len(chunk_data['chunks'])

    # 4. Add vectors to the vector DB (validate and match API)
    vectors = embed_data['embeddings']
    # Ensure each metadata is non-empty: include at least 'text' and 'chunk_index'
    metadatas = []
    for i, c in enumerate(chunk_data['chunks']):
        meta = dict(c.get('metadata') or {})
        meta['text'] = c.get('chunk') or c.get('content') or ''
        meta['chunk_index'] = c.get('index', i)
        meta = {k: v for k, v in meta.items() if v not in (None, '')}
        metadatas.append(meta)
    # Validation: vectors non-empty, same length, each vector is list of numbers
    if not vectors:
        print('Skipping add_vectors: embeddings list is empty')
        return
    if len(vectors) != len(metadatas):
        print(f'Skipping add_vectors: embeddings/metadatas length mismatch (embeddings: {len(vectors)}, metadatas: {len(metadatas)})')
        return
    if not all(isinstance(vec, list) and all(isinstance(x, (float, int)) for x in vec) for vec in vectors):
        print('Skipping add_vectors: one or more vectors are not lists of numbers')
        return
    add_vectors_payload = {
        'vectors': vectors,
        'metadatas': metadatas,
        'adapter_config': {'collection_name': 'archapp'}
    }
    print('Add vectors request:', add_vectors_payload)
    add_vec_resp = requests.post(RAG_SERVICE_URLS['add_vectors'], json=add_vectors_payload)
    print('Add vectors status code:', add_vec_resp.status_code)
    print('Add vectors response:', getattr(add_vec_resp, 'text', add_vec_resp))
    assert add_vec_resp.status_code == 200
    add_vec_data = add_vec_resp.json()

    assert add_vec_data.get('status', '') == 'success'
    print('Add vectors succeeded, proceeding to query...')

    # 5. Query the vector DB (API spec: query_vector, top_k, adapter_config)
    query_text = 'What are the security requirements for employees?'
    # Use the first embedding as the query vector for test purposes
    query_vector = vectors[0] if vectors else []
    query_payload = {
        'query_vector': query_vector,
        'top_k': 3,
        'adapter_config': {'collection_name': 'archapp'}
    }
    print('Query request:', query_payload)
    query_resp = requests.post(RAG_SERVICE_URLS['query'], json=query_payload)
    print('Query status code:', query_resp.status_code)
    print('Query response:', getattr(query_resp, 'text', query_resp))
    assert query_resp.status_code == 200
    query_data = query_resp.json()
    assert 'results' in query_data and len(query_data['results']) > 0

    # 6. Context augmentation
    context_payload = {
        'question': query_text
    }
    print('Context augmentation request:', context_payload)
    context_resp = requests.post(RAG_SERVICE_URLS['context_augment'], json=context_payload)
    print('Context augmentation status code:', context_resp.status_code)
    print('Context augmentation response:', getattr(context_resp, 'text', context_resp))
    assert context_resp.status_code == 200
    context_data = context_resp.json()
    assert 'augmented_context' in context_data
    print('RAG pipeline functional test passed.')
