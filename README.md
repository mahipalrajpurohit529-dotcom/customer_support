# AI Customer Support System — Phase 1: Intent Detection Agent

This is **Phase 1 only**. Scope is intentionally limited to detecting the intent
of a customer query. No database, no response generation, no RAG, no
LangGraph, no multi-agent logic — just classification.

## Project Structure

```
customer_support/
│── app.py                    # FastAPI app & the /detect-intent endpoint
│── .env                      # API key config (fill in your own key)
│── requirements.txt          # Python dependencies
│
├── agents/
│      └── intent_agent.py    # LangChain logic: prompt -> structured LLM call
│
├── prompts/
│      └── intent_prompt.py   # ChatPromptTemplate + system instructions
│
├── schemas.py                # Pydantic models (IntentLabel, request/response)
└── README.md
```

## File-by-file purpose

- **`schemas.py`** — Single source of truth for data shapes. Defines the
  `IntentLabel` enum (the 9 supported intents), the `QueryRequest` the API
  accepts, the `IntentResult` used internally for structured LLM output, and
  the `IntentResponse` returned to clients.

- **`prompts/intent_prompt.py`** — Contains the `ChatPromptTemplate` and the
  system instructions that tell the LLM exactly how to classify a message.
  Kept separate from agent code so the prompt can be edited/tuned on its own.

- **`agents/intent_agent.py`** — All LangChain wiring lives here: builds the
  Gemini chat model, binds it to `IntentResult` via `with_structured_output()`
  (so output is a validated Pydantic object, never raw text you have to
  parse), and exposes `IntentAgent.detect_intent(query)`.

- **`app.py`** — The FastAPI app. Exposes `POST /detect-intent` and a
  `GET /health` check. Catches agent-level errors and unexpected exceptions,
  translating them into proper HTTP error responses instead of leaking stack
  traces.

- **`.env`** — Holds `GOOGLE_API_KEY` (and an optional `GEMINI_MODEL_NAME`
  override). Never commit your real key — this file is a template.

- **`requirements.txt`** — Pinned dependencies for a reproducible environment.

## Setup & Run

1. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate      # Windows: venv\Scripts\activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure your API key**
   Open `.env` and replace `your_google_api_key_here` with a real key from
   https://aistudio.google.com/apikey

4. **Run the server**
   ```bash
   uvicorn app:app --reload
   ```
   Server starts at `http://127.0.0.1:8000`

5. **Test it**

   Via Swagger UI: open `http://127.0.0.1:8000/docs`

   Via curl:
   ```bash
   curl -X POST http://127.0.0.1:8000/detect-intent \
     -H "Content-Type: application/json" \
     -d '{"query": "Where is my order?"}'
   ```

   Expected response:
   ```json
   { "intent": "order_status" }
   ```

## Supported Intents

`refund_policy`, `return_policy`, `order_status`, `order_cancellation`,
`payment_issue`, `shipping_information`, `greeting`, `goodbye`, `unknown`

## Notes for Phase 2+ (not implemented here)

Deliberately out of scope for this phase: MySQL/SQL persistence, response
generation, LangGraph orchestration, RAG, vector databases, embeddings, and
any additional agents. These will build on top of this intent detection
layer in later phases.
