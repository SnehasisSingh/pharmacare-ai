
import logging
import os
from functools import lru_cache
from pathlib import Path

from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient, models


PROJECT_ROOT = Path(__file__).resolve().parents[2]

LOCAL_QDRANT_PATH = PROJECT_ROOT / "data" / "qdrant_storage"

COLLECTION_NAME = "medical_knowledge"

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

QDRANT_URL = (
    "https://5c4b8d6c-900a-47a8-a5b7-77fc02364f1a."
    "us-east-1-1.aws.cloud.qdrant.io"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_embeddings():
    """
    Load and cache the embedding model.

    The cached instance is reused across subsequent calls,
    including warm Lambda invocations.
    """
    logger.info("Loading embedding model: %s", EMBEDDING_MODEL)

    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def create_vector_store(chunks):
    """
    Create or rebuild the LOCAL Qdrant collection.

    This function is intended for document ingestion and indexing.
    It does not modify the Qdrant Cloud collection.
    """

    if not chunks:
        logger.warning("No document chunks provided")
        return

    documents = []

    for chunk in chunks:
        if not isinstance(chunk, dict) or "text" not in chunk:
            raise ValueError(
                "Expected each chunk to contain 'text' and 'metadata'. "
                f"Received: {type(chunk).__name__}"
            )

        documents.append(
            Document(
                page_content=chunk["text"],
                metadata=chunk.get("metadata", {}),
            )
        )

    LOCAL_QDRANT_PATH.mkdir(parents=True, exist_ok=True)

    logger.info(
        "Opening local Qdrant database: %s",
        LOCAL_QDRANT_PATH,
    )

    client = QdrantClient(path=str(LOCAL_QDRANT_PATH))

    try:
        embeddings = get_embeddings()

        if client.collection_exists(COLLECTION_NAME):
            logger.info(
                "Deleting existing LOCAL collection: %s",
                COLLECTION_NAME,
            )
            client.delete_collection(COLLECTION_NAME)

        vector_size = len(
            embeddings.embed_query("medical knowledge")
        )

        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=models.Distance.COSINE,
            ),
        )

        vector_store = QdrantVectorStore(
            client=client,
            collection_name=COLLECTION_NAME,
            embedding=embeddings,
        )

        vector_store.add_documents(documents)

        logger.info("Local indexing completed successfully")
        logger.info("Collection: %s", COLLECTION_NAME)
        logger.info("Indexed documents: %d", len(documents))

    finally:
        client.close()


def search_medical_documents(
    query,
    k=4,
    qdrant_url=None,
    api_key=None,
):
    """
    Search the Qdrant CLOUD medical knowledge collection.

    Credentials can be passed explicitly or supplied through
    runtime environment variables.

    Args:
        query: User's medical knowledge question.
        k: Number of relevant documents to retrieve.
        qdrant_url: Optional Qdrant Cloud URL.
        api_key: Optional Qdrant Cloud API key.

    Returns:
        List of LangChain Document objects.
    """

    if not query or not query.strip():
        raise ValueError("Search query cannot be empty")

    cloud_url = qdrant_url or os.getenv("QDRANT_URL") or QDRANT_URL
    cloud_api_key = api_key or os.getenv("QDRANT_API_KEY")

    if not cloud_api_key:
        raise ValueError(
            "QDRANT_API_KEY is missing. "
            "Pass api_key or configure it at runtime."
        )

    logger.info("Connecting to Qdrant Cloud")
    logger.info("Collection: %s", COLLECTION_NAME)

    client = QdrantClient(
        url=cloud_url,
        api_key=cloud_api_key,
        timeout=30,
    )

    try:
        if not client.collection_exists(COLLECTION_NAME):
            raise ValueError(
                f"Cloud collection '{COLLECTION_NAME}' not found."
            )

        embeddings = get_embeddings()

        vector_store = QdrantVectorStore(
            client=client,
            collection_name=COLLECTION_NAME,
            embedding=embeddings,
        )

        results = vector_store.similarity_search(
            query=query,
            k=k,
        )

        logger.info(
            "Retrieved %d documents from Qdrant Cloud",
            len(results),
        )

        for rank, document in enumerate(results, start=1):
            logger.info(
                "Result %d | Source: %s | Page: %s",
                rank,
                document.metadata.get("source", "unknown"),
                document.metadata.get("page", "unknown"),
            )

        return results

    finally:
        client.close()
