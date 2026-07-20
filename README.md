# AI Customer Support System

An AI-powered customer support backend built with **LangChain**, **FastAPI**, **MySQL**, and **Google Gemini**.

It reads a raw customer message, figures out what the customer wants, looks up the real answer in MySQL, and writes a natural, professional reply — fully automatically, through three separate AI agents chained together.

> **Example:** A customer types *"What's the status of my order 1002?"* The system detects the intent (`order_status`), extracts the order ID, pulls the real order record out of MySQL, and generates a grounded, natural response — with zero invented details.

---

## Table of Contents

1. [What this project does](#what-this-project-does)
2. [Architecture](#architecture)
3. [Tech stack](#tech-stack)
4. [Project structure](#project-structure)
5. [File-by-file explanation](#file-by-file-explanation)
6. [Database design](#database-design)
7. [The three agents, in detail](#the-three-agents-in-detail)
8. [The console (frontend)](#the-console-frontend)
9. [Setup & installation](#setup--installation)
10. [Running the project](#running-the-project)
11. [API reference](#api-reference)
12. [Example walkthrough](#example-walkthrough)
13. [Design decisions & trade-offs](#design-decisions--trade-offs)
14. [What's not included (by design)](#whats-not-included-by-design)

---

## What this project does

Customers ask about a handful of recurring topics:

- Order status
- Refund policy
- Return policy
- Order cancellation
- Payment issues
- Shipping information
- Greetings / farewells / off-topic messages

Instead of hand-coding a response for every phrasing of every question, this system runs each message through an automated **3-agent pipeline**:

```
Customer types a message
        │
        ▼
Agent 1 — figures out WHAT they're asking about (+ extracts an order ID if present)
        │
        ▼
Agent 2 — looks up the REAL answer in MySQL
        │
        ▼
Agent 3 — writes a professional REPLY using that real data
        │
        ▼
Customer receives the final response
```

Each agent does exactly one job. No agent knows how the others work internally — they only pass simple, well-defined data between each other.

---

## Architecture

```
┌────────────────────┐    ┌──────────────────────────┐    ┌──────────────────────┐    ┌───────────────────────────┐
│   Customer Query    │──▶ │  Intent Detection Agent  │──▶ │   Database Agent      │──▶ │ Response Generator Agent  │
│  (raw text input)   │    │  (LLM, structured out)   │    │  (structured lookups) │    │      (LLM, prose)         │
└────────────────────┘    └──────────────────────────┘    └──────────────────────┘    └───────────────────────────┘
                                                                        │
                                                                        ▼
                                                             ┌───────────────────────┐
                                                             │      MySQL Database     │
                                                             │  customers / orders /   │
                                                             │       policies          │
                                                             └───────────────────────┘
```

Everything is orchestrated by plain, sequential Python (`orchestrator.py`) — **not** LangGraph. Each agent is called one after another, and its output is passed as input to the next. There is no shared agent memory, no vector database, and no embeddings anywhere in this project, by design.

---

## Tech stack

| Layer           | Technology                                      | Why                                                       |
| ---------------- | ------------------------------------------------ | ----------------------------------------------------------- |
| LLM              | **Google Gemini** (`gemini-1.5-flash`)           | Fast, generous free tier                                    |
| Agent framework  | **LangChain** (`ChatPromptTemplate`, structured output, `@tool`) | Required by the project's scope; no LangGraph |
| Database         | **MySQL**                                        | Stores customers, orders, and policies                      |
| DB access        | **SQLAlchemy (ORM)** + **PyMySQL**               | No raw SQL strings anywhere                                  |
| API layer        | **FastAPI**                                      | Serves the pipeline as an HTTP API                           |
| Validation       | **Pydantic**                                     | Structured intent output + request/response schemas         |
| Config           | **python-dotenv**                                | Keeps API keys and DB credentials out of source code         |
| Frontend         | Plain **HTML/CSS/JS**, inline in `app.py`        | Single file, zero build step, served directly by FastAPI     |

---

## Project structure

```
customer_support/
├── app.py                     # FastAPI app: all routes + the test console UI
├── orchestrator.py            # Runs the 3 agents in sequence
├── schemas.py                 # All Pydantic request/response models
├── requirements.txt           # Python dependencies
├── .env                       # API keys + DB credentials (not committed)
│
├── agents/
│   ├── intent_agent.py        # Agent 1 — Intent Detection
│   ├── database_agent.py      # Agent 2 — Database Agent
│   └── response_agent.py      # Agent 3 — Response Generator
│
├── database/
│   ├── connection.py          # SQLAlchemy engine + session handling
│   ├── models.py               # ORM models: Customer, Order, Policy
│   └── crud.py                 # Read-only ORM queries (no raw SQL)
│
├── prompts/
│   ├── intent_prompt.py       # System prompt for Agent 1
│   └── response_prompt.py     # System prompt for Agent 3
│
└── tools/
    └── database_tool.py       # LangChain @tool wrappers around the Database Agent
```

---

## File-by-file explanation

### `database/connection.py`

Owns the SQLAlchemy engine, session factory, and declarative `Base`. Builds the MySQL connection string from `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`. Exposes `get_db()` (FastAPI-style dependency) and `get_db_session()` (context manager, used by the Database Agent since it runs outside FastAPI's request cycle).

### `database/models.py`

SQLAlchemy ORM models mapping to the `customers`, `orders`, and `policies` tables. Assumes the tables already exist — this file describes them for querying, it does not create or migrate them.

### `database/crud.py`

Pure, read-only ORM queries: `get_customer`, `get_customer_by_email`, `get_orders`, `get_order`, `validate_customer`, `get_policy`. No raw SQL strings anywhere — everything goes through SQLAlchemy's query builder.

### `agents/intent_agent.py` — Agent 1

Takes the raw customer message and returns a structured `IntentResult`:

```python
class IntentResult(BaseModel):
    intent: IntentLabel      # one of 9 predefined intents
    order_id: int | None     # extracted from the message, if present
```

Uses `llm.with_structured_output(IntentResult)` — the LLM's response is forced to match this schema, so nothing downstream ever has to parse free-form text. Runs at `temperature=0` since classification should be deterministic.

### `agents/database_agent.py` — Agent 2

The only part of the system allowed to talk to the database. Converts ORM objects into plain dictionaries and wraps SQLAlchemy errors into a clean `DatabaseAgentError`. Never generates natural-language text — structured data only. Exposes `get_customer`, `get_customer_by_email`, `get_orders`, `get_order`, `validate_customer`, `get_policy`.

### `agents/response_agent.py` — Agent 3

A simple LangChain chain (`prompt | llm | StrOutputParser`) that takes the original query, the detected intent, and the retrieved data, and writes a warm, professional customer-facing reply. Explicitly instructed never to invent information that isn't in the retrieved data, and to respond gracefully (without fabricating) when there's an error or no lookup was needed (e.g. greetings). Runs at `temperature=0.4` — a little natural variation is desirable in customer-facing prose, unlike classification.

### `tools/database_tool.py`

Wraps the Database Agent's methods as LangChain `@tool` functions (`get_customer_tool`, `get_orders_tool`, `get_order_tool`, `get_policy_tool`, etc.), each with a docstring describing exactly what it does. These exist so an LLM-driven tool-calling agent could pick between them in the future; the current pipeline calls the Database Agent's methods directly via a deterministic intent → lookup mapping in `orchestrator.py`.

### `orchestrator.py`

The glue that chains all three agents:

1. Calls Agent 1 → gets `intent` + `order_id`
2. Maps the intent to the right Database Agent lookup (policy text, order lookup by ID, or no lookup at all for greetings/farewells/unmatched topics) → gets `retrieved_data`
3. Calls Agent 3 → gets `final_response`
4. Returns everything as one dictionary

Plain sequential Python — not LangGraph — since the workflow is linear with no branching or looping beyond a simple intent → lookup table.

### `prompts/intent_prompt.py` / `prompts/response_prompt.py`

The system prompts for Agents 1 and 3, kept separate from agent code so tone and rules can be tuned without touching LangChain wiring.

### `schemas.py`

Every Pydantic model in the project in one place: the `IntentLabel` enum (single source of truth for supported intents), and all request/response schemas for every endpoint.

### `app.py`

The FastAPI app: all routes, plus a self-contained HTML/CSS/JS test console served at `/` (no build step, no separate frontend framework).

---

## Database design

### `customers`

| Column        | Type      | Notes            |
| -------------- | --------- | ----------------- |
| `customer_id`  | INT, PK   |                   |
| `first_name`   | VARCHAR(100) |                |
| `last_name`    | VARCHAR(100) |                |
| `email`        | VARCHAR(255), UNIQUE |        |
| `phone`        | VARCHAR(50)  |                |
| `address`      | VARCHAR(255) |                |
| `created_at`   | DATETIME  |                   |

### `orders`

| Column             | Type          | Notes                                                  |
| ------------------- | ------------- | -------------------------------------------------------- |
| `order_id`           | INT, PK       |                                                          |
| `customer_id`        | INT, FK       | references `customers.customer_id`                      |
| `product_name`       | VARCHAR(255)  |                                                          |
| `quantity`           | INT           |                                                          |
| `total_price`        | DECIMAL(10,2) |                                                          |
| `order_status`       | VARCHAR(50)   | processing / shipped / delivered / cancelled / returned  |
| `tracking_number`    | VARCHAR(100)  | nullable                                                 |
| `order_date`         | DATETIME      |                                                          |

### `policies`

| Column         | Type          | Notes                                                                       |
| --------------- | ------------- | ------------------------------------------------------------------------------ |
| `id`            | INT, PK       |                                                                                 |
| `policy_type`   | VARCHAR(50), UNIQUE | `refund_policy`, `return_policy`, `cancellation_policy`, `shipping_policy` |
| `title`         | VARCHAR(150)  |                                                                                 |
| `content`       | TEXT          | the actual policy text shown to customers                                       |
| `updated_at`    | TIMESTAMP     |                                                                                 |

---

## The three agents, in detail

### Why 3 separate agents instead of one big prompt?

Each agent has a single responsibility — independently testable, debuggable, and replaceable:

- If intent detection is wrong, only Agent 1's prompt needs fixing.
- If the wrong data is retrieved, only Agent 2 needs fixing.
- If replies sound robotic, only Agent 3's prompt needs fixing.

### Temperature settings

- Agent 1 (intent) → `temperature=0` — classification should be deterministic
- Agent 2 (database) → n/a — plain structured lookups, no LLM call at all
- Agent 3 (response) → `temperature=0.4` — natural variation is desirable in customer-facing prose

---

## The console (frontend)

A single self-contained page served at `/` — dark, terminal-styled, no build tools, no external frontend framework. It includes:

- A prominent **full pipeline** panel (`POST /support/query`) with example chips for each intent
- Four separate **debug panels**, one per lower-level endpoint (`/detect-intent`, `/policy`, `/customer`, `/generate-response`), for testing each agent independently
- A live status LED that pings `/health` on load

---

## Setup & installation

### 1. Create the MySQL database and tables

Run the table-creation SQL (see [Database design](#database-design) for the schema) against your MySQL instance, then load in policy and sample customer/order data.

### 2. Get a Google Gemini API key

Sign up free at [aistudio.google.com/apikey](https://aistudio.google.com/apikey).

### 3. Configure environment variables

Copy `.env` and fill in your own values:

```
GOOGLE_API_KEY=your_google_api_key_here
GEMINI_MODEL_NAME=gemini-1.5-flash

DB_HOST=localhost
DB_PORT=3306
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_NAME=your_db_name
```

### 4. Install dependencies

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

---

## Running the project

```bash
uvicorn app:app --reload
```

| URL                             | What it is                          |
| --------------------------------- | -------------------------------------- |
| `http://127.0.0.1:8000/`          | The test console (main UI)             |
| `http://127.0.0.1:8000/docs`      | Interactive Swagger API docs           |
| `http://127.0.0.1:8000/health`    | Health check                           |

---

## API reference

### `POST /support/query` — the main pipeline endpoint

**Request:**
```json
{ "query": "What's the status of my order 1002?" }
```

**Response:**
```json
{
  "query": "What's the status of my order 1002?",
  "detected_intent": "order_status",
  "order_id": 1002,
  "retrieved_data": { "order_id": 1002, "order_status": "shipped", "tracking_number": "TRK123456789" },
  "final_response": "Your order is currently on its way! It shipped with tracking number TRK123456789..."
}
```

### Individual agent-level endpoints (for debugging)

| Endpoint             | Purpose                                             |
| ---------------------- | ------------------------------------------------------ |
| `POST /detect-intent`  | Run just the Intent Agent                               |
| `POST /policy`         | Run just the Database Agent's policy lookup              |
| `POST /customer`       | Run just the Database Agent's customer lookup             |
| `POST /generate-response` | Run just the Response Agent, given manual inputs      |
| `GET /health`          | Liveness check                                          |

---

## Example walkthrough

**Customer types:** `"What's the status of my order 1002?"`

1. **Agent 1 (Intent Detection)** reads the message and outputs:
   ```json
   { "intent": "order_status", "order_id": 1002 }
   ```

2. **`orchestrator.py`** sees `intent = order_status` and a non-null `order_id`, so it calls `database_agent.get_order(1002)`, which returns the matching row from MySQL.

3. **Agent 3 (Response Generator)** turns that data into:

   > "Your order is currently on its way! It shipped with tracking number TRK123456789 — let us know if you need anything else."

---

## Design decisions & trade-offs

- **ORM over raw SQL.** Every database query goes through SQLAlchemy's query builder — no string-formatted SQL anywhere, no injection surface even though some values (like an extracted `order_id`) ultimately originate from an LLM's structured output.
- **Structured output over prompted JSON.** Agent 1 uses `with_structured_output()` rather than asking the LLM to "return JSON" in a text prompt — this guarantees a parseable, schema-valid result instead of hoping the model formats it correctly.
- **Plain orchestration over LangGraph.** The 3-agent handoff is ordinary sequential Python function calls — simpler to read and debug for a linear, non-branching workflow like this one.
- **Deterministic routing over an autonomous tool-calling agent.** The Database Agent's tools (`tools/database_tool.py`) exist and are LangChain-compatible, but the current pipeline decides which lookup to run based on a simple intent → function mapping in `orchestrator.py`, rather than having an LLM agent (`AgentExecutor`) choose the tool itself. This keeps behavior fully predictable and easy to debug; the trade-off is less flexibility if new, harder-to-map intents are added later.
- **Grounded response generation.** The Response Agent is explicitly instructed never to invent policy details, order statuses, or any other specifics not present in the retrieved data — including when there's an error or no lookup was needed at all (greetings, farewells, unmatched topics).

---

## What's not included (by design)

Deliberately out of scope for this project:

- LangGraph or any graph-based orchestration
- RAG, vector databases, or embeddings
- A supervisor/meta agent
- Response caching or streaming
- Authentication / customer identity verification (any `order_id` can currently be queried by anyone — a real production system would tie queries to an authenticated customer)
- An audit log table (`support_logs`) for every interaction — a natural next addition, not yet built