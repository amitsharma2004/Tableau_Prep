from fastapi import Header, HTTPException

from app.db.session import get_db

__all__ = ["get_db", "get_current_actor"]


def get_current_actor(x_actor_email: str = Header(...)) -> str:
    """MVP identity: the caller states who they are via a header, and every
    audit_log row / plan approval / connection creation is stamped with it.
    Not real auth - a proper session/login belongs to the hardening milestone."""
    if "@" not in x_actor_email:
        raise HTTPException(status_code=400, detail="X-Actor-Email header must be a valid email address")
    return x_actor_email
