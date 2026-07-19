"""
agents/database_agent.py
--------------------------
The Database Agent: the only part of the system allowed to talk to
the database. It never generates customer-facing text — it only
returns structured Python dictionaries (or None) that other layers
(LangChain tool, FastAPI routes, and in a later phase, a response
agent) can consume.
"""

from typing import List, Optional

from sqlalchemy.exc import SQLAlchemyError

from database import crud
from database.connection import get_db_session
from database.models import Customer, Order


class DatabaseAgentError(Exception):
    """Raised when a database operation fails."""


def _customer_to_dict(customer: Customer) -> dict:
    return {
        "customer_id": customer.customer_id,
        "first_name": customer.first_name,
        "last_name": customer.last_name,
        "email": customer.email,
        "phone": customer.phone,
        "address": customer.address,
        "created_at": customer.created_at.isoformat() if customer.created_at else None,
    }


def _order_to_dict(order: Order) -> dict:
    return {
        "order_id": order.order_id,
        "customer_id": order.customer_id,
        "product_name": order.product_name,
        "quantity": order.quantity,
        "total_price": float(order.total_price) if order.total_price is not None else None,
        "order_status": order.order_status,
        "tracking_number": order.tracking_number,
        "order_date": order.order_date.isoformat() if order.order_date else None,
    }


class DatabaseAgent:
    """
    Structured, LLM-agnostic access point for customer and order data.
    Every public method returns plain dicts / lists / bools / None —
    never ORM objects, never natural-language text.
    """

    def get_customer(self, customer_id: int) -> Optional[dict]:
        try:
            with get_db_session() as db:
                customer = crud.get_customer(db, customer_id)
                return _customer_to_dict(customer) if customer else None
        except SQLAlchemyError as exc:
            raise DatabaseAgentError(f"Failed to fetch customer {customer_id}: {exc}") from exc

    def get_customer_by_email(self, email: str) -> Optional[dict]:
        try:
            with get_db_session() as db:
                customer = crud.get_customer_by_email(db, email)
                return _customer_to_dict(customer) if customer else None
        except SQLAlchemyError as exc:
            raise DatabaseAgentError(f"Failed to fetch customer by email {email}: {exc}") from exc

    def get_orders(self, customer_id: int) -> List[dict]:
        try:
            with get_db_session() as db:
                orders = crud.get_orders(db, customer_id)
                return [_order_to_dict(order) for order in orders]
        except SQLAlchemyError as exc:
            raise DatabaseAgentError(f"Failed to fetch orders for customer {customer_id}: {exc}") from exc

    def get_order(self, order_id: int) -> Optional[dict]:
        try:
            with get_db_session() as db:
                order = crud.get_order(db, order_id)
                return _order_to_dict(order) if order else None
        except SQLAlchemyError as exc:
            raise DatabaseAgentError(f"Failed to fetch order {order_id}: {exc}") from exc

    def validate_customer(self, customer_id: int) -> bool:
        try:
            with get_db_session() as db:
                return crud.validate_customer(db, customer_id)
        except SQLAlchemyError as exc:
            raise DatabaseAgentError(f"Failed to validate customer {customer_id}: {exc}") from exc


# Singleton instance reused across the app, mirroring the intent_agent pattern.
database_agent = DatabaseAgent()