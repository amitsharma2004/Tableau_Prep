from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, new_uuid, utcnow


class FlowSchedule(Base):
    """Stores the scheduling configuration for an approved flow."""

    __tablename__ = "flow_schedules"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    flow_id: Mapped[str] = mapped_column(String, ForeignKey("flows.id"), unique=True, nullable=False)
    plan_version_id: Mapped[str] = mapped_column(String, ForeignKey("plan_versions.id"), nullable=False)

    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    cron_expression: Mapped[str] = mapped_column(String, nullable=False)
    timezone: Mapped[str] = mapped_column(String, default="UTC", nullable=False)

    next_run_at: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_at: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_status: Mapped[str | None] = mapped_column(String, nullable=True)  # 'succeeded' | 'failed'

    created_by: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
