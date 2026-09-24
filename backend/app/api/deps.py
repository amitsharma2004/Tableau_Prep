from fastapi import Header, HTTPException

from app.db.session import get_db

__all__ = ["get_db", "get_current_actor"]


def get_current_actor(x_actor_email: str | None = Header(default=None)) -> str:
    """MVP identity: the caller states who they are via a header, and every
    audit_log row / plan approval / connection creation is stamped with it.
    Not real auth - a proper session/login belongs to the hardening milestone."""
    if not x_actor_email or "@" not in x_actor_email:
        return "shubhanshu@tnqtech.com"
    return x_actor_email
