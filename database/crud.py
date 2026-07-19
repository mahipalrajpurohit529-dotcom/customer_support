"""
database/crud.py
------------------
Read-only ORM queries against the database — no raw SQL strings.
"""

from typing import List, Optional

from sqlalchemy.orm import Session

from database.models import Customer, Order , Policy


def get_customer(db: Session, customer_id: int) -> Optional[Customer]:
    """Fetch a single customer by primary key."""
    return db.query(Customer).filter(Customer.customer_id == customer_id).first()


def get_customer_by_email(db: Session, email: str) -> Optional[Customer]:
    """Fetch a single customer by email address."""
    return db.query(Customer).filter(Customer.email == email).first()


def get_orders(db: Session, customer_id: int) -> List[Order]:
    """Fetch all orders belonging to a given customer."""
    return db.query(Order).filter(Order.customer_id == customer_id).all()


def get_order(db: Session, order_id: int) -> Optional[Order]:
    """Fetch a single order by primary key."""
    return db.query(Order).filter(Order.order_id == order_id).first()


def validate_customer(db: Session, customer_id: int) -> bool:
    """Return True if a customer with this ID exists, else False."""
    return (
        db.query(Customer.customer_id)
        .filter(Customer.customer_id == customer_id)
        .first()
        is not None
    )


def get_policy(db: Session, policy_type: str) -> Optional[Policy]:
    """Fetch a single policy by its policy_type key (e.g. 'refund_policy')."""
    return db.query(Policy).filter(Policy.policy_type == policy_type).first()