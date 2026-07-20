"""
orchestrator.py
-----------------
Chains the three agents into one pipeline: Intent Agent -> Database
Agent -> Response Agent. Lives at the project root (not inside
agents/) since it isn't an agent itself — it's the glue that calls
agents in sequence.

Why this file exists:
- Nothing else in the project decides WHICH database lookup to run
  based on WHICH intent was detected. That mapping lives here, kept
  out of both the Database Agent (which shouldn't know about intents)
  and the Response Agent (which shouldn't know about the database).
- Plain sequential Python, not LangGraph — matches the project's
  existing constraint of no graph-based orchestration.
"""

from agents.database_agent import DatabaseAgentError, database_agent
from agents.intent_agent import IntentAgentError, intent_agent
from agents.response_agent import ResponseAgentError, response_agent
from schemas import IntentLabel

# Maps intents that resolve to a static company policy -> the
# policy_type key stored in the `policies` table.
INTENT_TO_POLICY_TYPE = {
    IntentLabel.REFUND_POLICY: "refund_policy",
    IntentLabel.RETURN_POLICY: "return_policy",
    IntentLabel.ORDER_CANCELLATION: "cancellation_policy",
    IntentLabel.SHIPPING_INFORMATION: "shipping_policy",
}

# Intents that need an order_id to look anything up.
ORDER_LOOKUP_INTENTS = {IntentLabel.ORDER_STATUS, IntentLabel.PAYMENT_ISSUE}

# Intents that need no database lookup at all.
NO_LOOKUP_INTENTS = {IntentLabel.GREETING, IntentLabel.GOODBYE, IntentLabel.UNKNOWN}


class OrchestratorError(Exception):
    """Raised when the pipeline fails at any stage."""


def _retrieve_data(intent: IntentLabel, order_id: int | None) -> dict:
    """
    Decide which Database Agent call (if any) to make based on the
    detected intent, and return its result as a plain dict.
    """
    try:
        if intent in INTENT_TO_POLICY_TYPE:
            policy_type = INTENT_TO_POLICY_TYPE[intent]
            policy = database_agent.get_policy(policy_type)
            if policy is None:
                return {"error": f"No policy found for {policy_type}."}
            return policy

        if intent in ORDER_LOOKUP_INTENTS:
            if order_id is None:
                return {
                    "error": (
                        "No order ID was found in the customer's message, so "
                        "the order could not be looked up."
                    )
                }
            order = database_agent.get_order(order_id)
            if order is None:
                return {"error": f"No order found with order_id={order_id}."}
            return order

        if intent in NO_LOOKUP_INTENTS:
            return {"note": f"No database lookup is needed for intent '{intent.value}'."}

        # Fallback for any future intent not yet mapped above.
        return {"note": f"No database lookup is configured for intent '{intent.value}'."}

    except DatabaseAgentError as exc:
        return {"error": str(exc)}


def run_support_pipeline(customer_query: str) -> dict:
    """
    Run the full pipeline for a single customer query.

    Returns a dict with: query, detected_intent, order_id,
    retrieved_data, final_response.

    Raises:
        OrchestratorError: if the Intent Agent or Response Agent
            stage fails outright (Database Agent failures are caught
            and surfaced as retrieved_data={"error": ...} instead,
            since a DB failure shouldn't prevent a graceful reply).
    """
    try:
        intent_result = intent_agent.detect_intent(customer_query)
    except IntentAgentError as exc:
        raise OrchestratorError(f"Intent detection failed: {exc}") from exc

    retrieved_data = _retrieve_data(intent_result.intent, intent_result.order_id)

    try:
        final_response = response_agent.generate_response(
            query=customer_query,
            intent=intent_result.intent.value,
            retrieved_data=retrieved_data,
        )
    except ResponseAgentError as exc:
        raise OrchestratorError(f"Response generation failed: {exc}") from exc

    return {
        "query": customer_query,
        "detected_intent": intent_result.intent.value,
        "order_id": intent_result.order_id,
        "retrieved_data": retrieved_data,
        "final_response": final_response,
    }