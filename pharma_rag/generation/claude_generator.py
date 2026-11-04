
import os
import logging

from anthropic import Anthropic, APIError


logger = logging.getLogger(__name__)

MODEL_NAME = os.getenv("CLAUDE_MODEL", "claude-haiku-5-5")

SYSTEM_PROMPT = """
You are PharmaCare AI, a medical knowledge assistant.

Your role is to provide educational medical information using
the supplied knowledge-base context.

STRICT RULES:

1. Answer using only the supplied medical context.
2. Do not invent medical facts or unsupported information.
3. Do not independently diagnose medical conditions.
4. Do not prescribe medicines or recommend dosages.
5. If the context does not contain sufficient information,
   clearly communicate that limitation.
6. Encourage users to consult qualified healthcare professionals.
7. If the question describes potentially life-threatening
   symptoms, advise immediate emergency medical assistance.
8. Include source document names and page numbers wherever
   relevant.
9. Clearly distinguish general educational information
   from professional medical advice.

The current knowledge base is synthetic educational test data.
It is not clinically validated and must not be used for
real-world diagnosis or treatment.
"""


def generate_medical_answer(question, documents):

    if not question or not question.strip():
        raise ValueError("Question cannot be empty.")

    if not documents:
        return {
            "answer": (
                "I could not find relevant information in the "
                "medical knowledge base. Please consult a "
                "qualified healthcare professional."
            ),
            "sources": []
        }

    context_parts = []
    sources = []

    for index, document in enumerate(documents, start=1):

        metadata = document.metadata or {}

        source = metadata.get("source", "Unknown source")
        page = metadata.get("page", "Unknown page")

        context_parts.append(
            f"""
            Context {index}
            Source: {source}
            Page: {page}

            {document.page_content}
            """
        )

        sources.append({
            "source": source,
            "page": page
        })

    context = "\n\n".join(context_parts)

    user_prompt = f"""
    Medical knowledge-base context:

    {context}

    User question:
    {question}

    Provide a clear educational answer based strictly
    on the supplied context.

    Mention the relevant source and page numbers.
    If the context is insufficient, say so explicitly.
    """

    try:

        client = Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            max_retries=0,
            timeout=30.0
        )

        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=500,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": user_prompt
                }
            ]
        )

        answer = "\n".join(
            block.text
            for block in response.content
            if block.type == "text"
        )

        logger.info(
            "Claude answer generated successfully. "
            "Input tokens: %s, Output tokens: %s",
            response.usage.input_tokens,
            response.usage.output_tokens
        )

        return {
            "answer": answer,
            "sources": sources
        }

    except APIError:
        logger.exception("Claude API request failed.")
        raise

    except Exception:
        logger.exception("Unexpected answer-generation error.")
        raise
