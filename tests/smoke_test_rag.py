
import logging
import sys

from backend.workflows.rag_workflow import run_medical_rag


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)

logger = logging.getLogger(__name__)


def main():
    question = "What are the common symptoms of high cholesterol?"

    logger.info("Starting PharmaCare RAG integration test.")

    result = run_medical_rag(question)

    answer = result.get("answer", "")
    sources = result.get("sources", [])

    if not answer or not answer.strip():
        raise RuntimeError("RAG workflow returned an empty answer.")

    if not sources:
        raise RuntimeError("RAG workflow returned no source references.")

    logger.info("RAG integration test passed.")
    logger.info("Question: %s", question)
    logger.info("Answer received successfully.")
    logger.info("Number of source references: %d", len(sources))

    print("\n========== PHARMACARE RAG TEST ==========")
    print("Status: PASSED")
    print("Question:", question)
    print("\nAnswer:\n", answer)
    print("\nSources:\n", sources)
    print("==========================================")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("PharmaCare RAG integration test failed.")
        sys.exit(1)
