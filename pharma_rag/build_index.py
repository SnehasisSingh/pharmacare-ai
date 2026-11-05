
import logging
import importlib.util
import sys
from pathlib import Path

# from retrieval.vector_store import create_vector_store

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PHARMA_RAG_DIR = Path(__file__).resolve().parent
INGESTION_FILE = PHARMA_RAG_DIR / "ingestion" / "document_loader.py"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)

logger = logging.getLogger(__name__)


def main():
    logger.info("Starting PharmaCare Qdrant indexing")

    if not INGESTION_FILE.exists():
        raise FileNotFoundError(
            f"Document loader not found: {INGESTION_FILE}"
        )

    sys.path.insert(0, str(PHARMA_RAG_DIR))

    spec = importlib.util.spec_from_file_location(
        "document_loader",
        INGESTION_FILE,
    )

    if spec is None or spec.loader is None:
        raise ImportError(
            f"Unable to load document loader: {INGESTION_FILE}"
        )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    pages = module.load_pdf_documents()
    chunks = module.split_documents(pages)

    logger.info("Total chunks: %d", len(chunks))

    # Inspect actual chunk structure before indexing.
    if chunks:
        first_chunk = chunks[0]

        logger.info("Chunk type: %s", type(first_chunk).__name__)

        if isinstance(first_chunk, dict):
            logger.info("Chunk keys: %s", list(first_chunk.keys()))

            for key, value in first_chunk.items():
                logger.info(
                    "Key: %s | Type: %s | Preview: %.200s",
                    key,
                    type(value).__name__,
                    str(value),
                )

        else:
            logger.info("First chunk preview: %.200s", str(first_chunk))

    if not chunks:
        logger.warning("No chunks available for indexing")
        return

    # create_vector_store(chunks)

    logger.info("Qdrant index build process completed")


if __name__ == "__main__":
    main()
