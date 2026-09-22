from sqlalchemy import Boolean, DateTime, Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, new_uuid, utcnow


class Connection(Base):
    """A stored connection to either a source database (must be read-only)
    or a Tableau Server/Cloud site (PAT auth).

    `encrypted_secret` is intentionally the only place the password/PAT lives.
    No schemas/connection.py response DTO includes this field - that is what
    makes it structurally impossible to leak via an API response.
    """

    __tablename__ = "connections"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)  # 'postgres' | 'mysql' | 'tableau_server'

    host: Mapped[str | None] = mapped_column(String, nullable=True)
    port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    database_name: Mapped[str | None] = mapped_column(String, nullable=True)
    username: Mapped[str | None] = mapped_column(String, nullable=True)

    encrypted_secret: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    is_read_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    tableau_site_id: Mapped[str | None] = mapped_column(String, nullable=True)
    tableau_project_id: Mapped[str | None] = mapped_column(String, nullable=True)

    created_by: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
