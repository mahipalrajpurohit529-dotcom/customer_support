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


# ---------------------------------------------------------------------------
# Phase 2 schemas (Database Agent testing endpoint)
# ---------------------------------------------------------------------------


class CustomerRequest(BaseModel):
    """Incoming request body for POST /customer."""

    customer_id: int = Field(
        ...,
        description="The numeric ID of the customer to look up.",
        examples=[101],
    )


class CustomerResponse(BaseModel):
    """Outgoing response body for POST /customer."""

    customer_id: int
    first_name: str
    last_name: str
    email: str
    phone: str | None = None
    address: str | None = None
    created_at: str | None = None


class PolicyRequest(BaseModel):
    """Incoming request body for POST /policy."""

    policy_type: str = Field(
        ...,
        description="One of: refund_policy, return_policy, cancellation_policy, shipping_policy.",
        examples=["refund_policy"],
    )


class PolicyResponse(BaseModel):
    """Outgoing response body for POST /policy."""

    policy_type: str
    title: str
    content: str
    updated_at: str | None = None






class ResponseGenerationRequest(BaseModel):
    """Incoming request body for POST /generate-response."""

    query: str = Field(
        ...,
        min_length=1,
        description="The original customer query.",
        examples=["What is your refund policy?"],
    )
    intent: str = Field(
        ...,
        description="The intent detected for this query.",
        examples=["refund_policy"],
    )
    retrieved_data: dict = Field(
        ...,
        description="The structured data retrieved from the Database Agent for this query.",
        examples=[
            {
                "policy_type": "refund_policy",
                "title": "Refund Policy",
                "content": "We offer a full refund within 30 days of delivery...",
            }
        ],
    )


class ResponseGenerationResult(BaseModel):
    """Outgoing response body for POST /generate-response."""

    response: str