
import logging
import os

from langchain_core.documents import Document
from qdrant_client import QdrantClient, models

logger = logging.getLogger(__name__)

COLLECTION_NAME = os.getenv(
    "QDRANT_COLLECTION",
    "medical_knowledge",
)

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def search_medical_documents(
    query,
    k=4,
    qdrant_url=None,
    api_key=None,
):
    cloud_url = qdrant_url or os.getenv("QDRANT_URL")
    cloud_api_key = api_key or os.getenv("QDRANT_API_KEY")

    if not isinstance(query, str) or not query.strip():
        raise ValueError("A valid search query is required.")

    if not cloud_url:
        raise ValueError("QDRANT_URL is not configured.")

    if not cloud_api_key:
        raise ValueError("QDRANT_API_KEY is not configured.")

    client = QdrantClient(
        url=cloud_url,
        api_key=cloud_api_key,
        cloud_inference=True,
        timeout=30,
    )

    try:
        if not client.collection_exists(COLLECTION_NAME):
            raise ValueError(
                f"Qdrant collection '{COLLECTION_NAME}' does not exist."
            )

        response = client.query_points(
            collection_name=COLLECTION_NAME,
            query=models.Document(
                text=query.strip(),
                model=EMBEDDING_MODEL,
            ),
            limit=k,
            with_payload=True,
        )

        documents = []

        for point in response.points:
            payload = point.payload or {}

            page_content = payload.get("page_content", "")
            metadata = payload.get("metadata", {}) or {}

            if not page_content:
                continue

            documents.append(
                Document(
                    page_content=page_content,
                    metadata={
                        **metadata,
                        "score": point.score,
                    },
                )
            )

        logger.info(
            "Retrieved %d documents from Qdrant.",
            len(documents),
        )

        return documents

    finally:
        client.close()
