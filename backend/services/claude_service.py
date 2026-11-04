
import logging

from pharma_rag.generation.claude_generator import (
    generate_medical_answer,
)

logger = logging.getLogger(__name__)


def get_medical_answer(question, documents):
    """
    Generate a medical knowledge answer using Claude.

    Args:
        question: User's medical question.
        documents: Retrieved LangChain Document objects.

    Returns:
        Dictionary containing answer and source references.
    """

    if not question or not question.strip():
        raise ValueError("Question cannot be empty.")

    logger.info("Generating medical answer using Claude.")

    try:
        result = generate_medical_answer(
            question=question,
            documents=documents,
        )

        return result

    except Exception:
        logger.exception("Claude medical answer generation failed.")
        raise
