"""initial schema: connections, flows, plan_versions, runs, audit_log

Revision ID: 0001
Revises:
Create Date: 2026-09-20

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "connections",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("type", sa.String, nullable=False),
        sa.Column("host", sa.String, nullable=True),
        sa.Column("port", sa.Integer, nullable=True),
        sa.Column("database_name", sa.String, nullable=True),
        sa.Column("username", sa.String, nullable=True),
        sa.Column("encrypted_secret", sa.LargeBinary, nullable=False),
        sa.Column("is_read_only", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("tableau_site_id", sa.String, nullable=True),
        sa.Column("tableau_project_id", sa.String, nullable=True),
        sa.Column("created_by", sa.String, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "flows",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("nl_request", sa.String, nullable=False),
        sa.Column("source_connection_id", sa.String, sa.ForeignKey("connections.id"), nullable=False),
        sa.Column("tableau_connection_id", sa.String, sa.ForeignKey("connections.id"), nullable=True),
        sa.Column("target_datasource_name", sa.String, nullable=True),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("active_plan_version_id", sa.String, nullable=True),
        sa.Column("created_by", sa.String, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "plan_versions",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("flow_id", sa.String, sa.ForeignKey("flows.id"), nullable=False),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("source", sa.String, nullable=False),
        sa.Column("plan_json", sa.String, nullable=False),
        sa.Column("schema_snapshot_json", sa.String, nullable=False),
        sa.Column("approved_by", sa.String, nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "runs",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("flow_id", sa.String, sa.ForeignKey("flows.id"), nullable=False),
        sa.Column("plan_version_id", sa.String, sa.ForeignKey("plan_versions.id"), nullable=False),
        sa.Column("run_type", sa.String, nullable=False),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("generated_sql", sa.String, nullable=True),
        sa.Column("generated_code_lang", sa.String, nullable=True),
        sa.Column("rows_before", sa.Integer, nullable=True),
        sa.Column("rows_after", sa.Integer, nullable=True),
        sa.Column("row_count_anomaly", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("sample_before_json", sa.String, nullable=True),
        sa.Column("sample_after_json", sa.String, nullable=True),
        sa.Column("hyper_file_path", sa.String, nullable=True),
        sa.Column("publish_status", sa.String, nullable=True),
        sa.Column("publish_error", sa.String, nullable=True),
        sa.Column("error_message", sa.String, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("triggered_by", sa.String, nullable=False),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("flow_id", sa.String, sa.ForeignKey("flows.id"), nullable=True),
        sa.Column("run_id", sa.String, sa.ForeignKey("runs.id"), nullable=True),
        sa.Column("connection_id", sa.String, sa.ForeignKey("connections.id"), nullable=True),
        sa.Column("event_type", sa.String, nullable=False),
        sa.Column("actor", sa.String, nullable=False),
        sa.Column("detail_json", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("runs")
    op.drop_table("plan_versions")
    op.drop_table("flows")
    op.drop_table("connections")
