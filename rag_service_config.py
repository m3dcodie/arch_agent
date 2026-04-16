"""
RAG service endpoint configuration for ADAG.

These point to the microservices in the /home/mst/projects/rag repo.
Start all services with: cd /home/mst/projects/rag && ./run_all_services.sh
"""

APPID = "archapp"

INGESTION_URL      = "http://localhost:8001/ingest/{appid}"
CHUNKING_URL       = "http://localhost:8002/chunk/{appid}"
EMBEDDING_URL      = "http://localhost:8003/embed/{appid}"
ADD_VECTORS_URL    = "http://localhost:8004/add_vectors/{appid}"
CONTEXT_AUG_URL    = "http://localhost:8000/context-augment/{appid}"

HF_ROUTER_BASE_URL = "https://router.huggingface.co/v1"
