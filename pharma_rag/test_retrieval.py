
import logging

from retrieval.vector_store import search_medical_documents

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)

logger = logging.getLogger(__name__)

TEST_QUERIES = [
    "What are the warning signs of a heart attack?",
    "What are the common symptoms and treatments for diabetes?",
    "What are the symptoms of skin infections?",
    "What are the warning signs of a stroke?",
    "What causes stomach ulcers and what are their symptoms?",
    "What are the symptoms of PCOS in women?",
]


def run_retrieval_tests():
    logger.info("=" * 70)
    logger.info("PHARMACARE AI - QDRANT RETRIEVAL EVALUATION")
    logger.info("=" * 70)

    for test_number, query in enumerate(TEST_QUERIES, start=1):

        logger.info("")
        logger.info("-" * 70)
        logger.info("TEST %d | Query: %s", test_number, query)
        logger.info("-" * 70)

        try:
            results = search_medical_documents(query, k=4)

            if not results:
                logger.warning("No relevant documents retrieved")
                continue

            for rank, document in enumerate(results, start=1):
                metadata = document.metadata

                logger.info(
                    "Result %d | Source: %s | Page: %s",
                    rank,
                    metadata.get("source", "unknown"),
                    metadata.get("page", "unknown"),
                )

                logger.info(
                    "Passage: %.400s",
                    document.page_content.replace("\n", " "),
                )

        except Exception:
            logger.exception(
                "Retrieval failed for query: %s",
                query,
            )

    logger.info("")
    logger.info("=" * 70)
    logger.info("RETRIEVAL EVALUATION COMPLETED")
    logger.info("=" * 70)


if __name__ == "__main__":
    run_retrieval_tests()
