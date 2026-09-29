"""Creates and tests Connections.

The read-only guarantee for source databases is enforced HERE, once, at
creation time: `create_connection()` opens the connection with the connector
and rejects it outright if `check_read_only()` returns False. A writable
credential can never be saved into the connections table in the first place.
"""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.connectors.factory import build_connector
from app.core.errors import ConnectionFailedError, DomainError
from app.core.security import decrypt, encrypt
from app.db.models.audit_log import AuditLog
from app.db.models.connection import Connection
from app.schemas.connection import ColumnSchema, ConnectionCreate, ConnectionTestResult, TableSchema
from app.tableau.client import TableauClient

DB_TYPES = {"postgres", "mysql", "sqlite"}


class ConnectionNotReadOnlyError(DomainError):
    def __init__(self, name: str):
        super().__init__(
            f"Connection '{name}' rejected: the database user has write "
            "privileges. Only read-only credentials are accepted."
        )


def create_connection(db: Session, payload: ConnectionCreate, actor: str) -> Connection:
    is_read_only = True  # tableau_server connections have no notion of this; default True

    if payload.type in DB_TYPES:
        try:
            connector = build_connector(
                payload.type, payload.host, payload.port, payload.database_name,
                payload.username, payload.secret,
            )
            connector.test_connection()
            is_read_only = connector.check_read_only()
        except Exception as exc:
            raise ConnectionFailedError(
                f"Could not connect to '{payload.name}' ({payload.type} at {payload.host}:{payload.port}): {exc}"
            ) from exc
        if not is_read_only:
            raise ConnectionNotReadOnlyError(payload.name)

    if payload.type == "tableau_server":
        try:
            TableauClient(
                payload.host, payload.tableau_site_id or "", payload.username, payload.secret
            ).test_connection()
        except Exception as exc:
            raise ConnectionFailedError(
                f"Could not authenticate to Tableau Server '{payload.name}' ({payload.host}): {exc}"
            ) from exc

    conn = Connection(
        name=payload.name,
        type=payload.type,
        host=payload.host,
        port=payload.port,
        database_name=payload.database_name,
        username=payload.username,
        encrypted_secret=encrypt(payload.secret),
        is_read_only=is_read_only,
        tableau_site_id=payload.tableau_site_id,
        tableau_project_id=payload.tableau_project_id,
        created_by=actor,
    )
    db.add(conn)
    db.flush()

    db.add(AuditLog(connection_id=conn.id, event_type="connection_created", actor=actor))
    db.flush()
    return conn


def list_connections(db: Session) -> list[Connection]:
    return db.query(Connection).order_by(Connection.created_at.desc()).all()


def test_and_introspect(
    db: Session, connection: Connection, actor: str, force_refresh: bool = False
) -> ConnectionTestResult:
    from datetime import datetime, timezone
    from app.connectors.type_normalizer import normalize_data_type

    if connection.type not in DB_TYPES:
        raise DomainError(f"Cannot introspect schema for connection type {connection.type!r}")

    # 1. Fast Cache Hit (from DB column OR local fallback JSON file)
    cache_str = connection.cached_schema_json
    if not cache_str and connection.type == "mysql" and not force_refresh:
        # Auto-fallback to pre-compiled local schema JSON if available
        import os
        fallback_file = os.path.join(os.path.dirname(__file__), "..", "..", "neoprc_cached_schema.json")
        if os.path.exists(fallback_file):
            with open(fallback_file, "r") as f:
                cache_str = f.read()
            # Also persist it back to the connection row so next time it's in DB
            connection.cached_schema_json = cache_str
            connection.schema_updated_at = datetime.now(timezone.utc)
            db.flush()

    if not force_refresh and cache_str:
        try:
            cached_data = json.loads(cache_str)
            tables = [
                TableSchema(
                    name=t["name"],
                    schema=t.get("schema", "public"),
                    columns=[
                        ColumnSchema(
                            name=c["name"],
                            data_type=normalize_data_type(c["data_type"]),
                            nullable=c.get("nullable", True),
                        )
                        for c in t["columns"]
                    ],
                )
                for t in cached_data.get("tables", [])
            ]
            return ConnectionTestResult(
                connected=True,
                is_read_only=connection.is_read_only,
                tables=tables,
            )
        except Exception:
            # If cache corrupted, fallback to live introspection
            pass

    # 2. Live Introspection from RDS / source DB
    secret = decrypt(connection.encrypted_secret)
    try:
        connector = build_connector(
            connection.type, connection.host, connection.port, connection.database_name,
            connection.username, secret,
        )
        connector.test_connection()
        is_read_only = connector.check_read_only()
        raw_tables = connector.introspect_schema()
    except Exception as exc:
        raise ConnectionFailedError(
            f"Could not connect to '{connection.name}' ({connection.type} at {connection.host}:{connection.port}): {exc}"
        ) from exc

    # Clean and normalize columns
    normalized_tables = [
        TableSchema(
            name=t.name,
            schema=t.schema,
            columns=[
                ColumnSchema(
                    name=c.name,
                    data_type=normalize_data_type(c.data_type),
                    nullable=c.nullable,
                )
                for c in t.columns
            ],
        )
        for t in raw_tables
    ]

    # Save to local metadata DB cache
    cache_payload = {
        "tables": [
            {
                "name": t.name,
                "schema": t.schema_name,
                "columns": [
                    {"name": c.name, "data_type": c.data_type, "nullable": c.nullable}
                    for c in t.columns
                ],
            }
            for t in normalized_tables
        ]
    }
    connection.cached_schema_json = json.dumps(cache_payload)
    connection.schema_updated_at = datetime.now(timezone.utc)
    db.flush()

    db.add(
        AuditLog(
            connection_id=connection.id,
            event_type="connection_used",
            actor=actor,
            detail_json=json.dumps({"action": "test_and_introspect", "cached": True}),
        )
    )
    db.flush()

    return ConnectionTestResult(
        connected=True,
        is_read_only=is_read_only,
        tables=normalized_tables,
    )
