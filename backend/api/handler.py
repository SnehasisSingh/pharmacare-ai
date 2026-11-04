
import json
import logging

from backend.workflows.rag_workflow import run_medical_rag


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}


def response(status_code, body):
    """Create an API Gateway-compatible response."""

    return {
        "statusCode": status_code,
        "headers": HEADERS,
        "body": json.dumps(body, default=str),
    }


def lambda_handler(event, context):
    """AWS Lambda entry point for PharmaCare AI."""

    try:
        http_method = (
            event.get("httpMethod")
            or event.get("requestContext", {})
                .get("http", {})
                .get("method")
            or "GET"
        )

        path = event.get("path") or event.get("rawPath", "")

        if http_method == "OPTIONS":
            return response(200, {"message": "CORS preflight successful"})

        if http_method == "GET" and path.rstrip("/") == "/health":
            return response(
                200,
                {
                    "message": "PharmaCare AI API is running",
                    "module": "Medical RAG",
                    "status": "healthy",
                },
            )

        if http_method == "POST" and path.rstrip("/") == "/medical/ask":

            raw_body = event.get("body")

            if isinstance(raw_body, str):
                body = json.loads(raw_body or "{}")
            elif isinstance(raw_body, dict):
                body = raw_body
            else:
                body = {}

            question = body.get("question", "")

            if not isinstance(question, str) or not question.strip():
                return response(
                    400,
                    {"error": "A valid question is required."},
                )

            logger.info("Received medical RAG request.")

            result = run_medical_rag(question.strip())

            return response(200, result)

        return response(
            404,
            {"error": "Endpoint not found."},
        )

    except json.JSONDecodeError:
        return response(400, {"error": "Invalid JSON request body."})

    except ValueError as exc:
        logger.warning("Invalid request: %s", exc)
        return response(400, {"error": str(exc)})

    except Exception:
        logger.exception("PharmaCare API request failed.")

        return response(
            500,
            {"error": "Unable to process the medical question."},
        )
