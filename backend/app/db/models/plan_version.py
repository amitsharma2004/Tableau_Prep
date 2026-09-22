from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, new_uuid, utcnow


class PlanVersion(Base):
    """Append-only: every LLM draft and every human edit is a new row.

    Never UPDATE an existing plan_versions row's plan_json - always INSERT a
    new version. This is what makes plan evolution fully auditable (who
    changed what, from the LLM's original proposal onward).
    """

    __tablename__ = "plan_versions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    flow_id: Mapped[str] = mapped_column(String, ForeignKey("flows.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)

    source: Mapped[str] = mapped_column(String, nullable=False)  # 'llm_generated' | 'human_edited'
    parent_version_id: Mapped[str | None] = mapped_column(String, nullable=True)
    change_summary: Mapped[str | None] = mapped_column(String, nullable=True)
    plan_json: Mapped[str] = mapped_column(String, nullable=False)
    schema_snapshot_json: Mapped[str] = mapped_column(String, nullable=False)

    approved_by: Mapped[str | None] = mapped_column(String, nullable=True)
    approved_at: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), default=utcnow)
