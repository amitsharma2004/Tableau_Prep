from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.state_machine import FlowStatus
from app.db.base import Base, new_uuid, utcnow


class Flow(Base):
    """One natural-language request -> one transformation pipeline.

    `status` mirrors FlowStatus and must only ever be changed via
    app.services.flow_service (which calls state_machine.assert_legal_transition
    and writes the corresponding AuditLog row) - never assigned directly.
    """

    __tablename__ = "flows"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    nl_request: Mapped[str] = mapped_column(String, nullable=False)

    source_connection_id: Mapped[str] = mapped_column(String, ForeignKey("connections.id"), nullable=False)
    tableau_connection_id: Mapped[str | None] = mapped_column(String, ForeignKey("connections.id"), nullable=True)

    # Fixed per flow (not timestamped) so publish_or_overwrite() can find and
    # overwrite the same datasource by name every run - see tableau/publisher.py.
    target_datasource_name: Mapped[str | None] = mapped_column(String, nullable=True)

    status: Mapped[str] = mapped_column(String, nullable=False, default=FlowStatus.DRAFT.value)
    active_plan_version_id: Mapped[str | None] = mapped_column(String, nullable=True)

    created_by: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
