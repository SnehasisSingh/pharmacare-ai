
import logging

from retrieval.vector_store import search_medical_documents

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)

logger = logging.getLogger(__name__)


def main():
    query = "What are the warning signs of a heart attack?"

    logger.info("Testing medical semantic search")
    logger.info("Query: %s", query)

    results = search_medical_documents(query, k=4)

    if not results:
        logger.warning("No relevant documents retrieved")
        return

    for rank, document in enumerate(results, start=1):
        metadata = document.metadata

        logger.info(
            "Result %d | Source: %s | Page: %s",
            rank,
            metadata.get("source", "unknown"),
            metadata.get("page", "unknown"),
        )

        logger.info(
            "Retrieved passage: %.500s",
            document.page_content.replace("\n", " "),
        )


if __name__ == "__main__":
    main()
