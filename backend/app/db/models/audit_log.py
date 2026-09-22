from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, new_uuid, utcnow


class AuditLog(Base):
    """Append-only event log. Every state transition and every access to a
    connection's secret is recorded here, but the secret VALUE never is -
    only `connection_id` and an event_type like 'connection_used'.
    """

    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    flow_id: Mapped[str | None] = mapped_column(String, ForeignKey("flows.id"), nullable=True)
    run_id: Mapped[str | None] = mapped_column(String, ForeignKey("runs.id"), nullable=True)
    connection_id: Mapped[str | None] = mapped_column(String, ForeignKey("connections.id"), nullable=True)

    event_type: Mapped[str] = mapped_column(String, nullable=False)
    actor: Mapped[str] = mapped_column(String, nullable=False)
    detail_json: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), default=utcnow)
