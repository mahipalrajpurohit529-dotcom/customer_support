"""
schemas.py
----------
Centralized Pydantic models used across the application.

Why this file exists:
- Keeps request/response contracts in one place instead of scattering
  model definitions across app.py and agents/intent_agent.py.
- The `IntentLabel` enum is the single source of truth for supported
  intents. Both the FastAPI response and the LangChain structured
  output use it, so the LLM is constrained to return only one of
  these values (never free text).
"""

from enum import Enum
from pydantic import BaseModel, Field


class IntentLabel(str, Enum):
    """All intents the system currently supports (Phase 1 scope)."""

    REFUND_POLICY = "refund_policy"
    RETURN_POLICY = "return_policy"
    ORDER_STATUS = "order_status"
    ORDER_CANCELLATION = "order_cancellation"
    PAYMENT_ISSUE = "payment_issue"
    SHIPPING_INFORMATION = "shipping_information"
    GREETING = "greeting"
    GOODBYE = "goodbye"
    UNKNOWN = "unknown"


class QueryRequest(BaseModel):
    """Incoming request body for POST /detect-intent."""

    query: str = Field(
        ...,
        min_length=1,
        description="The raw customer query text to classify.",
        examples=["Where is my order?"],
    )


class IntentResult(BaseModel):
    """
    Structured output schema the LLM is forced to produce.

    Passed to LangChain's `with_structured_output()` so the model's
    response is parsed directly into this Pydantic object instead of
    us having to manually parse raw text / JSON from the LLM.
    """

    intent: IntentLabel = Field(
        ...,
        description="The single best-matching intent for the customer query.",
    )


class IntentResponse(BaseModel):
    """Outgoing response body for POST /detect-intent."""

    intent: IntentLabel
