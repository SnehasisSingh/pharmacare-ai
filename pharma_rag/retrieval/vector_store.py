
import logging
from pathlib import Path

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient, models

PROJECT_ROOT = Path(__file__).resolve().parents[2]
QDRANT_PATH = PROJECT_ROOT / "data" / "qdrant_storage"
COLLECTION_NAME = "medical_knowledge"

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)

logger = logging.getLogger(__name__)


def get_embeddings():
    logger.info("Loading embedding model: %s", EMBEDDING_MODEL)

    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def create_vector_store(chunks):
    """Create or rebuild the local Qdrant collection."""

    if not chunks:
        logger.warning("No document chunks provided")
        return

    # Convert loader dictionaries into LangChain Documents first.
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

    QDRANT_PATH.mkdir(parents=True, exist_ok=True)

    logger.info("Opening local Qdrant database: %s", QDRANT_PATH)

    client = QdrantClient(path=str(QDRANT_PATH))

    try:
        embeddings = get_embeddings()

        # Rebuild collection only after validating document structure.
        if client.collection_exists(COLLECTION_NAME):
            logger.info("Deleting existing Qdrant collection")
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

        logger.info("Qdrant indexing completed successfully")
        logger.info("Collection: %s", COLLECTION_NAME)
        logger.info("Indexed documents: %d", len(documents))
        logger.info("Database location: %s", QDRANT_PATH)

    finally:
        client.close()


def search_medical_documents(query, k=4):
    """Search the local Qdrant medical knowledge collection."""

    if not QDRANT_PATH.exists():
        raise FileNotFoundError(
            f"Qdrant database not found: {QDRANT_PATH}"
        )

    client = QdrantClient(path=str(QDRANT_PATH))

    try:
        if not client.collection_exists(COLLECTION_NAME):
            raise ValueError(
                f"Qdrant collection '{COLLECTION_NAME}' not found. "
                "Build the index first."
            )

        vector_store = QdrantVectorStore(
            client=client,
            collection_name=COLLECTION_NAME,
            embedding=get_embeddings(),
        )

        results = vector_store.similarity_search(query, k=k)

        logger.info(
            "Retrieved %d documents for query: %s",
            len(results),
            query,
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
