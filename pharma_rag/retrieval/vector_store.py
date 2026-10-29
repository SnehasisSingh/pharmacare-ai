
import logging
from pathlib import Path

from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings


logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VECTOR_STORE_DIR = PROJECT_ROOT / "data" / "faiss_index"

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def create_vector_store(chunks):
    """Create a FAISS index from text chunks and their metadata."""
    if not chunks:
        raise ValueError("No document chunks provided for indexing")

    logger.info("Loading local embedding model: %s", EMBEDDING_MODEL)

    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

    documents = [
        Document(
            page_content=chunk["text"],
            metadata=chunk["metadata"],
        )
        for chunk in chunks
    ]

    logger.info("Creating FAISS index from %d chunks", len(documents))

    vector_store = FAISS.from_documents(documents, embeddings)

    VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
    vector_store.save_local(str(VECTOR_STORE_DIR))

    logger.info("FAISS index saved to %s", VECTOR_STORE_DIR)

    return vector_store


def load_vector_store():
    """Load the previously saved local FAISS index."""
    if not VECTOR_STORE_DIR.exists():
        raise FileNotFoundError(
            f"FAISS index not found: {VECTOR_STORE_DIR}"
        )

    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

    logger.info("Loading FAISS index from %s", VECTOR_STORE_DIR)

    return FAISS.load_local(
        str(VECTOR_STORE_DIR),
        embeddings,
        allow_dangerous_deserialization=True,
    )


def search_medical_documents(query, k=4):
    """Retrieve the most relevant document chunks for a query."""
    if not query or not query.strip():
        raise ValueError("Search query cannot be empty")

    vector_store = load_vector_store()
    results = vector_store.similarity_search(query, k=k)

    logger.info(
        "Retrieved %d chunks for medical knowledge search",
        len(results),
    )

    for result in results:
        logger.info(
            "Retrieved source=%s page=%s",
            result.metadata.get("source", "unknown"),
            result.metadata.get("page", "unknown"),
        )

    return results
