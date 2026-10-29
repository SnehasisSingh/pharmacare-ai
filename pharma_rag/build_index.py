
import logging
import importlib.util
from pathlib import Path

from retrieval.vector_store import create_vector_store

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INGESTION_FILE = PROJECT_ROOT / "pharma_rag" / "ingestion" / "document_loader.py"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    spec = importlib.util.spec_from_file_location(
        "document_loader", INGESTION_FILE
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    pages = module.load_pdf_documents()
    chunks = module.split_documents(pages)

    vector_store = create_vector_store(chunks)

    logger.info("FAISS index built successfully")
    logger.info("Indexed chunks: %d", len(chunks))


if __name__ == "__main__":
    main()
