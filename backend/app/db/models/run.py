from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, new_uuid, utcnow


class Run(Base):
    """One row per preview or execute attempt - the audit backbone.

    Stores only small samples (sample_before_json/sample_after_json), never
    the full result set, so the metadata DB doesn't balloon on large runs.
    """

    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    flow_id: Mapped[str] = mapped_column(String, ForeignKey("flows.id"), nullable=False)
    plan_version_id: Mapped[str] = mapped_column(String, ForeignKey("plan_versions.id"), nullable=False)

    run_type: Mapped[str] = mapped_column(String, nullable=False)  # 'preview' | 'execute'
    status: Mapped[str] = mapped_column(String, nullable=False)  # 'running' | 'succeeded' | 'failed'

    generated_sql: Mapped[str | None] = mapped_column(String, nullable=True)
    generated_code_lang: Mapped[str | None] = mapped_column(String, nullable=True)  # 'sql' | 'pandas'

    rows_before: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rows_after: Mapped[int | None] = mapped_column(Integer, nullable=True)
    row_count_anomaly: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    sample_before_json: Mapped[str | None] = mapped_column(String, nullable=True)
    sample_after_json: Mapped[str | None] = mapped_column(String, nullable=True)

    hyper_file_path: Mapped[str | None] = mapped_column(String, nullable=True)
    publish_status: Mapped[str | None] = mapped_column(String, nullable=True)
    publish_error: Mapped[str | None] = mapped_column(String, nullable=True)

    error_message: Mapped[str | None] = mapped_column(String, nullable=True)

    trigger_type: Mapped[str] = mapped_column(String, nullable=False, default="manual")  # 'manual' | 'scheduled'
    scheduled_for: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True), nullable=True)

    started_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True), nullable=True)
    triggered_by: Mapped[str] = mapped_column(String, nullable=False)
