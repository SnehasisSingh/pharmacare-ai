
import logging
import os
import uuid
from collections import defaultdict
from pathlib import Path

from qdrant_client import QdrantClient, models
from langchain_huggingface import HuggingFaceEmbeddings

from document_loader import (
    DOCUMENTS_DIR,
    load_pdf_documents,
    split_documents,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

COLLECTION_NAME = "medical_knowledge"

QDRANT_URL = os.getenv("QDRANT_URL")
api_key = os.getenv("QDRANT_API_KEY")

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

BATCH_SIZE = 64

# Stable namespace for deterministic Qdrant point IDs.
POINT_NAMESPACE = uuid.UUID(
    "b6a48a0a-6c4b-4e98-91c3-7b16c9b8a2f1"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)

logger = logging.getLogger(__name__)


def get_embeddings():
    """Load the same embedding model used by the existing RAG pipeline."""

    logger.info("Loading embedding model: %s", EMBEDDING_MODEL)

    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def get_point_id(source, page, start_index, text):
    """
    Generate a deterministic UUID for each document chunk.

    Identical chunks produce identical IDs across workflow runs.
    """

    identity = f"{source}|{page}|{start_index}|{text}"

    return str(
        uuid.uuid5(POINT_NAMESPACE, identity)
    )


def get_source_filter(source):
    """Build a Qdrant filter for one source document."""

    return models.Filter(
        must=[
            models.FieldCondition(
                key="metadata.source",
                match=models.MatchValue(value=source),
            )
        ]
    )


def get_existing_sources(client):
    """Read all source names currently stored in Qdrant."""

    sources = set()
    offset = None

    while True:
        points, offset = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=500,
            offset=offset,
            with_payload=["metadata"],
            with_vectors=False,
        )

        for point in points:
            metadata = point.payload.get("metadata", {}) or {}
            source = metadata.get("source")

            if source:
                sources.add(source)

        if offset is None:
            break

    return sources


def delete_source_points(client, source, keep_ids=None):
    """
    Delete obsolete chunks belonging to one source.

    When keep_ids is supplied, current chunks are preserved.
    """

    keep_ids = set(keep_ids or [])
    obsolete_ids = []
    offset = None

    while True:
        points, offset = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=get_source_filter(source),
            limit=500,
            offset=offset,
            with_payload=False,
            with_vectors=False,
        )

        for point in points:
            if str(point.id) not in keep_ids:
                obsolete_ids.append(point.id)

        if offset is None:
            break

    if obsolete_ids:
        client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=models.PointIdsList(
                points=obsolete_ids
            ),
            wait=True,
        )

        logger.info(
            "Deleted %d obsolete chunks for %s",
            len(obsolete_ids),
            source,
        )


def upload_document_chunks(client, embeddings, source, chunks):
    """Embed and synchronize all chunks belonging to one PDF."""

    if not chunks:
        raise ValueError(
            f"No chunks generated for {source}. "
            "Existing Cloud data will be preserved."
        )

    current_ids = []

    logger.info(
        "Uploading %d chunks for %s",
        len(chunks),
        source,
    )

    for start in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[start:start + BATCH_SIZE]

        texts = [
            chunk["text"]
            for chunk in batch
        ]

        vectors = embeddings.embed_documents(texts)

        points = []

        for chunk, vector in zip(batch, vectors):
            metadata = chunk["metadata"]

            point_id = get_point_id(
                source=metadata["source"],
                page=metadata["page"],
                start_index=metadata["start_index"],
                text=chunk["text"],
            )

            current_ids.append(point_id)

            points.append(
                models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "page_content": chunk["text"],
                        "metadata": metadata,
                    },
                )
            )

        # Upsert first, so existing document chunks remain available
        # until the replacement chunks have been uploaded.
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=points,
            wait=True,
        )

        logger.info(
            "Uploaded %d / %d chunks for %s",
            min(start + BATCH_SIZE, len(chunks)),
            len(chunks),
            source,
        )

    # Remove old chunks that are no longer part of this document.
    delete_source_points(
        client=client,
        source=source,
        keep_ids=current_ids,
    )

    logger.info(
        "Document synchronized: %s | chunks=%d",
        source,
        len(current_ids),
    )


def ensure_payload_indexes(client):
    """Create required Qdrant payload indexes if missing."""

    logger.info("Checking Qdrant payload indexes")

    client.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="metadata.source",
        field_schema=models.PayloadSchemaType.KEYWORD,
        wait=True,
    )

    logger.info("Payload index verified: metadata.source")


def main():
    logger.info("Starting automated Qdrant ingestion")

    if not DOCUMENTS_DIR.exists():
        raise FileNotFoundError(
            f"PDF directory not found: {DOCUMENTS_DIR}"
        )

    pdf_files = sorted(DOCUMENTS_DIR.glob("*.pdf"))

    if not pdf_files:
        raise ValueError(
            f"No PDFs found in {DOCUMENTS_DIR}. "
            "Refusing to synchronize an empty directory."
        )

    current_sources = {
        pdf.name for pdf in pdf_files
    }

    logger.info("PDF files discovered: %d", len(pdf_files))

    # Reuse your existing loader and chunking implementation.
    documents = load_pdf_documents()

    loaded_sources = {
        document["metadata"]["source"]
        for document in documents
    }

    # Never remove existing data if a PDF failed to load.
    failed_sources = current_sources - loaded_sources

    if failed_sources:
        raise RuntimeError(
            "Some PDFs could not be extracted. "
            "Cloud synchronization aborted to protect existing data: "
            + ", ".join(sorted(failed_sources))
        )

    chunks = split_documents(documents)

    if not chunks:
        raise ValueError(
            "No chunks generated. Cloud data will not be modified."
        )

    # Group chunks by PDF source.
    chunks_by_source = defaultdict(list)

    for chunk in chunks:
        source = chunk["metadata"]["source"]
        chunks_by_source[source].append(chunk)

    api_key = __import__("os").environ.get("QDRANT_API_KEY")

    if not api_key:
        raise ValueError("QDRANT_API_KEY is not configured")

    client = QdrantClient(
        url=QDRANT_URL,
        api_key=api_key,
        timeout=60,
    )

    try:
        if not client.collection_exists(COLLECTION_NAME):
            raise ValueError(
                f"Qdrant collection not found: {COLLECTION_NAME}"
            )

        ensure_payload_indexes(client)

        embeddings = get_embeddings()

        # Synchronize new and modified documents.
        for source, source_chunks in chunks_by_source.items():
            upload_document_chunks(
                client=client,
                embeddings=embeddings,
                source=source,
                chunks=source_chunks,
            )

        # Remove documents whose PDFs have been deleted.
        existing_sources = get_existing_sources(client)

        deleted_sources = existing_sources - current_sources

        for source in deleted_sources:
            logger.info(
                "Removing deleted PDF from Cloud: %s",
                source,
            )

            delete_source_points(
                client=client,
                source=source,
            )

        collection_info = client.get_collection(
            COLLECTION_NAME
        )

        logger.info("Ingestion completed successfully")
        logger.info("PDF files: %d", len(pdf_files))
        logger.info("Processed chunks: %d", len(chunks))
        logger.info(
            "Cloud collection points: %s",
            collection_info.points_count,
        )

    finally:
        client.close()


if __name__ == "__main__":
    main()
