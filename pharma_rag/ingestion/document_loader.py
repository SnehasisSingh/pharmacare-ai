
from pathlib import Path
import logging

from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DOCUMENTS_DIR = (
    PROJECT_ROOT
    / "knowledge_base_doc"
    / "sample_documents"
)

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150


def load_pdf_documents():
    """Extract text page by page while preserving source metadata."""
    if not DOCUMENTS_DIR.exists():
        logger.error("Document directory not found: %s", DOCUMENTS_DIR)
        raise FileNotFoundError(
            f"Document directory not found: {DOCUMENTS_DIR}"
        )

    pdf_files = sorted(DOCUMENTS_DIR.glob("*.pdf"))

    if not pdf_files:
        logger.warning("No PDF files found in %s", DOCUMENTS_DIR)
        return []

    documents = []

    for pdf_path in pdf_files:
        logger.info("Processing PDF: %s", pdf_path.name)

        try:
            reader = PdfReader(str(pdf_path))

            if reader.is_encrypted:
                logger.warning("Skipping encrypted PDF: %s", pdf_path.name)
                continue

            for page_number, page in enumerate(reader.pages, start=1):
                try:
                    text = (page.extract_text() or "").strip()
                except Exception:
                    logger.exception(
                        "Text extraction failed for %s, page %d",
                        pdf_path.name,
                        page_number,
                    )
                    continue

                if not text:
                    logger.warning(
                        "No extractable text in %s, page %d",
                        pdf_path.name,
                        page_number,
                    )
                    continue

                documents.append({
                    "text": text,
                    "metadata": {
                        "source": pdf_path.name,
                        "page": page_number,
                    },
                })

        except Exception:
            logger.exception("Failed to process PDF: %s", pdf_path.name)

    logger.info("Extracted text from %d pages", len(documents))
    return documents


def split_documents(documents):
    """Split page text into chunks and preserve source metadata."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        add_start_index=True,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks = []

    for document in documents:
        split_texts = splitter.split_text(document["text"])

        for chunk in split_texts:
            start_index = document["text"].find(chunk)

            chunks.append({
                "text": chunk,
                "metadata": {
                    **document["metadata"],
                    "start_index": start_index,
                },
            })

    logger.info("Created %d text chunks", len(chunks))
    return chunks


def main():
    logger.info("Starting medical PDF ingestion")
    logger.info("Document directory: %s", DOCUMENTS_DIR)

    documents = load_pdf_documents()

    if not documents:
        logger.warning("Ingestion finished without readable page text")
        return

    chunks = split_documents(documents)

    logger.info(
        "Ingestion completed: pages=%d, chunks=%d",
        len(documents),
        len(chunks),
    )

    if chunks:
        first_chunk = chunks[0]
        logger.info(
            "First chunk preview: source=%s, page=%s, characters=%d",
            first_chunk["metadata"]["source"],
            first_chunk["metadata"]["page"],
            len(first_chunk["text"]),
        )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    main()
