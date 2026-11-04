
import logging

from typing import TypedDict, List, Dict, Any

from langgraph.graph import StateGraph, START, END

from pharma_rag.retrieval.vector_store import (
    search_medical_documents,
)

from backend.services.claude_service import (
    get_medical_answer,
)


logger = logging.getLogger(__name__)


class RAGState(TypedDict, total=False):
    question: str
    documents: List[Any]
    answer: str
    sources: List[Dict[str, Any]]
    error: str


def retrieve_documents(state: RAGState) -> dict:
    """Retrieve relevant medical documents from Qdrant Cloud."""

    question = state.get("question", "")

    if not question.strip():
        raise ValueError("Question cannot be empty.")

    logger.info("Starting Qdrant document retrieval.")

    documents = search_medical_documents(
        query=question,
        k=4,
    )

    logger.info(
        "Retrieved %d relevant medical documents.",
        len(documents),
    )

    return {"documents": documents}


def generate_answer(state: RAGState) -> dict:
    """Generate an educational medical answer using Claude."""

    question = state["question"]
    documents = state.get("documents", [])

    logger.info("Starting Claude answer generation.")

    result = get_medical_answer(
        question=question,
        documents=documents,
    )

    return {
        "answer": result["answer"],
        "sources": result.get("sources", []),
    }


def build_rag_graph():
    """Build the LangGraph RAG workflow."""

    workflow = StateGraph(RAGState)

    workflow.add_node("retrieve", retrieve_documents)
    workflow.add_node("generate", generate_answer)

    workflow.add_edge(START, "retrieve")
    workflow.add_edge("retrieve", "generate")
    workflow.add_edge("generate", END)

    return workflow.compile()


rag_app = build_rag_graph()


def run_medical_rag(question: str) -> dict:
    """Execute the complete medical RAG workflow."""

    if not question or not question.strip():
        raise ValueError("Question cannot be empty.")

    logger.info("Executing PharmaCare RAG workflow.")

    result = rag_app.invoke({
        "question": question.strip(),
    })

    return {
        "question": question,
        "answer": result["answer"],
        "sources": result.get("sources", []),
    }
