"""Qdrant vector database initialization."""
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, PointStruct, VectorParams

from app.core.config import settings


def init_qdrant() -> None:
    """Initialize Qdrant collection for document chunks.
    
    Creates the collection idempotently if it doesn't exist.
    Collection stores embeddings for document chunks with metadata.
    """
    client = QdrantClient(url=settings.qdrant_url)

    # Collection configuration
    collection_name = settings.qdrant_collection_name
    vector_size = 1024  # BGE-large embedding dimension
    distance_metric = Distance.COSINE

    try:
        # Try to get collection info to see if it exists
        collection_info = client.get_collection(collection_name)
        print(f"Collection '{collection_name}' already exists")
        return
    except Exception as e:
        print(f"Collection '{collection_name}' does not exist, creating it: {e}")

    # Create collection
    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=vector_size,
            distance=distance_metric,
        ),
    )

    # Create vector index for efficient similarity search
    client.create_payload_index(
        collection_name=collection_name,
        field_name="document_id",
        field_schema="keyword",
    )
    client.create_payload_index(
        collection_name=collection_name,
        field_name="organization_id",
        field_schema="keyword",
    )
    client.create_payload_index(
        collection_name=collection_name,
        field_name="page_number",
        field_schema="integer",
    )

    print(f"Collection '{collection_name}' created successfully with indexes")


if __name__ == "__main__":
    init_qdrant()
