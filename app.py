"""
app.py
------
FastAPI entrypoint for the AI Customer Support System (Phase 1).

Why this file exists:
- The only HTTP-facing file in the project. It wires up the
  `/detect-intent` endpoint and delegates all classification logic to
  `agents/intent_agent.py`.
- Handles exceptions at the API boundary and translates internal
  errors into clean HTTP responses instead of leaking stack traces.

Run with:
    uvicorn app:app --reload
"""

import logging

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse

from agents.intent_agent import IntentAgentError, intent_agent
from schemas import IntentResponse, QueryRequest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("customer_support")

app = FastAPI(
    title="AI Customer Support System - Intent Detection Agent",
    description="Phase 1: classifies a customer query into a predefined intent.",
    version="1.0.0",
)


@app.get("/health", tags=["Health"])
def health_check() -> dict:
    """Basic liveness check."""
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def test_page() -> str:
    """
    A minimal, dependency-free HTML page for manually testing the
    /detect-intent endpoint without needing Swagger UI or curl.
    """
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Intent Detection - Test</title>
        <style>
            body { font-family: sans-serif; max-width: 600px; margin: 60px auto; padding: 0 20px; }
            h2 { margin-bottom: 4px; }
            p.sub { color: #666; margin-top: 0; }
            input { width: 100%; padding: 10px; font-size: 16px; box-sizing: border-box; }
            button { margin-top: 10px; padding: 10px 20px; font-size: 16px; cursor: pointer; }
            #result { margin-top: 20px; padding: 15px; background: #f0f0f0; border-radius: 6px;
                       font-size: 18px; display: none; }
            #result.error { background: #fdecea; color: #b00020; }
        </style>
    </head>
    <body>
        <h2>Intent Detection Agent</h2>
        <p class="sub">Type a customer query and see which intent it's classified as.</p>

        <input id="queryInput" type="text" placeholder="e.g. Where is my order?" />
        <button onclick="detectIntent()">Detect Intent</button>

        <div id="result"></div>

        <script>
            async function detectIntent() {
                const query = document.getElementById('queryInput').value;
                const resultBox = document.getElementById('result');
                resultBox.style.display = 'block';
                resultBox.className = '';
                resultBox.textContent = 'Detecting...';

                try {
                    const response = await fetch('/detect-intent', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ query: query })
                    });
                    const data = await response.json();

                    if (!response.ok) {
                        resultBox.className = 'error';
                        resultBox.textContent = 'Error: ' + (data.detail || 'Something went wrong');
                        return;
                    }

                    resultBox.textContent = 'Intent: ' + data.intent;
                } catch (err) {
                    resultBox.className = 'error';
                    resultBox.textContent = 'Error: ' + err.message;
                }
            }

            document.getElementById('queryInput').addEventListener('keydown', function(e) {
                if (e.key === 'Enter') detectIntent();
            });
        </script>
    </body>
    </html>
    """


@app.post(
    "/detect-intent",
    response_model=IntentResponse,
    tags=["Intent Detection"],
)
def detect_intent(payload: QueryRequest) -> IntentResponse:
    """
    Classify a customer query into one predefined intent.

    Request body:
        { "query": "Where is my order?" }

    Response body:
        { "intent": "order_status" }
    """
    try:
        result = intent_agent.detect_intent(payload.query)
        return IntentResponse(intent=result.intent)

    except IntentAgentError as exc:
        logger.error("Intent agent failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to classify the query. Please try again.",
        ) from exc

    except Exception as exc:  # noqa: BLE001 - final safety net
        logger.exception("Unexpected error in /detect-intent")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        ) from exc