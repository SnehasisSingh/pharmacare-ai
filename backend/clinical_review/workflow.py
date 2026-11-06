"""LangGraph draft preparation; durable approval gate is stored in DynamoDB.

This is an asynchronous handoff, NOT a LangGraph interrupt/checkpointer.
"""
from typing import TypedDict, Any
from langgraph.graph import StateGraph, START, END
from backend.workflows.rag_workflow import retrieve_documents, generate_answer

# Simple safety screening is only a supplemental warning, not clinical triage.
RED_FLAGS = ('difficulty breathing', 'severe chest pain', 'unconscious', 'seizure', 'stiff neck', 'confusion', 'heavy bleeding')
class CaseState(TypedDict, total=False):
    question: str
    documents: list[Any]
    answer: str
    sources: list[dict]
    emergency_warning: bool

def screen(state: CaseState):
    question = state['question'].lower()
    return {'emergency_warning': any(phrase in question for phrase in RED_FLAGS)}

def build():
    graph = StateGraph(CaseState)
    graph.add_node('screen', screen)
    graph.add_node('retrieve', retrieve_documents)
    graph.add_node('generate', generate_answer)
    graph.add_edge(START, 'screen')
    graph.add_edge('screen', 'retrieve')
    graph.add_edge('retrieve', 'generate')
    graph.add_edge('generate', END)
    return graph.compile()

case_graph = build()
