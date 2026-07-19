"""
tools/database_tool.py
------------------------
Wraps the Database Agent as LangChain Tools so an LLM/agent chain can
retrieve customer and order data without touching the database directly.
"""

import json

from langchain_core.tools import tool

from agents.database_agent import DatabaseAgentError, database_agent


@tool
def get_customer_tool(customer_id: int) -> str:
    """
    Look up a customer's profile information (name, email, phone,
    address) by their numeric customer_id. Returns a JSON object, or
    a JSON object with an "error" key if the customer is not found.
    """
    try:
        customer = database_agent.get_customer(customer_id)
        if customer is None:
            return json.dumps({"error": f"No customer found with customer_id={customer_id}"})
        return json.dumps(customer)
    except DatabaseAgentError as exc:
        return json.dumps({"error": str(exc)})


@tool
def get_customer_by_email_tool(email: str) -> str:
    """
    Look up a customer's profile information by their email address.
    Returns a JSON object, or a JSON object with an "error" key if no
    customer matches that email.
    """
    try:
        customer = database_agent.get_customer_by_email(email)
        if customer is None:
            return json.dumps({"error": f"No customer found with email={email}"})
        return json.dumps(customer)
    except DatabaseAgentError as exc:
        return json.dumps({"error": str(exc)})


@tool
def get_orders_tool(customer_id: int) -> str:
    """
    Retrieve the full order history for a customer given their
    customer_id. Returns a JSON array of orders (empty array if the
    customer has no orders), or a JSON object with an "error" key on
    failure.
    """
    try:
        orders = database_agent.get_orders(customer_id)
        return json.dumps(orders)
    except DatabaseAgentError as exc:
        return json.dumps({"error": str(exc)})


@tool
def get_order_tool(order_id: int) -> str:
    """
    Retrieve details (status, tracking number, product, etc.) for a
    single order given its order_id. Returns a JSON object, or a JSON
    object with an "error" key if the order is not found.
    """
    try:
        order = database_agent.get_order(order_id)
        if order is None:
            return json.dumps({"error": f"No order found with order_id={order_id}"})
        return json.dumps(order)
    except DatabaseAgentError as exc:
        return json.dumps({"error": str(exc)})


@tool
def validate_customer_tool(customer_id: int) -> str:
    """
    Check whether a customer_id corresponds to a real, existing
    customer. Returns a JSON object like {"exists": true} or
    {"exists": false}, or a JSON object with an "error" key on
    failure.
    """
    try:
        exists = database_agent.validate_customer(customer_id)
        return json.dumps({"exists": exists})
    except DatabaseAgentError as exc:
        return json.dumps({"error": str(exc)})




@tool
def get_policy_tool(policy_type: str) -> str:
    """
    Look up the full text of a company policy. policy_type must be
    one of: "refund_policy", "return_policy", "cancellation_policy",
    "shipping_policy". Returns a JSON object with the policy's title
    and content, or a JSON object with an "error" key if the policy
    type is not found.
    """
    try:
        policy = database_agent.get_policy(policy_type)
        if policy is None:
            return json.dumps({"error": f"No policy found with policy_type={policy_type}"})
        return json.dumps(policy)
    except DatabaseAgentError as exc:
        return json.dumps({"error": str(exc)})



# Convenience list for wiring all database tools into an agent/chain at once.
database_tools = [
    get_customer_tool,
    get_customer_by_email_tool,
    get_orders_tool,
    get_order_tool,
    validate_customer_tool,
    get_policy_tool
]