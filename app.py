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

from agents.database_agent import DatabaseAgentError, database_agent
from agents.intent_agent import IntentAgentError, intent_agent
from agents.response_agent import ResponseAgentError, response_agent
from schemas import (
    CustomerRequest,
    CustomerResponse,
    IntentResponse,
    PolicyRequest,
    PolicyResponse,
    QueryRequest,
    ResponseGenerationRequest,
    ResponseGenerationResult,
)

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
    A self-contained console for manually testing /detect-intent and
    /customer without needing Swagger UI or curl.
    """
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>customer_support :: agent console</title>
    <style>
        :root {
            --bg: #0a0c10;
            --panel: #12151b;
            --border: #232a35;
            --text: #d7dee8;
            --text-dim: #6b7688;
            --cyan: #4fd6c4;
            --amber: #e8a33d;
            --red: #e5484d;
            --font-mono: ui-monospace, "SF Mono", "JetBrains Mono", "Fira Code", Menlo, Consolas, monospace;
        }
        * { box-sizing: border-box; }
        body {
            background: var(--bg);
            color: var(--text);
            font-family: var(--font-mono);
            margin: 0;
            padding: 40px 20px 80px;
            min-height: 100vh;
        }
        .wrap { max-width: 880px; margin: 0 auto; }

        .titlebar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 12px 18px;
            border: 1px solid var(--border);
            border-radius: 8px 8px 0 0;
            background: linear-gradient(180deg, #161a22, #12151b);
        }
        .dots { display: flex; gap: 7px; }
        .dot { width: 11px; height: 11px; border-radius: 50%; }
        .dot.red { background: #3a2226; border: 1px solid var(--red); }
        .dot.amber { background: #3a2f1c; border: 1px solid var(--amber); }
        .dot.green { background: #1c3a30; border: 1px solid var(--cyan); }
        .path { color: var(--text-dim); font-size: 13px; letter-spacing: 0.02em; }

        .status {
            display: flex; align-items: center; gap: 7px; font-size: 12px; color: var(--text-dim);
        }
        .status .led { width: 8px; height: 8px; border-radius: 50%; background: var(--text-dim); }
        .status .led.up { background: var(--cyan); box-shadow: 0 0 8px var(--cyan); }
        .status .led.down { background: var(--red); box-shadow: 0 0 8px var(--red); }

        .hero {
            border: 1px solid var(--border);
            border-top: none;
            padding: 22px;
            background: var(--panel);
        }
        .hero h1 {
            margin: 0 0 4px;
            font-size: 20px;
            font-weight: 600;
            color: var(--text);
        }
        .hero h1 .prompt { color: var(--cyan); }
        .hero p { margin: 0; color: var(--text-dim); font-size: 13px; }

        .grid {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 16px;
            margin-top: 16px;
        }
        @media (max-width: 980px) {
            .grid { grid-template-columns: 1fr 1fr; }
        }
        @media (max-width: 640px) {
            .grid { grid-template-columns: 1fr; }
        }

        .card {
            border: 1px solid var(--border);
            border-radius: 8px;
            background: var(--panel);
            overflow: hidden;
        }
        .card-head {
            padding: 10px 16px;
            border-bottom: 1px solid var(--border);
            font-size: 12px;
            color: var(--text-dim);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .card-head .method {
            color: var(--cyan);
            font-weight: 600;
        }
        .card-body { padding: 16px; }

        label {
            display: block;
            font-size: 11px;
            color: var(--text-dim);
            margin-bottom: 6px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .input-row { display: flex; gap: 8px; margin-bottom: 4px; }
        input[type="text"], input[type="number"] {
            flex: 1;
            background: #0d1015;
            border: 1px solid var(--border);
            color: var(--text);
            font-family: var(--font-mono);
            font-size: 13px;
            padding: 10px 12px;
            border-radius: 6px;
            outline: none;
        }
        input:focus {
            border-color: var(--cyan);
        }
        input::placeholder { color: #3d4451; }

        button {
            background: #16211f;
            border: 1px solid var(--cyan);
            color: var(--cyan);
            font-family: var(--font-mono);
            font-size: 13px;
            padding: 10px 16px;
            border-radius: 6px;
            cursor: pointer;
            white-space: nowrap;
        }
        button:hover { background: #1c2d2a; }
        button:active { transform: translateY(1px); }
        button:disabled { opacity: 0.5; cursor: default; }

        .output {
            margin-top: 12px;
            background: #0d1015;
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 12px;
            font-size: 12.5px;
            min-height: 42px;
            white-space: pre-wrap;
            word-break: break-word;
            color: var(--text-dim);
        }
        .output.ok { color: var(--cyan); border-color: #1c3a30; }
        .output.err { color: var(--red); border-color: #3a2226; }
        .output .cursor {
            display: inline-block;
            width: 7px; height: 13px;
            background: var(--cyan);
            margin-left: 2px;
            animation: blink 1s step-start infinite;
            vertical-align: text-bottom;
        }
        @keyframes blink { 50% { opacity: 0; } }

        .examples { margin-top: 10px; display: flex; flex-wrap: wrap; gap: 6px; }
        .chip {
            font-size: 11px;
            color: var(--text-dim);
            border: 1px solid var(--border);
            padding: 4px 9px;
            border-radius: 20px;
            cursor: pointer;
        }
        .chip:hover { border-color: var(--cyan); color: var(--cyan); }

        .footer {
            margin-top: 18px;
            text-align: center;
            font-size: 11px;
            color: #3d4451;
        }
    </style>
    </head>
    <body>
    <div class="wrap">

        <div class="titlebar">
            <div class="dots">
                <span class="dot red"></span>
                <span class="dot amber"></span>
                <span class="dot green"></span>
            </div>
            <span class="path">~/customer_support</span>
            <span class="status"><span id="healthLed" class="led"></span><span id="healthText">checking</span></span>
        </div>

        <div class="hero">
            <h1><span class="prompt">$</span> agent-console</h1>
            <p>Send a query straight to the Intent Agent, or pull a customer record straight from the Database Agent.</p>
        </div>

        <div class="grid">

            <div class="card">
                <div class="card-head">
                    <span><span class="method">POST</span> /detect-intent</span>
                    <span>intent agent</span>
                </div>
                <div class="card-body">
                    <label for="queryInput">customer query</label>
                    <div class="input-row">
                        <input id="queryInput" type="text" placeholder="Where is my order?" />
                        <button id="intentBtn" onclick="detectIntent()">run</button>
                    </div>
                    <div class="examples">
                        <span class="chip" onclick="fillQuery('What is your refund policy?')">refund policy</span>
                        <span class="chip" onclick="fillQuery('Cancel my order')">cancellation</span>
                        <span class="chip" onclick="fillQuery('Hi there')">greeting</span>
                    </div>
                    <div id="intentOutput" class="output">awaiting input&hellip;</div>
                </div>
            </div>

            <div class="card">
                <div class="card-head">
                    <span><span class="method">POST</span> /policy</span>
                    <span>database agent</span>
                </div>
                <div class="card-body">
                    <label for="policyInput">policy_type</label>
                    <div class="input-row">
                        <input id="policyInput" type="text" placeholder="refund_policy" />
                        <button id="policyBtn" onclick="lookupPolicy()">run</button>
                    </div>
                    <div class="examples">
                        <span class="chip" onclick="fillPolicy('refund_policy')">refund</span>
                        <span class="chip" onclick="fillPolicy('return_policy')">return</span>
                        <span class="chip" onclick="fillPolicy('cancellation_policy')">cancellation</span>
                        <span class="chip" onclick="fillPolicy('shipping_policy')">shipping</span>
                    </div>
                    <div id="policyOutput" class="output">awaiting input&hellip;</div>
                </div>
            </div>

            <div class="card">
                <div class="card-head">
                    <span><span class="method">POST</span> /customer</span>
                    <span>database agent</span>
                </div>
                <div class="card-body">
                    <label for="customerInput">customer_id</label>
                    <div class="input-row">
                        <input id="customerInput" type="number" placeholder="101" />
                        <button id="customerBtn" onclick="lookupCustomer()">run</button>
                    </div>
                    <div class="examples">
                        <span class="chip" onclick="fillCustomer(101)">101</span>
                        <span class="chip" onclick="fillCustomer(115)">115</span>
                        <span class="chip" onclick="fillCustomer(999)">999 (missing)</span>
                    </div>
                    <div id="customerOutput" class="output">awaiting input&hellip;</div>
                </div>
            </div>

        </div>

        <div class="card" style="margin-top: 16px;">
            <div class="card-head">
                <span><span class="method">POST</span> /generate-response</span>
                <span>response agent</span>
            </div>
            <div class="card-body">
                <label for="genQueryInput">customer query</label>
                <input id="genQueryInput" type="text" placeholder="What is your refund policy?" style="margin-bottom: 10px;" />

                <label for="genIntentInput">intent</label>
                <input id="genIntentInput" type="text" placeholder="refund_policy" style="margin-bottom: 10px;" />

                <label for="genDataInput">retrieved_data (JSON)</label>
                <textarea id="genDataInput" rows="3" placeholder='{"policy_type": "refund_policy", "title": "Refund Policy", "content": "..."}'
                    style="width: 100%; background: #0d1015; border: 1px solid var(--border); color: var(--text);
                           font-family: var(--font-mono); font-size: 13px; padding: 10px 12px; border-radius: 6px;
                           outline: none; resize: vertical; margin-bottom: 4px;"></textarea>

                <div style="display: flex; justify-content: flex-end; margin-top: 8px;">
                    <button id="genBtn" onclick="generateResponse()">run</button>
                </div>

                <div class="examples">
                    <span class="chip" onclick="fillGenExample()">fill refund policy example</span>
                </div>

                <div id="genOutput" class="output">awaiting input&hellip;</div>
            </div>
        </div>

        <div class="footer">AI Customer Support System &middot; Phase 1 + Phase 2 + Phase 3 + Phase 4</div>
    </div>

    <script>
        async function checkHealth() {
            const led = document.getElementById('healthLed');
            const text = document.getElementById('healthText');
            try {
                const res = await fetch('/health');
                if (res.ok) {
                    led.className = 'led up';
                    text.textContent = 'online';
                } else {
                    throw new Error();
                }
            } catch {
                led.className = 'led down';
                text.textContent = 'offline';
            }
        }
        checkHealth();

        function fillQuery(text) {
            document.getElementById('queryInput').value = text;
            detectIntent();
        }
        function fillCustomer(id) {
            document.getElementById('customerInput').value = id;
            lookupCustomer();
        }
        function fillPolicy(type) {
            document.getElementById('policyInput').value = type;
            lookupPolicy();
        }

        async function detectIntent() {
            const query = document.getElementById('queryInput').value.trim();
            const out = document.getElementById('intentOutput');
            const btn = document.getElementById('intentBtn');
            if (!query) { out.className = 'output err'; out.textContent = 'error: query cannot be empty'; return; }

            btn.disabled = true;
            out.className = 'output';
            out.innerHTML = 'running<span class="cursor"></span>';

            try {
                const res = await fetch('/detect-intent', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query })
                });
                const data = await res.json();
                if (!res.ok) {
                    out.className = 'output err';
                    out.textContent = 'error: ' + (data.detail || 'request failed');
                } else {
                    out.className = 'output ok';
                    out.textContent = JSON.stringify(data, null, 2);
                }
            } catch (err) {
                out.className = 'output err';
                out.textContent = 'error: ' + err.message;
            } finally {
                btn.disabled = false;
            }
        }

        async function lookupCustomer() {
            const idVal = document.getElementById('customerInput').value.trim();
            const out = document.getElementById('customerOutput');
            const btn = document.getElementById('customerBtn');
            if (!idVal) { out.className = 'output err'; out.textContent = 'error: customer_id cannot be empty'; return; }

            btn.disabled = true;
            out.className = 'output';
            out.innerHTML = 'running<span class="cursor"></span>';

            try {
                const res = await fetch('/customer', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ customer_id: parseInt(idVal, 10) })
                });
                const data = await res.json();
                if (!res.ok) {
                    out.className = 'output err';
                    out.textContent = 'error: ' + (data.detail || 'request failed');
                } else {
                    out.className = 'output ok';
                    out.textContent = JSON.stringify(data, null, 2);
                }
            } catch (err) {
                out.className = 'output err';
                out.textContent = 'error: ' + err.message;
            } finally {
                btn.disabled = false;
            }
        }

        async function lookupPolicy() {
            const policyType = document.getElementById('policyInput').value.trim();
            const out = document.getElementById('policyOutput');
            const btn = document.getElementById('policyBtn');
            if (!policyType) { out.className = 'output err'; out.textContent = 'error: policy_type cannot be empty'; return; }

            btn.disabled = true;
            out.className = 'output';
            out.innerHTML = 'running<span class="cursor"></span>';

            try {
                const res = await fetch('/policy', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ policy_type: policyType })
                });
                const data = await res.json();
                if (!res.ok) {
                    out.className = 'output err';
                    out.textContent = 'error: ' + (data.detail || 'request failed');
                } else {
                    out.className = 'output ok';
                    out.textContent = JSON.stringify(data, null, 2);
                }
            } catch (err) {
                out.className = 'output err';
                out.textContent = 'error: ' + err.message;
            } finally {
                btn.disabled = false;
            }
        }

        document.getElementById('queryInput').addEventListener('keydown', e => { if (e.key === 'Enter') detectIntent(); });
        document.getElementById('customerInput').addEventListener('keydown', e => { if (e.key === 'Enter') lookupCustomer(); });
        document.getElementById('policyInput').addEventListener('keydown', e => { if (e.key === 'Enter') lookupPolicy(); });

        function fillGenExample() {
            document.getElementById('genQueryInput').value = 'What is your refund policy?';
            document.getElementById('genIntentInput').value = 'refund_policy';
            document.getElementById('genDataInput').value = JSON.stringify({
                policy_type: 'refund_policy',
                title: 'Refund Policy',
                content: 'We offer a full refund within 30 days of delivery for items in their original condition.'
            }, null, 2);
        }

        async function generateResponse() {
            const query = document.getElementById('genQueryInput').value.trim();
            const intent = document.getElementById('genIntentInput').value.trim();
            const dataRaw = document.getElementById('genDataInput').value.trim();
            const out = document.getElementById('genOutput');
            const btn = document.getElementById('genBtn');

            if (!query || !intent || !dataRaw) {
                out.className = 'output err';
                out.textContent = 'error: query, intent, and retrieved_data are all required';
                return;
            }

            let retrieved_data;
            try {
                retrieved_data = JSON.parse(dataRaw);
            } catch (err) {
                out.className = 'output err';
                out.textContent = 'error: retrieved_data must be valid JSON';
                return;
            }

            btn.disabled = true;
            out.className = 'output';
            out.innerHTML = 'running<span class="cursor"></span>';

            try {
                const res = await fetch('/generate-response', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query, intent, retrieved_data })
                });
                const data = await res.json();
                if (!res.ok) {
                    out.className = 'output err';
                    out.textContent = 'error: ' + (data.detail || 'request failed');
                } else {
                    out.className = 'output ok';
                    out.textContent = data.response;
                }
            } catch (err) {
                out.className = 'output err';
                out.textContent = 'error: ' + err.message;
            } finally {
                btn.disabled = false;
            }
        }
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


# ---------------------------------------------------------------------------
# Phase 2: Database Agent testing endpoint
# ---------------------------------------------------------------------------


@app.post(
    "/customer",
    response_model=CustomerResponse,
    tags=["Database"],
)
def get_customer(payload: CustomerRequest) -> CustomerResponse:
    """
    Look up a customer by customer_id. Exists purely to exercise the
    Database Agent independently of the intent/LLM layer.

    Request body:
        { "customer_id": 101 }

    Response body:
        { "customer_id": 101, "first_name": "John", "last_name": "Doe", "email": "john@gmail.com" }
    """
    try:
        customer = database_agent.get_customer(payload.customer_id)

        if customer is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No customer found with customer_id={payload.customer_id}",
            )

        return CustomerResponse(**customer)

    except DatabaseAgentError as exc:
        logger.error("Database agent failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to retrieve customer data. Please try again.",
        ) from exc

    except HTTPException:
        raise

    except Exception as exc:  # noqa: BLE001 - final safety net
        logger.exception("Unexpected error in /customer")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        ) from exc


# ---------------------------------------------------------------------------
# Phase 3: Policies data layer testing endpoint
# ---------------------------------------------------------------------------


@app.post(
    "/policy",
    response_model=PolicyResponse,
    tags=["Database"],
)
def get_policy(payload: PolicyRequest) -> PolicyResponse:
    """
    Look up a company policy by policy_type. Exists purely to
    exercise the Database Agent's policy lookup independently of the
    intent/LLM layer.

    Request body:
        { "policy_type": "refund_policy" }

    Response body:
        { "policy_type": "refund_policy", "title": "Refund Policy", "content": "...", "updated_at": null }
    """
    try:
        policy = database_agent.get_policy(payload.policy_type)

        if policy is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No policy found with policy_type={payload.policy_type}",
            )

        return PolicyResponse(**policy)

    except DatabaseAgentError as exc:
        logger.error("Database agent failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to retrieve policy data. Please try again.",
        ) from exc

    except HTTPException:
        raise

    except Exception as exc:  # noqa: BLE001 - final safety net
        logger.exception("Unexpected error in /policy")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        ) from exc


# ---------------------------------------------------------------------------
# Phase 4: Response Generator Agent testing endpoint
# ---------------------------------------------------------------------------


@app.post(
    "/generate-response",
    response_model=ResponseGenerationResult,
    tags=["Response Generation"],
)
def generate_response(payload: ResponseGenerationRequest) -> ResponseGenerationResult:
    """
    Generate a customer-facing reply from a query, intent, and
    previously retrieved data. Exists to test the Response Agent in
    isolation, before it's wired into the full pipeline (Phase 5).

    Request body:
        {
          "query": "What is your refund policy?",
          "intent": "refund_policy",
          "retrieved_data": {"policy_type": "refund_policy", "title": "Refund Policy", "content": "..."}
        }

    Response body:
        { "response": "Thanks for reaching out! We offer a full refund within 30 days..." }
    """
    try:
        reply = response_agent.generate_response(
            query=payload.query,
            intent=payload.intent,
            retrieved_data=payload.retrieved_data,
        )
        return ResponseGenerationResult(response=reply)

    except ResponseAgentError as exc:
        logger.error("Response agent failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to generate a response. Please try again.",
        ) from exc

    except Exception as exc:  # noqa: BLE001 - final safety net
        logger.exception("Unexpected error in /generate-response")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        ) from exc